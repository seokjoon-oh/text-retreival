# src/indexer.py
import os
import json
import struct
from .tokenizer import extract_terms


class Indexer:
    def __init__(self, data_dir, output_dir, doc_table_file, term_dict_file, postings_file):
        self.data_dir = os.path.abspath(data_dir)
        self.output_dir = os.path.abspath(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)

        self.doc_table_file = os.path.join(self.output_dir, doc_table_file)
        self.term_dict_file = os.path.join(self.output_dir, term_dict_file)
        self.postings_file = os.path.join(self.output_dir, postings_file)

    def _load_json(self, path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _get_field_texts(self, path):
        data = self._load_json(path)
        ds = data.get("dataset", {})

        t = ds.get("invention_title")
        a = ds.get("abstract")
        c = ds.get("claims")

        if t is None: t = ""
        if a is None: a = ""
        if c is None: c = ""

        return str(t), str(a), str(c)

    def build_index(self):
        
        term_postings = {}
        doc_table = {}
        n_docs = 0

        # 1) 문서 순회
        for dirpath, _, filenames in os.walk(self.data_dir):
            for name in filenames:
                if not name.lower().endswith(".json"):
                    continue

                path = os.path.join(dirpath, name)
                doc_id = n_docs
                n_docs += 1

                title_text, abs_text, clm_text = self._get_field_texts(path)

                T_terms = extract_terms(title_text)
                A_terms = extract_terms(abs_text)
                C_terms = extract_terms(clm_text)

                doc_table[doc_id] = {
                    "doc_id": doc_id,
                    "filename": name,
                    "path": path,
                    "len_T": len(T_terms),
                    "len_A": len(A_terms),
                    "len_C": len(C_terms),
                }

                # TF 계산(쉬운 방식)
                tfT = {}
                for w in T_terms:
                    tfT[w] = tfT.get(w, 0) + 1

                tfA = {}
                for w in A_terms:
                    tfA[w] = tfA.get(w, 0) + 1

                tfC = {}
                for w in C_terms:
                    tfC[w] = tfC.get(w, 0) + 1

                # postings 누적
                for term, tf in tfT.items():
                    if term not in term_postings:
                        term_postings[term] = {"T": [], "A": [], "C": []}
                    term_postings[term]["T"].append((doc_id, tf))

                for term, tf in tfA.items():
                    if term not in term_postings:
                        term_postings[term] = {"T": [], "A": [], "C": []}
                    term_postings[term]["A"].append((doc_id, tf))

                for term, tf in tfC.items():
                    if term not in term_postings:
                        term_postings[term] = {"T": [], "A": [], "C": []}
                    term_postings[term]["C"].append((doc_id, tf))

                # 진행률 표시
                if n_docs % 100 == 0:
                    print(f"[INDEX] {n_docs} docs processed...", flush=True)

        print(f"[INDEX] tokenizing done. writing index files...", flush=True)

        # 2) postings.bin + term_dict.json
        term_dict = {}
        offset = 0

        # 정렬은 재현성엔 좋지만, term이 매우 많으면 시간 꽤 먹습니다.
        # 속도 우선이면 sorted(...)를 빼도 됩니다.
        terms_sorted = sorted(term_postings.keys())

        with open(self.postings_file, "wb") as pbin:
            for term in terms_sorted:
                entry = term_postings[term]

                # 전역 df: T/A/C에 등장한 doc_id들의 합집합
                df_set = set()
                for doc_id, _ in entry["T"]:
                    df_set.add(doc_id)
                for doc_id, _ in entry["A"]:
                    df_set.add(doc_id)
                for doc_id, _ in entry["C"]:
                    df_set.add(doc_id)
                df = len(df_set)

                start_T = offset
                length_T = len(entry["T"])
                for doc_id, tf in entry["T"]:
                    pbin.write(struct.pack("ii", doc_id, tf))
                    offset += 8

                start_A = offset
                length_A = len(entry["A"])
                for doc_id, tf in entry["A"]:
                    pbin.write(struct.pack("ii", doc_id, tf))
                    offset += 8

                start_C = offset
                length_C = len(entry["C"])
                for doc_id, tf in entry["C"]:
                    pbin.write(struct.pack("ii", doc_id, tf))
                    offset += 8

                term_dict[term] = {
                    "df": df,
                    "T": {"start": start_T, "length": length_T},
                    "A": {"start": start_A, "length": length_A},
                    "C": {"start": start_C, "length": length_C},
                }

        with open(self.term_dict_file, "w", encoding="utf-8") as f:
            json.dump(term_dict, f, ensure_ascii=False, indent=4)

        with open(self.doc_table_file, "w", encoding="utf-8") as f:
            json.dump(doc_table, f, ensure_ascii=False, indent=4)

        print("[INDEX] done.", flush=True)
        print("문서 수:", n_docs, flush=True)
        print("고유 term 수:", len(term_dict), flush=True)
