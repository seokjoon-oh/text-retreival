# src/searcher.py
import os
import json
import math
import struct

from .tokenizer import extract_terms


class Searcher:
    def __init__(self, index_dir, doc_table_file, term_dict_file, postings_file):
        self.index_dir = os.path.abspath(index_dir)

        term_path = os.path.join(self.index_dir, term_dict_file)
        doc_path = os.path.join(self.index_dir, doc_table_file)
        post_path = os.path.join(self.index_dir, postings_file)

        with open(term_path, encoding="utf-8") as f:
            self.term_dict = json.load(f)

        with open(doc_path, encoding="utf-8") as f:
            self.doc_table = json.load(f)  # key: "0","1",...

        self.fp = open(post_path, "rb")
        self.N = len(self.doc_table)

        # BM25F parameters
        self.k1 = 1.1
        self.wT, self.wA, self.wC = 2.5, 1.5, 1.1
        self.bT, self.bA, self.bC = 0.3, 0.75, 0.8

        # avg length (field별)
        sumT = sumA = sumC = 0
        for k in self.doc_table:
            d = self.doc_table[k]
            sumT += int(d.get("len_T", 0))
            sumA += int(d.get("len_A", 0))
            sumC += int(d.get("len_C", 0))

        if self.N == 0:
            self.avgT = self.avgA = self.avgC = 1.0
        else:
            self.avgT = (sumT / self.N) or 1.0
            self.avgA = (sumA / self.N) or 1.0
            self.avgC = (sumC / self.N) or 1.0

        # VERBOSE window: 80자(띄어쓰기 포함)
        self.WINDOW_CHARS = 80

    def close(self):
        self.fp.close()

    # -------------------------
    # Query parsing
    # -------------------------
    def _parse_query(self, raw):
        s = raw.strip()
        verbose = False
        is_and = False
        is_phrase = False
        fields = []

        while s.startswith("["):
            r = s.find("]")
            if r == -1:
                break
            tag = s[1:r].strip().upper()
            s = s[r + 1 :].lstrip()

            if tag == "VERBOSE":
                verbose = True
            elif tag == "AND":
                is_and = True
            elif tag == "PHRASE":
                is_phrase = True
            elif tag.startswith("FIELD="):
                v = tag.split("=", 1)[1].strip()
                if v in ("T", "A", "C"):
                    fields.append(v)

        if not fields:
            fields = ["T", "A", "C"]

        return verbose, is_and, is_phrase, fields, s

    # -------------------------
    # Postings
    # -------------------------
    def get_postings(self, term, field):
        if term not in self.term_dict:
            return []

        entry = self.term_dict[term]
        if field not in entry:
            return []

        start = int(entry[field]["start"])
        length = int(entry[field]["length"])
        if length <= 0:
            return []

        self.fp.seek(start)
        postings = []
        for _ in range(length):
            data = self.fp.read(8)
            if len(data) != 8:
                break
            doc_id, tf = struct.unpack("ii", data)
            postings.append((doc_id, tf))
        return postings

    def _idf(self, df):
        return math.log((self.N - df + 0.5) / (df + 0.5) + 1.0)

    # -------------------------
    # Load document fields
    # -------------------------
    def _load_fields(self, doc_id):
        meta = self.doc_table.get(str(doc_id))
        if meta is None:
            return "", "", ""

        path = meta.get("path", "")
        if not path:
            return "", "", ""

        if not os.path.isabs(path):
            path = os.path.join(self.index_dir, path)

        if not os.path.exists(path):
            return "", "", ""

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        ds = data.get("dataset", {}) or {}
        title = str(ds.get("invention_title") or "")
        abstract = str(ds.get("abstract") or "")

        # 과제 기준은 "claims" (사용자 최종 확정)
        claims = ds.get("claims", "")
        if claims is None:
            claims = ""
        claims = str(claims)

        return title, abstract, claims

    # -------------------------
    # VERBOSE helpers (80자 기준)
    # -------------------------
    def _unique_terms(self, terms):
        out = []
        for t in terms:
            if t and (t not in out):
                out.append(t)
        return out

    def _find_all_occurs(self, text, term):
        """term의 모든 시작 index를 찾음 (re 없이)"""
        res = []
        if not term:
            return res
        start = 0
        while True:
            i = text.find(term, start)
            if i == -1:
                break
            res.append(i)
            start = i + 1
        return res

    def _count_distinct_in_snip(self, snip, terms):
        found = []
        for t in terms:
            if t and (snip.find(t) != -1):
                found.append(t)
        return found  # distinct list

    def _make_window(self, text, center_idx):
        """
        center_idx가 최대한 중앙에 오게 80자 window 생성
        """
        if not text:
            return ""
        half = self.WINDOW_CHARS // 2  # 40
        s = center_idx - half
        if s < 0:
            s = 0
        e = s + self.WINDOW_CHARS
        if e > len(text):
            e = len(text)
            s = e - self.WINDOW_CHARS
            if s < 0:
                s = 0
        return text[s:e]

    def _best_window_char(self, text, terms):
        """
        반환: (best_snip, best_found_terms(list), best_center_dist)
        - best_found_terms: snippet 내 포함된 서로 다른 term들
        - best_center_dist: highlight 중심이 window 중앙과 얼마나 가까운지(작을수록 좋음)
        """
        if not text:
            return "", [], 10**9

        uniq_terms = self._unique_terms(terms)
        if not uniq_terms:
            snip = text[: self.WINDOW_CHARS]
            return snip, [], 10**9

        # 모든 term occurrence를 후보 center로 모음
        centers = []
        for t in uniq_terms:
            occ = self._find_all_occurs(text, t)
            for idx in occ:
                centers.append(idx)

        # term이 하나도 없으면 앞 80자
        if not centers:
            snip = text[: self.WINDOW_CHARS]
            return snip, [], 10**9

        # 너무 많이 돌 필요 없게 앞쪽/중간/뒤쪽 일부만 샘플링 (간단하게)
        # 그래도 규칙(서로 다른 term 최대)을 만족해야 하므로 전체를 다 돌려도 되지만,
        # 속도 부담 줄이기 위해 centers를 제한한다.
        # (과제 데이터에서도 충분히 동작하는 수준으로)
        if len(centers) > 200:
            step = len(centers) // 200
            centers = centers[::max(1, step)]

        best_snip = ""
        best_found = []
        best_cnt = -1
        best_center_dist = 10**9

        window_mid = self.WINDOW_CHARS // 2

        for c in centers:
            snip = self._make_window(text, c)
            found = self._count_distinct_in_snip(snip, uniq_terms)
            cnt = len(found)

            # window 중앙 정렬 점수: 후보 중심 c가 snip에서 어디에 있는지 계산
            # snip 시작 위치를 역산하기 위해 _make_window와 동일 로직 재계산
            half = self.WINDOW_CHARS // 2
            s = c - half
            if s < 0:
                s = 0
            e = s + self.WINDOW_CHARS
            if e > len(text):
                e = len(text)
                s = e - self.WINDOW_CHARS
                if s < 0:
                    s = 0

            c_in_snip = c - s
            dist = abs(c_in_snip - window_mid)

            # 1) 서로 다른 term 수 최대
            # 2) 동점이면 중앙에 더 가깝게
            if (cnt > best_cnt) or (cnt == best_cnt and dist < best_center_dist):
                best_cnt = cnt
                best_snip = snip
                best_found = found
                best_center_dist = dist

        return best_snip, best_found, best_center_dist

    def _highlight(self, text, terms):
        # 긴 term 먼저 감싸서 겹침을 줄임
        uniq = self._unique_terms(terms)
        uniq.sort(key=len, reverse=True)

        out = text
        for t in uniq:
            if t:
                out = out.replace(t, f"<<{t}>>")
        return out

    # -------------------------
    # BM25F
    # -------------------------
    def _bm25f(self, terms, fields):
        scores = {}
        useT = ("T" in fields)
        useA = ("A" in fields)
        useC = ("C" in fields)

        for t in terms:
            if t not in self.term_dict:
                continue

            df = int(self.term_dict[t]["df"])
            idf = self._idf(df)

            tf_map = {}  # doc_id -> [tfT, tfA, tfC]
            if useT:
                for d, tf in self.get_postings(t, "T"):
                    tf_map.setdefault(d, [0, 0, 0])[0] = tf
            if useA:
                for d, tf in self.get_postings(t, "A"):
                    tf_map.setdefault(d, [0, 0, 0])[1] = tf
            if useC:
                for d, tf in self.get_postings(t, "C"):
                    tf_map.setdefault(d, [0, 0, 0])[2] = tf

            for d, (tfT, tfA, tfC) in tf_map.items():
                meta = self.doc_table.get(str(d))
                if meta is None:
                    continue

                lenT = float(meta.get("len_T", 0))
                lenA = float(meta.get("len_A", 0))
                lenC = float(meta.get("len_C", 0))

                denomT = (1 - self.bT) + self.bT * (lenT / self.avgT)
                denomA = (1 - self.bA) + self.bA * (lenA / self.avgA)
                denomC = (1 - self.bC) + self.bC * (lenC / self.avgC)
                if denomT <= 0: denomT = 1.0
                if denomA <= 0: denomA = 1.0
                if denomC <= 0: denomC = 1.0

                tf_hat = 0.0
                if useT:
                    tf_hat += self.wT * (tfT / denomT)
                if useA:
                    tf_hat += self.wA * (tfA / denomA)
                if useC:
                    tf_hat += self.wC * (tfC / denomC)

                if tf_hat > 0:
                    score = idf * ((self.k1 + 1) * tf_hat) / (self.k1 + tf_hat)
                    scores[d] = scores.get(d, 0.0) + score

        return scores

    # -------------------------
    # AND filter (모든 term 최소 1회 등장 문서만)
    # -------------------------
    def _and_filter(self, terms, fields):
        must = None
        for t in terms:
            if t not in self.term_dict:
                return set()

            s = set()
            for f in fields:
                for d, _tf in self.get_postings(t, f):
                    s.add(d)

            if must is None:
                must = s
            else:
                must = must.intersection(s)

            if not must:
                break

        return must if must is not None else set()

    # -------------------------
    # PHRASE (Title exact substring)
    # -------------------------
    def _phrase_search(self, phrase, verbose):
        phrase = phrase.strip()
        terms = extract_terms(phrase)

        print("RESULT:")
        if verbose:
            print(f"검색어 입력: [VERBOSE][PHRASE]{phrase}")
        else:
            print(f"검색어 입력: [PHRASE]{phrase}")

        if not phrase or not terms:
            print("term이 없다.")
            return

        # 후보 doc: title postings 교집합
        cand = None
        for t in terms:
            docs = set(d for d, _tf in self.get_postings(t, "T"))
            cand = docs if cand is None else cand.intersection(docs)
            if not cand:
                break

        if not cand:
            print("해당 문서가 없다.")
            return

        hits = []
        for d in cand:
            title, _a, _c = self._load_fields(d)
            if phrase in title:
                hits.append(d)

        if not hits:
            print("해당 문서가 없다.")
            return

        scores = self._bm25f(terms, ["T"])
        hits.sort(key=lambda d: scores.get(d, 0.0), reverse=True)
        top = hits[:5]

        print(f"총 {len(hits)}개 문서 검색")
        print("상위 5개 문서:")
        for d in top:
            meta = self.doc_table.get(str(d), {})
            print(f"{meta.get('filename','')}\t{scores.get(d,0.0):.2f}")

        if not verbose:
            return

        print("-" * 60)
        for d in top:
            meta = self.doc_table.get(str(d), {})
            print(f"파일명: {meta.get('filename','')}, 점수: {scores.get(d,0.0):.2f}")

            title, _a, _c = self._load_fields(d)
            idx = title.find(phrase)
            if idx != -1:
                snip = self._make_window(title, idx)
                snip = snip.replace(phrase, f"<<{phrase}>>")
                print(f"[TITLE] {snip}")
            print("-" * 60)

    # -------------------------
    # VERBOSE printing
    # -------------------------
    def _verbose_or(self, doc_id, terms, fields):
        """
        OR + VERBOSE:
        - “서로 다른 검색어”가 가장 많이 포함된 snippet 1개만 출력
        - 동점이면 TITLE > ABSTRACT > CLAIMS
        """
        title, abstract, claims = self._load_fields(doc_id)

        order = []
        if "T" in fields: order.append(("TITLE", title))
        if "A" in fields: order.append(("ABSTRACT", abstract))
        if "C" in fields: order.append(("CLAIMS", claims))

        best_label = ""
        best_snip = ""
        best_found = []
        best_cnt = -1
        best_dist = 10**9

        # 동점이면 먼저 나온 필드 유지되도록 (TITLE->ABSTRACT->CLAIMS 순회)
        for label, text in order:
            snip, found, dist = self._best_window_char(text, terms)
            cnt = len(found)

            if (cnt > best_cnt) or (cnt == best_cnt and dist < best_dist):
                best_cnt = cnt
                best_dist = dist
                best_label = label
                best_snip = snip
                best_found = found

        if best_snip:
            print(f"[{best_label}] {self._highlight(best_snip, best_found)}")

    def _verbose_and(self, doc_id, terms, fields):
        """
        AND + VERBOSE:
        - 모든 term이 등장할 때까지(여러 부분) 출력
        - 매번 남은 term을 가장 많이 커버하는 snippet 선택
        - 동점이면 TITLE > ABSTRACT > CLAIMS
        """
        title, abstract, claims = self._load_fields(doc_id)

        order = []
        if "T" in fields: order.append(("TITLE", title))
        if "A" in fields: order.append(("ABSTRACT", abstract))
        if "C" in fields: order.append(("CLAIMS", claims))

        remaining = self._unique_terms(terms)

        # 너무 많이 출력하지 않게 제한 (예시 수준)
        for _ in range(5):
            if not remaining:
                break

            best_label = ""
            best_snip = ""
            best_found = []
            best_cnt = 0
            best_dist = 10**9

            for label, text in order:
                snip, found, dist = self._best_window_char(text, remaining)
                cnt = len(found)
                # 1) 남은 term 커버 수 최대
                # 2) 동점이면 중앙 정렬(dist)
                # 3) 필드 동점은 order가 먼저인 쪽 유지
                if (cnt > best_cnt) or (cnt == best_cnt and cnt > 0 and dist < best_dist):
                    best_cnt = cnt
                    best_dist = dist
                    best_label = label
                    best_snip = snip
                    best_found = found

            if best_cnt == 0 or not best_snip:
                break

            # AND는 예시처럼 해당 snippet에서 보이는 것들 중심으로 하이라이트
            print(f"[{best_label}] {self._highlight(best_snip, best_found)}")

            # remaining에서 제거
            new_rem = []
            for t in remaining:
                if t not in best_found:
                    new_rem.append(t)
            remaining = new_rem

    # -------------------------
    # Main
    # -------------------------
    def process_query(self, query):
        verbose, is_and, is_phrase, fields, rest = self._parse_query(query)

        if is_phrase and is_and:
            print("PHRASE와 AND는 같이 사용할 수 없습니다.")
            return

        if is_phrase:
            self._phrase_search(rest, verbose)
            return

        terms = extract_terms(rest)
        if not terms:
            print("term이 없다.")
            return

        scores = self._bm25f(terms, fields)

        if is_and:
            must = self._and_filter(terms, fields)
            scores = {d: s for d, s in scores.items() if d in must}

        print("RESULT:")
        # 과제 출력 포맷: 검색어 입력 줄은 원문 query 그대로가 가장 안전
        print(f"검색어 입력: {query}")

        if not scores:
            print("해당 문서가 없다.")
            return

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]

        print(f"총 {len(scores)}개 문서 검색")
        print("상위 5개 문서:")
        for d, s in ranked:
            meta = self.doc_table.get(str(d), {})
            print(f"{meta.get('filename','')}\t{s:.2f}")

        if not verbose:
            return

        print("-" * 60)
        for d, s in ranked:
            meta = self.doc_table.get(str(d), {})
            print(f"파일명: {meta.get('filename','')}, 점수: {s:.2f}")

            if is_and:
                self._verbose_and(d, terms, fields)
            else:
                self._verbose_or(d, terms, fields)

            print("-" * 60)
