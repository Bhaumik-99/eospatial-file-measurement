.PHONY: install run test lint format migrate docker-up

install:
	python -m pip install -e '.[dev]'

run:
	uvicorn app.main:app --reload

test:
	pytest --cov=app --cov-report=term-missing

lint:
	ruff check .

format:
	ruff format .

migrate:
	alembic upgrade head

docker-up:
	docker compose up --build
