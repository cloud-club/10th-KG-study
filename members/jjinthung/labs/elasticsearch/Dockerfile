ARG ES_VERSION=9.1.0
FROM docker.elastic.co/elasticsearch/elasticsearch:${ES_VERSION}

RUN bin/elasticsearch-plugin install --batch analysis-nori
