---
incident_id: INC-003
title: API Server의 etcd client 인증서 만료
date: 2026-02-03
category: control-plane
systems: [kubernetes, kube-apiserver, etcd, pki]
severity: high
status: resolved
synthetic: true
tags: [apiserver, etcd, certificate, x509, tls]
---

# API Server의 etcd client 인증서 만료

## 요약

`cp-03`의 API Server가 시작되지 않았고 로그에 etcd TLS 인증 실패가 반복됐다. 해당 노드의 `apiserver-etcd-client` 인증서만 만료되어 있었다. etcd leader 변경은 없었다.

## 증상

- `x509: certificate has expired or is not yet valid`
- `cp-03:6443` 연결 실패
- 다른 control-plane API endpoint는 정상
- etcd cluster health와 quorum은 정상

## 확인 내용

- 노드 시간은 정상적으로 동기화되어 있었다.
- `/etc/kubernetes/pki/apiserver-etcd-client.crt`의 유효기간이 지났다.
- API Server manifest의 인증서 경로는 올바르게 설정되어 있었다.

## 확정 원인

인증서 갱신 작업에서 `cp-03`이 누락되어 API Server가 로컬 etcd에 인증할 수 없었다.

## 조치

- kubeadm 인증서 상태 확인
- 승인된 절차로 API Server의 etcd client 인증서 갱신
- static Pod가 새 인증서를 읽도록 재시작 후 `/readyz` 확인

## 재발 방지

- control-plane 모든 노드의 인증서 만료일을 한 번에 점검
- 만료 60일·30일 전 경보 설정
- 갱신 작업 완료 조건에 노드별 API endpoint 검증 포함

## 공개 참고자료

- https://kubernetes.io/docs/tasks/administer-cluster/kubeadm/kubeadm-certs/
- https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/high-availability/

