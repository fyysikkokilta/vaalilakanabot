FROM python:3.10-slim

LABEL version="2024" \
    description="Vaalilakanabot" \
    org.opencontainers.image.source="https://github.com/fyysikkokilta/vaalilakanabot"

WORKDIR /bot
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY assets ./assets
COPY google_service_account_creds.json google_service_account_creds.json
COPY vaalilakanabot.py vaalilakanabot.py

CMD ["python3", "vaalilakanabot.py"]
