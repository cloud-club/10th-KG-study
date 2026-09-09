#!/usr/bin/env bash
# 전체 파이프라인 한 번에: ./run_pipeline.sh "data/raw/여행모임*.txt" 여행모임
set -euo pipefail
GLOB="${1:?사용법: ./run_pipeline.sh \"data/raw/방이름*.txt\" 방이름}"
ROOM="${2:?방 이름이 필요합니다}"
python src/parse_kakao.py "$GLOB" --room "$ROOM" --out "data/interim/$ROOM.jsonl"
python src/pseudonymize.py "data/interim/$ROOM.jsonl" --out "data/interim/$ROOM.masked.jsonl" --map data/private/name_map.json
python src/load_postgres.py "data/interim/$ROOM.masked.jsonl" --room "$ROOM"
python src/embed.py --room "$ROOM"
python src/index_es.py
echo "완료. 이제: python src/search.py \"질문\" --room $ROOM"
