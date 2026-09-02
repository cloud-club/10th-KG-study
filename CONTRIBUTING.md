# CONTRIBUTING

## 폴더 규칙

- 개인 작업은 반드시 `members/<github-id>/` 아래에만 둡니다.
- 다른 사람 폴더는 수정하지 않습니다. 피드백은 PR 코멘트나 이슈로 남깁니다.
- 여러 사람이 같이 쓰는 코드는 `shared/` 아래에 둡니다.

## 멤버 폴더 만들기

```
members/<github-id>/
├── README.md     # 자기소개, 목표, 진행 현황
├── notes/        # 학습 정리
└── labs/         # 실습
```

```bash
GH_ID=<your-github-id>
mkdir -p members/$GH_ID/notes members/$GH_ID/labs
touch members/$GH_ID/notes/.gitkeep members/$GH_ID/labs/.gitkeep
```

폴더를 만든 뒤 루트 `README.md`의 멤버 표에 자기 행을 추가합니다.

## 네이밍 규칙

### 프론트매터 (notes / labs 공통)

파일 맨 위에 아래 블록을 둡니다. 현황판이 이걸 읽어 제목·날짜·태그를 뽑습니다.

```yaml
---
title: RDF 데이터 모델
date: 2026-09-10
tags: [rdf, triple, sparql]   # 소문자 영어, 지식그래프의 주제 노드가 됨
status: in-progress           # in-progress | done
---
```

- `tags`를 비워두면 빌드 시 GPT가 본문을 읽고 채워줍니다.
- `title`이 없으면 첫 `# 제목`을, 그것도 없으면 파일명을 씁니다.

### notes

- 파일 하나가 주제 하나입니다.
- `NN-kebab-case-topic.md` 형식으로 번호를 붙여 순서를 유지합니다.
  - 예: `01-data-model.md`, `02-storage-and-search.md`
- `templates/note-template.md`를 복사해서 시작합니다.

### labs

- 실습 하나가 폴더 하나입니다.
- `NN-kebab-case-topic/` 안에 `README.md`와 `src/`를 둡니다.
  - 예: `01-document-parser/README.md`, `01-document-parser/src/`
- `README.md`는 `templates/lab-template.md`를 복사해서 작성합니다.
- 실행 방법, 의존성, 결과를 README에 적어 다른 사람이 재현할 수 있게 합니다.

## 브랜치 & PR

- 브랜치 이름: `<github-id>/<short-description>`
  - 예: `sese2204/01-data-model`, `sese2204/lab-document-parser`
- `main`에 직접 푸시하지 않고 PR로 올립니다.
- 커밋 메시지: `<type>: <description>`
  - type: `docs`, `feat`, `fix`, `refactor`, `chore`
  - 예: `docs: 01-data-model 정리`, `feat: document parser 초안`

## 커밋하면 안 되는 것

- 데이터셋 원본, 대용량 파일 (필요하면 다운로드 스크립트나 링크로 대체)
- `.env`, API 키, 토큰 등 비밀 정보
- 가상환경, `node_modules`, 빌드 산출물, 캐시
