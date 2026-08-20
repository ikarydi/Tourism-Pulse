.PHONY: test lint format

test:
	python -m pytest

lint:
	ruff check .

format:
	ruff format .
run:
	uvicorn tourism_pulse_api.main:app --reload --app-dir apps/api/src