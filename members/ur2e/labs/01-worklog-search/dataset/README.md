# Work Log Vault (가정 데이터셋)

옵시디언에 쌓아둔 **내 작업 기록**을 자연어로 되찾기 위한 검색·RAG 실습용 데이터셋입니다.

목표는 장애 사례집을 만드는 게 아니라 이것입니다.

> "그때 그거 어떻게 했었지" 를 물어보면 관련 기록이 나오게 한다.

## 왜 가정 데이터인가

실제 기록은 사내망에 있어서 외부망으로 가져올 수 없습니다. 그래서 이 폴더의 문서는 **실제 vault 를 닮게 만든 합성 데이터**입니다. 실제 회사·고객·계정·클러스터·IP·티켓 정보는 없고, 사건·시각·수치·노드 이름은 모두 가상입니다.

여기서 파서와 검색을 완성해두고, 사내망에서는 vault 경로만 바꿔서 같은 코드를 돌리는 게 목적입니다. 따라서 **이 데이터셋에만 맞는 가정을 코드에 넣으면 안 됩니다.**

## 구조

```text
worklog-vault-dataset/
├── README.md
├── note-templates/          # 앞으로 실제 기록을 쓸 때 쓸 템플릿
│   ├── troubleshooting.md
│   ├── howto.md
│   ├── decision.md
│   └── daily.md
├── evaluation/
│   └── queries.jsonl        # 평가 질문 19건
└── vault/                   # ← 옵시디언 vault 로 바로 열림
    ├── daily/               # 날짜별 작업 로그 (여러 주제가 섞임)
    ├── troubleshooting/     # 삽질·장애 기록 12건
    ├── howto/               # 절차·명령어 메모
    ├── decisions/           # 왜 A 대신 B 를 골랐는지
    ├── learning/            # 학습 정리
    └── meetings/            # 논의·회의 기록
```

## 문서 형식은 일부러 제각각입니다

실제 개인 vault 는 형식이 통일돼 있지 않습니다. 어떤 문서는 프론트매터가 꽉 차 있고, 어떤 건 그냥 불릿 몇 줄입니다. 파서가 특정 필드를 필수로 가정하면 실제 vault 에 붙이는 순간 깨집니다. 그래서 이 데이터셋은 아래 조합을 **의도적으로** 섞어놨습니다.

| 폴더 | 프론트매터 | `# 제목` | `##` 소제목 | 날짜 출처 | 특징 |
|---|---|---|---|---|---|
| `daily/` | 없음 | 있음 (날짜) | 없음 | 파일명 | 인라인 `#태그`, `[[링크]]` 다수, 한 문서에 여러 주제 |
| `troubleshooting/` | 전체 (`incident_id`, `severity`, `status`…) | 있음 | 있음 | 프론트매터 | 구조가 12건 모두 동일 |
| `howto/` | `title`, `tags` 만 | 대체로 있음 | 4건 중 2건만 | **없음** | `harbor-robot-account-발급.md` 은 `#`·`##` 둘 다 없음 |
| `decisions/` | `date`, `status`, `tags` (**`title` 없음**) | 있음 | 있음 | 프론트매터 | `status: superseded` 로 뒤집힌 결정 포함 |
| `learning/` | **없음** | 있음 | 있음 | 없음 | 외부 링크 포함 |
| `meetings/` | `date` (+`attendees`) | 하나만 있음 | 없음 | 프론트매터 + 파일명 | 불릿 위주, 액션 아이템이 본문에 섞임 |

파일명도 한글·영어가 섞여 있고 날짜가 붙은 것과 안 붙은 것이 함께 있습니다. 이것도 실제 상황입니다.

## 파서가 지켜야 하는 계약

`.md` 파일을 읽어 검색 단위(청크) JSONL 로 바꾸는 게 파서의 일입니다. 옵시디언 앱을 조작하거나 전용 API 를 쓰는 게 아니라, 폴더의 파일을 읽는 로컬 전처리입니다.

**항상 뽑을 수 있어야 하는 것 (없으면 파서 버그):**

- `source_path` — vault 기준 상대 경로. 이게 유일한 안정적 식별자입니다.
- `doc_type` — 최상위 폴더명에서 유도 (`daily`, `howto`, …). 프론트매터에 의존하지 않습니다.
- `title` — 프론트매터 `title` → 첫 `#` 제목 → 파일명 순으로 **폴백**합니다.
- `content` — 본문.

**있으면 쓰고 없으면 비워두는 것 (없다고 실패하면 파서 버그):**

- `date` — 프론트매터 `date` → 파일명의 `YYYY-MM-DD` → 없음.
- `tags` — 프론트매터 `tags` + 본문 인라인 `#태그` 를 **합집합**으로. `#todo` 처럼 본문에만 있는 태그를 놓치면 Q-012 를 못 풉니다.
- `links` — 본문 `[[문서명]]`. 확장자 없이 파일명만 들어 있으므로 실제 경로로 해석해야 합니다.
- `heading` — `##` 소제목. **없는 문서가 있습니다.** 이때는 문서 전체가 한 청크입니다.
- 그 밖의 프론트매터 필드(`incident_id`, `status`, `severity`, `attendees`…) — 필터용으로 그대로 보존하되 필수로 두지 않습니다.

청크 예시:

```json
{
  "chunk_id": "howto/kubeadm-인증서-갱신-절차.md#갱신",
  "doc_type": "howto",
  "title": "kubeadm control-plane 인증서 갱신 절차",
  "heading": "갱신",
  "content": "kubeadm certs renew all ...",
  "date": null,
  "tags": ["kubernetes", "kubeadm", "certificate", "runbook"],
  "links": ["troubleshooting/INC-003-apiserver-etcd-tls-expiry.md"],
  "source_path": "howto/kubeadm-인증서-갱신-절차.md"
}
```

### 청킹 방침

- 기본은 `##` 소제목 단위. 문서 전체를 한 덩어리로 넣으면 증상·원인·조치가 섞여 검색 결과가 모호해집니다.
- 반대로 문장 단위로 쪼개면 어느 작업 얘기인지 문맥을 잃습니다. 그래서 **모든 청크에 `title` 과 `source_path` 를 함께 넣습니다.**
- `##` 이 없는 문서(대부분의 `daily/`, `meetings/`)는 문서 전체가 한 청크입니다. 불릿 하나씩 쪼개면 `daily/` 가 문맥 없는 조각으로 흩어집니다.
- 코드 블록은 중간에서 자르지 않습니다. 명령어가 반토막 나면 그 청크는 쓸모가 없어집니다.
- grep, BM25, 벡터 검색은 **같은 청크**를 씁니다. 그래야 방식별 비교가 의미가 있습니다.

## 평가

`evaluation/queries.jsonl` 각 행의 필드:

- `id`, `query` — 질문
- `type` — 질문 유형. 방식별 강약을 나눠 보기 위한 것입니다.
- `expected_primary` / `expected_supporting` — 정답 문서의 **vault 상대 경로**
- `answer_points` — RAG 답변에 들어가야 하는 내용

질문 유형이 섞여 있는 게 중요합니다. 한쪽 검색 방식만으로는 전체 점수가 안 오릅니다.

| `type` | 건수 | 질문 성격 | 유리할 것으로 보는 방식 |
|---|---|---|---|
| `troubleshooting` | 5 | 증상을 던지고 확인 순서를 찾는 것 | BM25 + 벡터 |
| `recall-command` | 3 | "그 명령어 뭐였지" | BM25 + 벡터 |
| `recall-decision` | 2 | "왜 그렇게 정했지" | 벡터 |
| `recall-meeting` | 2 | "그때 뭐 하기로 했지" | 벡터 |
| `concept` | 2 | "정리해둔 게 있었는데" | 벡터 |
| `cross-document` | 2 | 여러 문서를 모아야 답이 되는 것 | 태그·링크 활용 |
| `exact-token` | 1 | `x509: certificate has expired` 같은 원문 | grep / BM25 |
| `temporal` | 1 | "1월에 뭐 했지" | 날짜 필터 + 검색 |
| `low-signal` | 1 | 평범한 날의 기록 (노이즈 확인용) | — |

지표는 `Hit@3` 부터 시작합니다.

```text
Hit@3 = expected_primary 문서가 검색 결과 상위 3개에 있으면 1, 없으면 0
MRR   = 각 질문에서 첫 정답 문서 순위의 역수 평균
```

전체 평균만 보지 말고 `type` 별로 쪼개서 봐야 어떤 방식이 어디서 지는지 알 수 있습니다.

## 실제 vault 로 교체하기

경로를 코드에 박지 말고 환경변수나 인자로 받습니다.

```bash
# 외부망 (개발·평가)
OBSIDIAN_VAULT_PATH=members/ur2e/labs/01-worklog-search/dataset/vault

# 사내망
OBSIDIAN_VAULT_PATH=/path/to/real/vault
```

사내망에서는 이 값만 바꾸고, 원본 문서·변환 결과(JSONL)·임베딩 파일은 모두 git 에서 제외합니다.

## 주의

- `synthetic: true` 인 기록을 실제 장애의 확정 원인처럼 인용하지 않습니다.
- RAG 답변에는 사용한 문서의 제목과 `source_path` 를 표시합니다. 출처 없이 답하면 내 기록을 찾는 도구로 못 씁니다.
- 근거 문서가 부족하면 원인을 만들어내지 않고 확인할 항목만 제시합니다.
- `status: cause-unconfirmed`, `superseded` 처럼 **미확정·번복된 기록이 일부러 들어 있습니다.** 이걸 확정 사실로 요약하면 안 됩니다.
