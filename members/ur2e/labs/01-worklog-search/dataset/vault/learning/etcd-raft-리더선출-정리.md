# etcd raft 리더 선출 정리

[[INC-001-etcd-election-single-apiserver-stop]] 대응하면서 "리더 선출"을 제대로 모른다는 걸 깨달아서 정리.

## 세 가지 상태

- follower: 기본 상태. 리더에게서 heartbeat 를 받는다.
- candidate: election timeout 동안 heartbeat 를 못 받으면 스스로 전환. 다른 멤버에게 투표를 요청한다.
- leader: 과반 투표를 받으면 리더. 이후 heartbeat 를 계속 보낸다.

## 선출이 일어나는 조건

election timeout 안에 리더 heartbeat 가 도착하지 않으면 선출이 시작된다. 리더가 죽어서만 일어나는 게 아니라는 점이 중요하다.

- 리더 프로세스 종료
- peer 간 네트워크 지연
- 리더 쪽 디스크가 느려서 heartbeat 를 제때 못 보냄 → [[INC-002-etcd-disk-latency-cluster-timeout]]
- CPU starvation 으로 goroutine 이 못 돌아감

즉 **선출 발생 자체는 원인이 아니라 증상일 수 있다.** 이걸 몰라서 처음에 리더 변경을 원인으로 착각했다.

## quorum

3 멤버면 과반은 2. 하나 죽어도 동작하고 둘 죽으면 쓰기가 멈춘다. 그래서 짝수 멤버는 이득이 없다 — 4 멤버의 과반은 3 이라 여전히 하나만 감당한다.

## 왜 fsync 가 중요한가

raft 는 로그 엔트리를 디스크에 확실히 쓴 뒤에 응답한다. 그래서 WAL fsync 지연이 곧 쓰기 지연이고, 심하면 heartbeat 까지 밀려 선출로 이어진다. etcd 가 디스크 성능에 민감한 이유.

`etcd_disk_wal_fsync_duration_seconds` 를 먼저 본다.

## learner

새 멤버를 바로 voter 로 넣으면 따라잡는 동안 quorum 계산에 들어가서 위험하다. learner 로 붙여 로그를 따라잡은 뒤 승격하는 게 안전하다. 승격 조건을 못 맞춰서 실패한 적 있다 → [[INC-006-control-plane-join-etcd-learner]]

## 참고

- https://raft.github.io/
- https://etcd.io/docs/latest/learning/design-learner/
