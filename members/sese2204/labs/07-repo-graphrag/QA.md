# 질의–답변 모음 (정성평가용)

> `src/qa_report.py`가 `eval_run4_terra.json`에서 생성한다. 손으로 고치지 말고 다시 생성한다.
> 생성 `gpt-5.4-mini` · 추출 `gpt-5.6-terra` · 판정 `claude-sonnet-5-5`(1회, 참고용).
> 답변 속 `[C·G·S·W번호]`는 각 방식이 받은 근거 번호다. C 원문 청크, G 그래프 사실, S 커뮤니티 요약, W 위키.

## 읽는 법

질문마다 정답(gold)과 세 방식의 답을 나란히 둔다. 판정 표시는 참고용이고, 다음을 보며 읽는다.

- **누가 확인했나**를 맞게 붙였나 (멤버 id, 측정 vs 정리)
- 근거에 없는 것을 **단정**했나, 모르면 "근거 없음"이라고 했나
- 수치에 **조건**(데이터·문항 수·지표)이 따라왔나
- 여러 멤버를 **모았나**, 한 문서에 머물렀나

| # | 유형 | v1 | v2 | v3 |
|---|---|---|---|---|
| [Q01](#q01) | 단일 사실 | ✅ | ✅ | ✅ |
| [Q02](#q02) | 단일 사실 | △ | △⚠ | △ |
| [Q03](#q03) | 교차 멤버 | ❌⚠ | △⚠ | △⚠ |
| [Q04](#q04) | 교차 멤버 | △ | ❌⚠ | △⚠ |
| [Q05](#q05) | 멀티홉 | ✅ | ✅ | ✅ |
| [Q06](#q06) | 집계(구조) | ❌⚠ | ✅ | ❌ |
| [Q07](#q07) | 집계(구조) | ❌ | ✅ | ❌ |
| [Q08](#q08) | 집계(함정) | ✅ | △⚠ | ✅ |
| [Q09](#q09) | 글로벌 | ❌⚠ | △ | △ |
| [Q10](#q10) | 글로벌 | △⚠ | △⚠ | ✅⚠ |
| [Q11](#q11) | 모순 | ✅ | △⚠ | △ |
| [Q12](#q12) | 근거 없음 | ✅ | ✅ | ❌⚠ |

✅ 정답 · △ 부분 · ❌ 오답 · ⚠ 근거 없는 단정 (심판 1회 판정)

---

## Q01

**단일 사실** — kdyann의 6주차 GraphRAG 실습에서 다중 홉·추천 질문 4개의 Recall@5는 v1과 v2가 각각 얼마였나?

**정답(gold)**: v1 0.33 · 0.50 · 0.00 · 0.00, v2는 네 문항 모두 1.00 (단순 질문 2개는 둘 다 1.00)

<sub>gold 근거: members/kdyann/labs/06-graphrag/README.md 67~72행</sub>

### v1 · 청크 하이브리드

<sub>근거 청크의 문서: `labs/04-graphrag-agent/README.md` ×4, `labs/06-graphrag/README.md` ×4</sub>

> kdyann가 확인했고, 6주차 GraphRAG 실습에서 다중 홉·추천 질문 4개의 Recall@5는 v1이 각각 0.33, 0.50, 0.00, 0.00이고 v2가 각각 1.00, 1.00, 1.00, 1.00이었다고 정리했다.[C4]  
> 해당 4개 질문은 `내 오픈소스 기여와 같은 분야의 참고 글`, `내 AI 글과 연결되는 다른 주제 참고 글`, `내 게시물로 만들 만한 주제와 참고 글`, `아직 올리지 않은 AI 주제와 참고 글`이다.[C4]  
> 집계 2개는 Recall을 계산하지 않는다고 명시되어 있어, 여기서는 제외했다.[C4]  
> 근거는 `kdyann`의 실습 README에 있는 최종 검색 결과 표이다.[C4]

<details><summary>판정 ✅</summary>

v1 0.33·0.50·0.00·0.00, v2 네 문항 모두 1.00으로 gold 핵심 수치와 일치한다. 질문 목록과 집계 2개 제외는 gold에 없는 추가 정보지만 gold와 모순되지 않는다.

</details>

### v2 · GraphRAG

<sub>경로 `local` · 진입 엔티티 멀티홉 질의, Recall@k, GraphRAG</sub>

> kdyann가 확인한 6주차 GraphRAG 실습 결과에서, 다중 홉·추천 질문 4개의 Recall@5는 v1이 각각 0.33, 0.50, 0.00, 0.00이고 v2가 각각 1.00, 1.00, 1.00, 1.00입니다.[C4]  
> 이는 `내 오픈소스 기여와 같은 분야의 참고 글`, `내 AI 글과 연결되는 다른 주제 참고 글`, `내 게시물로 만들 만한 주제와 참고 글`, `아직 올리지 않은 AI 주제와 참고 글`의 값입니다.[C4]  
> 정리한 사람은 kdyann이며, 측정한 사람도 kdyann입니다.[C4]  
> v2는 비교 범위 전체를 조회해 집계와 연결을 더 잘 확보했고, v1은 상위 5개만으로는 일부 질문을 확정하지 못했습니다.[C3][C4]

<details><summary>판정 ✅</summary>

v1 0.33·0.50·0.00·0.00, v2 네 문항 모두 1.00으로 gold의 핵심 수치를 정확히 맞혔다. 질문 제목, 측정자, v2/v1 설명 등 추가 정보는 gold와 모순되지 않는다.

</details>

### v3 · LLM 위키

<sub>검색된 위키 페이지: [[실습-비교표]], [[멀티홉-질문과-Bridge-Entity]], [[RAG-vs-그래프-질의]], [[GraphRAG]], [[지식그래프와-온톨로지]], [[index]]</sub>

> kdyann의 6주차 GraphRAG 실습에서 다중 홉·추천 질문 4개의 Recall@5는 v1이 0.33·0.50·0.00·0.00, v2가 전부 1.00이었다고 확인했다. [W4]  
> 이 수치는 멤버 github id `kdyann`이 확인한 실습 결과다. [W4]  
> 여기서 나는 결과를 **정리했다**고 말할 수 있고, 직접 **측정했다**고는 말할 수 없다. [W4]

<details><summary>판정 ✅</summary>

v1 0.33·0.50·0.00·0.00, v2 네 문항 모두 1.00으로 gold의 핵심 수치를 정확히 맞혔다. 단순 질문 2개 언급은 없지만 질문 범위가 다중 홉·추천 4개이므로 핵심에는 영향이 없고, '정리했다/측정했다' 부연은 gold와 모순되지 않는다.

</details>

---

## Q02

**단일 사실** — sunghyun의 에이전틱 검색 비교에서 그래프 조회 도구를 추가했을 때 사실 항목 점수는 어떻게 바뀌었나?

**정답(gold)**: 그래프 없이 4/9 → 그래프 도구 추가 3/9로 떨어졌다. 경로를 잘못 골라(Task→Test Case 직접 연결) 13개를 18개로 셌다

<sub>gold 근거: members/sunghyun/labs/06-graphrag/README.md 111행, notes/06-graphrag-and-agentic-search.md</sub>

### v1 · 청크 하이브리드

<sub>근거 청크의 문서: `notes/06-graphrag-and-agentic-search.md` ×4, `labs/06-graphrag/README.md` ×4</sub>

> sunghyun이 **정리하고 측정한** 에이전틱 검색 비교 결과로, 그래프 조회 도구를 추가했을 때 사실 항목 점수는 **4/9에서 3/9로 낮아졌습니다**.[C5]  
> 같은 비교에서 그래프 없이 검색·원문·목록 방식은 4/9, 같은 도구에 그래프 조회를 더한 방식은 3/9였습니다.[C5]  
> 즉, 그래프 도구 추가가 점수 향상으로 이어지지 않았고 오히려 1점 낮아졌습니다.[C5]  
> 다만 이 결과는 질문별 한 번씩 실행한 기록이며, 자동 점수는 9개 사실 항목만 비교한 것입니다.[C5]  
> 근거는 sunghyun의 노트와 실습 README에 있습니다.[C5][C7]

<details><summary>판정 △</summary>

4/9에서 3/9로 떨어졌다는 핵심 수치는 맞혔지만, 경로를 잘못 골라(Task→Test Case 직접 연결) 13개를 18개로 센 원인 설명이 빠져 있다. 추가로 적은 내용(질문별 1회 실행, 9개 항목만 비교)은 gold와 모순되지 않는다.

</details>

### v2 · GraphRAG

<sub>경로 `local` · 진입 엔티티 에이전틱 검색</sub>

> sunghyun이 확인한 결과, 에이전틱 검색에 그래프 조회 도구를 추가하면 사실 항목 점수는 4/9에서 3/9로 낮아졌습니다.[C5][G1]  
> 즉, 그래프 도구 추가가 점수를 올리지 못했고 오히려 1점 감소했습니다.[C5][G1]  
> 이 비교는 sunghyun이 GLM-5.2로 같은 질문 세트를 두 방식으로 실행해 정리한 결과입니다.[C1][C4]  
> 정리했다는 의미이지, 별도의 수작업 측정이 아니라 실험 실행 결과를 기록한 것입니다.[C1][C5]

<details><summary>판정 △ ⚠</summary>

4/9에서 3/9로 떨어졌다는 핵심 수치는 맞혔지만, 경로를 잘못 골라(Task→Test Case 직접 연결) 13개를 18개로 센 원인은 빠졌다. 또한 GLM-5.2 사용과 수작업이 아닌 실험 실행 결과라는 설명은 gold에 없는 내용을 확정적으로 주장한 것이다.

</details>

### v3 · LLM 위키

<sub>검색된 위키 페이지: [[GraphRAG]], [[RAG-vs-그래프-질의]]</sub>

> sunghyun이 **측정한** 에이전틱 검색 비교에서는 그래프 조회 도구를 추가하자 사실 항목 점수가 **4/9에서 3/9로 떨어졌다**고 기록돼 있다. [W1][W4][W6]  
> 즉, 그래프 도구를 넣었는데도 성능이 좋아지지 않았고 오히려 1점 낮아졌다. [W1][W2]  
> 이 비교는 sunghyun이 확인한 것이며, 모델이 경로를 고르게 한 에이전틱 조건에서 나온 결과다. [W1][W6]

<details><summary>판정 △</summary>

4/9에서 3/9로 떨어졌다는 핵심 수치는 맞혔지만, 경로를 잘못 골라(Task→Test Case 직접 연결) 13개를 18개로 센 원인이 빠졌다. 추가 설명은 gold와 모순되지 않는다.

</details>

---

## Q03

**교차 멤버** — RRF 융합이 BM25나 벡터 단독 검색보다 못한 결과를 직접 측정한 멤버는 누구이고, 각각 어떤 조건이었나?

**정답(gold)**: 다섯 명 — Yeongeunn(Notion 10문항, R@5 BM25 0.60·벡터 0.70·RRF 0.55), yujeong430(카카오톡 40문항, R@1 BM25 58.8% > RRF 57.5%), sunghyun(회의록 질문 Q5, R@10 BM25 1.00 > RRF 0.75), lys0611(R@10에서 BM25보다 낮음), e0ng(36문항 R@3·R@5). do-dop은 단독 검색이 아니라 정규화 융합과의 비교라 별개

<sub>gold 근거: wiki 하이브리드-검색과-RRF 정의문 + 원문 대조(yujeong430 evaluation/README 37행, sunghyun notes/03 167~169행, Yeongeunn labs/04 35행)</sub>

### v1 · 청크 하이브리드

<sub>근거 청크의 문서: `labs/04-hybrid-evaluation/README.md` ×3, `notes/04-reciprocal-rank-fusion.md` ×4, `labs/03-company-analysis-kg/rag-vs-kg-summary.md`</sub>

> 직접 **측정했다**고 확인되는 멤버는 **Yeongeunn(github id)** 입니다. [C1][C4]  
> Yeongeunn은 같은 Notion 청크와 질문으로 BM25·벡터·RRF를 비교했고, 결과 표에서 BM25 0.60, 벡터 0.70, RRF 0.55로 RRF가 단독 검색보다 낮았음을 정리했습니다. [C1][C4]  
> 조건은 q01(정확한 용어)에서 BM25 1위였던 지정 근거가 벡터 후보 30개에 없어서 RRF가 6위로 밀린 경우, q05(다른 표현)에서 벡터 1위의 지정 근거가 BM25 후보에 없어서 RRF가 7위였던 경우입니다. [C2][C4]  
> 또 q09(다중 홉)에서는 BM25 0.5, 벡터 1.0, RRF 0.5로 RRF가 벡터 단독보다 낮았습니다. [C4]  
> 근거상 “직접 측정한” 사람은 Yeongeunn뿐이며, 다른 멤버가 RRF가 더 못한 결과를 직접 측정했다는 근거는 없습니다. [C1][C4]

<details><summary>판정 ❌ ⚠</summary>

정답은 다섯 명(Yeongeunn, yujeong430, sunghyun, lys0611, e0ng)인데, 시스템은 Yeongeunn 한 명뿐이라고 단정하고 나머지 멤버를 모두 누락했으며 "다른 멤버의 근거는 없다"고 잘못 주장했다.

</details>

### v2 · GraphRAG

<sub>경로 `aggregate` · Cypher 결과 6행</sub>

> 직접 **측정**해서 RRF가 BM25 또는 임베딩보다 못하다고 보고한 멤버는 **Yeongeunn, do-dop, lys0611**입니다. [G1]  
> Yeongeunn은 **“BM25·벡터 순위를 결합한 이번 실험”**에서 평균 점수가 오히려 낮아졌다고 측정했고, 비교 대상은 BM25와 임베딩이었습니다. [G1]  
> do-dop은 **“벡터 검색 결과에는 해당 정답 문서가 없는 하이브리드 검색”** 조건에서 BM25 20개 후보 중 1등이던 것이 RRF 융합 후 11위로 떨어졌다고 측정했습니다. [G1]  
> 또 do-dop은 **“상위 20개 BM25·벡터 검색 결과를 RRF로 융합”** 조건에서도 BM25 1위(점수 21.56)에서 RRF 융합 후 11위(점수 0.0164)로 내려갔다고 측정했습니다. [G1]  
> lys0611은 **“1,922개 청크, 검색기별 후보 50개, c=60, ef_search=100, 27문항 초기 라벨 기준”**에서 Evidence Recall@10이 RRF 0.907, BM25 0.926으로 RRF가 낮았다고 측정했습니다. [G1]  
> 또 lys0611은 **“두 대화방에 걸친 bridge 질의에서 결정 청크와 구현 세부 청크를 함께 찾아야 하는 경우”**에 구현 세부 근거가 BM25 8위에서 RRF 11위로 떨어졌다고 측정했습니다. [G1]

<details><summary>생성된 Cypher</summary>

```cypher
MATCH (m:Member)-[:REPORTED]->(f:Finding {kind:'measured'})-[:ABOUT]->(rrf:Technique {name:'RRF'})
MATCH (f)-[cw:COMPARED_WITH {outcome:'lose'}]->(o)
WHERE o.name IN ['BM25','임베딩']
OPTIONAL MATCH (f)-[:ON_DATA]->(d:Dataset)
RETURN DISTINCT m.id AS member, o.name AS compared_with, f.condition AS condition, f.metric AS metric, f.value AS value, d.name AS dataset
ORDER BY member, compared_with, condition LIMIT 50
```

</details>

<details><summary>판정 △ ⚠</summary>

gold는 다섯 명(Yeongeunn, yujeong430, sunghyun, lys0611, e0ng)인데, 시스템은 Yeongeunn과 lys0611만 맞혔고 yujeong430·sunghyun·e0ng은 빠뜨렸다. 또한 gold가 별개로 분류한 do-dop을 포함시켰고, Yeongeunn의 구체 수치(10문항, R@5 0.60/0.70/0.55)도 없다.

</details>

### v3 · LLM 위키

<sub>검색된 위키 페이지: [[하이브리드-검색과-RRF]], [[검색의-세-세대]], [[RAG-평가-지표]]</sub>

> RRF 융합이 BM25나 벡터 단독보다 못한 결과를 **직접 측정**한 멤버는 **Yeongeunn, yujeong430, sunghyun, lys0611, e0ng**입니다.[W1][W4]  
> **Yeongeunn**은 30+30 후보 조건에서 RRF가 꼴찌였고, 평균 기준으로도 졌다고 정리돼 있습니다.[W3][W1]  
> **yujeong430**은 40문항 평가에서 RRF가 전부 졌고, 질문 수가 가장 많은 평가에서도 패배했다고 측정했습니다.[W1]  
> **sunghyun**은 Q5에서 RRF가 졌고, Q1–Q4·Q6에서는 동률이라서 일부 조건에서만 열세였다고 확인했습니다.[W1]  
> **lys0611**은 27문항 Recall@5에서 BM25 0.833 / 벡터 0.815 / RRF 0.907로 RRF가 이겼지만, 10문항 정성 평가에서는 셋 다 실패한 질문이 있어 RRF가 항상 우세하진 않음을 함께 확인했습니다.[W2][W1]  
> **e0ng**은 10문항 평가에서 RRF가 모든 k에서 최고인 유일한 사례였고, 오히려 RRF가 못한 사례로는 제시되지 않았습니다.[W1]

<details><summary>판정 △ ⚠</summary>

다섯 명의 이름은 맞았지만 조건·수치가 대부분 빠졌거나 틀렸다. Yeongeunn은 Notion 10문항 R@5 수치가 없고, yujeong430은 R@1 58.8% 대 57.5%가 없다. sunghyun은 Q5의 R@10 수치가 없다. lys0611은 RRF가 이긴 사례로 설명해 gold와 모순되고, e0ng은 RRF가 최고인 유일한 사례(10문항)라고 해 gold의 36문항 R@3·R@5 열세와 모순된다.

</details>

---

## Q04

**교차 멤버** — BM25가 벡터 검색보다 더 잘 찾았다고 측정한 멤버와, 반대로 벡터가 더 나았던 멤버를 나눠서 알려줘.

**정답(gold)**: BM25 우세: lys0611(R@10 0.926 > 0.870), dldusgh318(R@5 0.469 > 0.407), kdyann(R@1 0.733 > 0.600), jjinthung(Hit@5 45% ≫ 2.5%). 벡터 우세: heebindev(0.50 < 0.80), Yeongeunn(0.60 < 0.70), e0ng(10문항 0.575 < 0.675, 36문항에서는 격차 소멸)

<sub>gold 근거: wiki 하이브리드-검색과-RRF 23행 (멤버 노트 수치 정리)</sub>

### v1 · 청크 하이브리드

<sub>근거 청크의 문서: `labs/04-hybrid-evaluation/README.md` ×3, `labs/01-ingest/compare.md` ×3, `notes/04-hybrid-search.md` ×2</sub>

> BM25가 벡터 검색보다 더 잘 찾았다고 **측정한** 멤버는 `lys0611`입니다. [C5][C7] 이 멤버는 희소한 기술 용어 질문에서 BM25가 강했다고 **정리했다**고 적었고, 정확한 문구가 있을 때는 grep만으로도 충분했다고 **정리했다**고 적었습니다. [C7] 반대로 벡터가 더 나았다고 **측정한** 멤버는 `Yeongeunn`입니다. [C2] `Yeongeunn`은 평균 지정 근거 Recall@5에서 벡터 0.70, BM25 0.60으로 벡터가 더 높게 나왔다고 **측정했다**고 볼 수 있습니다. [C2] 다만 `Yeongeunn`의 문서에는 “BM25가 벡터보다 더 잘 찾았다”는 반대 결론은 없어서, 그쪽은 **근거 없음**입니다. [C2][C8]

<details><summary>판정 △</summary>

BM25 우세는 lys0611만, 벡터 우세는 Yeongeunn만 맞혔고 dldusgh318·kdyann·jjinthung과 heebindev·e0ng는 빠졌다. 일부만 맞혀 partial이다.

</details>

### v2 · GraphRAG

<sub>경로 `aggregate` · Cypher 결과 2행</sub>

> BM25가 벡터 검색보다 더 잘 찾았다고 **측정한** 멤버는 `lys0611`입니다. [G1]  
> 반대로 벡터 검색이 BM25보다 더 나았다고 **측정한** 멤버는 `Yeongeunn`, `dldusgh318`, `e0ng`, `lys0611`입니다. [G1]  
> 이 구분은 그래프에서 `Finding.kind = 'measured'`인 보고만 집계한 결과입니다. [G1]  
> 확인한 멤버 github id는 위에 적은 각 멤버 id입니다. [G1]  
> 정리한 것이 아니라, 측정 결과를 그대로 분류한 것입니다. [G1]

<details><summary>생성된 Cypher</summary>

```cypher
MATCH (m:Member)-[:REPORTED]->(f:Finding)-[:ABOUT]->(a)
WHERE f.kind = 'measured'
  AND a.name = 'BM25'
  AND EXISTS { MATCH (f)-[:COMPARED_WITH {outcome:'win'}]->(:Technique {name:'임베딩'}) }
RETURN 'BM25가 벡터 검색보다 더 잘 찾았다고 측정한 멤버' AS group, collect(DISTINCT m.id) AS members, count(DISTINCT m) AS member_count
UNION ALL
MATCH (m:Member)-[:REPORTED]->(f:Finding)-[:ABOUT]->(a)
WHERE f.kind = 'measured'
  AND a.name = '임베딩'
  AND EXISTS { MATCH (f)-[:COMPARED_WITH {outcome:'win'}]->(:Technique {name:'BM25'}) }
RETURN '벡터 검색이 BM25보다 더 나았다고 측정한 멤버' AS group, collect(DISTINCT m.id) AS members, count(DISTINCT m) AS member_count LIMIT 50
```

</details>

<details><summary>판정 ❌ ⚠</summary>

BM25 우세 멤버를 lys0611 하나만 댔고 dldusgh318, kdyann, jjinthung은 빠뜨렸다. 벡터 우세에는 dldusgh318과 lys0611을 잘못 넣었고 heebindev는 빠뜨렸다. lys0611이 양쪽에 동시에 들어가 모순이며, gold와 어긋나는 내용을 확정적으로 주장했다.

</details>

### v3 · LLM 위키

<sub>검색된 위키 페이지: [[검색의-세-세대]], [[RAG-평가-지표]], [[역색인과-BM25]]</sub>

> BM25가 벡터 검색보다 더 잘 찾았다고 **측정한** 멤버는 dldusgh318, heebindev, lys0611, jjinthung입니다. [W1][W6] dldusgh318은 `@Transactional` 코드 심볼에서 Recall@5가 BM25 1.000, Hybrid 0.500으로 BM25가 우세했다고 정리했고, heebindev는 `CPU 작업 순서`에서 BM25 85청크가 벡터 3건보다 더 정확했다고 정리했습니다. [W6][W1] lys0611은 27문항 Recall@5에서 BM25 0.833, 벡터 0.815로 BM25가 약간 앞섰다고 정리했고, jjinthung은 Hit@5가 BM25 45%, 벡터 2.5%로 BM25가 더 잘 찾았다고 측정했습니다. [W1][W6] 반대로 벡터가 더 나았다고 **측정한** 멤버는 e0ng, kdyann, do-dop입니다. [W1][W6] e0ng은 `수강 신청`에서 Precision@5가 BM25 0.6, pgvector 1.0이었고, kdyann은 `집중 시간을 관리하는 생산성 도구`에서 벡터만 결과가 나왔다고 정리했으며, do-dop은 `우리 팀명 뭐였지?`에서 BM25 74문서보다 pgvector가 팀명 논의 청크를 상위에 올려 확인 가능했다고 정리했습니다. [W1][W4]

<details><summary>판정 △ ⚠</summary>

BM25 우세 중 dldusgh318, lys0611, jjinthung은 맞혔지만 kdyann을 벡터 쪽에 잘못 넣었고, heebindev는 gold에서 벡터 우세인데 BM25 쪽으로 분류했다. 벡터 우세에서 e0ng만 맞고 Yeongeunn은 빠졌으며, do-dop은 gold에 없는 멤버다.

</details>

---

## Q05

**멀티홉** — Text2Cypher를 직접 돌려 본 멤버 중에서, 검토 대기(review_queue)로 빼 둔 관계가 리트리버에서는 제외됐는데 Text2Cypher 집계에는 들어가 버린 문제를 겪은 사람은?

**정답(gold)**: heebindev. 닫힌 스키마에 억지로 맞춘 관계를 predicate null로 review_queue.json에 모아 v2 근거에서 뺐지만, Text2Cypher는 Neo4j를 직접 조회해 그 관계까지 셌다

<sub>gold 근거: members/heebindev/labs/04-graphrag-agent/README.md, wiki GraphRAG 함정 절</sub>

### v1 · 청크 하이브리드

<sub>근거 청크의 문서: `labs/04-graphrag-agent/README.md` ×4, `notes/06-1-graphrag-patterns.md`, `notes/06-graphrag.md`, `labs/06-graphrag/README.md`, `notes/06-graphrag-and-agentic-search.md`</sub>

> heebindev가 확인했다. [C1]  
> 그는 `members/heebindev/labs/04-graphrag-agent/README.md`에서 review_queue에 넣어 둔 관계가 GraphRAG v2 검색기에서는 제외되지만, Text2Cypher가 Neo4j 원본을 직접 조회해 집계에 포함된다고 정리했다. [C1][C3]  
> 즉, 이 문제는 heebindev가 직접 실행 결과로 확인한 사례다. [C1]  
> 다만 이 답은 “정리했다”는 기록이며, 별도의 수치 측정이나 비교 실험을 추가로 측정했다는 근거는 없다. [C1][C3]

<details><summary>판정 ✅</summary>

heebindev를 정확히 지목했고, review_queue 관계가 v2 검색기에서는 제외되지만 Text2Cypher는 Neo4j를 직접 조회해 집계에 포함된다는 핵심을 맞혔다. predicate null이나 닫힌 스키마 같은 세부 내용은 빠졌지만 핵심 결론은 gold와 일치한다.

</details>

### v2 · GraphRAG

<sub>경로 `local` · 진입 엔티티 Text2Cypher</sub>

> 이 문제를 겪은 멤버는 **heebindev**입니다. [G1][C1]  
> heebindev가 확인했고, `review_queue.json`에 넣어 둔 검토 대상 관계가 리트리버에서는 제외됐지만 Text2Cypher가 Neo4j 원본을 직접 조회해 집계에 포함됐다고 정리했습니다. [C1][C3]  
> 즉, **정리한 사람은 heebindev**이고, **측정한 내용은 Neo4j 원본 관계 수가 그대로 집계에 들어간 것**입니다. [C1][G2]

<details><summary>판정 ✅</summary>

heebindev를 정확히 지목했고, review_queue 관계가 리트리버에서는 제외됐지만 Text2Cypher가 Neo4j를 직접 조회해 집계에 포함됐다는 핵심을 맞혔다. 다만 '측정한 내용' 등 일부 표현은 군더더기지만 gold와 모순되지 않는다.

</details>

### v3 · LLM 위키

<sub>검색된 위키 페이지: [[Text2Cypher]]</sub>

> 검토 대기(review_queue)로 빼 둔 관계가 리트리버에서는 제외됐는데 Text2Cypher 집계에는 들어가 버린 문제를 겪은 사람은 **heebindev**입니다. [W1][W2]  
> 위키에 따르면 heebindev는 집계 1문항에서 **검토 대상 관계가 포함된 채로** 성공했다고 정리돼 있습니다. [W2]  
> 이건 **heebindev가 확인한 것**으로, 제가 새로 측정한 값은 아닙니다. [W2]  
> 근거상 해당 문제를 겪은 멤버는 heebindev로 특정할 수 있습니다. [W1][W2]

<details><summary>판정 ✅</summary>

핵심 인물 heebindev를 정확히 맞혔고, 검토 대상 관계가 Text2Cypher 집계에 포함됐다는 취지도 gold와 부합한다. 다만 gold의 predicate null·v2 근거 제외 같은 세부 설명은 빠졌고, '집계 1문항 성공'은 gold에 없는 세부 정보지만 모순되지는 않는다.

</details>

---

## Q06

**집계(구조)** — frontmatter에 graphrag 태그를 단 문서를 쓴 멤버는 몇 명이고 누구인가?

**정답(gold)**: 6명 — do-dop, e0ng, heebindev, kdyann, sunghyun, yujeong430

<sub>gold 근거: corpus.py 태그 집계 (main fd8b7f6)</sub>

### v1 · 청크 하이브리드

<sub>근거 청크의 문서: `notes/week4/04-history.md`, `notes/08-llm-wiki.md`, `notes/06-1-graphrag-patterns.md`, `notes/01-rag-history.md`, `notes/13-week6-graphrag.md`, `notes/04-1-kg-history.md`, `notes/week4/00-summary.md`, `notes/06-graphrag.md`</sub>

> 근거로 확인되는 멤버는 5명입니다.[C1][C3][C4][C5][C6]  
> 확인한 멤버 github id는 dldusgh318, e0ng, kdyann, Yeongeunn, heebindev입니다.[C1][C3][C4][C5][C6]  
> 다만 이 근거들에는 각 문서의 frontmatter 원문이 직접 보이지 않아, 실제로 `graphrag` 태그를 단 문서인지까지는 근거 없음입니다.[C1][C3][C4][C5][C6]  
> 따라서 여기서는 “GraphRAG 관련 노트를 쓴 멤버”만 정리했고, “frontmatter에 graphrag 태그를 단 문서”는 추가 근거가 필요합니다.[C1][C3][C4][C5][C6]

<details><summary>판정 ❌ ⚠</summary>

정답은 6명(do-dop, e0ng, heebindev, kdyann, sunghyun, yujeong430)인데, 시스템은 5명이라고 하고 dldusgh318, Yeongeunn 등 gold에 없는 id를 포함했다. 일치하는 id는 e0ng, kdyann, heebindev 셋뿐이다. 또한 frontmatter 근거가 없다며 답을 유보했다.

</details>

### v2 · GraphRAG

<sub>경로 `aggregate` · Cypher 결과 1행</sub>

> frontmatter에 `graphrag` 태그를 단 문서를 쓴 멤버는 **6명**입니다. [G1]  
> 확인된 멤버 github id는 **e0ng, yujeong430, do-dop, kdyann, sunghyun, heebindev**입니다. [G1]  
> 이 값은 그래프 질의로 **측정한** 결과이며, 제가 따로 정리한 것이 아닙니다. [G1]

<details><summary>생성된 Cypher</summary>

```cypher
MATCH (m:Member)-[:WROTE]->(d:Document)-[:TAGGED]->(t:Tag)
WHERE toLower(t.name) = 'graphrag'
RETURN count(DISTINCT m) AS member_count, collect(DISTINCT m.id) AS members LIMIT 50
```

</details>

<details><summary>판정 ✅</summary>

시스템 답은 6명이라는 수치와 gold의 여섯 명(e0ng, yujeong430, do-dop, kdyann, sunghyun, heebindev)을 순서만 다르게 모두 맞혔다. 그래프 질의로 측정했다는 설명은 gold와 모순되지 않는다.

</details>

### v3 · LLM 위키

<sub>검색된 위키 페이지: [[LLM-트리플-추출]], [[실습-비교표]], [[GraphRAG]], [[log]]</sub>

> 근거 없음입니다. [W6]에는 frontmatter 누락·태그 표기 불일치가 언급되지만, `graphrag` 태그를 frontmatter에 단 문서와 그 멤버 목록은 제시되지 않았습니다. [W6]  
> 따라서 몇 명인지와 누구인지는 이 근거만으로 확인할 수 없습니다. [W6]  
> 확인한 멤버 github id도 근거에 없어 밝힐 수 없습니다. [W6]

<details><summary>판정 ❌</summary>

gold는 6명과 구체적인 멤버 목록을 제시하지만, 시스템은 '근거 없음'이라며 답하지 않았다. 답할 수 있는 질문에 답하지 못했으므로 wrong이다. 확정적으로 주장한 잘못된 사실은 없다.

</details>

---

## Q07

**집계(구조)** — 실습(labs) 문서를 가장 많이 쓴 멤버 상위 3명과 각자의 문서 수는?

**정답(gold)**: dldusgh318 10, lys0611 7, sunghyun 6

<sub>gold 근거: corpus.py kind=lab 집계 (dataset/·note-templates/ 제외, main fd8b7f6)</sub>

### v1 · 청크 하이브리드

<sub>근거 청크의 문서: `labs/03-triple-extraction-kg/README.md`, `labs/01-three-generations/WEEK5_result.md` ×2, `labs/01-notion-search/README.md`, `notes/07-recall-at-k.md` ×2, `README.md`, `README.md`</sub>

> 근거 없음입니다. [C1]~[C8]에는 각 멤버가 **labs 문서를 몇 개 썼는지 전체 집계**가 없어서 상위 3명을 정확히 계산할 수 없습니다. [C1][C2][C3][C4][C6][C8] 확인된 멤버 github id는 `heebindev`, `dldusgh318`, `yujeong430`, `lys0611`이지만, 이 근거만으로는 문서 수 비교가 불가능합니다. [C1][C2][C3][C4][C6][C8] 정리한 사람은 각 문서의 작성자이고, 측정한 사람은 따로 제시되지 않았습니다.

<details><summary>판정 ❌</summary>

gold는 dldusgh318 10, lys0611 7, sunghyun 6으로 답할 수 있는 질문인데, 시스템은 '근거 없음'이라 답하고 상위 3명과 문서 수를 하나도 제시하지 못했다.

</details>

### v2 · GraphRAG

<sub>경로 `aggregate` · Cypher 결과 3행</sub>

> 실습(labs) 문서를 가장 많이 쓴 상위 3명은 dldusgh318(10개), lys0611(7개), sunghyun(6개)입니다. [G1]  
> 이 결과는 멤버별 고유 lab 문서 수를 집계한 것이므로, “정리했다”가 아니라 “측정했다”에 해당합니다. [G1]  
> 확인한 멤버 github id는 dldusgh318, lys0611, sunghyun입니다. [G1]

<details><summary>생성된 Cypher</summary>

```cypher
MATCH (m:Member)-[:WROTE]->(d:Document)
WHERE d.kind = 'lab'
WITH m, count(DISTINCT d) AS doc_count
ORDER BY doc_count DESC, m.id ASC
LIMIT 3
RETURN m.id AS member_id, doc_count
```

</details>

<details><summary>판정 ✅</summary>

상위 3명과 문서 수(dldusgh318 10, lys0611 7, sunghyun 6)가 gold와 정확히 일치한다. 추가로 붙은 설명은 gold와 모순되지 않는다.

</details>

### v3 · LLM 위키

<sub>검색된 위키 페이지: [[실습-비교표]], [[현황판]], [[스터디-노트-지도]]</sub>

> 근거 없음입니다. [W1][W3][W6]  
> 제공된 근거에는 `labs` 문서를 멤버별로 집계한 전체 표가 없고, 일부 멤버의 실습 문서 예시만 있어 상위 3명을 정확히 정리할 수 없습니다. [W3][W6]  
> 누가 확인했는지까지 밝히려면 멤버 GitHub id 기준의 집계표가 필요한데, 현재 근거에는 그 정보가 없습니다. [W5][W6]

<details><summary>판정 ❌</summary>

정답은 dldusgh318 10, lys0611 7, sunghyun 6으로 답할 수 있는 질문인데, 시스템은 "근거 없음"이라고 답하고 상위 3명과 문서 수를 하나도 제시하지 않았다. gold와 모순되는 사실을 주장하지는 않았다.

</details>

---

## Q08

**집계(함정)** — 커뮤니티 탐지(Leiden·Louvain)와 글로벌 서치를 실제로 구현해 돌려 본 멤버는 누구인가?

**정답(gold)**: 없다. 6주차에 여러 멤버가 공부만 했고, heebindev 등은 그래프가 작아 의미 있는 커뮤니티가 안 나온다며 실행하지 않았다

<sub>gold 근거: members/heebindev/labs/04-graphrag-agent/README.md 12·249행, wiki GraphRAG 세 패턴 표</sub>

### v1 · 청크 하이브리드

<sub>근거 청크의 문서: `notes/06-graphrag.md` ×2, `notes/06-graphrag-and-agentic-search.md` ×2, `notes/13-week6-graphrag.md`, `notes/06-1-graphrag-patterns.md`, `notes/04-knowledge-graph-background.md` ×2</sub>

> 근거상 **실제로 구현해 돌려 본 멤버는 확인되지 않습니다**. [C1][C3][C6]  
> heebindev는 커뮤니티 탐지를 **이번 필수 실습에서 제외하고 선택 과제로 둔다고 정리**했고, 직접 실행하지 않았다고 적었습니다. [C1]  
> sunghyun도 커뮤니티 탐지와 보고서 생성을 **이번 실습에는 적용하지 않았다**고 정리했습니다. [C3]  
> 또 sunghyun은 글로벌 서치를 **“공부만, 미구현”**으로 정리했습니다. [C6]  
> 따라서 누가 **측정했다/실행했다**고 볼 근거는 없고, 현재 근거로는 **구현·실행한 멤버 없음**입니다. [C1][C3][C6]

<details><summary>판정 ✅</summary>

구현해 돌려 본 멤버가 없다는 gold의 핵심 결론을 맞혔고, heebindev가 실행하지 않았다는 점도 포함했다. 다만 '그래프가 작아서'라는 이유는 언급하지 않았지만 핵심은 아니고, 추가로 제시한 sunghyun 관련 내용도 gold와 모순되지 않는다.

</details>

### v2 · GraphRAG

<sub>경로 `aggregate→local` · 진입 엔티티 글로벌 서치, 커뮤니티 탐지 · Cypher 결과 0행</sub>

> 근거상 **실제로 구현해 돌려 본 것으로 확인되는 멤버는 heebindev와 sunghyun**입니다.[C1][C3] heebindev는 그래프 규모가 작아 커뮤니티 탐지를 **직접 실행하지 않고** 로컬 서치와 Text2Cypher를 먼저 확인했다고 정리했으므로, 커뮤니티 탐지를 실제로 돌렸다고 보기는 어렵습니다.[C1] sunghyun은 GraphRAG의 글로벌 질문 평가 결과를 **인용**했지만, 본인이 직접 구현·실행했다는 근거는 없습니다.[G2] 따라서 이 근거들만으로는 **커뮤니티 탐지와 글로벌 서치를 실제로 구현해 돌려 본 멤버를 확정할 수 없고, 근거 없음**입니다.[C1][C3][G2]

<details><summary>생성된 Cypher</summary>

```cypher
MATCH (m:Member)-[:REPORTED]->(f:Finding)-[:ABOUT]->(t:Technique)
WHERE t.name IN ['커뮤니티 탐지','글로벌 서치']
WITH m, collect(DISTINCT t.name) AS techniques
WHERE '커뮤니티 탐지' IN techniques AND '글로벌 서치' IN techniques
RETURN DISTINCT m.id AS member
ORDER BY member LIMIT 50
```

</details>

<details><summary>판정 △ ⚠</summary>

최종 결론은 '확정할 수 없다/근거 없음'으로 gold와 대체로 맞고 heebindev가 실행하지 않았다는 점도 맞췄지만, 첫 문장에서 heebindev와 sunghyun이 실제로 구현해 돌려 본 것으로 확인된다고 확정적으로 말해 gold와 모순되며 일관성이 없다.

</details>

### v3 · LLM 위키

<sub>검색된 위키 페이지: [[GraphRAG]], [[온톨로지와-추론]], [[실습-비교표]], [[10기-KG-스터디]]</sub>

> 근거상 **실제로 구현해 돌려 본 멤버는 없습니다**. [W2][W6]  
> 위키에는 **글로벌 서치는 아무도 구현하지 않았다**고 되어 있고, 6주차 스코프에도 글로벌 서치는 **아직 밖**으로 적혀 있습니다. [W2][W6]  
> 따라서 누가 **정리했다**고 볼 수 있는지도 근거가 없고, **측정했다**는 멤버는 확인되지 않습니다. [W2][W10]  
> 확인한 멤버 github id는 **없음**입니다. [W2][W6]

<details><summary>판정 ✅</summary>

시스템 답은 '실제로 구현해 돌려 본 멤버는 없다'는 gold의 핵심 결론을 맞혔다. 6주차에 공부만 했고 heebindev 등이 그래프가 작아 실행하지 않았다는 세부 사항은 빠졌지만, 핵심 결론과는 모순되지 않는다. 글로벌 서치 미구현이라는 추가 설명도 gold와 충돌하지 않는다.

</details>

---

## Q09

**글로벌** — 10기 스터디 전체에서 멤버들이 공통으로 부딪힌 문제나 교훈을 4~5가지로 정리해줘.

**정답(gold)**: 핵심 5개 중 3개 이상이면 정답: ① BM25는 여전히 강한 기준선이고 RRF가 항상 이기지는 않는다 ② 평가 수치는 정답셋을 누가 어떻게 만들었는지·채점 엄격도에 좌우된다 ③ 멀티홉이라고 그래프가 필요한 건 아니다(한 번 검색으로 근거가 모이느냐가 기준) ④ LLM이 뽑은 트리플은 사실이 아니라 후보 — 형식 통과와 의미 오류가 함께 나온다 ⑤ 그래프는 관계·집계 질문에서만, 맞는 경로를 골랐을 때만 이긴다

<sub>gold 근거: docs/10기-최종발표/10기-최종정리.md §3 (위키 합성 결과를 사람이 정리)</sub>

### v1 · 청크 하이브리드

<sub>근거 청크의 문서: `notes/week4/04-history.md`, `labs/01-three-generations/WEEK5_HANDOFF.md` ×4, `notes/week4/04.1-deep_dive.md`, `README.md`, `notes/08-llm-wiki.md`</sub>

> 멤버 github id `dldusgh318`, `sese2204`의 기록을 바탕으로 정리했다.[C1][C3][C8]  
> 1) 여러 사람의 데이터를 합치기 전에 공통 스키마와 관계 정의를 먼저 합의해야 한다는 점이 반복해서 확인됐다.[C1][C3]  
> 2) 같은 대상을 하나의 Entity로 묶는 Entity Resolution 문제가 실제로 생기며, 이름 표기 차이까지 정리 대상이 된다.[C1][C3]  
> 3) 표본이 작아도 엔티티 분해, 중복 생성, 결측 해석 같은 품질 문제가 이미 나타나고, 이를 방치하면 전체로 확대된다.[C2][C6][C7]  
> 4) 구조화 출력은 끝까지 안정적으로 나오지 않을 수 있어 JSON 절단 같은 오류를 먼저 발견하고, 출력량·재시도·종료 사유를 관리해야 한다.[C4][C6]  
> 5) 위키와 파이프라인 운영에서는 “누가 정리했다”와 “누가 측정했다”를 구분하고, 출처·북키핑·검증을 강제하는 절차가 필요하다는 교훈이 있었다.[C8]

<details><summary>판정 ❌ ⚠</summary>

시스템 답은 스키마 합의, 엔티티 해소, JSON 절단 같은 데이터 파이프라인 이슈만 다뤘고, gold의 핵심 5개(BM25 기준선/RRF, 정답셋·채점 엄격도, 멀티홉≠그래프, LLM 트리플은 후보, 그래프는 관계·집계에서만 우위) 중 어느 것도 맞히지 못했다. 또한 두 멤버의 기록만으로 '스터디 전체'의 교훈이라고 확정적으로 주장해 근거가 부족하다.

</details>

### v2 · GraphRAG

<sub>경로 `global`</sub>

> 10기 스터디 전체에서 멤버들이 공통으로 부딪힌 문제는, 검색기가 질문 유형에 따라 달라져서 하나의 방법으로는 다 못 맞춘다는 점이었다 [S2][S5][S7][S20].  
> 또한 멀티홉·집계·3-hop처럼 근거가 분산되거나 누적되는 질문에서는 검색과 추론이 함께 무너졌고, 필요한 근거를 다 넣어도 생성 단계에서 틀리는 경우가 있었다 [S1][S6][S11][S14].  
> 하이브리드/RRF, 리랭커, 그래프 도구 같은 보완책도 도움이 되지만 만능은 아니어서, 잘못된 문서 선택·직접 경로 선택·대화 오독 같은 실패가 계속 남았다 [S5][S10][S12][S15][S16].  
> 청킹과 인용·평가에서도 의미 단위 청킹이 더 유리했고, 인용 precision/recall이나 형식 통제만으로는 실제 답변 정확도와 근거 지지 여부를 보장하지 못했다 [S9][S11][S13][S18][S19].  
> 정리한 멤버 github id는 [do-dop], [dldusgh318], [lys0611], [sunghyun], [sese2204], [ur2e]이고, 이들은 각각 검색·추론 실패, RAG 검증, 그래프 활용, 평가 한계를 확인했다 [S1][S4][S6][S8][S9][S11][S12][S13][S14][S17][S18].

<details><summary>판정 △</summary>

gold 핵심 5개 중 시스템 답이 명확히 맞힌 것은 하이브리드/RRF가 만능이 아니라는 ①의 일부와 평가 한계(②와 부분 일치) 정도다. 멀티홉에 그래프가 꼭 필요한 건 아니라는 ③, LLM 트리플이 후보라는 ④, 그래프가 관계·집계 질문에서만 이긴다는 ⑤는 빠졌거나 모호하다. 3개 기준에는 못 미치지만 일부는 맞혔다. gold와 모순되는 확정적 주장은 없다.

</details>

### v3 · LLM 위키

<sub>검색된 위키 페이지: [[10기-KG-스터디]], [[시맨틱-웹에서-지식그래프까지]]</sub>

> 멤버 공통의 문제·교훈은 5가지로 정리할 수 있습니다. [W2][W5][W6]  
> 1) 개인 데이터에서 출발해도 결국 **관계·집계·시간처럼 청크 검색이 못 푸는 질문**이 남아, 이를 그래프로 넘겨야 한다는 점입니다. [W1][W6]  
> 2) 여러 멤버의 그래프를 합치려면 **관계 의미 합의, 공통 vocabulary, entity resolution, schema/ontology alignment**가 필요하다는 점입니다. [W5][W11]  
> 3) **RDF/프로퍼티 그래프, SPARQL/그래프 DB, Neo4j/Postgres**처럼 모델과 도구의 차이는 “무엇이 더 좋다”보다 **어떤 설계 관점을 강조하느냐**의 문제라는 점입니다. [W8][W9][W6]  
> 4) **추출·저장 품질이 먼저**여야 멀티홉 질의나 RAG가 의미가 있고, 스키마·관계가 제대로 들어가 있지 않으면 질의 언어만으로는 해결되지 않는다는 점입니다. [W9][W10][W6]  
> 5) 개인 데이터·조직 데이터 모두에서 **식별자 정리, 근거/품질 관리, 변경 반영, 가명화와 공개 범위 조정**이 반복되는 실무적 교훈입니다. [W2][W6][W11]  
> 이 정리는 위키 기준으로 제가 **정리한 것**이고, 별도 실측은 하지 않았습니다. [W2][W4]

<details><summary>판정 △</summary>

시스템 답은 gold 핵심 5개 중 ⑤(그래프는 관계·집계 질문에 유효)와 ④(추출 품질이 먼저)만 대략 맞혔다. BM25 기준선/RRF, 평가 정답셋·채점 엄격도, 멀티홉이 곧 그래프 필요는 아니라는 점은 언급하지 않아 3개 기준에 못 미친다. 다만 gold에 없는 내용도 위키 기반 정리로 보여 근거 없는 주장으로 단정하기는 어렵다.

</details>

---

## Q10

**글로벌** — 이 스터디는 어떤 순서로 주제를 밟아 왔나? 큰 흐름을 요약해줘.

**정답(gold)**: grep → 역색인·BM25(nori) → 임베딩·벡터 검색(HNSW·pgvector) → 하이브리드(RRF)·RAG·평가 → 지식그래프 이론(RDF·OWL·SPARQL·프로퍼티 그래프) → 닫힌 스키마·LLM 트리플 추출·적재 → GraphRAG(로컬·글로벌·Text2Cypher). '무엇을 찾을까'에서 '찾은 것을 어떻게 이을까'로

<sub>gold 근거: docs/10기-최종발표/10기-최종정리.md §2</sub>

### v1 · 청크 하이브리드

<sub>근거 청크의 문서: `readings.md`, `README.md`, `notes/05-reranker.md`, `notes/04-1-kg-history.md`, `README.md`, `notes/11-rdf-data-pipeline-concepts.md`, `notes/10-semantic-web-to-knowledge-graph.md`, `notes/02-search-generations.md`</sub>

> 이 스터디의 큰 흐름은 먼저 온톨로지와 시맨틱 웹의 개념적 배경을 이해하는 것에서 시작해, RDF·RDFS·OWL 같은 표준과 지식 그래프의 역사로 이어지는 순서입니다. [C1][C4][C7]  
> 그다음에는 문장을 그래프 데이터로 바꾸는 방법, 즉 어떤 대상을 기록하고 어떻게 추출하며 어떤 형식으로 전달할지(RDF, Turtle, JSON-LD)를 다룹니다. [C6]  
> 이후에는 검색 관점으로 넘어가서 grep → BM25 → 벡터 → 하이브리드 → GraphRAG처럼 검색/회수 방식의 변천과 각 단계의 장단점을 비교하려는 흐름이 보입니다. [C2][C3][C8]  
> 또한 GraphRAG는 문서 관계를 탐색·요약에 쓰는 방향으로, Palantir Ontology는 업무 모델과 액션에 연결하는 방향으로 구분해 이해하도록 정리되어 있습니다. [C7][C4]  
> 확인한 멤버는 heebindev, lys0611, sese2204, kdyann, yujeong430, e0ng입니다. [C1][C2][C3][C4][C5][C6][C7][C8]  
> 정리한 내용이며, 별도의 측정은 근거에 없습니다. [C1][C2][C3][C4][C5][C6][C7][C8]

<details><summary>판정 △ ⚠</summary>

grep→BM25→벡터→하이브리드→GraphRAG라는 검색 흐름은 언급했지만, 순서가 gold와 반대다. 온톨로지·RDF에서 시작해 검색으로 넘어간다고 했는데, gold는 검색(grep~RAG·평가)이 먼저이고 지식그래프 이론이 그 뒤에 온다. 또 역색인/nori, HNSW/pgvector, RRF, 평가, 닫힌 스키마·LLM 트리플 추출, Text2Cypher 같은 핵심 단계가 빠졌고, '무엇을 찾을까→어떻게 이을까'라는 핵심 메시지도 없다. 시작점을 온톨로지·시맨틱 웹 배경으로 확정한 것은 gold와 모순된다.

</details>

### v2 · GraphRAG

<sub>경로 `global`</sub>

> 스터디는 먼저 BM25·벡터 검색·HNSW·하이브리드·RRF 같은 **기본 검색기법 비교와 융합 함정**을 보며 출발했고, 이 흐름은 검색 성능 차이와 후보 누락 문제까지 정리한 것으로 확인됐다. [C0][C9][C17]  
> 그다음에는 **문자열/의미 검색, 청킹, 검색평가 지표**를 다루며 grep·BM25·pgvector의 강약과 Recall@k·MRR·Hit@k, 의미 단위 청킹의 유리함을 점검했다. [C4][C6]  
> 이후 **RAG 검증과 실패 양상, RAGAS 평가, 리랭커**로 넘어가 단일 홉·2-hop·3-hop 실패, Faithfulness/Answer Relevance/Context Relevance, 심판 프롬프트 개선과 리랭커 지연·도메인 밖 한계를 살폈다. [S7][C8][C9][S16]  
> 그 다음 큰 축은 **멀티홉 검색·추론 보완**으로, 쿼리 분해·에이전틱 검색·그래프 도구가 어디까지 통하고 어디서 실패하는지 확인했다. [C5][S13][S20]  
> 마지막으로 **지식그래프 추출·검증과 그래프 저장/질의**로 확장해, 엔티티 정규화·신원해소·트리플 추출·스키마 한계, 그리고 PostgreSQL·Neo4j·RDF 저장 일관성과 Cypher/JOIN/Text2Cypher/GraphRAG 질의를 비교했다. [C1][S3][S11][S18]  
> 정리하면, 확인한 멤버는 dldusgh318, sese2204, Yeongeunn이고, 이 흐름은 제가 **정리한** 것이며 별도 **측정한** 것은 아닙니다. [S7][S8][S18]

<details><summary>판정 △ ⚠</summary>

검색 → RAG·평가 → 지식그래프·GraphRAG라는 큰 방향은 맞지만, gold의 단계 순서를 놓쳤다. grep → 역색인·BM25 → 임베딩·벡터 → 하이브리드·RAG·평가 → KG 이론(RDF·OWL·SPARQL) → 스키마·트리플 추출 → GraphRAG 순서인데, 시스템 답은 BM25·벡터·하이브리드로 시작하고 grep을 뒤에 넣었다. KG 이론 단계도 빠졌고 '멀티홉 검색' 단계를 따로 끼워 넣었다. 또한 gold에 없는 멤버 이름을 확정적으로 언급했다.

</details>

### v3 · LLM 위키

<sub>검색된 위키 페이지: [[지식그래프와-온톨로지]], [[10기-KG-스터디]], [[RAG-변천사]]</sub>

> 이 스터디의 큰 흐름은 **OT·데이터 선정·개인정보/가명화·KG 기초**에서 시작해, **검색의 세 세대(grep → BM25 → 임베딩/벡터)**를 거쳐, **하이브리드 검색·RAG·멀티홉 한계**를 다룬 뒤, **시맨틱 웹/RDF·OWL/SPARQL·Wikidata 같은 KG 이론**으로 넘어가고, 마지막에 **닫힌 스키마·LLM 트리플 추출·그래프 적재·Cypher·GraphRAG**로 확장한 순서입니다.[W2][W5]  
> 이 흐름은 “검색이 못 푸는 질문을 그래프로 넘긴다”는 방향으로 정리되며, 특히 관계·다중 홉·집계 질문을 다루는 쪽으로 점점 이동했습니다.[W4][W7]  
> 또한 6주차에는 GraphRAG, Text2Cypher, 에이전틱 검색 비교까지 들어와서, **그래프를 만드는 단계**에서 **그래프를 리트리버로 붙여 비교하는 단계**로 넘어갔습니다.[W5][W8]  
> 이 순서는 dldusgh318, e0ng, do-dop, Yeongeunn, kdyann, sunghyun, heebindev, sese2204 등이 각 주차 실습과 정리에서 확인한 내용입니다.[W3][W6][W8]  
> 다만 “각 주제를 정확히 어떤 비중으로, 어떤 순서로 모두가 동일하게 밟았는지”까지는 근거가 부족하고, 위키상으로는 주차별 주제와 일부 실측만 확인됩니다.[W2][W5]

<details><summary>판정 ✅ ⚠</summary>

gold의 큰 흐름(grep→BM25→임베딩/벡터→하이브리드·RAG→RDF·OWL·SPARQL KG 이론→닫힌 스키마·LLM 트리플 추출·적재→GraphRAG·Text2Cypher)을 순서대로 모두 맞혔고 '검색이 못 푸는 질문을 그래프로'라는 결론도 일치한다. 다만 시작 단계의 'OT·데이터 선정·개인정보/가명화', 참여자 명단, '6주차' 같은 gold에 없는 세부 사실을 확정적으로 덧붙였다.

</details>

---

## Q11

**모순** — 점수 정규화 융합과 RRF 중 어느 쪽이 나은지를 두고 결론이 갈린 사례가 있나? 무엇이 결과를 뒤집었나?

**정답(gold)**: do-dop이 min-max 정규화 + 동일 가중 융합을 RRF와 같은 10문항으로 비교: 뉴스룸 57청크에서는 정규화 R@5 100% vs RRF 96.7%로 정규화가 이겼고, 무관 문서 4건을 더한 69청크에서는 RRF 100% vs 정규화 96.7%로 뒤집혔다. 코퍼스에 어떤 문서가 섞였는지에 따라 승자가 바뀐다 — '정규화는 안 된다'는 이전 정리에 대한 반례

<sub>gold 근거: wiki 하이브리드-검색과-RRF ⚠️ Contradiction, members/do-dop/notes/03-reciprocal-rank-fusion.md</sub>

### v1 · 청크 하이브리드

<sub>근거 청크의 문서: `labs/03-company-analysis-kg/README.md` ×2, `notes/03-reciprocal-rank-fusion.md` ×2, `notes/04-reciprocal-rank-fusion.md` ×2, `labs/03-company-analysis-kg/rag-vs-kg-summary.md`, `notes/03-rrf.md`</sub>

> 네, 결론이 갈린 사례가 있습니다. [C2][C7]  
> 멤버 `do-dop`이 확인했고, `search_common/score_fusion.py`로 RRF와 점수 정규화 융합을 비교해 정리했습니다. [C2][C3]  
> 57개 청크에서는 점수 정규화가 Recall@5 100%로 RRF(96.7%)보다 좋았지만, 69개 청크로 코퍼스를 늘리자 RRF가 100%로 역전되고 점수 정규화는 96.7%로 내려갔습니다. [C2][C7]  
> 뒤집힌 이유는 코퍼스 구성 변화였습니다: 한쪽에서는 BM25에서 압도적 1위였지만 벡터 후보에 없던 문서를 점수 정규화가 살렸고, 다른 쪽에서는 점수가 소수 문서에 쏠려 점수 정규화가 편향되면서 RRF가 더 유리해졌습니다. [C3][C7]  
> 즉, “항상 더 낫다”는 결론은 없고, 실제 데이터와 코퍼스에 따라 승자가 바뀐다고 확인했습니다. [C2][C7]

<details><summary>판정 ✅</summary>

do-dop, 57청크에서 정규화 100% vs RRF 96.7%, 69청크에서 RRF 100% vs 정규화 96.7%로 역전, 코퍼스 구성에 따라 승자가 바뀐다는 핵심을 모두 맞혔다. '무관 문서 4건 추가'와 '10문항'은 언급하지 않았고 BM25/점수 쏠림 설명은 gold에 없지만 모순되지 않는 부가 설명이다.

</details>

### v2 · GraphRAG

<sub>경로 `local` · 진입 엔티티 RRF, 점수 정규화 융합</sub>

> 네, 결론이 갈린 사례가 있습니다. do-dop가 확인한 실험에서 57개 청크 코퍼스에서는 점수 정규화 융합이 더 좋았고, 69개 청크로 넓히면 RRF가 더 좋았으며, 이 차이는 코퍼스 구성과 문서 수 변화가 뒤집은 것으로 정리했다. [G7][G4][G5][C3]  
> 또 다른 do-dop 확인 사례에서는 BM25에서 압도적 1위였지만 벡터 검색에 없는 문서를 RRF가 11위로 밀어냈고, 점수 정규화 융합은 그 문서를 4위로 살려냈다. [G3][G6][C1]  
> 즉, RRF는 등수만 반영해 점수 격차를 버리는 반면, 점수 정규화는 원래 점수 차이를 반영해 이런 문서를 더 높게 유지한 것이 결과를 뒤집은 핵심이다. [C3][C4][C5]  
> 다만 같은 do-dop 실험에서도 코퍼스를 69개 청크로 늘리면 RRF가 다시 우세해져, 어느 방식이 항상 낫다고는 단정할 수 없다고 확인했다. [G1][G2][C2]

<details><summary>판정 △ ⚠</summary>

57청크에서는 정규화가 이기고 69청크에서는 RRF가 이긴다는 뒤집힘은 맞혔지만, R@5 수치(100% vs 96.7%)와 '무관 문서 4건 추가'라는 핵심 조건이 빠졌다. 또한 gold에 없는 'RRF 11위/정규화 4위' 사례를 덧붙이고, 뒤집힌 원인을 '점수 격차 반영'이라고 주장해 gold의 원인(코퍼스에 섞인 문서)과 어긋난다.

</details>

### v3 · LLM 위키

<sub>검색된 위키 페이지: [[하이브리드-검색과-RRF]]</sub>

> 네, 결론이 갈린 사례가 있습니다. [W1][W3]  
> do-dop 멤버가 확인했고, 57청크에서는 정규화 융합이 RRF보다 R@5가 높았지만 69청크에서는 RRF가 정규화를 뒤집었습니다. [W1]  
> 뒤집힌 이유는 코퍼스에 섞인 문서 구성이 달라졌기 때문이며, 57청크에서는 벡터 후보에 없던 정답이 RRF에서 11위로 밀렸고 정규화가 4위로 건졌습니다. [W1][W3]  
> 반대로 69청크에서는 q009의 정답 3개 중 하나가 정규화에서 한 문서에 점수가 쏠려 top-5를 그 문서가 채우면서 정답 하나를 놓쳤습니다. [W1]  
> 즉, 어떤 방식이 낫다고 미리 고정할 수 없고, 평가셋이 있으면 둘 다 돌려봐야 한다는 결론입니다. [W1][W3]  
> 정리한 멤버는 do-dop이고, 측정한 멤버도 do-dop입니다. [W1][W9]

<details><summary>판정 △</summary>

57청크에서는 정규화가 이기고 69청크에서는 RRF가 뒤집었다는 방향과 '코퍼스 문서 구성이 승자를 바꾼다'는 핵심 결론은 맞았다. 다만 R@5 수치(100% vs 96.7%)와 '무관 문서 4건 추가'라는 구체적 조건이 빠졌고, 이전의 '정규화는 안 된다'는 정리에 대한 반례라는 점도 언급하지 않았다. 추가된 세부 사례(11위/4위, q009)는 gold에 없지만 모순되지는 않는다.

</details>

---

## Q12

**근거 없음** — 10기 멤버 중 임베딩 모델이나 LLM을 직접 파인튜닝해서 검색 성능을 비교한 사람은 누구인가?

**정답(gold)**: 없다(근거 없음). 파인튜닝은 KURE(bge-m3를 한국어로 파인튜닝한 외부 모델) 같은 모델 설명에만 나오고, 멤버가 직접 파인튜닝한 기록은 없다

<sub>gold 근거: members/ 전체 grep — 파인튜닝은 모델 설명에만 등장</sub>

### v1 · 청크 하이브리드

<sub>근거 청크의 문서: `notes/03-embedding-models.md` ×2, `notes/week2/03-embedding-vector-search.md` ×2, `labs/01-ingest/GUIDE.md`, `notes/02-embeddings-cosine-hnsw.md`, `notes/07-embedding-models.md`, `notes/02-search-generations.md`</sub>

> 근거 없음. [C1][C3][C5][C6][C8]  
> 제공된 근거에는 10기 멤버 중 **임베딩 모델이나 LLM을 직접 파인튜닝해서 검색 성능을 비교했다**는 확인된 기록이 없고, 확인된 사람의 github id도 나오지 않습니다. [C1][C3][C5][C6][C8]  
> 대신 `sese2204`는 자체 골든셋으로 임베딩 모델을 비교한 사례를 정리했고, `dldusgh318`은 `BAAI/bge-m3`로 임베딩해 pgvector에 저장한 측정 기록을 남겼습니다. [C1][C3][C5]  
> 하지만 이 둘 모두 **파인튜닝 여부**와 **검색 성능 비교 결과**는 근거에 없습니다. [C1][C3][C5][C6][C8]

<details><summary>판정 ✅</summary>

시스템은 멤버가 직접 파인튜닝해 검색 성능을 비교한 근거가 없다고 답해 gold의 핵심 결론과 일치한다. 추가로 언급한 sese2204의 임베딩 모델 비교와 dldusgh318의 bge-m3 사용은 파인튜닝 주장이 아니므로 gold와 모순되지 않는다.

</details>

### v2 · GraphRAG

<sub>경로 `aggregate→local` · 진입 엔티티 임베딩 · Cypher 결과 0행</sub>

> 근거 없음입니다. [C1][C2][C3][C4][C5]  
> 제공된 근거에는 임베딩 모델이나 LLM을 **직접 파인튜닝해서 검색 성능을 비교했다**는 내용이 없고, 검색 방식 비교나 벤치마크/실험만 있습니다. [G1][G2][G3][G4][G5][G6][G8][G11][G14]  
> 따라서 누가 그런 비교를 했는지, 그리고 멤버 github id가 누구인지 확인할 수 없습니다. [C1][C5]  
> 정리된 근거만 보면 `sese2204`, `dldusgh318`, `lys0611`, `Yeongeunn`, `do-dop`, `e0ng`, `jjinthung`, `sunghyun` 등이 검색 실험을 했지만, 파인튜닝 여부는 확인되지 않습니다. [G1][G2][G4][G5][G6][G7][G8][G9][G10][G11][G12][G13][G14]

<details><summary>생성된 Cypher</summary>

```cypher
MATCH (m:Member)-[:REPORTED]->(f:Finding)-[:ABOUT]->(t:Technique)
WHERE m.cohort = 10
  AND f.kind = 'measured'
  AND (
    t.name = '임베딩'
    OR t.name = 'RAG'
    OR t.name = '하이브리드 검색'
    OR t.name = '리랭커'
    OR t.name = '쿼리 재작성'
    OR t.name = 'Text2Cypher'
    OR t.name = 'GraphRAG'
  )
  AND (
    toLower(f.claim) CONTAINS '파인튜닝'
    OR toLower(f.claim) CONTAINS 'fine-tun'
    OR toLower(f.claim) CONTAINS 'finetun'
    OR toLower(f.evidence) CONTAINS '파인튜닝'
    OR toLower(f.evidence) CONTAINS 'fine-tun'
    OR toLower(f.evidence) CONTAINS 'finetun'
  )
WITH DISTINCT m
RETURN m.id AS member
ORDER BY member LIMIT 50
```

</details>

<details><summary>판정 ✅</summary>

시스템 답이 '근거 없음'이라고 했고, 멤버가 직접 파인튜닝해 검색 성능을 비교했다는 기록이 없다는 gold 결론과 일치한다. 검색 실험을 한 멤버를 나열했지만 파인튜닝 여부는 확인되지 않는다고 분명히 밝혀서 누군가를 지목한 것은 아니다.

</details>

### v3 · LLM 위키

<sub>검색된 위키 페이지: [[임베딩-모델-선택]], [[임베딩과-벡터-검색]], [[실습-비교표]]</sub>

> 근거로 확인되는 10기 멤버는 **lys0611**뿐입니다. [W2][W5]  
> lys0611은 `nlpai-lab/KURE-v1`을 **bge-m3를 한국어 query-document 약 200만 쌍으로 파인튜닝한 모델**로 써서, 자기 코퍼스에서 검색 성능을 측정했습니다. [W1][W5][W7]  
> 다만 이 근거에는 **LLM을 직접 파인튜닝했다**는 사례는 없고, 임베딩 모델 비교도 “같은 데이터에서 모델끼리 비교한 멤버는 없다”고 되어 있습니다. [W2][W4]  
> 즉, **파인튜닝된 임베딩 모델을 사용해 검색 성능을 비교한 사람은 lys0611**이고, **직접 파인튜닝한 LLM 비교는 근거 없음**입니다. [W1][W2][W5]

<details><summary>판정 ❌ ⚠</summary>

gold는 멤버가 직접 파인튜닝해 검색 성능을 비교한 기록이 없다는 것인데, 시스템은 lys0611을 지목하며 파인튜닝된 임베딩 모델로 검색 성능을 비교한 사람이라고 답했다. 이는 gold와 모순되고 근거 없는 주장이다. 다만 LLM 직접 파인튜닝 근거가 없다고 한 부분은 맞다.

</details>
