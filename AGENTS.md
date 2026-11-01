
1. Think Before Coding
Don't assume. Don't hide confusion. Surface tradeoffs.

Before implementing:

State your assumptions explicitly. If uncertain, ask.
If multiple interpretations exist, present them - don't pick silently.
If a simpler approach exists, say so. Push back when warranted.
If something is unclear, stop. Name what's confusing. Ask.
2. Simplicity First
Minimum code that solves the problem. Nothing speculative.

No features beyond what was asked.
No abstractions for single-use code.
No "flexibility" or "configurability" that wasn't requested.
No error handling for impossible scenarios.
If you write 200 lines and it could be 50, rewrite it.
Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

3. Surgical Changes
Touch only what you must. Clean up only your own mess.

When editing existing code:

Don't "improve" adjacent code, comments, or formatting.
Don't refactor things that aren't broken.
Match existing style, even if you'd do it differently.
If you notice unrelated dead code, mention it - don't delete it.
When your changes create orphans:

Remove imports/variables/functions that YOUR changes made unused.
Don't remove pre-existing dead code unless asked.
The test: Every changed line should trace directly to the user's request.

4. Goal-Driven Execution
Define success criteria. Loop until verified.

Transform tasks into verifiable goals:

"Add validation" → "Write tests for invalid inputs, then make them pass"
"Fix the bug" → "Write a test that reproduces it, then make it pass"
"Refactor X" → "Ensure tests pass before and after"
For multi-step tasks, state a brief plan:

1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.





# Repository Guidelines

## Project Structure & Module Organization

This is a Django REST Framework API. `core/manage.py` is the command entry point; `core/core/` holds settings and project URL routing. `core/catalog/` contains category models, serializers, service functions, API views, routes, and tests. `core/users/` defines the custom user model. Keep new app code and migrations under its app directory. There are no separate frontend assets or build artifacts in this repository.

## Build, Test, and Development Commands

Run commands from `core/` after creating a virtual environment and installing `requirements.txt`. `core/core/settings.py` also imports `python-dotenv`, which is not listed in that file; install it separately until the dependency list is updated.

```bash
cd core
../.venv/bin/python manage.py check       # validate Django configuration
../.venv/bin/python manage.py makemigrations # generate migrations after model changes
../.venv/bin/python manage.py migrate       # apply database migrations
../.venv/bin/python manage.py runserver     # start the local API
../.venv/bin/python manage.py test          # run Django tests
```

The checkout currently lacks initial app migrations, so database-backed tests and `migrate` need those migrations added first. There is no separate build command.

## Coding Style & Naming Conventions

Use four-space indentation and Python `snake_case` for modules, functions, and fields; use `PascalCase` for classes. Follow the existing API split: request and response `serializers.Serializer` classes in `serializers.py`, database operations in `services.py`, thin `APIView` classes in `views.py`, and app routes in `urls.py`. Keep project-level routes in `core/core/urls.py`. No formatter or linter is configured; keep imports organized and formatting consistent with PEP 8.

## Testing Guidelines

Use Django's test runner and DRF's `APITestCase` for API behavior. Put tests in each app's `tests.py`, name methods `test_<behavior>`, and check response status plus relevant response data or database effects. Run `../.venv/bin/python manage.py test` from `core/`. No coverage threshold is configured.

## Commit & Pull Request Guidelines

Git history is unavailable in this checkout, so no existing commit convention can be verified. Use short, imperative subjects such as `Add category validation`. In pull requests, summarize behavior changes, mention migrations and test results, link related issues when available, and include request/response examples for API changes.

## Security & Configuration

Keep secrets and local settings in `.env`; it is ignored by Git. The checked-in settings currently enable `DEBUG` and contain a development secret key, so configure production values before deployment.


