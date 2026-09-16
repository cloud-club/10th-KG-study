# Elasticsearch + analysis-nori (한국어 형태소 분석기)
# docker compose 가 자동으로 빌드합니다. 버전은 .env 의 ES_VERSION 으로 조정.
ARG ES_VERSION=9.1.0
FROM docker.elastic.co/elasticsearch/elasticsearch:${ES_VERSION}

RUN bin/elasticsearch-plugin install --batch analysis-nori
