"""1세대: Elasticsearch 역색인 + BM25

저장 구조의 핵심은 '매핑'이다. 같은 문장이라도 어떤 analyzer로 쪼개 넣느냐에
따라 나중에 무엇이 검색되는지가 결정된다. 그래서 여기서는 같은 본문을
두 가지로 동시에 색인해 두고 나중에 비교한다:

  text        -> nori (형태소 분석). "학교에서" -> 학교 + 에서 로 쪼개 원형 색인
  text.ngram  -> 2-3 그램. 형태소 사전에 없는 신조어·고유명사에 강하다

사용:
    python src/gen1_es.py index      # 매핑 만들고 적재
    python src/gen1_es.py mapping    # 저장 구조 출력
    python src/gen1_es.py 학교        # BM25 검색
"""
import json
import sys

from elasticsearch import Elasticsearch, helpers

from common import CHUNKS, ES_INDEX, ES_URL

SETTINGS = {
    "settings": {
        "index": {"max_ngram_diff": 1},
        "analysis": {
            "tokenizer": {
                "kor_nori": {
                    "type": "nori_tokenizer",
                    # mixed: 복합명사를 원형과 분해형 둘 다 색인한다.
                    # "지식그래프" -> 지식그래프 + 지식 + 그래프
                    "decompound_mode": "mixed",
                },
                "kor_ngram": {"type": "ngram", "min_gram": 2, "max_gram": 3},
            },
            "filter": {
                # 조사·어미·기호를 버린다. 이게 "학교에서 -> 학교"를 만든다.
                "kor_pos": {
                    "type": "nori_part_of_speech",
                    "stoptags": ["E", "J", "IC", "MAJ", "SP", "SSC", "SSO", "SC", "SE"],
                },
            },
            "analyzer": {
                "kor_nori_analyzer": {
                    "type": "custom",
                    "tokenizer": "kor_nori",
                    "filter": ["kor_pos", "nori_readingform", "lowercase"],
                },
                "kor_ngram_analyzer": {
                    "type": "custom",
                    "tokenizer": "kor_ngram",
                    "filter": ["lowercase"],
                },
            },
        },
    },
    "mappings": {
        "properties": {
            "text": {
                "type": "text",
                "analyzer": "kor_nori_analyzer",
                "fields": {"ngram": {"type": "text", "analyzer": "kor_ngram_analyzer"}},
            },
            "title": {"type": "text", "analyzer": "kor_nori_analyzer",
                       "fields": {"raw": {"type": "keyword"}}},
            "heading": {"type": "text", "analyzer": "kor_nori_analyzer"},
            # 0세대엔 없던 것: 메타데이터로 필터·정렬이 된다
            "source": {"type": "keyword"},
        }
    },
}


def client() -> Elasticsearch:
    return Elasticsearch(ES_URL, request_timeout=60)


def index() -> None:
    es = client()
    if es.indices.exists(index=ES_INDEX):
        es.indices.delete(index=ES_INDEX)
    es.indices.create(index=ES_INDEX, **SETTINGS)

    def actions():
        with CHUNKS.open(encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                yield {
                    "_index": ES_INDEX,
                    "_id": r["id"],
                    "text": r["text"],
                    "title": r["title"],
                    "heading": r["heading"],
                    "source": r["source"],
                }

    ok, errs = helpers.bulk(es, actions(), stats_only=False, raise_on_error=False)
    es.indices.refresh(index=ES_INDEX)
    count = es.count(index=ES_INDEX)["count"]
    print(f"[1세대] 색인 완료: {ok}건 성공, 실패 {len(errs)}건 / 인덱스 문서 수 {count:,}")


def show_mapping() -> None:
    es = client()
    stats = es.indices.stats(index=ES_INDEX)["indices"][ES_INDEX]["total"]
    print("[1세대 Elasticsearch] 저장 구조")
    print(f"  인덱스        : {ES_INDEX}")
    print(f"  문서(청크)    : {es.count(index=ES_INDEX)['count']:,}")
    print(f"  디스크        : {stats['store']['size_in_bytes']/1024/1024:.2f} MB  <- 원문보다 크다. 역색인 값")
    print("  저장 단위     : _doc (역색인 postings + TF/위치)")
    print("  스키마        : 아래 매핑 (analyzer가 곧 검색 성능)")
    print("  랭킹          : BM25 (기본 k1=1.2, b=0.75)")
    print(json.dumps(SETTINGS["mappings"], ensure_ascii=False, indent=2))


def analyze(text: str) -> None:
    """같은 문장이 두 analyzer에서 어떤 토큰으로 쪼개지는지 눈으로 본다."""
    es = client()
    for name in ("kor_nori_analyzer", "kor_ngram_analyzer"):
        toks = es.indices.analyze(index=ES_INDEX, analyzer=name, text=text)["tokens"]
        print(f"  {name:22s}: {[t['token'] for t in toks]}")


def search(query: str, limit: int = 5, field: str = "text"):
    es = client()
    res = es.search(
        index=ES_INDEX,
        query={"match": {field: query}},
        size=limit,
        _source=["title", "heading", "source", "text"],
    )
    return res["hits"]["hits"], res["hits"]["total"]["value"], res["took"]


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else "mapping"
    if arg == "index":
        index()
    elif arg == "mapping":
        show_mapping()
    elif arg == "analyze":
        analyze(sys.argv[2])
    else:
        for field in ("text", "text.ngram"):
            hits, total, took = search(arg, field=field)
            print(f'[1세대/{field}] "{arg}" — {total}건 / {took}ms (역색인 조회, 스캔 없음)')
            for h in hits:
                snippet = h["_source"]["text"].replace("\n", " ")[:110]
                print(f'  {h["_score"]:6.2f}  {snippet}')
            print()


if __name__ == "__main__":
    main()
