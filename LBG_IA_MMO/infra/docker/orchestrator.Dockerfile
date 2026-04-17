FROM python:3.11-slim

COPY LBG_IA_MMO/agents /deps/agents
WORKDIR /deps/agents
RUN pip install --no-cache-dir -U pip \
  && pip install --no-cache-dir .

WORKDIR /app
COPY LBG_IA_MMO/orchestrator /app

RUN pip install --no-cache-dir -U pip \
  && pip install --no-cache-dir .

EXPOSE 8010
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8010"]

