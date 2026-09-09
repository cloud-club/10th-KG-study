#!/usr/bin/env bash
# 세 서비스가 정상 기동됐고 확장/플러그인이 붙어 있는지 확인합니다.
#   bash infra/check.sh
set -uo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env ]]; then set -a; . ./.env; set +a; fi
PG_USER="${POSTGRES_USER:-kg}"; PG_DB="${POSTGRES_DB:-kg}"
ES_PORT="${ES_PORT:-9200}"; NEO4J_PW="${NEO4J_PASSWORD:-kgstudy2026}"

fail=0
ok()   { printf '  \033[32m✔\033[0m %s\n' "$*"; }
bad()  { printf '  \033[31m✘\033[0m %s\n' "$*"; fail=1; }

echo "== 컨테이너 상태"
docker compose ps --format 'table {{.Name}}\t{{.Status}}'
echo

echo "== postgres (pgvector)"
if out=$(docker compose exec -T postgres psql -U "$PG_USER" -d "$PG_DB" -tAc \
  "SELECT string_agg(extname||' '||extversion, ', ') FROM pg_extension WHERE extname IN ('vector','pg_trgm');" 2>&1); then
  [[ "$out" == *vector* ]] && ok "extensions: $out" || bad "vector 확장 없음: $out"
  dist=$(docker compose exec -T postgres psql -U "$PG_USER" -d "$PG_DB" -tAc "SELECT '[1,2,3]'::vector <-> '[1,2,4]'::vector;" 2>&1)
  [[ "$dist" == "1" ]] && ok "vector 거리 연산 동작 (<-> = $dist)" || bad "vector 연산 실패: $dist"
else
  bad "psql 접속 실패: $out"
fi
echo

echo "== elasticsearch (nori)"
if info=$(curl -sf "http://localhost:${ES_PORT}" 2>&1); then
  ok "version: $(echo "$info" | grep -o '"number" *: *"[^"]*"' | head -1)"
  plugins=$(curl -sf "http://localhost:${ES_PORT}/_cat/plugins?h=component" 2>&1)
  [[ "$plugins" == *analysis-nori* ]] && ok "plugin: analysis-nori" || bad "analysis-nori 없음: $plugins"
  tokens=$(curl -sf "http://localhost:${ES_PORT}/_analyze" -H 'Content-Type: application/json' \
    -d '{"tokenizer":"nori_tokenizer","text":"지식그래프 스터디"}' 2>&1 | grep -o '"token" *: *"[^"]*"' | sed 's/.*: *"//;s/"//' | tr '\n' ' ')
  [[ -n "$tokens" ]] && ok "nori 토큰화: $tokens" || bad "nori 토큰화 실패"
else
  bad "http://localhost:${ES_PORT} 응답 없음 (기동 중이면 30초 뒤 다시)"
fi
echo

echo "== neo4j (apoc)"
if out=$(docker compose exec -T neo4j cypher-shell -u neo4j -p "$NEO4J_PW" --format plain \
  "RETURN apoc.version() AS apoc;" 2>&1); then
  ok "apoc: $(echo "$out" | tail -1 | tr -d '"')"
else
  bad "cypher-shell 실패: $(echo "$out" | tail -1)"
fi
echo

if [[ $fail -eq 0 ]]; then
  echo "모두 정상입니다."
  echo "  psql:          docker compose exec postgres psql -U $PG_USER -d $PG_DB"
  echo "  Neo4j Browser: http://localhost:${NEO4J_HTTP_PORT:-7474}  (neo4j / $NEO4J_PW)"
  echo "  Elasticsearch: http://localhost:${ES_PORT}"
else
  echo "문제가 있습니다. 로그: docker compose logs -f <service>"; exit 1
fi
