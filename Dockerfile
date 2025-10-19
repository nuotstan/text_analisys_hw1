FROM python:3.12-slim

WORKDIR /app

# Устанавливаем системные зависимости для pymorphy2
RUN apt-get update && apt-get install -y locales && \
    locale-gen ru_RU.UTF-8 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Устанавливаем переменные окружения для локали
ENV LANG ru_RU.UTF-8
ENV LANGUAGE ru_RU.UTF-8
ENV LC_ALL ru_RU.UTF-8

# Копируем и устанавливаем Python зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY main.py .
COPY law_aliases.json .
COPY process_text.py .

EXPOSE 8978

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8978"]