FROM ghcr.io/astral-sh/uv:0.12.22@sha256:f513a91fc62fe7c17567eee97230dd198e43edb8a9fbecca843714a4358fe1bc AS uv
FROM python:3.12.15-slim-bookworm@sha256:54c85f3c47607a77f32adec749d3c81d1348bf25833671f512b26a9b6d778cb3 AS dependencies

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    SQLMESH__DISABLE_ANONYMIZED_ANALYTICS=true
COPY --from=uv /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev libpq-dev=15.19-0+deb12u1 \
    && uv sync --frozen --no-dev --no-install-project

FROM python:3.12.15-slim-bookworm@sha256:54c85f3c47607a77f32adec749d3c81d1348bf25833671f512b26a9b6d778cb3
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    SQLMESH__DISABLE_ANONYMIZED_ANALYTICS=true
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libpq5=15.19-0+deb12u1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 sqlmesh
COPY --from=dependencies /app/.venv /app/.venv
COPY --chown=sqlmesh:sqlmesh config.py external_models.yaml start.sh ./
COPY --chown=sqlmesh:sqlmesh models/ models/
COPY --chown=sqlmesh:sqlmesh audits/ audits/
COPY --chown=sqlmesh:sqlmesh tests/ tests/
COPY --chown=sqlmesh:sqlmesh scripts/ scripts/
COPY LICENSE ./LICENSE
COPY THIRD_PARTY_NOTICES.md runtime-license-inventory.json ./
RUN chmod 0555 start.sh && chown sqlmesh:sqlmesh /app
USER 10001:10001
CMD ["./start.sh"]
