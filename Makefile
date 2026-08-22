.PHONY: test lint format run scheduler

test:
	python -m pytest

lint:
	ruff check .

format:
	ruff format .
run:
	uvicorn tourism_pulse_api.main:app --reload --app-dir apps/api/src
scheduler:
	python -m tourism_pulse_api.scheduler