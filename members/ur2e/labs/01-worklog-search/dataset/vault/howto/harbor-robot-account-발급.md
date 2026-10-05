---
title: Harbor robot account 발급하고 imagePullSecret 넣기
tags: [harbor, registry, kubernetes, secret]
---

Harbor UI → 프로젝트 → Robot Accounts → NEW ROBOT ACCOUNT.

이름은 `robot$<project>+<용도>` 형태로 나온다. 토큰은 **발급 화면에서만 보인다.** 놓치면 재발급.

만료기간 기본값이 있어서 그냥 두면 언젠가 터진다. 실제로 터졌다 → [[INC-009-harbor-imagepullbackoff]]

시크릿 생성:

```bash
kubectl create secret docker-registry harbor-pull \
  --docker-server=harbor.internal \
  --docker-username='robot$myproj+pull' \
  --docker-password='<token>' \
  -n myns
```

username 에 `$` 가 들어가니 반드시 싱글쿼트. 더블쿼트로 감싸서 셸이 변수로 먹은 적 있다.

Pod 쪽:

```yaml
spec:
  imagePullSecrets:
    - name: harbor-pull
```

확인은 `kubectl describe pod` 의 Events. 401 이면 토큰, 404 면 이미지 경로 문제.
