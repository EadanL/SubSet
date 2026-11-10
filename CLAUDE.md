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
