import json
from typing import List, Optional, Dict

import uvicorn
from fastapi import FastAPI, Request, Depends
from pydantic import BaseModel
from contextlib import asynccontextmanager

from process_text import find_links


class LawLink(BaseModel):
    law_id: Optional[int] = None
    article: Optional[str] = None
    point_article: Optional[str] = None
    subpoint_article: Optional[str] = None


class LinksResponse(BaseModel):
    links: List[LawLink]


class TextRequest(BaseModel):
    text: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    with open("law_aliases.json", "r") as file:
        codex_aliases = json.load(file)
    
    app.state.codex_aliases = codex_aliases
    print("🚀 Сервис запускается...")
    yield
    # Shutdown
    del codex_aliases
    print("🛑 Сервис завершается...")


def get_codex_aliases(request: Request) -> Dict:
    return request.app.state.codex_aliases


app = FastAPI(
    title="Law Links Service",
    description="Cервис для выделения юридических ссылок из текста",
    version="1.0.0",
    lifespan=lifespan
)


@app.post("/detect")
async def get_law_links(
    data: TextRequest,
    request: Request,
    codex_aliases: Dict = Depends(get_codex_aliases),
    ) -> LinksResponse:
    """
    Принимает текст и возвращает список юридических ссылок
    """
    # Место для алгоритма распознавания ссылок
    print(f"Получен текст: {data.text[:100]}...")
    try:
        all_links = await find_links(data.text)
        if all_links is None:
            all_links = []
        print(f"Найдено ссылок: {len(all_links)}")
        print(f"Ссылки: {all_links}")
        
        # Преобразуем найденные ссылки в объекты LawLink
        law_links = []
        for link_data in all_links:
            law_link = LawLink(
                law_id=link_data.get("law_id"),
                article=link_data.get("article"),
                point_article=link_data.get("point_article"),
                subpoint_article=link_data.get("subpoint_article")
            )
            law_links.append(law_link)
        
        print(f"Возвращаем {len(law_links)} ссылок")
        return LinksResponse(links=law_links)
    except Exception as e:
        print(f"Ошибка при обработке: {e}")
        import traceback
        traceback.print_exc()
        return LinksResponse(links=[])


@app.get("/health")
async def health_check():
    """
    Проверка состояния сервиса
    """
    return {"status": "healthy"}



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8978)