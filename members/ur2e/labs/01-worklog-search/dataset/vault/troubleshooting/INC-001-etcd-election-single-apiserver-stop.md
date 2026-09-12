---
incident_id: INC-001
title: etcd 리더 변경 직후 특정 API Server 일시 중단
date: 2026-01-14
category: control-plane
systems: [kubernetes, kube-apiserver, etcd, kubelet]
severity: high
status: cause-unconfirmed
synthetic: true
tags: [control-plane, etcd, leader-election, apiserver, static-pod]
---

# etcd 리더 변경 직후 특정 API Server 일시 중단

## 요약

3대의 control-plane 노드로 구성된 stacked etcd 클러스터에서 etcd 리더 선출이 한 번 발생했다. 약 40초 뒤 `cp-02`의 `kube-apiserver`만 응답하지 않았고 로드밸런서 대상에서도 제외되었다. `cp-01`, `cp-03`의 API Server는 요청을 계속 처리했다. `cp-02`의 kubelet이 static Pod를 다시 시작하면서 서비스는 복구됐다.

리더 변경과 API Server 종료가 가까운 시간에 발생했지만, 이 기록만으로 둘의 인과관계는 확정하지 않았다.

## 환경

- Kubernetes: kubeadm 기반 HA 클러스터
- control-plane: `cp-01`, `cp-02`, `cp-03`
- etcd: control-plane과 함께 배치된 3-member stacked topology
- API 진입점: 3대 API Server를 대상으로 하는 TCP load balancer

## 증상

- etcd 로그에 candidate 전환과 새 leader 선출이 한 차례 기록됨
- 직후 일부 API 요청에서 `etcdserver: leader changed`와 timeout 발생
- `cp-02:6443` 연결 실패, 다른 두 endpoint는 정상
- `cp-02`의 kube-apiserver 컨테이너가 한 번 종료된 뒤 재생성됨
- 워커의 기존 Pod에는 직접적인 중단이 관찰되지 않음

## 타임라인

1. 14:02:11 — etcd heartbeat 지연 경고
2. 14:02:13 — follower가 candidate로 전환
3. 14:02:14 — 새 leader 선출 완료
4. 14:02:51 — `cp-02` API Server health check 실패
5. 14:03:29 — kubelet이 API Server static Pod 재시작
6. 14:03:34 — load balancer 대상 정상 복귀

## 확인 내용

- etcd quorum은 유지됐고 리더 선출은 한 번만 발생했다.
- 장애 범위는 `cp-02` 한 대에 집중됐다.
- API Server 종료 직전 로그와 컨테이너 종료 사유는 보존되지 않아 OOM, probe 실패, 프로세스 panic을 구분하지 못했다.
- 같은 시각의 etcd WAL 지연, 노드 CPU steal, 네트워크 loss 지표도 수집되지 않았다.

## 판단

현재 상태는 `원인 미확정`이다. 리더 선출은 관찰된 선행 이벤트이며 확정 원인이 아니다. stacked topology에서는 영향 노드의 로컬 etcd 연결, kubelet, container runtime, 메모리와 디스크 상태를 우선 확인한다.

## 조치

- 세 etcd endpoint의 health와 member status를 확인
- `cp-02`의 kubelet journal과 종료된 컨테이너 로그 수집
- load balancer에서 나머지 두 API Server가 정상인지 확인
- 클러스터 쓰기 작업을 잠시 줄이고 재선출 여부 관찰

## 재발 방지

- API Server와 etcd 컨테이너의 이전 종료 로그 보존
- etcd leader change, WAL fsync, peer RTT, API Server restart count를 같은 대시보드에 배치
- control-plane 노드별 메모리 압박과 디스크 지연 경보 추가
- 이벤트의 시간적 인접성과 인과관계를 구분하는 장애 기록 양식 사용

## 공개 참고자료

- https://github.com/kubernetes/kubeadm/issues/2927
- https://github.com/kubernetes/kubernetes/issues/127114
- https://github.com/etcd-io/etcd/issues/14027
- https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/ha-topology/
- https://kubernetes.io/docs/concepts/workloads/pods/static-pods/

