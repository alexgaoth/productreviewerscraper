.PHONY: help install dev-install test lint format clean run docker-build docker-up docker-down

help:
	@echo "Available commands:"
	@echo "  make install      - Install production dependencies"
	@echo "  make dev-install  - Install development dependencies"
	@echo "  make test         - Run tests"
	@echo "  make lint         - Run linters"
	@echo "  make format       - Format code"
	@echo "  make clean        - Clean up generated files"
	@echo "  make run          - Run the application locally"
	@echo "  make worker       - Run Celery worker"
	@echo "  make docker-build - Build Docker images"
	@echo "  make docker-up    - Start Docker services"
	@echo "  make docker-down  - Stop Docker services"

install:
	pip install -r requirements.txt

dev-install: install
	pip install pytest pytest-asyncio pytest-cov black flake8 mypy

test:
	pytest

lint:
	flake8 app tests
	mypy app

format:
	black app tests

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -rf .pytest_cache .mypy_cache .coverage htmlcov
	rm -f seller_reviews.db

run:
	python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	celery -A app.worker.celery_app worker --loglevel=info --concurrency=4

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f
