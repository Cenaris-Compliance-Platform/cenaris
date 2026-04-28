# PROJECT CONTEXT

## Project
Cenaris

## Tech Stack
- Backend: Python / Flask
- Database: PostgreSQL (Docker)
- Desktop Client: Flutter Desktop
- Supporting pieces: SQLAlchemy, Alembic, Flask-Login, Flask-WTF, Flask-Mail, Azure Blob Storage / Application Insights / OpenAI integrations

## Directory Structure
- `app/` contains the Flask application package
- `app/main/` contains main routes, forms, and UI workflow logic
- `app/api/` contains API routes
- `app/auth/` contains authentication routes and helpers
- `app/services/` contains business logic and integrations
- `templates/` contains Jinja templates
- `static/` contains frontend assets
- `tests/` contains pytest coverage
- `migrations/` contains Alembic migrations
- `docs/` contains product and API documentation

## Naming Conventions
- Python: use `snake_case` for functions, variables, routes, and module-level helpers
- Python classes: use `PascalCase`
- Flask routes: keep endpoint names descriptive and consistent with existing `blueprint.route_name` patterns
- Flutter / Dart: use `PascalCase` for widgets and classes, `lowerCamelCase` for variables and methods, and `snake_case` for file names
- Database fields: prefer clear, descriptive `snake_case` names that match existing SQLAlchemy models

## State of Play
- The database is already running on port `5432`.
- Do not suggest changes to the `.env` file unless explicitly asked.
- Treat the current AI workflow as the AI Review Workspace, not the old demo wording.
- Existing work already includes retention controls for AI usage logs, and the code now enforces a minimum retention floor.

## Working Rules
- Preserve existing behavior unless a change is explicitly requested
- Prefer small, focused edits over broad refactors
- Verify any code change with targeted tests when possible
- Avoid recommending environment or secret changes unless the user asks for them
