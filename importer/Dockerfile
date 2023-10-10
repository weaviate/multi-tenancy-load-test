FROM python:3.11-bullseye

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt
COPY weaviate_client-3.21.1.dev14+g18eb192-py3-none-any.whl .
RUN pip install weaviate_client-3.21.1.dev14+g18eb192-py3-none-any.whl

COPY *.py ./
