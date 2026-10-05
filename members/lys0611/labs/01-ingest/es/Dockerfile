# Elasticsearch 공식 이미지에는 한국어 형태소 분석기(nori)가 들어있지 않다.
# 플러그인 버전은 ES 버전과 정확히 같아야 하므로 이미지 태그를 바꾸면 그대로 맞춰 설치된다.
FROM docker.elastic.co/elasticsearch/elasticsearch:9.5.3
RUN bin/elasticsearch-plugin install --batch analysis-nori
