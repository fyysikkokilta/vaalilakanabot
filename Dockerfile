FROM python:3.13-slim

LABEL version="2025" \
    description="Vaalilakanabot" \
    org.opencontainers.image.source="https://github.com/fyysikkokilta/vaalilakanabot"

WORKDIR /bot
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY assets ./assets
COPY src ./src
COPY vaalilakanabot.py vaalilakanabot.py


CMD ["python3", "vaalilakanabot.py"]
