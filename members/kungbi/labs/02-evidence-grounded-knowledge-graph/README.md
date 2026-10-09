---
title: 근거 기반 Knowledge Graph 구축 방법과 합성 예제
date: 2026-10-08
tags: [knowledge-graph, neo4j, provenance, ontology]
status: done
---

# 근거 기반 Knowledge Graph 구축 방법과 합성 예제

검색용 청크와 객체 노드를 구분하고, 명시적 근거가 있는 관계만 만드는 방법을 정리한다.
공유 코드는 일반화한 그래프 구축 로직과 **가상의 합성 입력**으로 제한한다.
실제 데이터로 실행한 결과를 공개 예제의 결과로 제시하지 않는다.

## 공유 경계

**내부 데이터는 익명화 여부와 무관하게 포함하지 않는다.**

다음 항목은 모두 로컬에만 남기고 이 실습 PR에서 제외한다.

- 내부 Slack 대화, PR payload, commit/file snapshot, AWS snapshot.
- 실제 source code와 endpoint, 이벤트 계약, repository/account/resource 식별자.
- 내부 자료에서 파생된 candidate graph, topology JSON, 그래프 스크린샷과 발표 HTML.
- 실제 업무 사례의 상세 내용과 데이터 집계 결과.
- private binding, identity 승인 파일, `.env`, credential, Neo4j 저장소.

> 실험 데이터·`.env`·snapshot·Neo4j 저장소는 계속 로컬에만 두고, 공유할 자료에는 익명화된 코드와 집계 결과만 남기는 게 맞아.

위 문구는 로컬 보관 원칙을 설명한다. **이번 PR은 더 엄격하게 내부 자료의 집계 결과도 제외**하고,
일반화한 실습 구현과 합성 입력에 대한 검증만 공유한다.
합성 입력은 실제 값을 치환한 데이터가 아니라 독립적으로 만든 가상 예시다.

## 모델링 원칙

| 객체 | 역할 |
| --- | --- |
| Case | 수동으로 정한 조사 범위. 원천 업무 객체가 아님 |
| SlackThread | 가상 대화 스레드 객체 |
| PullRequest | 가상 변경 요청 객체 |
| Commit / CodeFile | 변경 이력과 파일 객체 |
| Identity / Person | 원천별 계정과 승인된 사람 매핑을 구분 |
| AWSResource | snapshot에서 식별 가능한 클라우드 구성 객체 |
| APIContract | service·HTTP method·path로 구분한 정적 계약 |

청크는 객체 노드로 materialize하지 않고 `evidence_chunk_ids` 등의 속성으로 참조한다.
같은 Case 소속이나 이름 유사성만으로 의미 관계를 추가하지 않는다.

## 관계의 의미

- `INCLUDES`: 조사 범위에 포함. 인과관계나 실제 호출이 아니다.
- `LINKS_TO`: 본문에 명시된 URL로 연결. 같은 범위에 있다는 이유로 만들지 않는다.
- `AUTHORED`: PR 작성자.
- `CONTRIBUTED_TO`: 이 구현에서는 Slack에서 PR 링크를 공유한 관계. 코드 기여를 뜻하지 않는다.
- `IDENTITY_OF`: 승인된 매핑만 허용. 이름만으로 사람을 합치지 않는다.
- `RELATED_TO`: 코드 이벤트 계약 일치 또는 snapshot의 구성 소속. 운영 전달 성공이 아니다.
- `IMPLEMENTS`: PR의 라우트 추가 또는 고정 revision의 코드 구현. 근거 수준을 구분한다.
- `CALLS_WITH`: 코드의 정적 HTTP method/path 사용. 실제 요청 성공이 아니다.

## 근거 검증 방법

1. 직접적인 링크와 원천 객체 ID를 확인한다.
2. PR 변경 근거와 고정된 코드 snapshot의 근거를 구분한다.
3. endpoint의 controller/router prefix·method·path를 정확히 대조한다.
4. 호출 경로의 baseURL-relative scope와 서버의 controller-relative scope를 보존한다.
5. AWS 이벤트 source/detail-type과 필터를 정확히 대조한다.
6. 구성 소속과 실제 운영 전달을 구분한다.
7. 근거가 없거나 범위를 확인하지 못하면 관계를 만들지 않는다.

## 재현 범위

`src/`의 공개용 테스트와 합성 데모로 일반화한 로직을 검증한다.
실제 업무 corpus·승인 mapping·운영 환경을 재현하는 패키지는 아니다.

## 공개 실행 및 실제 검증

저장소 루트에서 다음처럼 실행한다. `.venv`는 Git에 추가하지 않는다.

```sh
cd members/kungbi/labs/02-evidence-grounded-knowledge-graph/src
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python synthetic_demo.py
```

공개 PR 준비 과정에서 CPython 3.13.7 및 `neo4j` 6.4.0으로 위 테스트를 실제 실행했다.

- 50개 테스트 통과, skip 없음.
- 합성 demo: 10개 노드·11개 관계, provenance validation 통과.
- demo/test는 네트워크·live Neo4j를 사용하지 않는다.
- Neo4j driver 호출은 mock으로 검증했으며, 실제 database loading은 이 공개 실습 범위에 포함하지 않는다.

## 후속 평가

독립적으로 검증한 gold evidence로 검색·답변을 평가해야 한다.
Case 선정 파일 자체를 gold 정답으로 간주하지 않으며, 그래프 구축 성공을 검색 품질 향상으로 해석하지 않는다.
공개 예제의 합성 데이터 테스트 역시 실제 환경의 성능 검증을 대신하지 않는다.
