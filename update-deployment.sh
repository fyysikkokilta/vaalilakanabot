#!/bin/bash
git pull
docker compose -f docker-compose.yaml up --build -d