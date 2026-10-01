#!/usr/bin/env bash
# 오류가 발생하거나 정의되지 않은 변수를 사용하면 즉시 종료한다.
set -euo pipefail

# 입력 파일, 질의 TSV, 출력 TSV까지 인자 3개를 받는다.
if [[ $# -ne 3 ]]; then
  cat >&2 <<'EOF'
사용법:
  run_grep_queries.sh <input.txt> <queries.tsv> <output.tsv>

질의별 고정 문자열 일치 줄 수를 TSV로 저장합니다. 원문은 출력하지 않습니다.
EOF
  exit 2
fi

# 전달받은 세 인자와 단일 검색 스크립트의 위치를 변수에 저장한다.
input_path=$1
query_path=$2
output_path=$3
script_dir=$(cd "$(dirname "$0")" && pwd)
search_script="$script_dir/search_grep.sh"

# 검색 대상과 질의 목록이 실제 파일인지 확인한다.
if [[ ! -f "$input_path" ]]; then
  printf '입력 파일을 찾을 수 없습니다: %s\n' "$input_path" >&2
  exit 2
fi

if [[ ! -f "$query_path" ]]; then
  printf '질의 파일을 찾을 수 없습니다: %s\n' "$query_path" >&2
  exit 2
fi

# 결과 폴더가 없으면 만들고, 작업 중 사용할 임시 파일을 준비한다.
mkdir -p "$(dirname "$output_path")"
temp_path="${output_path}.tmp.$$"
# 스크립트가 중간에 끝나도 임시 파일은 삭제한다.
trap 'rm -f "$temp_path"' EXIT

# 결과 TSV의 첫 번째 줄에 열 이름을 쓴다.
printf 'query_id\ttype\tquery\tmatched_lines\tpurpose\n' > "$temp_path"

{
  # 입력 TSV의 헤더는 읽기만 하고 건너뛴다.
  IFS= read -r _header || true
  # 탭을 기준으로 각 열을 변수에 담아 한 줄씩 반복한다.
  while IFS=$'\t' read -r query_id query_type query purpose; do
    [[ -z "$query_id" ]] && continue
    # 검색어 하나를 담당하는 search_grep.sh를 호출해 일치 줄 수를 받는다.
    count=$(bash "$search_script" "$input_path" "$query")
    # 원래 질의 정보에 검색 결과를 붙여 출력 TSV에 쓴다.
    printf '%s\t%s\t%s\t%s\t%s\n' \
      "$query_id" "$query_type" "$query" "$count" "$purpose"
  done
} < "$query_path" >> "$temp_path"

# 모든 검색이 성공했을 때만 임시 파일을 최종 결과 파일로 바꾼다.
mv "$temp_path" "$output_path"
trap - EXIT
printf '질의 수: %s\n' "$(( $(wc -l < "$output_path") - 1 ))"
printf '결과 파일: %s\n' "$output_path"
