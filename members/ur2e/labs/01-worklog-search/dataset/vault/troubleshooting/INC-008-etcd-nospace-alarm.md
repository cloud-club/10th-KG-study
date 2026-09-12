---
incident_id: INC-008
title: etcd NOSPACE alarm으로 중단된 리소스 변경
date: 2026-03-25
category: control-plane
systems: [kubernetes, etcd, storage]
severity: critical
status: resolved
synthetic: true
tags: [etcd, nospace, quota, compaction, defrag]
---

# etcd NOSPACE alarm으로 중단된 리소스 변경

## 요약

조회 요청은 일부 성공했지만 Deployment 변경과 Lease 갱신이 실패했다. etcd 로그에서 `mvcc: database space exceeded`와 NOSPACE alarm이 확인됐다. leader election이나 특정 API Server 종료는 없었다.

## 증상

- 새 리소스 생성과 기존 리소스 갱신 실패
- API 응답에 `etcdserver: mvcc: database space exceeded`
- etcd endpoint status의 DB 크기가 quota에 근접
- 세 API Server 프로세스는 실행 중

## 확정 원인

이벤트와 이전 revision이 누적되어 etcd backend가 설정된 공간 quota를 초과했다.

## 조치

- snapshot 백업과 endpoint 상태 확인
- 보존 가능한 revision을 기준으로 compaction 수행
- member별 defrag 수행
- DB 크기 감소 확인 후 NOSPACE alarm 해제

## 재발 방지

- DB 사용량과 quota 비율 경보 설정
- 정기 compaction 정책 검토
- 이벤트를 과도하게 생성하는 controller 탐지

## 공개 참고자료

- https://etcd.io/docs/v3.5/op-guide/maintenance/
- https://etcd.io/docs/v3.3/faq/

