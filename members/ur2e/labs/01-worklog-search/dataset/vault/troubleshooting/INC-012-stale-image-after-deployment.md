---
incident_id: INC-012
title: 배포 성공 후 일부 Pod에 남은 이전 이미지
date: 2026-04-27
category: cicd
systems: [jenkins, kubernetes, harbor]
severity: high
status: resolved
synthetic: true
tags: [deployment, image-tag, digest, imagepullpolicy, stale-image]
---

# 배포 성공 후 일부 Pod에 남은 이전 이미지

## 요약

Jenkins pipeline과 Kubernetes rollout은 성공으로 표시됐지만 노드별 Pod의 응답 버전이 달랐다. 동일한 `release` 태그를 다시 사용했고 일부 노드는 기존 이미지를 재사용했다.

## 증상

- Deployment rollout status 성공
- Pod spec의 image 문자열은 모두 동일
- 애플리케이션 version endpoint는 일부 Pod에서 이전 commit 표시
- Pod별 `imageID` digest가 서로 다름

## 확인 내용

- Harbor의 `release` 태그가 새 digest를 가리키도록 덮어써졌다.
- workload의 `imagePullPolicy`는 `IfNotPresent`였다.
- 기존 digest가 남아 있는 노드에서 이전 이미지가 사용됐다.

## 확정 원인

변경 가능한 태그를 재사용하면서 이미지 pull 정책이 로컬 캐시 사용을 허용해, 같은 태그 아래 서로 다른 digest가 실행됐다.

## 조치

- commit SHA 기반의 새 이미지 태그로 다시 배포
- 모든 Pod의 `imageID` digest 일치 확인

## 재발 방지

- 배포 이미지에 불변 태그 또는 digest 사용
- pipeline 완료 조건에 실제 실행 digest 검증 포함
- 같은 환경에서 release 태그 덮어쓰기 금지

## 공개 참고자료

- https://kubernetes.io/docs/concepts/containers/images/
- https://goharbor.io/docs/main/working-with-projects/working-with-images/
