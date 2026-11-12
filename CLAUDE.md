# Claude Project Guidelines - Django + HTMX Monolith

## Tech Stack & Architecture
- **Backend:** Django monolith (Server-rendered templates).
- **Frontend:** HTMX + Alpine.js + Tailwind CSS.
- **API Strategy:** NO REST/GraphQL APIs. Views must return HTML fragments or full templates.
- **State Management:** Alpine.js for lightweight frontend state; HTML-driven state via HTMX.

## Critical Guardrails & Disallowed Patterns
- **DO NOT** build Django Rest Framework (DRF) serializers, viewsets, or JSON endpoints.
- **DO NOT** put business logic inside Django views or templates. Move complex logic to a `services.py` module within the app.
- **DO NOT** write vanilla JavaScript or fetch requests. Use HTMX attributes (`hx-*`) or Alpine.js (`x-data`, `x-on`) exclusively for interactivity.
- **DO NOT** write raw CSS. Use utility classes from Tailwind CSS.
- **DO NOT** run migrations without running the check command first.

## Strict Workflow: Plan-First Rule
Before writing, modifying, or deleting any code, you MUST follow this sequence:
1. **Analyze:** Assess the task against the existing codebase.
2. **Draft Plan:** Output a concise, bulleted implementation plan detailing which files will be added/changed, the proposed logic, and HTMX attributes to be used.
3. **Wait for Approval:** Explicitly end your response asking for user confirmation. Do not execute code until approved.

## Verification Commands
Execute and verify these commands pass before marking a task as complete:
- **Code Integrity:** `python manage.py check`
- **Migration Check:** `python manage.py makemigrations --check --dry-run`
- **Run Tests:** `pytest` or `python manage.py test`
- **Linting/Formatting:** `black . --check` / `flake8`

## Local Environment
- **Python:** use the project virtualenv (`.venv/bin/python`, or activate it first). There is no bare `python` on PATH. Install with `pip install -r requirements-dev.txt`.
- **Database:** PostgreSQL runs in Docker (`docker compose up -d`) on host port **5433**, because a local Homebrew Postgres holds 5432. Settings read `DATABASE_URL`, `SECRET_KEY`, `DEBUG` and `ALLOWED_HOSTS` from `.env` through `django-environ`.
- **Tests:** tests are pytest-style (pytest-django), so run them with `pytest`. `python manage.py test` will not discover them.
- **Secrets in `.env`:** avoid `$`, `#`, quotes and spaces in values, because Docker Compose reads `.env` too and expands `$`.

## Project Conventions
- **Base models:** every model inherits `core.models.UUIDModel` (and `TimeStampedModel` where useful). Shared choices live in `core/choices.py`.
- **Validation:** put field-specific errors in `Model.clean()`, and back each rule with a named database `CheckConstraint`/`UniqueConstraint`. ModelForms must include every field such a rule reports on.
- **Services:** functions in `<app>/services.py` take keyword-only arguments and raise `ValidationError` keyed by field, so forms can display the errors directly.
