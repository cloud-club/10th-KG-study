---
incident_id: INC-011
title: Jenkins에서 Nexus artifact 업로드 시 발생한 401
date: 2026-04-19
category: registry
systems: [jenkins, nexus, maven]
severity: medium
status: resolved
synthetic: true
tags: [nexus, jenkins, artifact, unauthorized, credential]
---

# Jenkins에서 Nexus artifact 업로드 시 발생한 401

## 요약

개발자 로컬 환경에서는 artifact 업로드가 성공했지만 Jenkins pipeline에서는 Nexus가 401 Unauthorized를 반환했다.

## 증상

- compile과 test 단계 성공
- deploy 단계에서 HTTP 401
- Nexus 서비스와 저장소 browse는 정상
- 로컬의 개인 계정으로는 동일 artifact 업로드 성공

## 확인 내용

- Jenkins credential ID는 존재했지만 pipeline의 환경 변수 이름과 일치하지 않았다.
- 익명 접근은 read만 허용됐고 deployment 저장소에는 write 권한이 필요했다.
- repository URL과 artifact 좌표는 정상적이었다.

## 확정 원인

pipeline이 Jenkins credential을 주입받지 못해 인증 없이 Nexus deployment endpoint를 호출했다.

## 조치

- Jenkins credential binding 이름 수정
- 최소 권한을 가진 CI 전용 계정으로 업로드 재검증
- 비밀값이 console log에 출력되지 않는지 확인

## 재발 방지

- pipeline lint와 credential ID 사전 검사
- 로컬 개인 계정이 아닌 CI 계정으로 smoke test
- 401, 403, repository path 오류를 구분해 기록

## 공개 참고자료

- https://help.sonatype.com/en/configure-oci-repository.html
- https://velog.io/tags/nexus

