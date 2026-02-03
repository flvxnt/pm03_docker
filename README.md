# SED Project (FastAPI + Postgres + Docker)

## Запуск
```bash
docker compose up --build

Открыть Swagger:
http://localhost:8000/docs

Остановка
docker compose down

Прогон тестов безопасности
docker compose run --rm tests

На другом компьютере нужно установить:

Docker Desktop 
Git — чтобы клонировать проект  
Windows 10/11 (или Linux/Mac)
