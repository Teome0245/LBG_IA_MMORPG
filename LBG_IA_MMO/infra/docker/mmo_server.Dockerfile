FROM python:3.11-slim

WORKDIR /app
COPY LBG_IA_MMO/mmo_server /app

RUN pip install --no-cache-dir -U pip \
  && pip install --no-cache-dir .

CMD ["python", "main.py"]

