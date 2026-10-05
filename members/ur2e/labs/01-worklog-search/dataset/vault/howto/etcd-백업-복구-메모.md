---
title: etcd 스냅샷 백업과 복구 메모
tags: [etcd, backup, snapshot, runbook]
---

# etcd 스냅샷 백업과 복구 메모

## 백업

```bash
ETCDCTL_API=3 etcdctl snapshot save /var/backups/etcd-$(date +%F).db \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key
```

## 상태 확인

```bash
etcdctl endpoint status --write-out=table --cluster
etcdctl endpoint health --cluster
etcdctl alarm list
```

`alarm list` 에 NOSPACE 가 떠 있으면 리소스 변경이 전부 막힌다. compaction → defrag → `alarm disarm` 순서로 풀었다. → [[INC-008-etcd-nospace-alarm]]

```bash
etcdctl compact <revision>
etcdctl defrag --cluster
etcdctl alarm disarm
```

defrag 는 멤버별로 순차로. 동시에 걸면 quorum 흔들린다.

## 복구

복구는 실제로 해본 적 없다. 절차만 적어둔다. 검증 안 됨 주의.

```bash
etcdctl snapshot restore /var/backups/etcd-2026-03-25.db \
  --data-dir=/var/lib/etcd-restored
```

- 전체 멤버를 멈추고 같은 스냅샷으로 각각 복구해야 한다.
- 복구 후 멤버 peer 주소가 예전 값으로 남는 문제가 있다고 한다. 다음에 테스트 클러스터에서 한 번 해봐야 함. #todo
