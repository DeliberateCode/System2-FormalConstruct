.PHONY: setup test lint format clean sync-version

setup:
	python3 -m venv .venv
	.venv/bin/pip install -e ".[dev]"

test:
	.venv/bin/python -m pytest tests/ -q

lint:
	@.venv/bin/ruff check formalconstruct/ tests/ 2>/dev/null || .venv/bin/python -m py_compile formalconstruct/__init__.py

format:
	.venv/bin/ruff format formalconstruct/ tests/

sync-version:
	python3 scripts/sync_version.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
