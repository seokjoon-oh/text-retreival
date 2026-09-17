# Text Retrieval Search Engine

JSON 문서의 index를 직접 구축하고 검색할 수 있도록 구현한 Python 기반 검색엔진입니다.

프로젝트에서는 기계·재료·화공 분야의 특허 문서 1,238건을 데이터셋으로 사용했습니다. Title, Abstract, Claims를 각각 index에 반영하고 Komoran으로 검색에 필요한 용어를 추출했으며, 검색 결과는 BM25F 점수를 기준으로 정렬하도록 구현했습니다.

## 구현 내용

- 특허 JSON 문서 1,238건 index 구축
- Komoran을 이용한 NNG / NNP / SL 추출
- 영문 용어 소문자 정규화
- 10,306개 고유 term 기반 inverted index 구축
- Title / Abstract / Claims 필드별 term frequency 저장
- postings를 binary 파일로 저장
- BM25F 기반 검색 순위 계산
- AND / PHRASE / FIELD / VERBOSE 검색 구현
- 관련도 상위 5개 문서 출력

## 검색 흐름

```text
JSON Documents
   ↓
Komoran Tokenization
(NNG / NNP / SL)
   ↓
Inverted Index
(Title / Abstract / Claims)
   ↓
BM25F Scoring
   ↓
Query Processing
   ↓
Top-5 Results
```

## 주요 기능

### 1. 용어 추출

`Komoran`을 이용해 일반명사(NNG), 고유명사(NNP), 외국어(SL)를 추출합니다. 영문 용어는 소문자로 변환해 대소문자 차이로 같은 단어가 따로 처리되지 않도록 했습니다.

### 2. Inverted Index

문서의 Title, Abstract, Claims 세 필드를 나누어 index를 구축합니다.

- `T`: Title
- `A`: Abstract
- `C`: Claims

각 term에 대해 문서 ID와 term frequency를 저장하고, postings 데이터는 binary 형식으로 관리합니다.

### 3. BM25F Ranking

검색 결과의 순위는 BM25F를 이용해 계산합니다. Title, Abstract, Claims의 문서 길이를 각각 반영하고 필드별 가중치를 다르게 적용했습니다.

현재 코드의 필드 가중치는 다음과 같습니다.

- Title: 2.5
- Abstract: 1.5
- Claims: 1.1

### 4. 검색 옵션

아래 입력은 검색 문법을 설명하기 위한 일반형 예시입니다.

| 입력 형식 | 기능 |
| --- | --- |
| `<검색어>` | 기본 검색 |
| `[AND]<검색어1> <검색어2>` | 모든 검색어가 포함된 문서 검색 |
| `[PHRASE]<검색 구문>` | Title에서 정확 구문 검색 |
| `[FIELD=T]<검색어>` | Title만 검색 |
| `[FIELD=A]<검색어>` | Abstract만 검색 |
| `[FIELD=C]<검색어>` | Claims만 검색 |
| `[VERBOSE]<검색어1> <검색어2>` | 검색어가 포함된 문맥 출력 |

`AND`, `FIELD`, `VERBOSE`는 함께 사용할 수 있습니다.

```text
[VERBOSE][AND][FIELD=A]<검색어1> <검색어2>
```

`PHRASE` 검색은 별도로 사용하며 `AND`와 동시에 사용하지 않습니다.

## 구현 결과

총 1,238건의 특허 문서에 대한 index를 구축했고, 그 결과 10,306개의 고유 term을 구성했습니다.

검색 시 BM25F 점수를 기준으로 관련도가 높은 상위 5개 문서를 출력하도록 구현했습니다. 기본 검색 외에도 여러 검색어를 모두 포함하는 AND 검색, Title 정확 구문 검색, 특정 필드만 대상으로 하는 검색, 검색어가 실제 문서의 어느 부분에 포함됐는지 확인하는 문맥 출력 기능을 추가했습니다.

별도의 검색 정확도나 처리 속도 비교 실험은 진행하지 않았기 때문에 확인한 구현 결과만 정리했습니다.

### Index 결과 파일

기존 실험에서 생성한 index 결과는 소스 코드와 섞이지 않도록 `index_results/` 폴더에 묶어서 보관했습니다.

- `index_results/doc_table.json`: 문서 ID, 파일명, 문서 경로, Title / Abstract / Claims 길이 정보
- `index_results/term_dict.json`: term별 document frequency와 postings 위치 정보
- `index_results/postings.bin`: 문서 ID와 term frequency를 저장한 binary postings

공개 저장소에 개인 PC 경로가 노출되지 않도록 `doc_table.json`의 `path` 값은 `data/<파일명>` 형태의 상대경로로 정리했습니다. 문서 ID, 파일명, 각 필드 길이 등 index 결과값은 그대로 유지했습니다.

## 프로젝트 구조

```text
text-retrieval/
├── main.py
├── requirements.txt
├── README.md
├── .gitignore
├── index_results/
│   ├── doc_table.json
│   ├── term_dict.json
│   └── postings.bin
└── src/
    ├── __init__.py
    ├── tokenizer.py
    ├── indexer.py
    └── searcher.py
```

## 실행 방법

### 1. 저장소 내려받기

```bash
git clone https://github.com/seokjoon-oh/text-retrieval.git
cd text-retrieval
```

### 2. 패키지 설치

```bash
pip install -r requirements.txt
```

`Komoran` 사용을 위해 Java/JDK 환경이 필요합니다.

### 3. Index 생성

원천 JSON 파일이 저장된 디렉터리를 지정합니다.

```bash
python main.py index "path/to/patent-json-directory"
```

새로 index를 생성하면 결과는 `index/` 폴더에 저장됩니다.

```text
index/
├── doc_table.json
├── term_dict.json
└── postings.bin
```

### 4. 검색

대화형 검색:

```bash
python main.py search
```

검색어를 한 번만 입력해 실행할 수도 있습니다.

```bash
python main.py search "[VERBOSE][AND]<검색어1> <검색어2>"
```

## 파일 구성

- `src/tokenizer.py`: Komoran 기반 term 추출 및 영문 정규화
- `src/indexer.py`: JSON 문서 순회, 필드별 TF 계산, inverted index와 postings 생성
- `src/searcher.py`: query parsing, BM25F ranking, AND / PHRASE / FIELD 검색 및 문맥 출력
- `main.py`: index 생성과 검색 실행을 위한 CLI
- `index_results/`: 기존 실험에서 생성한 index 결과 파일 묶음

## 참고

원천 특허 JSON 데이터는 저장소에 포함하지 않습니다. `index_results/` 폴더에는 기존 실험에서 생성된 index 결과를 보관했으며, `doc_table.json`의 개인 로컬 경로만 공개용 상대경로로 정리했습니다. 다른 환경에서 전체 검색 과정을 재현하려면 원천 데이터를 준비한 뒤 다시 index를 생성하면 됩니다.
