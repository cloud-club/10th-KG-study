#!/usr/bin/env bash
# 오류가 발생하거나 정의되지 않은 변수를 사용하면 즉시 종료한다.
set -euo pipefail

# 사용법을 여러 줄로 출력하는 함수다.
usage() {
  cat <<'EOF'
사용법:
  search_grep.sh [--show] [--regex] [--ignore-case] <input.txt> <query>

기본값은 개인정보가 포함된 본문 대신 일치한 줄 수만 출력합니다.
  --show         줄 번호와 일치한 원문을 출력합니다.
  --regex        고정 문자열(-F) 대신 확장 정규식(-E)을 사용합니다.
  --ignore-case  대소문자를 무시합니다.
EOF
}

# 별도 옵션이 없을 때 사용할 기본 검색 방식이다.
show=false
matcher="-F"
ignore_case=false

# 앞에서부터 옵션을 하나씩 읽는다.
while [[ $# -gt 0 ]]; do
  case "$1" in
    --show)
      show=true
      shift
      ;;
    --regex)
      matcher="-E"
      shift
      ;;
    --ignore-case)
      ignore_case=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    -*)
      printf '알 수 없는 옵션: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
    *)
      break
      ;;
  esac
done

# 옵션을 제외하고 입력 파일과 검색어, 두 값이 남아야 한다.
if [[ $# -ne 2 ]]; then
  usage >&2
  exit 2
fi

# $1은 원본 파일, $2는 검색할 문자열이다.
input_path=$1
query=$2

# 존재하지 않는 파일을 grep에 넘기지 않는다.
if [[ ! -f "$input_path" ]]; then
  printf '입력 파일을 찾을 수 없습니다: %s\n' "$input_path" >&2
  exit 2
fi

# 기본값 -F는 검색어를 정규식이 아닌 고정 문자열로 처리한다.
grep_options=("$matcher")
if [[ "$ignore_case" == true ]]; then
  grep_options+=("-i")
fi

# grep의 종료 코드를 직접 확인하기 위해 잠시 자동 종료를 끈다.
set +e
if [[ "$show" == true ]]; then
  # -n은 일치한 원문의 줄 번호까지 보여준다.
  grep -n "${grep_options[@]}" -- "$query" "$input_path"
  grep_status=$?
else
  # -c는 원문 대신 일치한 줄 수만 보여준다.
  grep -c "${grep_options[@]}" -- "$query" "$input_path"
  grep_status=$?
fi
set -e

# grep은 일치 결과가 없을 때 종료 코드 1을 반환한다. 이는 정상적인 검색 결과다.
if [[ $grep_status -eq 0 || $grep_status -eq 1 ]]; then
  exit 0
fi

exit "$grep_status"
