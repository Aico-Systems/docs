# Use direnv Python environment
PYTHON_PREFIX := .direnv/python-3.13
PYTHON := $(PYTHON_PREFIX)/bin/python
PIP := $(PYTHON_PREFIX)/bin/pip

.PHONY: help install install-dev check format lint clean

help:
	@echo "make install     - install runtime deps only"
	@echo "make install-dev - install deps + dev tools"
	@echo "make check       - type check"
	@echo "make format      - format code"
	@echo "make lint        - lint code"
	@echo "make clean       - clean caches"

install:
	@if [ ! -d "$(PYTHON_PREFIX)" ]; then \
		echo "Direnv environment not found. Run 'direnv allow' first."; \
		exit 1; \
	fi
	@$(PIP) install -q -e .

install-dev:
	@if [ ! -d "$(PYTHON_PREFIX)" ]; then \
		echo "Direnv environment not found. Run 'direnv allow' first."; \
		exit 1; \
	fi
	@$(PIP) install -q -e ".[dev]"

check: install-dev
	@$(PYTHON) -m pyright .

format: install-dev
	@$(PYTHON) -m ruff format .

lint: install-dev
	@$(PYTHON) -m ruff check . --fix

clean:
	@rm -rf __pycache__ .pyright_cache .ruff_cache *.egg-info
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
