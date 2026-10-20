"""구조 층 적재 — LLM 없이 저장소에서 결정적으로 뽑는 그래프.

  (Member)-[:WROTE]->(Document)-[:HAS_CHUNK]->(Chunk)
  (Document)-[:TAGGED]->(Tag)      (Document)-[:IN_WEEK]->(Week)

위키 층(v3 전용, v1·v2 리트리버는 읽지 않는다):
  (WikiPage)-[:LINKS_TO]->(WikiPage)   (WikiPage)-[:CITES]->(Document)
  (WikiPage)-[:CREDITS]->(Member)      (Contradiction)-[:IN_PAGE]->(WikiPage), -[:INVOLVES]->(Member)

실행: python load_structure.py   (Neo4j 를 비우고 다시 적재한다)
"""
import json
import re
from pathlib import PurePosixPath

from common import OUT, REPO, neo4j_driver
from corpus import collect, parse_frontmatter

WIKI_SKIP = re.compile(r"wiki/(_templates|inbox|\.obsidian)/")


def wiki_pages(member_ids):
    pages = []
    for p in sorted((REPO / "wiki").rglob("*.md")):
        rel = p.relative_to(REPO).as_posix()
        if WIKI_SKIP.search(rel):
            continue
        text = p.read_text()
        fm, body = parse_frontmatter(text)
        links = sorted({m.strip() for m in re.findall(r"\[\[([^\]|#]+)", body)})
        cites = set()
        for target in re.findall(r"\]\(((?:\.\./)+members/[^)\s]+)\)", body):
            path = PurePosixPath(p.parent.relative_to(REPO), target.split("#")[0])
            parts = []
            for part in path.parts:  # ../ 정규화
                if part == "..":
                    parts.pop()
                else:
                    parts.append(part)
            cites.add("/".join(parts))
        contradictions = []
        for para in re.split(r"\n\s*\n", body):
            if "Contradiction" in para:
                involved = sorted({m for m in member_ids if re.search(rf"\b{re.escape(m)}\b", para)})
                contradictions.append({"text": para.strip()[:600], "members": involved})
        pages.append(
            {
                "name": p.stem,
                "path": rel,
                "type": fm.get("type") or p.parent.name,
                "title": fm.get("title") or p.stem,
                "status": fm.get("status"),
                "members": [m for m in (fm.get("members") or []) if m in member_ids],
                "links": links,
                "cites": sorted(cites),
                "contradictions": contradictions,
                "summary": next((l.lstrip("> ").strip() for l in body.splitlines() if l.startswith("> ")), ""),
            }
        )
    return pages


SCHEMA = [
    "CREATE CONSTRAINT member_id IF NOT EXISTS FOR (n:Member) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT doc_path IF NOT EXISTS FOR (n:Document) REQUIRE n.path IS UNIQUE",
    "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (n:Chunk) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT tag_name IF NOT EXISTS FOR (n:Tag) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT week_n IF NOT EXISTS FOR (n:Week) REQUIRE n.n IS UNIQUE",
    "CREATE CONSTRAINT wiki_name IF NOT EXISTS FOR (n:WikiPage) REQUIRE n.name IS UNIQUE",
]


def load(docs, pages):
    with neo4j_driver() as drv, drv.session() as s:
        s.run("MATCH (n) DETACH DELETE n")
        for q in SCHEMA:
            s.run(q)
        members = sorted({(d["member"], d["cohort"]) for d in docs})
        s.run("UNWIND $rows AS r MERGE (m:Member {id: r[0]}) SET m.cohort = r[1]", rows=members)
        s.run(
            """
            UNWIND $docs AS d
            MATCH (m:Member {id: d.member})
            MERGE (doc:Document {path: d.path})
            SET doc.kind = d.kind, doc.title = d.title, doc.date = d.date,
                doc.week = d.week, doc.week_source = d.week_source
            MERGE (m)-[:WROTE]->(doc)
            FOREACH (t IN d.tags | MERGE (tag:Tag {name: t}) MERGE (doc)-[:TAGGED]->(tag))
            FOREACH (_ IN CASE WHEN d.week IS NULL THEN [] ELSE [1] END |
                MERGE (w:Week {n: d.week}) MERGE (doc)-[:IN_WEEK]->(w))
            WITH doc, d
            UNWIND d.chunks AS c
            MERGE (ch:Chunk {id: c.id})
            SET ch.seq = c.seq, ch.heading = c.heading, ch.text = c.text
            MERGE (doc)-[:HAS_CHUNK]->(ch)
            """,
            docs=docs,
        )
        s.run(
            """
            UNWIND $pages AS p
            MERGE (w:WikiPage {name: p.name})
            SET w.path = p.path, w.type = p.type, w.title = p.title, w.status = p.status, w.summary = p.summary
            """,
            pages=pages,
        )
        s.run(
            """
            UNWIND $pages AS p
            MATCH (w:WikiPage {name: p.name})
            FOREACH (l IN p.links | MERGE (t:WikiPage {name: l}) MERGE (w)-[:LINKS_TO]->(t))
            WITH w, p
            UNWIND p.members AS mid
            MATCH (m:Member {id: mid}) MERGE (w)-[:CREDITS]->(m)
            """,
            pages=pages,
        )
        s.run(
            """
            UNWIND $pages AS p
            MATCH (w:WikiPage {name: p.name})
            UNWIND p.cites AS path
            MATCH (doc:Document {path: path}) MERGE (w)-[:CITES]->(doc)
            """,
            pages=pages,
        )
        s.run(
            """
            UNWIND $pages AS p
            MATCH (w:WikiPage {name: p.name})
            UNWIND range(0, size(p.contradictions) - 1) AS i
            WITH w, p, i, p.contradictions[i] AS c
            CREATE (x:Contradiction {id: p.name + '#' + i, text: c.text})-[:IN_PAGE]->(w)
            WITH x, c
            UNWIND c.members AS mid
            MATCH (m:Member {id: mid}) MERGE (x)-[:INVOLVES]->(m)
            """,
            pages=pages,
        )
        counts = s.run(
            "CALL () { MATCH (n) RETURN labels(n)[0] AS k, count(*) AS c "
            "UNION ALL MATCH ()-[r]->() RETURN type(r) AS k, count(*) AS c } RETURN k, c ORDER BY k"
        ).data()
    return counts


if __name__ == "__main__":
    docs = collect()
    pages = wiki_pages({d["member"] for d in docs})
    (OUT / "corpus.json").write_text(json.dumps(docs, ensure_ascii=False))
    (OUT / "wiki.json").write_text(json.dumps(pages, ensure_ascii=False))
    for row in load(docs, pages):
        print(f"{row['k']:>14} {row['c']}")
    cited = {c for p in pages for c in p["cites"]}
    known = {d["path"] for d in docs}
    print("위키 출처 중 Document 로 이어지지 않은 경로:", len(cited - known), sorted(cited - known)[:8])
