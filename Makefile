.PHONY: install up down seed seed-fresh test eval eval-fast api

install:
	python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev,embeddings]" && .venv/Scripts/python -m pip install -e ../evalkit[anthropic]

up:
	docker compose up -d

down:
	docker compose down

seed:
	.venv/Scripts/python -m scripts.seed --limit 2000

seed-fresh:
	.venv/Scripts/python -m scripts.seed --recreate --limit 2000

test:
	.venv/Scripts/python -m pytest -v

eval:
	.venv/Scripts/python -m scripts.eval --out evals/reports/$$(powershell -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd-HHmm'").md

eval-fast:
	.venv/Scripts/python -m scripts.eval --no-llm-judge --json

api:
	.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8003 --reload
