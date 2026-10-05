---
incident_id: INC-007
title: 메모리 압박으로 종료된 단일 API Server
date: 2026-03-17
category: control-plane
systems: [kubernetes, kube-apiserver, linux, memory]
severity: high
status: resolved
synthetic: true
tags: [apiserver, oomkilled, exit-137, memory-pressure, static-pod]
---

# 메모리 압박으로 종료된 단일 API Server

## 요약

`cp-01`의 kube-apiserver가 종료 코드 137로 재시작됐다. 같은 시각 etcd leader 변경 로그가 한 번 있었지만, 컨테이너와 커널 로그에서 메모리 부족 종료가 확인됐다.

## 증상

- `cp-01` API Server restart count 증가
- 종료 코드 `137`
- 커널 로그에 OOM kill 기록
- 나머지 API Server 두 대는 정상
- 재시작 시점에 etcd client 요청 timeout 일부 발생

## 확인 내용

- 감사 로그 처리량 증가와 다른 관리 프로세스의 메모리 사용이 겹쳤다.
- etcd leader 변경은 API Server 종료 전후에 관찰됐지만 직접 종료 원인은 아니었다.
- kubelet이 static Pod를 자동으로 다시 시작했다.

## 확정 원인

control-plane 노드의 메모리 압박으로 kube-apiserver 컨테이너가 OOM 종료됐다.

## 조치

- 비필수 관리 프로세스 중지
- API Server 메모리 사용과 감사 로그 설정 확인
- 종료된 컨테이너 로그와 커널 OOM 기록 보존

## 재발 방지

- control-plane 전용 자원 확보
- node memory pressure와 API Server RSS 경보 설정
- 종료 코드와 커널 이벤트를 장애 타임라인에 자동 수집

## 공개 참고자료

- https://kubernetes.io/docs/concepts/workloads/pods/static-pods/
- https://github.com/kubernetes/kubernetes/issues/127114

