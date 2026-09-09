#!/usr/bin/env python3
"""Postgres의 chunks(및 선택적으로 messages)를 Elasticsearch에 색인한다. (BM25 + nori 한국어 분석기)

  python src/index_es.py                # kakao_chunks 인덱스 생성(없으면) + 전체 청크 색인
  python src/index_es.py --recreate     # 인덱스 지우고 다시 (analyzer 설정을 바꿨을 때)
  python src/index_es.py --messages     # 메시지 1건 단위 인덱스(kakao_messages)도 함께
  python src/index_es.py --analyze "부산 여행 숙소 예약했어요"   # nori 토큰 확인만

analyzer
  korean        nori_tokenizer(decompound_mode=mixed) → nori_part_of_speech(조사·어미 등 제거) → nori_readingform → lowercase
  korean_ngram  2~3글자 n-gram (분담 과제 "nori vs n-gram" 비교용 서브필드 text.ngram)
"""
from __future__ import annotations

import argparse
import sys

from elasticsearch import helpers

from common import ES_INDEX, ES_MSG_INDEX, get_es, get_pg

SETTINGS = {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "analysis": {
        "tokenizer": {
            "nori_mixed": {"type": "nori_tokenizer", "decompound_mode": "mixed"},
            "ngram_2_3": {"type": "ngram", "min_gram": 2, "max_gram": 3, "token_chars": ["letter", "digit"]},
        },
        "analyzer": {
            "korean": {
                "type": "custom",
                "tokenizer": "nori_mixed",
                "filter": ["nori_part_of_speech", "nori_readingform", "lowercase"],
            },
            "korean_ngram": {"type": "custom", "tokenizer": "ngram_2_3", "filter": ["lowercase"]},
        },
    },
}

CHUNK_MAPPINGS = {
    "properties": {
        "chunk_id": {"type": "long"},
        "room": {"type": "keyword"},
        "start_at": {"type": "date"},
        "end_at": {"type": "date"},
        "participants": {"type": "keyword"},
        "n_messages": {"type": "integer"},
        "text": {
            "type": "text",
            "analyzer": "korean",
            "fields": {"ngram": {"type": "text", "analyzer": "korean_ngram"}},
        },
    }
}

MSG_MAPPINGS = {
    "properties": {
        "message_id": {"type": "long"},
        "room": {"type": "keyword"},
        "sent_at": {"type": "date"},
        "sender": {"type": "keyword"},
        "msg_type": {"type": "keyword"},
        "text": {"type": "text", "analyzer": "korean",
                 "fields": {"ngram": {"type": "text", "analyzer": "korean_ngram"}}},
    }
}


def ensure_index(es, name: str, mappings: dict, recreate: bool):
    if recreate and es.indices.exists(index=name):
        es.indices.delete(index=name)
        print(f"[es] {name} 삭제", file=sys.stderr)
    if not es.indices.exists(index=name):
        es.indices.create(index=name, settings=SETTINGS, mappings=mappings)
        print(f"[es] {name} 생성 (nori analyzer)", file=sys.stderr)


def iter_chunks(cur):
    cur.execute(
        """SELECT c.id, r.name, c.start_at, c.end_at, c.participants, c.n_messages, c.text
           FROM chunks c JOIN rooms r ON r.id = c.room_id ORDER BY c.id"""
    )
    for cid, room, s, e, parts, n, text in cur:
        yield {
            "_index": ES_INDEX, "_id": cid,  # _id = chunk_id → 재실행해도 덮어쓰기(멱등)
            "_source": {"chunk_id": cid, "room": room, "start_at": s.isoformat(), "end_at": e.isoformat(),
                        "participants": parts, "n_messages": n, "text": text},
        }


def iter_messages(cur):
    cur.execute(
        """SELECT m.id, r.name, m.sent_at, mem.name, m.msg_type, m.text
           FROM messages m JOIN rooms r ON r.id = m.room_id LEFT JOIN members mem ON mem.id = m.sender_id
           WHERE m.msg_type IN ('text', 'link') ORDER BY m.id"""
    )
    for mid, room, s, sender, mtype, text in cur:
        yield {"_index": ES_MSG_INDEX, "_id": mid,
               "_source": {"message_id": mid, "room": room, "sent_at": s.isoformat(), "sender": sender,
                           "msg_type": mtype, "text": text}}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--recreate", action="store_true")
    ap.add_argument("--messages", action="store_true", help="메시지 단위 인덱스도 만들기")
    ap.add_argument("--analyze", help="문장을 nori 로 토큰화해 보기만 하고 종료")
    args = ap.parse_args()

    es = get_es()
    info = es.info()
    print(f"[es] 연결됨: {info['version']['number']}", file=sys.stderr)
    ensure_index(es, ES_INDEX, CHUNK_MAPPINGS, args.recreate)

    if args.analyze:
        for name in ("korean", "korean_ngram"):
            res = es.indices.analyze(index=ES_INDEX, analyzer=name, text=args.analyze)
            print(f"  {name:13s}: {[t['token'] for t in res['tokens']]}")
        return

    with get_pg() as conn, conn.cursor() as cur:
        ok, _ = helpers.bulk(es, iter_chunks(cur), chunk_size=500)
        es.indices.refresh(index=ES_INDEX)
        print(f"[es] {ES_INDEX}: {ok:,}건 색인, 총 {es.count(index=ES_INDEX)['count']:,}건", file=sys.stderr)

        if args.messages:
            ensure_index(es, ES_MSG_INDEX, MSG_MAPPINGS, args.recreate)
            ok, _ = helpers.bulk(es, iter_messages(cur), chunk_size=1000)
            es.indices.refresh(index=ES_MSG_INDEX)
            print(f"[es] {ES_MSG_INDEX}: {ok:,}건 색인", file=sys.stderr)

    sample = "부산 여행 숙소 예약했어요"
    res = es.indices.analyze(index=ES_INDEX, analyzer="korean", text=sample)
    print(f"[es] nori 확인: {sample!r} → {[t['token'] for t in res['tokens']]}", file=sys.stderr)


if __name__ == "__main__":
    main()
