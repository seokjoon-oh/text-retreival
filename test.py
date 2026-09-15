from src.searcher import Searcher

INDEX_DIR = "index"
DOC_TABLE_FILE = "doc_table.json"
TERM_DICT_FILE = "term_dict.json"
POSTINGS_FILE = "postings.bin"

searcher = Searcher(INDEX_DIR, DOC_TABLE_FILE, TERM_DICT_FILE, POSTINGS_FILE)
searcher.process_query("test")