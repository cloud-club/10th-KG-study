"""실제 기록이 아직 없을 때 중계 피드를 채우는 목데이터. 날짜는 빌드일 기준 상대값이라 항상 최신처럼 보인다."""
from __future__ import annotations

import datetime as dt

MOCK_FEED = [
    {
        "days_ago": 0, "member": "kungbi", "kind": "lab", "title": "LLM 트리플 추출",
        "text": "🎙️ kungbi 선수, 문장을 넣으면 (s, p, o)가 튀어나오는 추출기 완성! 트리플 추출 라운드 선취점입니다.",
        "summary": "문장을 넣으면 (s, p, o) 리스트를 JSON 으로 돌려주는 프롬프트를 만들고, 뉴스 기사 20건으로 정확도를 눈으로 확인했다.",
        "tags": ["triple-extraction", "llm", "nlp"],
    },
    {
        "days_ago": 0, "member": "sese2204", "kind": "note", "title": "저장소와 SPARQL 검색",
        "text": "sese2204 선수, SPARQL 노트로 연타! BGP 패턴 매칭까지 정리하며 검색 구간을 돌파합니다.",
        "summary": "SPARQL 은 트리플 패턴 매칭으로 그래프를 질의한다. 기본 그래프 패턴(BGP)이 핵심이고 OPTIONAL, FILTER 로 살을 붙인다.",
        "tags": ["sparql", "rdf", "triplestore"],
    },
    {
        "days_ago": 1, "member": "sese2204", "kind": "streak", "title": "3일 연속 활동",
        "text": "🔥 sese2204 선수 3일 연속 출석! 히트맵이 초록으로 물들기 시작했습니다.",
        "summary": "", "tags": [],
    },
    {
        "days_ago": 1, "member": "kungbi", "kind": "note", "title": "그래프 DB 비교 (Neo4j vs RDF store)",
        "text": "kungbi 선수, Neo4j와 RDF 스토어를 나란히 세워 놓고 비교 분석. 프로퍼티 그래프 진영에 한 표?",
        "summary": "프로퍼티 그래프(Neo4j)와 RDF 스토어는 모델링 철학이 다르다. 스키마 유연성 vs 표준 호환, 우리 스터디엔 둘 다 한 번씩.",
        "tags": ["neo4j", "rdf", "property-graph"],
    },
    {
        "days_ago": 2, "member": "sese2204", "kind": "note", "title": "RDF 데이터 모델과 트리플",
        "text": "🎙️ 경기 시작! sese2204 선수가 RDF 트리플 노트로 시즌 첫 득점을 올립니다.",
        "summary": "지식그래프의 최소 단위는 (주어, 술어, 목적어) 트리플이고, RDF 는 이걸 IRI 로 전역 식별하는 표준이다.",
        "tags": ["rdf", "triple", "ontology"],
    },
    {
        "days_ago": 2, "member": "kungbi", "kind": "level", "title": "Lv.2 달성",
        "text": "⬆️ kungbi 선수 레벨 2 진입! 노트와 실습을 동시에 쌓는 균형형 플레이.",
        "summary": "", "tags": [],
    },
    {
        "days_ago": 3, "member": "hana", "kind": "join", "title": "스터디 합류",
        "text": "새 선수 입장! hana 선수가 members/ 에 폴더를 만들고 워밍업에 들어갑니다.",
        "summary": "", "tags": [],
    },
    {
        "days_ago": 4, "member": "sese2204", "kind": "lab", "title": "문서 파서 만들기",
        "text": "sese2204 선수, PDF에서 문장을 뽑아내는 파서로 실습 첫 골! 트리플 추출로 가는 길을 닦았습니다.",
        "summary": "PDF/마크다운에서 문장 단위로 텍스트를 뽑아 트리플 추출 입력으로 넘긴다. 표와 각주 처리가 생각보다 골치.",
        "tags": ["document-parsing", "nlp"],
    },
    {
        "days_ago": 5, "member": "kungbi", "kind": "note", "title": "그래프 임베딩 훑어보기",
        "text": "kungbi 선수, node2vec 으로 노드를 벡터에 태우는 실험 예고. 링크 예측까지 노리는 눈치입니다.",
        "summary": "노드를 벡터로 바꾸면 유사도 검색과 링크 예측이 가능해진다. node2vec 의 random walk 파라미터 p, q 가 탐색 성향을 정한다.",
        "tags": ["embedding", "node2vec"],
    },
]


def mock_feed(today: dt.date) -> list[dict]:
    return [
        {
            "id": f"mock-{i}",
            "date": (today - dt.timedelta(days=entry["days_ago"])).isoformat(),
            "member": entry["member"],
            "kind": entry["kind"],
            "title": entry["title"],
            "url": "",
            "text": entry["text"],
            "summary": entry["summary"],
            "tags": list(entry["tags"]),
            "mock": True,
        }
        for i, entry in enumerate(MOCK_FEED)
    ]
