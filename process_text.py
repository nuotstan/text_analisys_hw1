#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any, Set

# Импортируем все константы и регулярки
from const import (
    DOC_ANCHORS, ABBR_LEMMAS, OPTIONAL_LEMMAS,
    CYR_WORD_RE, UPPER_CYR_RE, MIXED_CYR_RE, NUM_RE, PUNCT_RE, TOKENIZER_RE,
    NUM_OR_LETTER, LIST_EXPR, ART_LIST, SUB_LABEL_RE, PT_LABEL_RE, ART_LABEL_RE, PT_ART_SEP,
    MAIN_RE, PT_ONLY_RE, RUS_ALPHA, RUS_INDEX
)

try:
    import pymorphy3
    MORPH = pymorphy3.MorphAnalyzer()
except ImportError:
    print("Не установлен pymorphy3. Установите: pip install pymorphy3")
    MORPH = None

@dataclass
class Token:
    text: str
    lemma: str
    is_punct: bool

def tokenize(text: str) -> List[str]:
    return [next(g for g in m.groups() if g is not None) for m in TOKENIZER_RE.finditer(text)]

def _morph_lemma(tok: str) -> str:
    if MORPH is None:
        return tok.lower().replace("ё", "е")
    try:
        p = MORPH.parse(tok)[0]
        return p.normal_form.replace("ё", "е")
    except Exception:
        return tok.lower().replace("ё", "е")

def lemma_of_token(tok: str) -> str:
    if tok == "№":
        return tok
    if NUM_RE.match(tok):
        return tok.replace("–", "-").replace("—", "-")
    if PUNCT_RE.match(tok):
        return tok
    if re.match(r"^[A-Za-z]+$", tok):
        return tok.lower()
    if UPPER_CYR_RE.match(tok):
        return tok.lower().replace("ё", "е")
    if MIXED_CYR_RE.match(tok) or CYR_WORD_RE.match(tok):
        return _morph_lemma(tok)
    return tok.lower().replace("ё", "е")

def to_tokens(text: str) -> List[Token]:
    toks = tokenize(text)
    return [Token(text=t, lemma=lemma_of_token(t), is_punct=bool(PUNCT_RE.match(t))) for t in toks]

def join_lemmas(tokens: List[Token], i: int, j: int) -> str:
    return " ".join(tok.lemma for tok in tokens[i:j] if not tok.is_punct)

def join_lemmas_compact(tokens: List[Token], i: int, j: int, optional: Set[str]) -> str:
    return " ".join(tok.lemma for tok in tokens[i:j] if (not tok.is_punct) and (tok.lemma not in optional))


@dataclass
class LawCandidate:
    law_id: int
    i: int
    j: int
    kind: str     # "exact" | "compact"
    tok_count: int
    has_abbr: bool

class LawAliasIndex:
    def __init__(self, alias_json: Dict[str, List[str]], allow_compact: bool = False):
        self.allow_compact = allow_compact
        self.lemma_to_id: Dict[str, int] = {}
        self.compact_to_id: Dict[str, int] = {}
        self.max_alias_len = 1

        compact_to_ids: Dict[str, Set[int]] = {}

        for sid, variants in alias_json.items():
            try:
                law_id = int(sid)
            except Exception:
                continue
            for v in variants:
                toks = [tok for tok in to_tokens(v) if not tok.is_punct]
                lemmas = [tok.lemma for tok in toks]
                if not lemmas:
                    continue

                key = " ".join(lemmas)
                if key not in self.lemma_to_id:
                    self.lemma_to_id[key] = law_id
                self.max_alias_len = max(self.max_alias_len, len(lemmas))

                if self.allow_compact:
                    compact_tokens = [l for l in lemmas if l not in OPTIONAL_LEMMAS]
                    if len(compact_tokens) >= 2:
                        compact_key = " ".join(compact_tokens)
                        compact_to_ids.setdefault(compact_key, set()).add(law_id)

        if self.allow_compact:
            self.compact_to_id = {k: next(iter(v)) for k, v in compact_to_ids.items() if len(v) == 1}

    def _collect_candidates(self, toks: List[Token]) -> List[LawCandidate]:
        n = len(toks)
        cands: List[LawCandidate] = []
        if n == 0:
            return cands

        max_len = min(self.max_alias_len, n)
        for length in range(max_len, 0, -1):
            for i in range(0, n - length + 1):
                j = i + length

                key = join_lemmas(toks, i, j)
                if key in self.lemma_to_id:
                    has_abbr = any(t.lemma in ABBR_LEMMAS for t in toks[i:j])
                    tok_cnt = len([t for t in toks[i:j] if not t.is_punct])
                    cands.append(LawCandidate(self.lemma_to_id[key], i, j, "exact", tok_cnt, has_abbr))
                    continue

                if self.allow_compact:
                    ckey = join_lemmas_compact(toks, i, j, OPTIONAL_LEMMAS)
                    if ckey and (len(ckey.split()) >= 2) and (ckey in self.compact_to_id):
                        has_abbr = any(t.lemma in ABBR_LEMMAS for t in toks[i:j])
                        tok_cnt = len(ckey.split())
                        cands.append(LawCandidate(self.compact_to_id[ckey], i, j, "compact", tok_cnt, has_abbr))
        return cands

    @staticmethod
    def _rank(c: LawCandidate) -> Tuple[int, int, int, int]:
        kind_rank = 0 if c.kind == "exact" else 1
        abbr_rank = 0 if c.has_abbr else 1
        return (kind_rank, c.i, -c.tok_count, abbr_rank)

    def best_in_tokens(self, toks: List[Token]) -> Optional[int]:
        cands = self._collect_candidates(toks)
        if not cands:
            return None
        cands.sort(key=self._rank)
        return cands[0].law_id

def _build_lookahead_window(post_text: str, max_nonpunct_lookahead: int) -> List[Token]:
    toks = to_tokens(post_text)
    window: List[Token] = []
    nonp = 0

    in_ascii = False
    in_angle = False
    in_smart = False
    anchor_before_quotes = False

    def in_quotes() -> bool:
        return in_ascii or in_angle or in_smart

    for t in toks:
        window.append(t)
        if not t.is_punct:
            nonp += 1
            if t.lemma in DOC_ANCHORS or t.lemma in ABBR_LEMMAS:
                anchor_before_quotes = True

        if t.text == '"':
            in_ascii = not in_ascii
        elif t.text == '«':
            in_angle = True
        elif t.text == '»':
            in_angle = False
        elif t.text in {'"', '„'}:
            in_smart = True
        elif t.text in {'"', '‟'}:
            in_smart = False

        if nonp >= max_nonpunct_lookahead and not (anchor_before_quotes and in_quotes()):
            break

        if len(window) > 800:
            break

    return window

def find_law_after(text: str, start_char: int, idx: LawAliasIndex, max_nonpunct_lookahead: int = 12) -> Optional[int]:
    post_text = text[start_char:]
    window = _build_lookahead_window(post_text, max_nonpunct_lookahead)
    if not window:
        return None
    return idx.best_in_tokens(window)

def has_article_label_ahead(text: str, start_char: int, max_nonpunct_lookahead: int = 12) -> bool:
    post_text = text[start_char:]
    toks = to_tokens(post_text)
    cnt = 0
    for t in toks:
        if not t.is_punct:
            cnt += 1
            if t.lemma == "статья" or t.lemma == "ст":
                return True
            if cnt >= max_nonpunct_lookahead:
                break
    return False


def norm_list_text(s: Optional[str]) -> str:
    if not s:
        return ""
    s = s.strip()
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"\s*-\s*", "-", s)
    s = re.sub(r"\s+", " ", s)
    return s

def _expand_numeric_range(a: str, b: str) -> Optional[List[str]]:
    if not (a.isdigit() and b.isdigit()):
        return None
    start, end = int(a), int(b)
    if start > end:
        return None
    # ограничение на раздувание, чтобы не улететь в сотни ссылок
    if end - start > 400:
        return None
    return [str(x) for x in range(start, end + 1)]

def _expand_letter_range(a: str, b: str) -> Optional[List[str]]:
    a = a.lower().replace("ё", "е")
    b = b.lower().replace("ё", "е")
    if a not in RUS_INDEX or b not in RUS_INDEX:
        return None
    ia, ib = RUS_INDEX[a], RUS_INDEX[b]
    if ia > ib:
        return None
    if ib - ia > 40:
        return None
    return [RUS_ALPHA[i] for i in range(ia, ib + 1)]

def expand_subpoints(sub_list: str) -> List[str]:
    """
    Разворачивает перечень подпунктов:
    - разделители: запятые, 'и', 'или'
    - диапазоны чисел: 6-12 -> 6,7,8,9,10,11,12
    - диапазоны букв: а-г -> а,б,в,г
    """
    if not sub_list:
        return [""]
    # заменяем ' и ' / ' или ' на запятые
    tmp = re.sub(r"\s+(?:и|или)\s+", ",", sub_list.strip(), flags=re.IGNORECASE)
    raw_items = [x.strip() for x in tmp.split(",") if x.strip()]
    out: List[str] = []
    for it in raw_items:
        it_norm = it.replace("–", "-").replace("—", "-").strip()
        m_num = re.match(r"^(\d+)\-(\d+)$", it_norm)
        if m_num:
            a, b = m_num.group(1), m_num.group(2)
            exp = _expand_numeric_range(a, b)
            if exp:
                out.extend(exp)
                continue
        m_let = re.match(r"^([А-Яа-яЁё])\-([А-Яа-яЁё])$", it_norm)
        if m_let:
            a, b = m_let.group(1), m_let.group(2)
            exp = _expand_letter_range(a, b)
            if exp:
                out.extend(exp)
                continue
        out.append(it_norm)
    return out if out else [""]

def build_link(law_id: int, article: str, point_article: str = "", subpoint_article: str = "") -> Dict[str, Any]:
    return {
                    "law_id": law_id,
                    "article": article if article else None,
                    "point_article": point_article if point_article else None,
                    "subpoint_article": subpoint_article if subpoint_article else None,
                }

def extract_links(text: str, idx: LawAliasIndex, lookahead: int = 12) -> List[Dict[str, Any]]:
    links: List[Dict[str, Any]] = []
    used_spans: List[Tuple[int, int]] = []

    def overlaps(a: Tuple[int, int], b: Tuple[int, int]) -> bool:
        return not (a[1] <= b[0] or b[1] <= a[0])

    print(f"DEBUG: Ищем паттерны MAIN_RE в тексте: '{text}'")
    main_matches = list(MAIN_RE.finditer(text))
    print(f"DEBUG: Найдено MAIN_RE совпадений: {len(main_matches)}")
    
    # 1) [подпункт?] [пункт/часть?] ст. N ...
    for m in main_matches:
        span = m.span()
        if any(overlaps(span, s) for s in used_spans):
            continue

        law_id = find_law_after(text, m.end(), idx, max_nonpunct_lookahead=lookahead)
        if law_id is None:
            continue

        sub_list = norm_list_text(m.group("sub_list"))
        pt_list  = norm_list_text(m.group("pt_list"))
        art_list = norm_list_text(m.group("art_list"))

        # Подпункты разворачиваем ТОЛЬКО если распознан пункт/часть
        if sub_list and pt_list:
            for sub in expand_subpoints(sub_list):
                links.append(build_link(law_id, article=art_list, point_article=pt_list, subpoint_article=sub))
        else:
            links.append(build_link(law_id, article=art_list, point_article=pt_list, subpoint_article=""))

        used_spans.append(span)

    # 2) п./ч. N ...
    for m in PT_ONLY_RE.finditer(text):
        span = m.span()
        if any(overlaps(span, s) for s in used_spans):
            continue

        if has_article_label_ahead(text, m.end(), max_nonpunct_lookahead=lookahead):
            continue

        law_id = find_law_after(text, m.end(), idx, max_nonpunct_lookahead=lookahead)
        if law_id is None:
            continue

        links.append(build_link(law_id, article="", point_article="", subpoint_article=""))
        used_spans.append(span)

    return links

# Глобальный индекс законов (инициализируется при старте приложения)
_global_law_index = None

def initialize_law_index(aliases: Dict[str, List[str]]) -> None:
    """
    Инициализирует глобальный индекс законов при старте приложения.
    """
    global _global_law_index
    try:
        _global_law_index = LawAliasIndex(aliases, allow_compact=True)
        print(f"✅ Индекс законов инициализирован: {len(aliases)} законов")
    except Exception as e:
        print(f"❌ Ошибка инициализации индекса: {e}")
        _global_law_index = None

async def find_links(text: str) -> List[Dict]:
    """
    Основная функция для извлечения ссылок из текста.
    Использует продвинутый алгоритм с лемматизацией и морфологическим анализом.
    """
    global _global_law_index
    
    try:
        if _global_law_index is None:
            print("❌ Индекс законов не инициализирован!")
            return []
        
        # Извлекаем ссылки используя глобальный индекс
        print(f"DEBUG: Ищем ссылки в тексте: '{text}'")
        links = extract_links(text, _global_law_index, lookahead=12)
        print(f"DEBUG: extract_links вернул: {links}")
        return links if links is not None else []
    except Exception as e:
        print(f"Ошибка в find_links: {e}")
        import traceback
        traceback.print_exc()
        return []