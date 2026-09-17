# Patent Text Retrieval Engine

기계·재료·화공 분야의 특허 JSON 문서를 대상으로 직접 색인하고 검색하는 Python 기반 정보검색(Text Retrieval) 프로젝트입니다.

형태소 분석을 통해 검색어와 문서를 정규화하고, Title / Abstract / Claims 필드별 inverted index를 구축한 뒤 BM25F 기반으로 문서의 관련도를 계산합니다. 단순 키워드 검색뿐 아니라 AND, 정확 구문(PHRASE), 필드 지정, 문맥 출력(VERBOSE)을 지원합니다.

## Project Overview

- 대상 데이터: 특허 문서 1,238건
- 고유 용어: 10,306개
- 전처리: Komoran 형태소 분석기
- 사용 품사: 일반명사(NNG), 고유명사(NNP), 외국어(SL)
- 색인 구조: field별 inverted index + binary postings
- 검색 랭킹: BM25F
- 검색 필드: Title / Abstract / Claims
- 결과 출력: 관련도 상위 5개 문서 및 선택적 문맥 하이라이트

## Search Pipeline

```text
Patent JSON
   ↓
Komoran Tokenization
(NNG / NNP / SL)
   ↓
Field-wise Inverted Index
(Title / Abstract / Claims)
   ↓
BM25F Scoring
   ↓
Query Filtering
(AND / PHRASE / FIELD)
   ↓
Top-5 Results + VERBOSE Context
```

## Key Features

### 1. Korean / English term extraction

`Komoran`을 이용해 문장에서 NNG, NNP, SL 품사만 추출합니다. 영문 토큰은 소문자로 정규화합니다.

### 2. Field-wise inverted index

각 특허 문서의 다음 필드를 별도로 색인합니다.

- `T`: invention title
- `A`: abstract
- `C`: claims

각 term에 대해 문서 ID와 term frequency를 저장하며, postings는 binary 형식으로 기록합니다.

### 3. BM25F ranking

Title, Abstract, Claims의 길이와 중요도를 각각 반영하여 BM25F 점수를 계산합니다. 동일한 검색어라도 어느 필드에 등장했는지에 따라 가중치를 다르게 적용합니다.

### 4. Query operators

| Query | Description |
| --- | --- |
| `motor` | 기본 OR 검색 |
| `[AND]motor sensor` | 모든 검색어가 등장하는 문서만 검색 |
| `[PHRASE]temperature sensor` | Title에서 정확 구문 검색 |
| `[FIELD=T]motor` | Title만 검색 |
| `[FIELD=A]motor` | Abstract만 검색 |
| `[FIELD=C]motor` | Claims만 검색 |
| `[VERBOSE]motor sensor` | 검색어가 포함된 문맥과 하이라이트 출력 |

태그는 조합할 수 있습니다. 예를 들어 `[VERBOSE][AND][FIELD=A]motor sensor`처럼 사용할 수 있습니다. 단, `PHRASE`와 `AND`는 동시에 사용하지 않습니다.

## Project Structure

```text
text-retreival/
├── main.py
├── requirements.txt
├── README.md
├── .gitignore
└── src/
    ├── __init__.py
    ├── tokenizer.py
    ├── indexer.py
    └── searcher.py
```

실행 중 생성되는 `data/`, `index/`, Python cache, IDE 설정 파일은 Git에서 제외합니다.

## Installation

### 1. Clone

```bash
git clone https://github.com/seokjoon-oh/text-retreival.git
cd text-retreival
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

`Komoran`은 Java 환경을 사용하므로 로컬에 Java/JDK가 설치되어 있어야 합니다.

## Usage

### Build index

원천 특허 JSON이 저장된 디렉터리를 지정합니다.

```bash
python main.py index "path/to/patent-json-directory"
```

색인 결과는 자동으로 `index/`에 생성됩니다.

```text
index/
├── doc_table.json
├── term_dict.json
└── postings.bin
```

### Interactive search

```bash
python main.py search
```

검색어를 입력하고, 빈 줄을 입력하면 종료됩니다.

### One-shot search

```bash
python main.py search "[VERBOSE][AND]sensor measurement"
```

## Core Files

- `src/tokenizer.py`: Komoran 기반 term 추출 및 영문 정규화
- `src/indexer.py`: 특허 JSON 순회, field별 TF 계산, inverted index 및 postings 생성
- `src/searcher.py`: query parsing, BM25F ranking, AND/PHRASE/FIELD 검색, 문맥 하이라이트
- `main.py`: indexing/search CLI 진입점

## Notes

원천 특허 데이터와 생성된 index 파일은 저장소에 포함하지 않습니다. `doc_table.json`에는 색인 당시의 로컬 원천 데이터 경로가 저장되므로, 다른 환경에서는 원천 데이터를 준비한 뒤 다시 indexing하는 방식으로 사용합니다.
