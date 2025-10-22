#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from typing import Set

# Константы для продвинутого алгоритма

DOC_ANCHORS: Set[str] = {"закон", "кодекс", "указ", "постановление", "положение", "правило", "правила"}
ABBR_LEMMAS: Set[str] = {"апк", "гк", "гпк", "ук", "нк", "жк", "ск", "тк", "коап", "рф", "фз"}
OPTIONAL_LEMMAS: Set[str] = {"российский", "федерация", "рф", "россия", "федеральный"}


# Регулярные выражения для токенизации

CYR_WORD_RE = re.compile(r"^[А-Яа-яЁё]+$")
UPPER_CYR_RE = re.compile(r"^[А-ЯЁ]{2,}$")
MIXED_CYR_RE = re.compile(r"^[А-ЯЁ][а-яё]+$")
NUM_RE = re.compile(r"^\d+(?:\.\d+)*(?:[-–—]\d+(?:\.\d+)*)?$")
PUNCT_RE = re.compile(r"^[\.\,\;\:\!\?KATEX_INLINE_OPENKATEX_INLINE_CLOSE```math```\{\}\"«»""„‟‹›—–\-]+$")

TOKENIZER_RE = re.compile(
    r"""
    (№)|
    (\d+(?:\.\d+)*(?:[-–—]\d+(?:\.\d+)*)?)|
    ([A-Za-z]+)|
    ([А-ЯЁ]{2,})|
    ([А-ЯЁ][а-яё]+)|
    ([а-яё]+)|
    ([\.\,\;\:\!\?KATEX_INLINE_OPENKATEX_INLINE_CLOSE```math
```\{\}\"«»""„‟‹›—–\-])
    """,
    re.VERBOSE | re.U
)


# Регулярные выражения для поиска ссылок

NUM_OR_LETTER = r'(?:\d+(?:\.\d+)*(?:\s*[-–—]\s*\d+(?:\.\d+)*)?|[а-я])'
LIST_EXPR = rf'(?:{NUM_OR_LETTER})(?:\s*,\s*{NUM_OR_LETTER})*(?:\s*(?:и|или)\s*{NUM_OR_LETTER})?'
ART_LIST = r'\d+(?:\.\d+)*(?:\s*,\s*\d+(?:\.\d+)*)?(?:\s*(?:и|или)\s*\d+(?:\.\d+)*)?'

SUB_LABEL_RE = r'(?:подпункт[а-я]*|пп\.?)'
PT_LABEL_RE  = r'(?:пункт[а-я]*|п\.|част[ьи][а-я]*|ч\.)'
ART_LABEL_RE = r'(?:ст\.?|стать[яеию])'
PT_ART_SEP = r'(?:\s*(?:,|;)?\s*(?:в|во)?\s*)?'

MAIN_RE = re.compile(
    rf"""
    (?:
        (?P<sub_label>{SUB_LABEL_RE})
        \s*
        (?P<sub_list>{LIST_EXPR})
        \s*
    )?
    (?:
        (?P<pt_label>{PT_LABEL_RE})
        \s*
        (?P<pt_list>{LIST_EXPR})
        \s*
        {PT_ART_SEP}
    )?
    (?P<art_label>{ART_LABEL_RE})
    \s*
    (?P<art_list>{ART_LIST})
    """,
    re.IGNORECASE | re.VERBOSE | re.U,
)

PT_ONLY_RE = re.compile(
    rf"""
    (?P<pt_label>{PT_LABEL_RE})
    \s*
    (?P<pt_list>{LIST_EXPR})
    """,
    re.IGNORECASE | re.VERBOSE | re.U,
)

# Дополнительный паттерн для ссылок в формате "статье N закона"
ARTICLE_LAW_RE = re.compile(
    rf"""
    (?P<art_label>{ART_LABEL_RE})
    \s*
    (?P<art_list>{ART_LIST})
    \s+
    (?P<law_name>[А-Я][^,\.\s]+(?:\s+[А-Я][^,\.\s]+)*)
    """,
    re.IGNORECASE | re.VERBOSE | re.U,
)


# Константы для разворачивания подпунктов
RUS_ALPHA = list("абвгдеёжзийклмнопрстуфхцчшщъыьэюя")
RUS_INDEX = {ch: i for i, ch in enumerate(RUS_ALPHA)}

# ==========================
# Регулярные выражения для токенизации
# ==========================

CYR_WORD_RE = re.compile(r"^[А-Яа-яЁё]+$")
UPPER_CYR_RE = re.compile(r"^[А-ЯЁ]{2,}$")
MIXED_CYR_RE = re.compile(r"^[А-ЯЁ][а-яё]+$")
NUM_RE = re.compile(r"^\d+(?:\.\d+)*(?:[-–—]\d+(?:\.\d+)*)?$")
PUNCT_RE = re.compile(r"^[\.\,\;\:\!\?KATEX_INLINE_OPENKATEX_INLINE_CLOSE```math```\{\}\"«»""„‟‹›—–\-]+$")

TOKENIZER_RE = re.compile(
    r"""
    (№)|
    (\d+(?:\.\d+)*(?:[-–—]\d+(?:\.\d+)*)?)|
    ([A-Za-z]+)|
    ([А-ЯЁ]{2,})|
    ([А-ЯЁ][а-яё]+)|
    ([а-яё]+)|
    ([\.\,\;\:\!\?KATEX_INLINE_OPENKATEX_INLINE_CLOSE```math
```\{\}\"«»""„‟‹›—–\-])
    """,
    re.VERBOSE | re.U
)
