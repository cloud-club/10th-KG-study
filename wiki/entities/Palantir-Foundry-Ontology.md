---
title: Palantir Foundry Ontology — 조회에서 실행으로
type: entity
tags: [tool]
status: maintained
created: 2026-10-02
updated: 2026-10-02
members: [kdyann, do-dop, e0ng, dldusgh318, Yeongeunn, kungbi, sunghyun]
weeks: [4]
---

> Object Type · Property · Link Type · **Action Type** · Function으로 조직의 운영 객체를 모델링하는 Palantir Foundry의 온톨로지 층. 4주차에 일곱 멤버가 서로 다른 공식 문서 세 개를 인용해 같은 구조를 정리했고, 둘(kdyann, Yeongeunn)이 같은 경고를 했다 — **Action은 OWL 추론이 아니다.** RDF 표준 어휘와 섞이지 않도록 이 페이지에 따로 둔다. 다른 기업 사례는 [[기업-지식그래프-사례]].

## 개요

| 요소 | 뜻 | 비고 |
|---|---|---|
| Object Type / Object | 종류와 인스턴스 (주문, 제품, 공급업체) | CRM·주문 DB·물류·인사 테이블 행이 Object로 매핑된다 (e0ng) |
| Property | 속성 | |
| Link Type / Link | 관계. 생성 방식 셋 — 외래키 / 조인 테이블 / **관계 속성을 중간 Object Type으로** (kdyann) | RDF의 "사건 노드" 모델링과 같은 문제를 제품이 UI로 노출한 것 → [[RDF와-트리플]] |
| **Action Type / Action** | 업무에서 허용된 변경. 입력값·변경 규칙·검증 조건·권한을 구성 (kdyann) | "이 주문을 승인한다", Claim 승인, 관계 수정, 중복 엔티티 병합 (do-dop) |
| Function | 계산·모델 예측 | OWL 공리의 논리적 결론과 구분 (kdyann) |

- 공식 문서의 분류: **Semantic**(Objects·Properties·Links) vs **Kinetic**(Actions·Functions·Dynamic security) (kdyann).
- 핵심 전환: 조회("이 주문의 상태는?")에서 운영("이 주문을 승인한다")으로. 그래프가 **조회 대상 → 운영 인터페이스**로 확장된다 (dldusgh318). "단순히 담당 팀을 답하는 데 Action은 필요 없고, 승인된 담당자가 장애 상태를 바꾸려면 실행이 필요하다" (sunghyun).
- **Writeback 경계** (kdyann): 온톨로지 데이터 변경 ≠ 외부 시스템 반영. 외부 API 호출은 웹훅 등 별도 구성. "화면의 버튼만 보고 실제 비행편이나 장비가 어떻게 움직이는지 알 수는 없다." Yeongeunn: "조회에서 실행으로 확장할수록 권한·변경 이력·원래 업무 시스템과의 **상태 동기화**가 중요해진다."

## RDF·OWL과의 비교

| 축 | RDF · OWL | Foundry Ontology |
|---|---|---|
| 범위·목적 | 사실의 의미 표현과 추론, 시스템 간 공유 | 한 조직의 업무 플랫폼 |
| 상태 변경 | `SPARQL Update`로 가능 — "RDF는 읽기 전용"은 오해 (kdyann) | Action으로 규칙·권한·이력과 함께 |
| 실행 기능 | 없음 (추론기) | Action·Function |
| 표준·생태계 | W3C 공개 표준 | 벤더 제품 |

- "비교의 핵심은 수정 가능 여부가 아니라 표준 데이터 표현과 업무 플랫폼이 제공하는 범위의 차이" (kdyann). "RDF·OWL이 사실의 의미와 추론에 초점을 두는 반면 Palantir는 애플리케이션·권한·업무 행동까지 연결한다" (do-dop).
- **Action ≠ 추론**: Action은 "새 사실의 논리적 도출"이 아니라 "업무에서 허용된 변경의 모델링" (kdyann). → [[온톨로지와-추론]]
- 역사적 자리: 시맨틱 웹의 비전이 웹 전체가 아니라 한 조직 범위에서 재등장한 형태 (dldusgh318) → [[시맨틱-웹에서-지식그래프까지]]. [[OpenViking-컨텍스트-데이터베이스]]와의 경계 — 자료·기억·절차를 찾는 것 vs 업무 객체를 바꾸는 것.

## 겪은 문제 · 함정

- 실측은 없다. 전원 공식 문서와 제품 화면 관찰 기반 정리이고 스크린샷은 없다.

## 의사결정 · 남은 일

- 스터디의 개인 그래프에 Action에 해당하는 것은 없다. 조회·탐색까지만이다.

## 관련

- [[기업-지식그래프-사례]] · [[시맨틱-웹에서-지식그래프까지]] · [[온톨로지와-추론]] · [[RDF와-트리플]] · [[OpenViking-컨텍스트-데이터베이스]]

## 출처

- kdyann · 팔란티어 온톨로지의 Object·Link·Action과 RDF 비교 — [members/kdyann/notes/04-3-palantir-ontology.md](../../members/kdyann/notes/04-3-palantir-ontology.md); 온톨로지 변천사 (§8) — [04-1-kg-history.md](../../members/kdyann/notes/04-1-kg-history.md)
- do-dop · 시맨틱 웹에서 지식그래프까지 (§12) — [members/do-dop/notes/04-semantic-web-to-knowledge-graph.md](../../members/do-dop/notes/04-semantic-web-to-knowledge-graph.md)
- e0ng · 지식 그래프의 변천사 (§Palantir Ontology) — [members/e0ng/notes/04-1-knowledge-graph-history.md](../../members/e0ng/notes/04-1-knowledge-graph-history.md)
- dldusgh318 · 변천사 (§10) — [members/dldusgh318/notes/week4/04-history.md](../../members/dldusgh318/notes/week4/04-history.md)
- Yeongeunn · 기업의 지식 그래프 활용 사례 (§8) — [members/Yeongeunn/notes/12-enterprise-knowledge-graph-cases.md](../../members/Yeongeunn/notes/12-enterprise-knowledge-graph-cases.md)
- kungbi · W4 지식 그래프의 배경 (§2) — [members/kungbi/notes/02-knowledge-graph-background.md](../../members/kungbi/notes/02-knowledge-graph-background.md)
- sunghyun · 지식 그래프는 왜 필요한가 (§팔란티어) — [members/sunghyun/notes/04-knowledge-graph-background.md](../../members/sunghyun/notes/04-knowledge-graph-background.md)
- 외부: Palantir Foundry Ontology overview https://www.palantir.com/docs/foundry/ontology/overview (kdyann) · Ontology core concepts https://palantir.com/docs/foundry/ontology/core-concepts (kungbi) · Ontology system (architecture center) https://www.palantir.com/docs/foundry/architecture-center/ontology-system (Yeongeunn·sunghyun) · Object and Link Types https://www.palantir.com/docs/foundry/object-link-types/type-reference (do-dop)
