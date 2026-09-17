---
title: Elasticsearch 운영 함정 모음
type: entity
tags: [pitfall, tooling]
status: maintained
created: 2026-09-16
updated: 2026-09-16
members: [lys0611, do-dop, ur2e, dldusgh318, e0ng, yujeong430, heebindev, sese2204]
weeks: [2]
---

> nori 플러그인, 메모리, 버전 불일치, 기본 OR 매치, 필드 부스트, refresh. 검색 품질 문제로 보이는 것의 절반은 설정 문제였다. 한국어 분석기 자체는 [[한국어-토크나이징-nori와-n-gram]].

## 설치·기동

- **공식 이미지에는 nori가 없다.** `elasticsearch-plugin install analysis-nori`를 넣은 Dockerfile로 빌드하고, 플러그인 버전은 ES 버전과 정확히 같아야 한다. `Unknown tokenizer type [nori_tokenizer]`가 나오면 플러그인 미설치 (lys0611). 공용 인프라는 `infra/elasticsearch/Dockerfile`, dldusgh318·e0ng·yujeong430·lys0611은 자체 Dockerfile.
- **메모리 부족으로 계속 재시작** (exit 78, 137): Docker/Colima VM 4GB 이상, `ES_JAVA_OPTS=-Xms1g -Xmx1g`(8GB 노트북이면 512m). Linux는 `sudo sysctl -w vm.max_map_count=262144`. `discovery.type=single-node`면 부트스트랩 체크를 피해 Colima 기본 VM에서도 뜬다. Colima 기본값은 CPU 2·메모리 2GiB라 그대로 두면 ES가 뜨다 죽는다 → `colima start --cpu 4 --memory 6` (lys0611, infra README).
- `xpack.security.enabled=false`로 로컬 인증/TLS를 끈다. 공용 인프라 `http://localhost:9200`은 인증 없음.
- **클라이언트 메이저 버전 = 서버 메이저 버전.** `UnsupportedProductError`나 버전 경고가 나면 서버 9.x에 `pip install "elasticsearch>=9,<10"` (lys0611). 멤버별 버전이 제각각이다: 공용 9.1, dldusgh318 8.15.1, e0ng 8.15.0, lys0611 9.5.3.
- 색인 스크립트는 ES 준비까지 최대 90초 대기하고 인덱스를 새로 만들어 중복 적재를 막는다 (e0ng). `_id = chunk_id`로 두면 다시 실행해도 덮어쓴다 (lys0611).
- 볼륨이 없으면 컨테이너를 지우는 순간 역색인이 통째로 사라진다 (dldusgh318 compose 주석). ES는 `data/` 마운트가 없어 Python/curl로 `_bulk` 적재한다 (data/README).
- Elasticsearch는 GUI가 아니라 HTTP 요청을 받는 서버다 (heebindev). 인덱스 탐색은 Kibana(`--profile ui`).

## 검색 설정

- **기본 `match`는 OR.** `마감 일정`이면 `일정`만 있어도 후보가 된다. `operator: and`, `minimum_should_match`, `match_phrase`(토큰 순서·인접성)는 서로 다른 것이다. 조건을 엄격히 해도 `제출일`·`언제까지` 같은 표현 불일치는 해결되지 않는다 (lys0611). do-dop은 `몇시`에서 75건, heebindev는 `CPU 작업 순서`에서 85건 → [[역색인과-BM25]].
- **`multi_match` 기본 `best_fields`는 합산하지 않는다.** 필드별 최고점만 쓰고 dis_max가 나머지를 버린다. `title^2` 부스트가 습관적 제목 단어로 문서 전체를 밀어올렸다 (ur2e).
- **stopword 필터**: `nori_part_of_speech`만으로는 "있다/않다" 어간과 "노드" 같은 짧은 명사가 남는다 (ur2e).
- **nori 필드와 n-gram 필드의 점수 절댓값을 비교하지 않는다** (do-dop). Lucene BM25는 분자의 `(k1+1)`을 생략하므로 필드마다 설정이 다르면 점수 크기도 다르다 (lys0611).
- 디버깅 도구: `_analyze`로 토큰 확인, `_search?explain=true`로 어느 토큰이 점수를 냈는지 확인 (ur2e, dldusgh318). explain 총점 예: `트러블슈팅` 13.63 (dldusgh318).
- 청크 설정마다 인덱스를 분리하지 않으면 비교가 섞인다: `ur2e_worklog_chunks_fixed_300_100` 식으로 설정키를 이름에 넣는다 (ur2e). 공용 인스턴스에서는 멤버 접두사(`do-dop-kakao-messages`).
- ES 문서 단위 = 메시지 1건인데 pgvector는 청크 단위로 두면 방식별 검색 단위가 달라진다 (do-dop) → [[검색의-세-세대]].

## refresh와 세그먼트

- Lucene은 불변 세그먼트에 쓰고 나중에 병합한다. `refresh`는 새 세그먼트를 검색 가능하게 여는 작업이며 기본 약 1초 주기, 최근 30초 안에 검색된 인덱스 한정. 대량 색인 뒤 `indices.refresh()`를 직접 호출하면 확인 쿼리가 주기를 기다리지 않는다. lys0611은 "count가 잠시 0이었다는 관찰"을 코드가 명시 refresh를 하므로 철회했다 → [[저장-구조-LSM과-B-tree]].
- 대량 색인 중 `refresh_interval` 조정 시 처리량·가시성 변화는 lys0611의 TODO.

## 관련

- [[한국어-토크나이징-nori와-n-gram]] · [[역색인과-BM25]] · [[로컬-인프라]] · [[PostgreSQL과-pgvector-함정]] · [[저장-구조-LSM과-B-tree]]

## 출처

- lys0611 · 역색인과 BM25 노트, GUIDE §2·§트러블슈팅, RUNBOOK §Colima 문제 — [members/lys0611/notes/01-inverted-index-bm25.md](../../members/lys0611/notes/01-inverted-index-bm25.md), [labs/01-ingest/GUIDE.md](../../members/lys0611/labs/01-ingest/GUIDE.md), [RUNBOOK_mac_colima.md](../../members/lys0611/labs/01-ingest/RUNBOOK_mac_colima.md) (PR #15 미머지)
- do-dop · 카카오톡 검색 비교 (§nori와 2-gram, §BM25 점수) — [members/do-dop/labs/02-kakaotalk-search/README.md](../../members/do-dop/labs/02-kakaotalk-search/README.md)
- ur2e · 검색 방식 비교 실험 (실험 2), 실습 README — [members/ur2e/notes/01-search-methods-comparison.md](../../members/ur2e/notes/01-search-methods-comparison.md), [labs/01-worklog-search/README.md](../../members/ur2e/labs/01-worklog-search/README.md) (PR #11 미머지)
- dldusgh318 · 1세대 노트 (§4), WEEK2 — [members/dldusgh318/notes/week2/02-inverted-index-bm25.md](../../members/dldusgh318/notes/week2/02-inverted-index-bm25.md), [labs/01-three-generations/WEEK2.md](../../members/dldusgh318/labs/01-three-generations/WEEK2.md)
- e0ng · 실습 — [members/e0ng/labs/02-search-generations/README.md](../../members/e0ng/labs/02-search-generations/README.md); yujeong430 · 실습 — [members/yujeong430/labs/01-kakaotalk-search/README.md](../../members/yujeong430/labs/01-kakaotalk-search/README.md); heebindev · 실습 — [members/heebindev/labs/01-notion-search/README.md](../../members/heebindev/labs/01-notion-search/README.md) (PR #12 미머지)
- sese2204 · infra/README.md (§문제 해결) — [infra/README.md](../../infra/README.md) (PR #6 미머지)
- 외부: Elastic Near real-time search https://www.elastic.co/docs/manage-data/data-store/near-real-time-search · `match` query https://www.elastic.co/docs/reference/query-languages/query-dsl/query-dsl-match-query · Bootstrap checks (lys0611 readings)
