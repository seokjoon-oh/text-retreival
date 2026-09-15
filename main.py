from src.indexer import Indexer
from src.searcher import Searcher


DATA_DIR = r"D:\algorithm111\01.원천데이터\TS_TS1_EA_기계_EA01_측정표준_시험평가기술"
INDEX_DIR = "index"
DOC_TABLE_FILE = "doc_table.json"
TERM_DICT_FILE = "term_dict.json"
POSTINGS_FILE = "postings.bin"

if __name__ == "__main__":
    task = input("작업을 선택하세요 (index/search): ").strip().lower()

    if task in ("index", "i"):
        indexer = Indexer(DATA_DIR, INDEX_DIR, DOC_TABLE_FILE, TERM_DICT_FILE, POSTINGS_FILE)
        indexer.build_index()
        print(f"색인이 완료되었습니다. 색인 결과는 '{INDEX_DIR}'에 저장되었습니다.")

    elif task in ("search", "s"):
        searcher = Searcher(INDEX_DIR, DOC_TABLE_FILE, TERM_DICT_FILE, POSTINGS_FILE)
        while True:
            q = input("검색어를 입력하세요: ").strip()
            if not q:
                break
            searcher.process_query(q)
