# Sqube Agent Control — control plane (API + dashboard) image.
#
#   docker build -t sqube-agent-control .
#   docker run -p 8080:8080 -v sqube-data:/data sqube-agent-control
#
# Then open http://127.0.0.1:8080/setup to create the admin account.

FROM python:3.12-slim AS build
WORKDIR /src
RUN pip install --no-cache-dir build
COPY pyproject.toml README.pypi.md LICENSE ./
COPY src ./src
RUN python -m build --wheel --outdir /dist

FROM python:3.12-slim
LABEL org.opencontainers.image.title="sqube-agent-control" \
      org.opencontainers.image.description="Sqube Agent Control: execution authorization control plane for AI agents" \
      org.opencontainers.image.source="https://github.com/Sqube-Groups/sqube-agent-control" \
      org.opencontainers.image.licenses="Apache-2.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SQUBE_LEDGER_PATH=/data/sqube_ledger.sqlite3

COPY --from=build /dist/*.whl /tmp/
RUN whl="$(ls /tmp/*.whl)" \
    && pip install --no-cache-dir "${whl}[control-plane,policy,otel]" \
    && rm -f /tmp/*.whl \
    && useradd --system --uid 10001 --home-dir /data --shell /usr/sbin/nologin sqube \
    && mkdir -p /data && chown sqube:sqube /data

USER sqube
WORKDIR /data
VOLUME ["/data"]
EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/v1/health', timeout=2).status == 200 else 1)"

ENTRYPOINT ["sqube-agent-guard"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8080", "--data-dir", "/data"]
