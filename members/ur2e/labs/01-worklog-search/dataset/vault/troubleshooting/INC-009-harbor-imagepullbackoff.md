---
incident_id: INC-009
title: 만료된 Harbor robot account로 발생한 ImagePullBackOff
date: 2026-04-02
category: workload
systems: [kubernetes, harbor, containerd]
severity: medium
status: resolved
synthetic: true
tags: [harbor, imagepullbackoff, imagepullsecret, robot-account, registry]
---

# 만료된 Harbor robot account로 발생한 ImagePullBackOff

## 요약

신규 Pod가 사설 Harbor에서 이미지를 내려받지 못하고 `ImagePullBackOff` 상태에 머물렀다. 기존 Pod는 노드에 캐시된 이미지로 계속 실행됐다.

## 증상

- Pod event에 registry `unauthorized` 기록
- 이미지와 태그는 Harbor에 존재
- 다른 namespace에서는 같은 이미지를 정상적으로 pull
- 장애 namespace의 `imagePullSecret`만 오래된 상태

## 확인 내용

- Secret은 Pod와 같은 namespace에 존재했다.
- Secret에 저장된 robot account secret이 갱신 전 값이었다.
- robot account의 기존 secret은 만료됐고 새 secret이 Jenkins에만 반영돼 있었다.

## 확정 원인

Harbor robot account secret 갱신 후 Kubernetes의 image pull Secret을 함께 갱신하지 않았다.

## 조치

- robot account의 pull 권한과 유효기간 확인
- 해당 namespace의 imagePullSecret 갱신
- 새 Pod를 만들어 image pull 성공 확인

## 재발 방지

- robot account 만료 전 경보
- credential 갱신 대상을 Jenkins와 Kubernetes로 함께 관리
- 배포 전 임시 Pod로 registry pull 검증

## 공개 참고자료

- https://kubernetes.io/docs/tasks/configure-pod-container/pull-image-private-registry/
- https://goharbor.io/docs/main/working-with-projects/project-configuration/create-robot-accounts/

