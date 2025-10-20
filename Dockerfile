FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y locales && \
    locale-gen ru_RU.UTF-8 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ENV LANG ru_RU.UTF-8
ENV LANGUAGE ru_RU.UTF-8
ENV LC_ALL ru_RU.UTF-8

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY law_aliases.json .
COPY process_text.py .
COPY const.py .

EXPOSE 8978

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8978"]