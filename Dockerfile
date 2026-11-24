FROM node:22-alpine AS ui
WORKDIR /ui
COPY frontend/package*.json ./
RUN --mount=type=secret,id=build_ca if [ -s /run/secrets/build_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/build_ca; fi && npm ci
COPY frontend/ ./
RUN npm run build
FROM python:3.12-slim
WORKDIR /app
COPY requirements*.txt ./
RUN --mount=type=secret,id=build_ca if [ -s /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi && pip install --no-cache-dir -r requirements.txt -r requirements-metrics.txt
RUN --mount=type=bind,source=.,target=/src --mount=type=bind,from=ui,source=/ui/dist,target=/dist cp -r /src/backend /src/migrations /src/fixtures /src/alembic.ini /app/ && mkdir -p frontend && cp -r /dist frontend/dist
ENV DEEPEVAL_TELEMETRY_OPT_OUT=YES RAGAS_DO_NOT_TRACK=true
CMD ["python","-m","backend.serve"]
