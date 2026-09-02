# 10th-KG-study

10기 KG(Knowledge Graph) 스터디 레포입니다.
각자 공부한 내용(notes)과 실습 코드(labs)를 자기 폴더 아래에 정리합니다.

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
└── shared/                # 공용 작업 공간
    └── cloudclub-agent/
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

## 멤버

| GitHub ID | 폴더 |
|-----------|------|
| sehyun | [members/sehyun](members/sehyun) |
