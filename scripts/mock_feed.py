"""실제 기록이 아직 없을 때 중계 피드를 채우는 목데이터. 날짜는 빌드일 기준 상대값이라 항상 최신처럼 보인다."""
from __future__ import annotations

import datetime as dt

# (며칠 전, 멤버 id, 종류, 제목, 중계 문장)
MOCK_FEED = [
    (0, "kungbi", "lab", "LLM 트리플 추출",
     "🎙️ kungbi 선수, 문장을 넣으면 (s, p, o)가 튀어나오는 추출기 완성! 트리플 추출 라운드 선취점입니다."),
    (0, "sehyun", "note", "저장소와 SPARQL 검색",
     "sehyun 선수, SPARQL 노트로 연타! BGP 패턴 매칭까지 정리하며 검색 구간을 돌파합니다."),
    (1, "sehyun", "streak", "3일 연속 활동",
     "🔥 sehyun 선수 3일 연속 출석! 히트맵이 초록으로 물들기 시작했습니다."),
    (1, "kungbi", "note", "그래프 DB 비교 (Neo4j vs RDF store)",
     "kungbi 선수, Neo4j와 RDF 스토어를 나란히 세워 놓고 비교 분석. 프로퍼티 그래프 진영에 한 표?"),
    (2, "sehyun", "note", "RDF 데이터 모델과 트리플",
     "🎙️ 경기 시작! sehyun 선수가 RDF 트리플 노트로 시즌 첫 득점을 올립니다."),
    (2, "kungbi", "level", "Lv.2 달성",
     "⬆️ kungbi 선수 레벨 2 진입! 노트와 실습을 동시에 쌓는 균형형 플레이."),
    (3, "hana", "join", "스터디 합류",
     "새 선수 입장! hana 선수가 members/ 에 폴더를 만들고 워밍업에 들어갑니다."),
    (4, "sehyun", "lab", "문서 파서 만들기",
     "sehyun 선수, PDF에서 문장을 뽑아내는 파서로 실습 첫 골! 트리플 추출로 가는 길을 닦았습니다."),
    (5, "kungbi", "note", "그래프 임베딩 훑어보기",
     "kungbi 선수, node2vec 으로 노드를 벡터에 태우는 실험 예고. 링크 예측까지 노리는 눈치입니다."),
]


def mock_feed(today: dt.date) -> list[dict]:
    return [
        {
            "id": f"mock-{i}",
            "date": (today - dt.timedelta(days=days_ago)).isoformat(),
            "member": member,
            "kind": kind,
            "title": title,
            "url": "",
            "text": text,
            "mock": True,
        }
        for i, (days_ago, member, kind, title, text) in enumerate(MOCK_FEED)
    ]
