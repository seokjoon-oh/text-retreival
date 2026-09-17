import argparse
from pathlib import Path

from src.indexer import Indexer
from src.searcher import Searcher


INDEX_DIR = Path("index")
DOC_TABLE_FILE = "doc_table.json"
TERM_DICT_FILE = "term_dict.json"
POSTINGS_FILE = "postings.bin"


def build_index(data_dir: str) -> None:
    indexer = Indexer(
        data_dir,
        str(INDEX_DIR),
        DOC_TABLE_FILE,
        TERM_DICT_FILE,
        POSTINGS_FILE,
    )
    indexer.build_index()
    print(f"Index 생성이 완료되었습니다. 결과는 '{INDEX_DIR}'에 저장되었습니다.")


def run_search(query: str | None = None) -> None:
    searcher = Searcher(
        str(INDEX_DIR),
        DOC_TABLE_FILE,
        TERM_DICT_FILE,
        POSTINGS_FILE,
    )

    try:
        if query:
            searcher.process_query(query)
            return

        while True:
            q = input("검색어를 입력하세요 (빈 줄 입력 시 종료): ").strip()
            if not q:
                break
            searcher.process_query(q)
    finally:
        searcher.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Patent text retrieval engine using an inverted index and BM25F."
    )
    subparsers = parser.add_subparsers(dest="command")

    index_parser = subparsers.add_parser("index", help="Build an index from patent JSON files")
    index_parser.add_argument("data_dir", help="Directory containing source patent JSON files")

    search_parser = subparsers.add_parser("search", help="Search the generated index")
    search_parser.add_argument(
        "query",
        nargs="?",
        help="Optional one-shot query. Omit it to start interactive search.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.command == "index":
        build_index(args.data_dir)
    elif args.command == "search":
        run_search(args.query)
    else:
        print("사용법: python main.py {index|search} ...")
        print("자세한 옵션은 python main.py -h 로 확인하세요.")


if __name__ == "__main__":
    main()
