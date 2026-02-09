.PHONY: venv lint test build wheel precommit

venv:
	python -m venv .venv && . .venv/bin/activate && pip install -U pip

dev:
	. .venv/bin/activate && pip install -e .[dev]

lint:
	. .venv/bin/activate && ruff check . && mypy src || true

format:
	. .venv/bin/activate && ruff format .

test:
	. .venv/bin/activate && pytest -q

wheel:
	. .venv/bin/activate && python -m build

precommit:
	. .venv/bin/activate && pre-commit install