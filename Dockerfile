# Helios staffing engine — API image (also reused for the optional Discord bot).
# FastAPI + the std-lib engine in src/ / eval/. The scored path needs no API key; set
# ANTHROPIC_API_KEY in the environment to enable the optional LLM note-parsing / narration.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first for layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application code + the dataset the engine reads at runtime.
COPY src/ ./src/
COPY api/ ./api/
COPY eval/ ./eval/
COPY bot/ ./bot/
COPY hackathon-dataset/ ./hackathon-dataset/
COPY state/ ./state/

EXPOSE 8000

# Default: serve the API. The bot service overrides this command in docker-compose.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
