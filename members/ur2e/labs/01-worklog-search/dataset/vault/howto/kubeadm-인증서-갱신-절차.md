---
title: kubeadm control-plane 인증서 갱신 절차
tags: [kubernetes, kubeadm, certificate, runbook]
---

# kubeadm control-plane 인증서 갱신 절차

매번 검색해서 찾다가 시간 버려서 정리. [[INC-003-apiserver-etcd-tls-expiry]] 겪고 나서 만들었다.

## 만료일 먼저 확인

```bash
kubeadm certs check-expiration
openssl x509 -enddate -noout -in /etc/kubernetes/pki/apiserver-etcd-client.crt
```

`check-expiration` 은 그 노드 것만 보여준다. **control-plane 노드 전부 돌려야 한다.** 한 노드만 보고 끝내서 사고 났었다.

## 갱신

```bash
# 전체
kubeadm certs renew all

# 특정 인증서만
kubeadm certs renew apiserver-etcd-client
```

갱신해도 static Pod 는 파일을 다시 읽지 않는다. manifest 를 잠깐 빼서 재시작시키는 방식으로 처리했다.

```bash
mv /etc/kubernetes/manifests/kube-apiserver.yaml /tmp/
# Pod 사라진 것 확인 후
mv /tmp/kube-apiserver.yaml /etc/kubernetes/manifests/
```

## 확인

```bash
curl -k https://localhost:6443/readyz
kubectl get --raw='/readyz?verbose'
```

노드별로 각각 찍어봐야 한다. LB 뒤에서 보면 죽은 노드가 가려진다. ([[INC-005-load-balancer-health-check-mismatch]] 참고)

## 주의

- kubeconfig 안에 박힌 인증서도 같이 갱신 대상이다. `admin.conf` 갱신 후 로컬로 다시 복사하는 걸 잊지 말 것.
- 실제 운영 클러스터에서는 승인된 변경 절차를 먼저 밟아야 한다.
