# RUNBOOK — lys0611 · MacBook (Apple Silicon, 16GB, macOS 26) · Colima

이 문서는 `README.md`의 일반 절차를 **이 노트북·이 레포·이 파일 두 개**에 맞게 줄인 실행표다.
경로는 전부 실제 값이다. 위에서 아래로 그대로 실행하면 된다. `#` 뒤는 설명.

```
레포      /Users/yeseung/dev/10th-KG-study
랩 폴더   /Users/yeseung/dev/10th-KG-study/members/lys0611/labs/01-ingest
원본      KakaoTalkChats_ㅇ.txt, KakaoTalkChats_팀리더단톡방.txt   (안드로이드 '텍스트만 보내기' 결과)
런타임    Colima (Docker 29.1.3, Compose 5.0.2) · Python 3.13.5 (python.org 설치판)
```

---

## 0. 파일 확인 — 2분

```bash
cd ~/Downloads                                   # 두 txt 가 있는 폴더로
ls -lh KakaoTalkChats_*.txt; wc -l KakaoTalkChats_*.txt
for f in KakaoTalkChats_*.txt; do echo "== $f"; head -n 4 "$f" | sed -E 's/^.* 님과/<방> 님과/; s/, [^:]+ :/, <이름> :/'; done
```

기대하는 모양 (안드로이드): `2024년 3월 2일 오후 7:12, <이름> : 메시지`. 다르게 보이면 이 출력을 그대로 공유.
`ㅇ` 파일이 어떤 방인지 정하고 `--room` 이름을 미리 정해 둔다. 아래에서는 예시로 `프로젝트팀`, `팀리더` 를 쓴다.

---

## 1. Colima 켜기 + 메모리 — 3분 (지금 데몬이 꺼져 있어서 socket 오류가 난 것)

```bash
colima version
colima list                                      # 인스턴스가 있는지, 메모리가 얼마인지
```

- **인스턴스가 없거나 지워도 되는 상태**라면 (권장):
  ```bash
  colima start --cpu 4 --memory 6 --disk 60 --vm-type vz --mount-type virtiofs
  ```
- **이미 인스턴스가 있고 그 안에 다른 데이터가 있다**면 vm-type 은 건드리지 말고 자원만 올린다:
  ```bash
  colima stop && colima start --cpu 4 --memory 6
  ```

기본값은 CPU 2·메모리 2GiB·디스크 60GiB 라서 그대로 두면 Elasticsearch 가 뜨다 죽는다. 디스크는 만든 뒤 바꿀 수 없지만 CPU·메모리는 stop 후 start 에 플래그로 바꿀 수 있다. 16GB 노트북에서 6GB 배정은 여유 있는 편.

```bash
docker info --format '{{.MemTotal}}' | awk '{printf "Docker VM mem: %.1f GB\n", $1/1073741824}'   # 6.0 GB 근처
docker run --rm hello-world | head -3
colima ssh -- sudo sysctl -w vm.max_map_count=1048576   # 선택. 재시작하면 풀리지만, 아래 compose 는 single-node 라 이 값이 낮아도 기동은 된다
```

---

## 2. 랩 폴더 만들고 프로젝트 배치 — 3분

```bash
cd /Users/yeseung/dev/10th-KG-study && git pull
mkdir -p members/lys0611/notes members/lys0611/labs
cd ~/Downloads && unzip -o kakao-kg-lab01.zip
mv ~/Downloads/kakao-kg-lab01 /Users/yeseung/dev/10th-KG-study/members/lys0611/labs/01-ingest
cd /Users/yeseung/dev/10th-KG-study/members/lys0611/labs/01-ingest
mv ~/Downloads/KakaoTalkChats_*.txt data/raw/
ls -a                                            # .gitignore 가 같이 들어왔는지 확인
git -C /Users/yeseung/dev/10th-KG-study check-ignore -v members/lys0611/labs/01-ingest/data/raw/KakaoTalkChats_팀리더단톡방.txt
# ↑ 무언가 출력되면(ignore 규칙에 매칭) 정상. 아무것도 안 나오면 멈추고 알려 줄 것.
```

레포 루트 `.gitignore` 는 `data/raw/` 만 막고, 랩 폴더 안의 `.gitignore` 가 `data/interim/`·`data/private/`·`.env` 를 막는다. 둘 다 있어야 실명 매핑표가 안 올라간다.

---

## 3. Python 환경 — 3분

```bash
cd /Users/yeseung/dev/10th-KG-study/members/lys0611/labs/01-ingest
python3 -m venv .venv && source .venv/bin/activate
python -V                                        # Python 3.13.5
pip install -r requirements.txt
cp .env.example .env
```

---

## 4. OpenAI API 키 — 5분 · **ChatGPT Plus 와 별개**

Plus 구독에는 API 사용이 포함되지 않는다. API 는 platform.openai.com 에서 따로 결제한다.

1. https://platform.openai.com 로그인 (ChatGPT 계정 그대로 가능) → Settings → **Billing** → Add payment details
2. 크레딧 구매: 최소 **$5** (기본 제안 $10). **Use auto-reload 는 끄기**(기본 켜짐). 크레딧은 1년 뒤 만료.
3. **API keys** → Create new secret key → 복사
4. Settings → Data controls 에서 "Sharing / complimentary tokens" 류 토글이 **꺼져 있는지** 확인(기본 꺼짐). 켜면 카톡 텍스트가 학습에 쓰인다.
5. `.env` 편집:
   ```
   EMBED_PROVIDER=openai
   EMBED_MODEL=text-embedding-3-small
   EMBED_DIM=1536
   OPENAI_API_KEY=sk-...
   ```

이번 랩 비용은 청크 수천 개 기준 몇십 원. W5 트리플 추출까지 합쳐도 $5 로 시즌을 넘길 가능성이 높다.

---

## 5. 인프라 — 첫 빌드 10~15분 (이미지 다운로드)

```bash
docker compose up -d --build
docker compose ps                                # 둘 다 (healthy) 가 될 때까지 1~2분
curl -s localhost:9200 | head -5
curl -s "localhost:9200/_cat/plugins?v"          # analysis-nori 9.5.3
docker exec -it kg-postgres psql -U kg -d kg -c "CREATE EXTENSION IF NOT EXISTS vector; SELECT extversion FROM pg_extension WHERE extname='vector';"
```

ES 가 `Exited` 면 `docker compose logs elasticsearch | tail -30`. 메모리 부족이면 1번으로 돌아가 `--memory 8`.

---

## 6. 파이프라인 실행 — 방 두 개 — 10~20분

`ㅇ` 방부터 작은 것으로 한 번 끝까지 돌려보고, 잘 되면 두 번째 방을 돌린다.

```bash
source .venv/bin/activate
./run_pipeline.sh "data/raw/KakaoTalkChats_ㅇ.txt" 프로젝트팀
./run_pipeline.sh "data/raw/KakaoTalkChats_팀리더단톡방.txt" 팀리더
```

한 단계씩 확인하며 가고 싶으면:

```bash
python src/parse_kakao.py "data/raw/KakaoTalkChats_팀리더단톡방.txt" --room 팀리더 --out data/interim/팀리더.jsonl
python src/pseudonymize.py data/interim/팀리더.jsonl --out data/interim/팀리더.masked.jsonl --map data/private/name_map.json
open -e data/private/name_map.json               # 가명 다듬기 (두 방에 같은 사람이 있으면 같은 가명이 유지된다)
python src/load_postgres.py data/interim/팀리더.masked.jsonl --room 팀리더
python src/embed.py --room 팀리더 --limit 20      # 키·차원 확인
python src/embed.py --room 팀리더
python src/index_es.py --analyze "배포 일정 다시 잡아야 할 것 같아"
python src/index_es.py
```

두 방을 **같은 name_map.json** 으로 가명화해야 한다. 팀 톡방과 리더 톡방에 겹치는 사람이 같은 가명을 받아야 뒤(W5)에서 사람 노드가 하나로 합쳐진다.

확인:

```bash
docker exec -it kg-postgres psql -U kg -d kg -c "SELECT r.name, count(*) FROM messages m JOIN rooms r ON r.id=m.room_id GROUP BY 1;"
docker exec -it kg-postgres psql -U kg -d kg -c "SELECT r.name, count(*) FROM chunks c JOIN rooms r ON r.id=c.room_id GROUP BY 1;"
docker exec -it kg-postgres psql -U kg -d kg -c "SELECT model, count(*) FROM chunk_embeddings GROUP BY 1;"
curl -s "localhost:9200/kakao_chunks/_count"
```

---

## 7. 세 방식 비교 — 프로젝트 팀 톡방용 질문 예시

```bash
python src/search.py "배포 일정" --room 팀리더
python src/search.py "서버 터졌던 날 무슨 일 있었어" -k 8
cp questions.example.txt questions.txt && open -e questions.txt
python src/search.py --batch questions.txt --md > compare.md
```

`questions.txt` 에 넣을 만한 것 (내 방에 맞게 고치기):

```
# 단일 사실 — grep/BM25 가 이길 것
깃허브 레포 주소
발표 날짜
# 표현 불일치 — 벡터가 이길 것
서버 터졌던 날 무슨 일 있었어
회의 시간 바꾼 적 있어?
마감 미룬 이유
# 다중 홉 / 집계 — 셋 다 못 답할 것 (W4~W6 재료)
백엔드 맡은 사람 중 회의에 가장 많이 빠진 사람
가장 많이 언급된 기능/이슈
리더방에서 결정된 내용 중 팀방에 공유 안 된 것
```

---

## 8. 커밋 — 코드와 결과만

```bash
cd /Users/yeseung/dev/10th-KG-study
git checkout -b lys0611/lab-01-ingest
git status                                       # members/lys0611/... 만 보여야 함. data/, .env, name_map.json 이 보이면 중단
git add members/lys0611
git commit -m "feat: 01-ingest 카톡 적재·임베딩·ES 색인 파이프라인"
git push -u origin lys0611/lab-01-ingest         # → GitHub 에서 PR
```

`labs/01-ingest/README.md` 맨 위 프론트매터(title/date/tags/status)는 현황판이 읽는다. 내 상황에 맞게 `status: done` 으로 바꾸고, `compare.md` 표를 README 결과 절에 붙이면 W2 실습 산출물이 된다.

---

## Colima 에서 자주 나는 문제

| 증상 | 처리 |
|---|---|
| `failed to connect to the docker API at unix:///Users/yeseung/.colima/default/docker.sock` | Colima 가 꺼져 있음 → `colima start` (재부팅 후마다 필요. 자동 시작은 `brew services start colima`) |
| ES 컨테이너 `Exited (137)` 또는 `(78)` | VM 메모리 부족 → `colima stop && colima start --memory 8` |
| `docker compose build` 가 매우 느림 | 첫 빌드는 ES 이미지 ~1GB 다운로드. 두 번째부터는 캐시 |
| `vm.max_map_count` 경고가 로그에 보임 | single-node 모드라 경고만 뜨고 기동은 됨. 신경 쓰이면 1번의 `colima ssh -- sudo sysctl ...` |
| 파일명에 `ㅇ`·한글이 있어 glob 이 안 됨 | 항상 큰따옴표: `"data/raw/KakaoTalkChats_*.txt"` |
| `insufficient_quota` | Plus 결제가 아니라 platform.openai.com 크레딧이 필요 (4번) |
