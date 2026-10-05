---
date: 2026-01-28
status: decided
tags: [registry, harbor, nexus, decision]
---

# 컨테이너 이미지는 Harbor, 일반 artifact 는 Nexus 로 간다

## 배경

컨테이너 이미지와 jar/npm artifact 를 한 곳에서 관리하자는 얘기가 나왔다. 둘 다 이미 떠 있는 상태였고, 하나로 합치면 운영 대상이 줄어든다는 게 제안 이유였다.

## 후보

- Harbor 하나로 통합
- Nexus 하나로 통합
- 지금처럼 둘 다 유지 (이미지 = Harbor, artifact = Nexus)

## 판단 근거

Harbor 로 통합:

- 이미지 스캔, 서명, 프로젝트별 robot account 같은 게 이미 붙어 있어서 이미지 쪽은 확실히 낫다.
- 일반 artifact(maven, npm) 지원은 약하다. 결국 별도 도구가 또 필요해진다.

Nexus 로 통합:

- artifact 포맷 지원은 넓다.
- 이미지 취약점 스캔과 프로젝트 단위 권한 모델이 Harbor 만큼 안 나온다. 이미지 권한을 세밀하게 못 나누면 지금 쓰는 배포 흐름을 바꿔야 한다.

## 결정

**둘 다 유지한다.** 통합해서 줄어드는 운영 부담보다, 각각에서 잃는 기능이 크다고 봤다.

## 대신 감수하는 것

- 인증 정보가 두 군데로 나뉜다. 두 시스템 모두 토큰 만료로 사고를 한 번씩 냈다. → [[INC-009-harbor-imagepullbackoff]], [[INC-011-nexus-upload-401]]
- 그래서 토큰 만료 알람은 두 시스템 다 걸어야 한다는 게 이 결정의 전제 조건이다.

## 재검토 조건

- Nexus 쪽 이미지 권한 모델이 개선되면
- 또는 artifact 사용량이 거의 없어져서 Nexus 자체가 필요 없어지면
