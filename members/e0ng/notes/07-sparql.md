---
title: SPARQL 맛보기
date: 2026-09-27
tags: [sparql, wikidata, rdf]
status: in-progress
---

## SPARQL 맛보기

### SPARQL

그래프 데이터를 조회하는 질의 언어

**트리플**(주어 – 술어 – 목적어)로 이루어진 그래프에서 패턴을 찾는 언어

> 트리플 패턴에서 빈칸을 뚫어놓고, 
”그 빈칸에 들어갈 수 있는 값을 다 찾아줘"
> 
1. 변수는 `?`로 시작한다. `?country`
2. 트리플 패턴은 `주어 술어 목적어 .`로 쓰고 끝에 마침표를 찍는다
3. 같은 주어를 이어 쓸 때는 `;`를 쓴다. `?c a :Country ; :population ?p .`
4. 조건은 `FILTER(?p > 1000000)`, 
없을 수도 있는 값은 `OPTIONAL { … }`로 쓴다.

```sql
PREFIX : <http://example.org/>   # (선택) 긴 주소의 줄임말 선언
SELECT ?country                  # 무엇을 보여줄지[변수]
WHERE {                          # 어떤 패턴을 만족하는 것을 찾을지
  :Seoul :capitalOf ?country .   # 트리플 패턴 (끝에 마침표)
}
LIMIT 10                         # (선택) 개수 제한, ORDER BY 등도 여기
```

### 실제 테스트

> 
> 
> 
> query.wikidata.org
> 
- 한국의 수도

```sql
SELECT ?capitalLabel 
WHERE {
  wd:Q884 wdt:P36 ?capital.                      # 대한민국(Q884) – 수도(P36) – ?
  SERVICE wikibase:label {                       # Wikidata가 제공하는 "이름 붙여주기" 서비스를 호출한다
    bd:serviceParam wikibase:language "ko,en".   # 이름 언어 우선순위: 한국어 → 없으면 영어
  }                                             
}                                                
```

!스크린샷 2026-09-26 오후 8.09.13.png

- 봉준호 감독의 영화

```sql
SELECT DISTINCT ?filmLabel WHERE {   # DISTINCT = 중복 제거
  ?film wdt:P57 wd:Q495980.          # 감독(P57) = 봉준호
  SERVICE wikibase:label { bd:serviceParam wikibase:language "ko,en". }
} LIMIT 5
```

!스크린샷 2026-09-26 오후 8.13.40.png

- **봉준호 감독 영화에 가장 많이 나온 배우는?** 
** 다른 쿼리에 비해 시간이 더 많이 걸림

```sql
SELECT ?actorLabel (COUNT(?film) AS ?n) WHERE {
  ?film wdt:P57  wd:Q495980;         # 봉준호가 감독한 영화
        wdt:P161 ?actor.             # 그 영화의 출연진(P161)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "ko,en". }
} GROUP BY ?actorLabel               # 배우별로 묶어서
  ORDER BY DESC(?n) LIMIT 5          # 출연 편수 많은 순
```

!스크린샷 2026-09-26 오후 8.14.41.png

