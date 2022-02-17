FROM python:3.9-slim

LABEL version="2021" \
    description="Vaalilakanabot" \
    org.opencontainers.image.source="https://github.com/fyysikkokilta/vaalilakanabot"

WORKDIR /bot
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY assets ./assets
COPY vaalilakanabot2021.py vaalilakanabot2021.py

CMD ["python3", "vaalilakanabot2021.py"]