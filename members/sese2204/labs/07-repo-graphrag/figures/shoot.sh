#!/bin/zsh
# 슬라이드를 PNG로 찍는다. 사용: ./shoot.sh [슬라이드 id ...]   (id 를 빼면 전부)
# qualitative.html 은 아티팩트용 조각이라 doctype 을 씌운 임시 파일로 연다. png/neo4j-*.png 를 상대 경로로 읽으므로 이 폴더에서 연다.
cd ${0:A:h}
CH=${CHROME:-"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"}
TMP=.shot.html; PROF=$(mktemp -d)
{ echo '<!doctype html><html lang="ko"><head><meta charset="utf-8"></head><body>'; cat qualitative.html; echo '</body></html>'; } > $TMP
IDS=("$@")
(( ${#IDS} )) || IDS=(overview observations q01 q02 q03 q04 q05 q06 q07 q08 q09 q10 q11 q12 schema db-1 db-2 db-3 db-4 db-5 db-6 graph-finding graph-pitfall graph-evidence graph-community graph-t2c graph-aggregate)
for id in $IDS; do
  "$CH" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=2 --window-size=1600,900 \
    --virtual-time-budget=8000 --user-data-dir=$PROF --screenshot=png/slide-$id.png "file://$PWD/$TMP#shot-$id" >/dev/null 2>&1
  echo "png/slide-$id.png"
done
rm -f $TMP; rm -rf $PROF
