---
incident_id: INC-006
title: control-plane 합류 중 etcd learner 승격 실패
date: 2026-03-04
category: control-plane
systems: [kubernetes, kubeadm, etcd, kube-apiserver]
severity: high
status: resolved
synthetic: true
tags: [kubeadm, control-plane-join, etcd, learner, crashloopbackoff]
---

# control-plane 합류 중 etcd learner 승격 실패

## 요약

세 번째 control-plane 노드를 추가하는 과정에서 새 etcd member가 leader의 로그를 충분히 따라잡지 못했다. learner 승격이 거부됐고 새 노드의 API Server가 CrashLoopBackOff 상태가 됐다.

## 증상

- `can only promote a learner member which is in sync with leader`
- 새 노드의 etcd health check 실패
- 새 노드의 kube-apiserver CrashLoopBackOff
- 기존 두 control-plane을 통한 API 요청은 정상

## 확인 내용

- 기존 etcd quorum은 유지됐다.
- 실패한 join 시도에서 생성된 member 정보와 static Pod manifest가 남아 있었다.
- 새 노드와 기존 leader 사이의 복제 지연이 컸다.

## 확정 원인

새 etcd learner가 leader와 동기화되기 전에 승격 단계가 진행됐고, 불완전한 join 상태가 남았다.

## 조치

- 기존 endpoint health와 member list 확인
- 실패한 member를 승인된 복구 절차에 따라 정리
- 네트워크와 디스크 상태를 확인한 뒤 control-plane을 한 대씩 다시 합류

## 재발 방지

- join 전 peer 포트 연결과 시간 동기화 확인
- control-plane 동시 추가 금지
- learner 동기화 상태를 완료 조건에 포함

## 공개 참고자료

- https://github.com/kubernetes/kubeadm/issues/2997
- https://github.com/kubernetes/kubernetes/issues/102715
- https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/high-availability/

