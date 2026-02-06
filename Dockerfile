FROM python:3.13-slim

LABEL version="2025" \
    description="Vaalilakanabot" \
    org.opencontainers.image.source="https://github.com/fyysikkokilta/vaalilakanabot"

WORKDIR /bot

COPY pyproject.toml README.md ./
COPY src ./src
COPY assets ./assets

RUN pip install --no-cache-dir .

CMD ["vaalilakanabot"]
