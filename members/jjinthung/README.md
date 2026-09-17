# jjinthung RAG 사용법

모든 명령어는 아래 폴더에서 실행한다.

```powershell
Set-Location "C:\Users\jinsung\github\10th-KG-study\members\jjinthung"
```

## 1. 데이터셋 만들기

먼저 카카오톡 원본 파일을 아래 폴더에 넣는다.

```text
Data\Talk_*.txt
```

청크 데이터 생성:

```powershell
C:\Users\jinsung\AppData\Local\Programs\Python\Python312\python.exe .\labs\prepare_dataset.py
```

생성 결과:

```text
Data\documents.jsonl
```

## 2. 전체 시작

### 2-1. 패키지 설치

```powershell
C:\Users\jinsung\AppData\Local\Programs\Python\Python312\python.exe -m pip install -r .\labs\requirements.txt
```

### 2-2. Elasticsearch 시작

Docker Desktop을 실행한 뒤:

```powershell
C:\Users\jinsung\AppData\Local\Programs\Python\Python312\python.exe .\labs\docker.py
```

### 2-3. Vector 인덱스 만들기

```powershell
C:\Users\jinsung\AppData\Local\Programs\Python\Python312\python.exe .\labs\02-vector\index.py
```

### 2-4. BM25 인덱스 만들기

```powershell
C:\Users\jinsung\AppData\Local\Programs\Python\Python312\python.exe .\labs\01-bm25\index.py
```

## 3. 검색만 실행

GPT를 호출하지 않고 top-5 검색 결과만 확인한다.

```powershell
C:\Users\jinsung\AppData\Local\Programs\Python\Python312\python.exe .\labs\main.py "국밥" --top-k 5 --retrieve-only
```

## 4. GPT 답변 실행

같은 PowerShell 창에서 API 키를 설정한다.

```powershell
$env:OPENAI_API_KEY="새로_발급한_API_KEY"
```

top-5 검색 결과를 GPT에 전달한다.

```powershell
C:\Users\jinsung\AppData\Local\Programs\Python\Python312\python.exe .\labs\main.py "국밥" --top-k 5
```

질문 예시:

```powershell
C:\Users\jinsung\AppData\Local\Programs\Python\Python312\python.exe .\labs\main.py "국밥 먹은 날이 언제야?" --top-k 5

C:\Users\jinsung\AppData\Local\Programs\Python\Python312\python.exe .\labs\main.py "가장 최근에 먹은 음식은?" --top-k 5
```

## 5. 시스템 프롬프트 수정

GPT 답변 규칙은 아래 파일에서 수정한다.

```text
labs\04-generate\system_prompt.txt
```

수정 후 별도 빌드 없이 GPT 명령을 다시 실행한다.

## 6. 원본 데이터가 변경된 경우

아래 순서로 다시 실행한다.

```powershell
C:\Users\jinsung\AppData\Local\Programs\Python\Python312\python.exe .\labs\prepare_dataset.py
C:\Users\jinsung\AppData\Local\Programs\Python\Python312\python.exe .\labs\02-vector\index.py
C:\Users\jinsung\AppData\Local\Programs\Python\Python312\python.exe .\labs\01-bm25\index.py
```
