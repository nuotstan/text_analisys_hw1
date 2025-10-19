import re
import json
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
import asyncio
from typing import List, Dict, Optional


class LawLinkExtractor:
    def __init__(self, law_aliases_path="law_aliases.json"):
        self.law_aliases = self._load_law_aliases(law_aliases_path)
        self.law_names = []
        for key, value in self.law_aliases.items():
            self.law_names.extend(value)

    def _load_law_aliases(self, law_aliases_path):
        """Загружает law_aliases.json."""
        with open(law_aliases_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _find_law_id(self, law_name):
        """Находит law_id по названию закона, используя нечеткий поиск."""
        if not law_name:
            return None
            
        # Сначала попробуем точное совпадение
        for law_id, aliases in self.law_aliases.items():
            for alias in aliases:
                if law_name.lower().strip() == alias.lower().strip():
                    return int(law_id)
        
        # Простая нормализация (убираем лишние пробелы и приводим к нижнему регистру)
        law_name_normalized = ' '.join(law_name.lower().split())
        for law_id, aliases in self.law_aliases.items():
            for alias in aliases:
                alias_normalized = ' '.join(alias.lower().split())
                if law_name_normalized == alias_normalized:
                    return int(law_id)

        # Fuzzy matching
        best_match, score = process.extractOne(law_name, self.law_names, scorer=fuzz.ratio)
        if score > 75:  # threshold
            for law_id, aliases in self.law_aliases.items():
                for alias in aliases:
                    if best_match == alias:
                        return int(law_id)

        return None

    def _parse_subpoints(self, subpoint_text: str) -> List[str]:
        """Парсит подпункты из текста типа '1, 2, 3' или 'а, б, в'"""
        if not subpoint_text:
            return []
        
        # Убираем лишние пробелы и разбиваем по запятым
        subpoints = [sp.strip() for sp in subpoint_text.split(',')]
        # Убираем пустые элементы
        return [sp for sp in subpoints if sp]

    def _parse_complex_subpoints(self, subpoint_text: str) -> List[str]:
        """Парсит сложные подпункты типа 'а, б и с'"""
        if not subpoint_text:
            return []
        
        # Обрабатываем "а, б и с" -> ["а", "б", "с"]
        subpoints = []
        # Разбиваем по запятым и "и"
        parts = re.split(r'[,и]', subpoint_text)
        for part in parts:
            part = part.strip()
            if part:
                subpoints.append(part)
        
        return subpoints

    async def find_links_from_text(self, text: str) -> List[Dict]:
        """
        Правильный алгоритм извлечения ссылок:
        1. Нормализуем текст
        2. Ищем все возможные названия законов в тексте
        3. Сопоставляем с базой алиасов
        4. Извлекаем номера статей, пунктов, подпунктов рядом с найденными законами
        """
        links = []
        
        # Нормализуем текст
        normalized_text = ' '.join(text.split())
        
        # Ищем все возможные названия законов в тексте
        for law_id, aliases in self.law_aliases.items():
            for alias in aliases:
                # Ищем упоминания этого алиаса в тексте
                alias_positions = []
                start = 0
                while True:
                    pos = normalized_text.lower().find(alias.lower(), start)
                    if pos == -1:
                        break
                    alias_positions.append(pos)
                    start = pos + 1
                
                # Для каждого найденного упоминания ищем рядом статьи, пункты, подпункты
                for pos in alias_positions:
                    # Ищем в окрестности ±200 символов от найденного алиаса
                    context_start = max(0, pos - 200)
                    context_end = min(len(normalized_text), pos + 200)
                    context = normalized_text[context_start:context_end]
                    
                    # Ищем статьи, пункты, подпункты в контексте
                    found_links = self._extract_links_from_context(context, int(law_id))
                    links.extend(found_links)
        
        # Убираем дубликаты
        unique_links = []
        seen = set()
        for link in links:
            link_key = (link["law_id"], link["article"], link["point_article"], link["subpoint_article"])
            if link_key not in seen:
                seen.add(link_key)
                unique_links.append(link)
        
        return unique_links
    
    def _extract_links_from_context(self, context: str, law_id: int) -> List[Dict]:
        """Извлекает ссылки из контекста вокруг найденного закона"""
        links = []
        
        # Паттерны для поиска статей, пунктов, подпунктов
        patterns = [
            # пп. 1, 2, 3 п. 1 ст. 374
            r'пп\.?\s*([^п]+?)\s+п\.?\s*([0-9]+(?:\.[0-9]+)*)\s+ст\.?\s*([0-9]+(?:\.[0-9]+)*)',
            # п. 1 ст. 374
            r'п\.?\s*([0-9]+(?:\.[0-9]+)*)\s+ст\.?\s*([0-9]+(?:\.[0-9]+)*)',
            # ст. 374
            r'ст\.?\s*([0-9]+(?:\.[0-9]+)*)',
            # статья 374
            r'стать[еи]\s+([0-9]+(?:\.[0-9]+)*)',
            # пункта а ст. 20
            r'пункта\s+([а-я])\s+ст\.?\s*([0-9]+(?:\.[0-9]+)*)',
            # пункте 1 статьи 34
            r'пункте\s+([0-9]+(?:\.[0-9]+)*)\s+статьи\s+([0-9]+(?:\.[0-9]+)*)',
            # подпункту 2 пунта б статьи 22
            r'подпункту\s+([0-9]+)\s+пунта\s+([а-я])\s+статьи\s+([0-9]+(?:\.[0-9]+)*)',
            # подпунктах а, б и с пункта 3.345, 23 в статье 66
            r'подпунктах\s+([^п]+?)\s+пункта\s+([^в]+?)\s+в\s+статье\s+([0-9]+(?:\.[0-9]+)*)',
            # часть 3, ст. 30.1
            r'часть\s+([0-9]+),\s*ст\.?\s*([0-9]+(?:\.[0-9]+)*)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, context, re.IGNORECASE)
            for match in matches:
                groups = match.groups()
                match_text = match.group(0)
                
                if len(groups) == 3:  # пп. п. ст. или подпунктах а, б и с
                    if 'подпунктах' in match_text:
                        # подпунктах а, б и с пункта 3.345, 23 в статье 66
                        subpoints_text, point_text, article_text = groups
                        subpoints = self._parse_complex_subpoints(subpoints_text)
                        for subpoint in subpoints:
                            links.append({
                                "law_id": law_id,
                                "article": article_text.strip(),
                                "point_article": point_text.strip(),
                                "subpoint_article": subpoint
                            })
                    else:
                        # пп. 1 п. 1 ст. 374
                        subpoint_text, point_text, article_text = groups
                        subpoints = self._parse_subpoints(subpoint_text)
                        if subpoints:
                            for subpoint in subpoints:
                                links.append({
                                    "law_id": law_id,
                                    "article": article_text.strip(),
                                    "point_article": point_text.strip(),
                                    "subpoint_article": subpoint
                                })
                        else:
                            links.append({
                                "law_id": law_id,
                                "article": article_text.strip(),
                                "point_article": point_text.strip(),
                                "subpoint_article": None
                            })
                
                elif len(groups) == 2:  # п. ст., пункта а ст., пункте 1 статьи, часть 3, ст.
                    if 'часть' in match_text:
                        # часть 3, ст. 30.1
                        part_text, article_text = groups
                        links.append({
                            "law_id": law_id,
                            "article": article_text.strip(),
                            "point_article": part_text.strip(),
                            "subpoint_article": None
                        })
                    elif 'пункта' in match_text:
                        # пункта а ст. 20
                        point_text, article_text = groups
                        links.append({
                            "law_id": law_id,
                            "article": article_text.strip(),
                            "point_article": point_text.strip(),
                            "subpoint_article": None
                        })
                    elif 'пункте' in match_text:
                        # пункте 1 статьи 34
                        point_text, article_text = groups
                        links.append({
                            "law_id": law_id,
                            "article": article_text.strip(),
                            "point_article": point_text.strip(),
                            "subpoint_article": None
                        })
                    else:
                        # п. 1 ст. 374
                        point_text, article_text = groups
                        links.append({
                            "law_id": law_id,
                            "article": article_text.strip(),
                            "point_article": point_text.strip(),
                            "subpoint_article": None
                        })
                
                elif len(groups) == 1:  # ст. 374, статья 374
                    article_text = groups[0]
                    links.append({
                        "law_id": law_id,
                        "article": article_text.strip(),
                        "point_article": None,
                        "subpoint_article": None
                    })
        
        # Убираем дубликаты
        unique_links = []
        seen = set()
        for link in links:
            link_key = (link["law_id"], link["article"], link["point_article"], link["subpoint_article"])
            if link_key not in seen:
                seen.add(link_key)
                unique_links.append(link)
        
        return unique_links


async def find_links(text: str) -> List[Dict]:
    """
    Основная функция для извлечения ссылок из текста.
    Возвращает список словарей с найденными ссылками.
    """
    extractor = LawLinkExtractor()
    links = await extractor.find_links_from_text(text)
    return links



