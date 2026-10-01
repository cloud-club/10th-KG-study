#!/usr/bin/env bash
set -euo pipefail

lab_dir=$(cd "$(dirname "$0")/.." && pwd)
temp_dir=$(mktemp -d)
trap 'rm -rf "$temp_dir"' EXIT

fixture="$temp_dir/chat.txt"
queries="$temp_dir/queries.tsv"
output="$temp_dir/results.tsv"

printf '%s\n' \
  '2026. 9. 10. 19:30, 사용자A : 저녁 약속을 정하자' \
  '2026. 9. 10. 19:31, 사용자B : 저녁에 만나자' \
  '2026. 9. 10. 19:32, 사용자A : 주말에 보자' > "$fixture"

count=$(bash "$lab_dir/src/search_grep.sh" "$fixture" '저녁')
[[ "$count" == '2' ]]

no_match=$(bash "$lab_dir/src/search_grep.sh" "$fixture" '검색되지 않음')
[[ "$no_match" == '0' ]]

shown=$(bash "$lab_dir/src/search_grep.sh" --show "$fixture" '주말')
[[ "$shown" == 3:* ]]

printf 'query_id\ttype\tquery\tpurpose\n' > "$queries"
printf 'q01\texact\t저녁\t정확 검색\n' >> "$queries"
printf 'q02\texact\t약속\t희귀 키워드\n' >> "$queries"

bash "$lab_dir/src/run_grep_queries.sh" "$fixture" "$queries" "$output" >/dev/null
[[ "$(wc -l < "$output" | tr -d ' ')" == '3' ]]
grep -Fq $'q01\texact\t저녁\t2\t정확 검색' "$output"
grep -Fq $'q02\texact\t약속\t1\t희귀 키워드' "$output"

printf 'grep 테스트 통과\n'
