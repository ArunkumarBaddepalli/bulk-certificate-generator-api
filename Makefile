.PHONY: install run test lint format

install:
	pip install -r requirements.txt

run:
	uvicorn app.main:app --reload

test:
	python -m pytest

lint:
	ruff check .
	ruff format --check .

format:
	ruff format .
	ruff check --fix .
