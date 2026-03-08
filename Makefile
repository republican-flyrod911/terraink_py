.PHONY: all test check

all: check

check:
	uv run ruff check src
	uv run mypy src

test:
	uv run pytest tests/ -v
