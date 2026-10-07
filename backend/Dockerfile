FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home appuser
COPY backend/ ./
COPY docs/openapi.json ./openapi.json
ENV API_CONTRACT_PATH=/app/openapi.json
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && python -m app.demo && uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log"]
