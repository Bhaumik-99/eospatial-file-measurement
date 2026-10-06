.PHONY: install run test lint format docker-up

install:
	python -m pip install -e '.[dev]'

run:
	uvicorn app.main:app --reload

test:
	PYTHONPATH=. pytest --cov=app --cov-report=term-missing

lint:
	ruff check .

format:
	ruff format .

docker-up:
	docker compose up --build
