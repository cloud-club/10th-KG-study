#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "사용법: bash src/grep/search.sh '검색어' [TSV 파일]" >&2
  exit 1
fi

grep -Fn -- "$1" "${2:-data/processed/chat.tsv}"
