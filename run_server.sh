#!/bin/bash
uv run uvicorn main:app --reload --host "${APP_HOST:-127.0.0.1}" --port 8000
