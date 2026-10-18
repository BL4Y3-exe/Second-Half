# Second Half in one image: the API, the MCP endpoint and the built web app on port 8000.
#   docker build -t second-half .
#   docker run -p 8000:8000 second-half                  (mock model)
#   docker run -p 8000:8000 --env-file .env second-half  (Foundry settings; needs a credential, see README)

# 1. Build the web app.
FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# 2. The Python app.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY agents agents
COPY api api
COPY mcp_server mcp_server
COPY plugins plugins
COPY simulator simulator
COPY stats stats
COPY --from=web /web/dist web/dist
RUN useradd --create-home --uid 1000 app
USER app
EXPOSE 8000
CMD ["python", "-m", "api", "--host", "0.0.0.0", "--port", "8000"]
