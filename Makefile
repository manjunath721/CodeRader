.PHONY: up down backend-shell frontend-shell test-backend migrate seed-demo lint

up:
	docker compose up --build

down:
	docker compose down

backend-shell:
	docker compose exec backend bash

frontend-shell:
	docker compose exec frontend sh

test-backend:
	cd backend && python -m pytest tests/ -v

migrate:
	cd backend && alembic upgrade head

seed-demo:
	cd backend && python ../scripts/seed_demo.py

lint:
	cd backend && python -m pyflakes app || true
	cd frontend && npm run lint
