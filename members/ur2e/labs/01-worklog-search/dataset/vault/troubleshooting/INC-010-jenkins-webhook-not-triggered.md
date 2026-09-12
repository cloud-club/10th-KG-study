---
incident_id: INC-010
title: Git push 이후 시작되지 않은 Jenkins pipeline
date: 2026-04-11
category: cicd
systems: [git, jenkins, webhook]
severity: medium
status: resolved
synthetic: true
tags: [jenkins, git, webhook, trigger, branch-filter]
---

# Git push 이후 시작되지 않은 Jenkins pipeline

## 요약

Git 저장소에는 새 commit이 올라갔지만 Jenkins job이 생성되지 않았고 build log도 없었다. 빌드 실패가 아니라 trigger 단계 이전의 문제였다.

## 증상

- Git push 성공
- Jenkins build history에 신규 실행 없음
- Jenkins controller와 agent는 정상
- 수동 Build Now는 성공

## 확인 내용

- Git webhook 전달 기록은 HTTP 200이었다.
- Jenkins Generic Webhook Trigger가 payload를 받았다.
- branch filter가 `main`만 허용했지만 실제 push branch는 `release`였다.
- 커밋 메시지 skip filter는 이번 사건과 무관했다.

## 확정 원인

Jenkins job의 branch 정규식이 release branch를 제외해 webhook을 받은 뒤 실행 조건에서 탈락했다.

## 조치

- branch filter에 승인된 release 패턴 추가
- 동일 payload로 dry-run 후 pipeline 실행 확인

## 재발 방지

- webhook 수신과 job trigger 결과를 별도 로그로 남김
- 신규 branch 정책 변경 시 Jenkins filter 테스트
- 실행 기록이 없으면 build log보다 webhook 경로를 먼저 확인

## 공개 참고자료

- https://velog.io/%40gyudong17/0730

