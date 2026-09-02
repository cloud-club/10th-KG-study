# 10th-KG-study

10기 KG(Knowledge Graph) 스터디 레포입니다.
각자 공부한 내용(notes)과 실습 코드(labs)를 자기 폴더 아래에 정리합니다.

**현황판:** https://cloud-club.github.io/10th-KG-study/ — 누가 뭘 공부했고 어디까지 왔는지 한눈에.

## 구조

```
10th-KG-study/
├── README.md
├── CONTRIBUTING.md        # 참여 방법, 네이밍 규칙
├── .gitignore
├── members/               # 멤버별 개인 작업 공간
│   └── <github-id>/
│       ├── README.md      # 자기소개, 목표
│       ├── notes/         # 학습 정리 (01-topic.md ...)
│       └── labs/          # 실습 (01-topic/README.md + src/)
├── templates/             # notes / labs 템플릿
│   ├── note-template.md
│   └── lab-template.md
├── shared/                # 공용 작업 공간
│   └── cloudclub-agent/
├── dashboard/             # 현황판 정적 사이트 (GitHub Pages)
├── scripts/               # 현황판 데이터 빌드 스크립트
└── .github/workflows/     # Pages 배포
```

## 참여 방법

1. `members/<github-id>/` 폴더를 만듭니다. (아래 명령 참고)
2. `README.md`에 간단한 자기소개와 스터디 목표를 적습니다.
3. `notes/`, `labs/`에 공부한 내용을 쌓아갑니다.
4. PR로 올립니다. 자세한 규칙은 [CONTRIBUTING.md](CONTRIBUTING.md)를 참고하세요.

```bash
GH_ID=<your-github-id>
mkdir -p members/$GH_ID/notes members/$GH_ID/labs
cp templates/note-template.md members/$GH_ID/notes/01-topic.md
```

## 현황판 (dashboard)

`main`에 푸시하면 GitHub Actions가 `members/`를 스캔해 노트·실습·커밋·활동 히트맵을 뽑고,
GPT가 멤버별 칭호·요약·태그와 스터디 소식을 붙여 GitHub Pages로 배포합니다.

- 노트/실습 맨 위 프론트매터의 `tags`가 지식그래프의 주제 노드가 됩니다. 비워두면 GPT가 채워줍니다.
- 상단 "중계석"은 노트/실습 추가, 연속 출석, 레벨 업을 캐스터 톤으로 중계합니다.
  실제 기록이 없으면 목데이터로 채우고 MOCK 표시가 붙습니다. `DASHBOARD_MOCK_FEED=0`이면 목데이터를 끄고, `1`이면 항상 씁니다.
- 로컬 미리보기:

```bash
python3 scripts/build_dashboard.py                        # LLM 없이
OPENAI_API_KEY=sk-... python3 scripts/build_dashboard.py  # GPT 요약 포함
python3 -m http.server -d dashboard 8000                  # http://localhost:8000
```

- GPT 요약을 켜려면 레포 **Settings → Secrets and variables → Actions**에 `OPENAI_API_KEY`를 등록합니다.
  키가 없어도 규칙 기반 요약으로 빌드됩니다. 모델은 `OPENAI_MODEL` 변수로 바꿀 수 있습니다 (기본 `gpt-5-mini`).

## 멤버

| GitHub ID | 폴더 |
|-----------|------|
| sese2204 | [members/sese2204](members/sese2204) |
