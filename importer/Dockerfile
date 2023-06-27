FROM python:bullseye

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt
COPY weaviate_client-3.19.3.dev20+gca4f188-py3-none-any.whl .
RUN pip install weaviate_client-3.19.3.dev20+gca4f188-py3-none-any.whl

COPY *.py .
