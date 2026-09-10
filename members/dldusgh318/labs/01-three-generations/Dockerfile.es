# 공식 이미지에는 nori가 없어서 직접 설치한다.
# 1세대 실습의 핵심: 한국어는 색인 시점의 분석기 선택이 검색 결과를 좌우한다.
FROM docker.elastic.co/elasticsearch/elasticsearch:8.15.1
RUN bin/elasticsearch-plugin install --batch analysis-nori
