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
│       ├── readings.md    # 주차별 읽을거리·참고자료 (현황판에 모아서 표시)
│       ├── notes/         # 학습 정리 (01-topic.md ...)
│       └── labs/          # 실습 (01-topic/README.md + src/)
├── templates/             # notes / labs / readings 템플릿
│   ├── note-template.md
│   ├── lab-template.md
│   └── readings-template.md
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
4. 주차별 참고자료는 `readings.md`에 `## 1주차` 제목 아래 링크로 적습니다. 현황판이 멤버 전체 것을 모아 보여줍니다.
5. PR로 올립니다. 자세한 규칙은 [CONTRIBUTING.md](CONTRIBUTING.md)를 참고하세요.

```bash
GH_ID=<your-github-id>
mkdir -p members/$GH_ID/notes members/$GH_ID/labs
cp templates/note-template.md members/$GH_ID/notes/01-topic.md
cp templates/readings-template.md members/$GH_ID/readings.md
```

## 현황판 (dashboard)

`main`에 푸시하면 GitHub Actions가 `members/`를 스캔해 노트·실습·커밋·활동 히트맵을 뽑고,
GPT가 멤버별 칭호·요약·태그와 스터디 소식을 붙여 GitHub Pages로 배포합니다.

- 노트/실습 맨 위 프론트매터의 `tags`가 지식그래프의 주제 노드가 됩니다. 비워두면 GPT가 채워줍니다.
- "주차별 읽을거리"는 각자 `members/<id>/readings.md`의 `## N주차` 아래 불릿을 모아 주차별로 보여줍니다. `[제목](링크) — 메모` 형식이면 링크·도메인·메모까지 뽑히고, 링크 없는 책 제목도 됩니다.
- "중계석"은 최근 커밋의 diff를 GPT가 읽고 무슨 작업인지 캐스터 톤으로 중계합니다. `members/`, `shared/` 어디든 스터디 작업 커밋이면 잡히고, 3일 이상 연속 출석과 레벨 업도 사건으로 올라갑니다. 현황판 코드나 템플릿만 바꾼 커밋은 제외합니다.
- 커밋은 멤버 폴더 경로, GitHub 로그인, 이메일 순으로 멤버에 연결됩니다. `shared/` 커밋도 히트맵과 최근 활동에 포함됩니다.
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
