---
incident_id: INC-002
title: etcd 디스크 지연으로 반복된 리더 선출과 API timeout
date: 2026-01-21
category: control-plane
systems: [kubernetes, etcd, storage]
severity: critical
status: resolved
synthetic: true
tags: [etcd, wal, fsync, leader-election, timeout, disk-latency]
---

# etcd 디스크 지연으로 반복된 리더 선출과 API timeout

## 요약

클러스터 전체에서 `kubectl get` 요청이 간헐적으로 5~10초씩 멈추고 etcd leader가 짧은 시간에 여러 번 변경됐다. etcd가 사용하는 디스크에서 WAL fsync 지연이 급증한 것이 확인됐다.

## 환경

- control-plane 및 etcd: 3대
- etcd 데이터 디스크: 다른 로그 워크로드와 공유
- 영향 범위: 모든 API endpoint

## 증상

- `failed to send out heartbeat on time`
- `timed out waiting for read index response`
- `etcdserver: leader changed`
- API Server 프로세스는 살아 있지만 읽기·쓰기 요청이 간헐적으로 지연됨

## 확인 내용

- `etcd_disk_wal_fsync_duration_seconds`의 p99가 평시보다 크게 증가했다.
- 같은 시간에 로그 압축 작업이 동일 디스크의 I/O를 점유했다.
- 특정 노드가 아니라 세 API endpoint 모두 영향을 받았다.
- 네트워크 packet loss와 CPU saturation은 관찰되지 않았다.

## 확정 원인

공유 디스크의 I/O 경합으로 etcd가 Raft 로그를 제시간에 영속화하지 못했다. heartbeat가 지연되면서 불필요한 leader election과 요청 timeout이 발생했다.

## 조치

- 로그 압축 작업 중지
- etcd 데이터 디스크를 전용 볼륨으로 분리
- etcd endpoint health와 WAL fsync 지연 정상화 확인

## 재발 방지

- WAL fsync p99와 backend commit 지연 경보 설정
- etcd 디스크에 대규모 로그·백업 작업을 함께 배치하지 않음
- election timeout 조정보다 먼저 디스크·CPU·네트워크 병목을 제거

## 공개 참고자료

- https://etcd.io/docs/v3.1/faq/
- https://etcd.io/docs/v3.8/tuning/
- https://github.com/etcd-io/etcd/issues/14027

