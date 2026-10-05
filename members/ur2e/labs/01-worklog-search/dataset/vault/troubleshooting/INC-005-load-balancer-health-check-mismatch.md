---
incident_id: INC-005
title: 정상 API Server가 load balancer에서 제외된 장애
date: 2026-02-20
category: control-plane
systems: [kubernetes, kube-apiserver, load-balancer, security-group]
severity: medium
status: resolved
synthetic: true
tags: [apiserver, load-balancer, health-check, port, network]
---

# 정상 API Server가 load balancer에서 제외된 장애

## 요약

`cp-02`의 API Server는 로컬에서 `/readyz` 요청에 성공했지만 load balancer 대상 상태는 unhealthy였다. etcd와 API Server 프로세스에는 장애가 없었다.

## 증상

- `curl -k https://127.0.0.1:6443/readyz` 성공
- load balancer에서는 `cp-02`만 unhealthy
- 다른 두 control-plane을 통한 kubectl 요청은 정상
- API Server restart count 변화 없음

## 확인 내용

- load balancer health check 포트가 `6443`이 아닌 이전 테스트 포트로 남아 있었다.
- 네트워크 보안 규칙도 새 health check source를 허용하지 않았다.
- 노드 로컬 접근과 load balancer 경유 접근의 결과가 달랐다.

## 확정 원인

load balancer 대상 그룹의 health check 설정과 네트워크 허용 범위가 실제 API Server endpoint와 일치하지 않았다.

## 조치

- health check를 API Server의 실제 포트와 프로토콜에 맞춤
- health check source의 접근 허용
- 세 endpoint의 직접 연결과 load balancer 연결을 각각 검증

## 재발 방지

- API Server 변경 후 load balancer endpoint 검증 자동화
- 프로세스 상태와 트래픽 경로 상태를 분리해 모니터링

## 공개 참고자료

- https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/high-availability/

