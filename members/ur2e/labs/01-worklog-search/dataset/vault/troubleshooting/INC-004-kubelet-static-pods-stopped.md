---
incident_id: INC-004
title: kubelet 중단으로 사라진 control-plane static Pod
date: 2026-02-12
category: control-plane
systems: [kubernetes, kubelet, containerd, kube-apiserver, etcd]
severity: high
status: resolved
synthetic: true
tags: [kubelet, static-pod, apiserver, etcd, container-runtime]
---

# kubelet 중단으로 사라진 control-plane static Pod

## 요약

`cp-03`에서 API Server와 etcd 컨테이너가 동시에 사라졌다. 클러스터의 나머지 두 control-plane 노드는 정상 작동했고 etcd quorum도 유지됐다. 해당 노드의 kubelet이 설정 오류로 시작하지 못한 것이 원인이었다.

## 증상

- `cp-03`의 `kube-apiserver`, `etcd`, `kube-scheduler` 컨테이너가 모두 없음
- `/etc/kubernetes/manifests`에는 manifest 파일이 남아 있음
- `systemctl status kubelet`이 failed 상태
- containerd는 실행 중

## 확인 내용

- kubeadm control-plane 구성 요소는 kubelet이 관리하는 static Pod였다.
- kubelet 설정 파일의 잘못된 YAML 들여쓰기 때문에 서비스가 시작되지 않았다.
- API Server 자체 로그가 새로 생성되지 않은 이유는 컨테이너가 시작되지 않았기 때문이다.

## 확정 원인

노드 설정 자동화 중 kubelet 구성 파일이 잘못 덮어써져 static Pod 관리가 중단됐다.

## 조치

- kubelet 구성 복원 및 설정 검증
- kubelet 재시작
- static Pod와 mirror Pod가 모두 복원되는지 확인

## 재발 방지

- kubelet 설정 배포 전 구문 검증
- control-plane 변경을 한 대씩 적용
- kubelet 중단과 핵심 static Pod 부재를 별도로 경보

## 공개 참고자료

- https://kubernetes.io/docs/concepts/workloads/pods/static-pods/
- https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/setup-ha-etcd-with-kubeadm/

