.DEFAULT_GOAL := help

UV ?= uv

# Use the checkout's optional Node installation when present, falling back to PATH.
# Windows recipes must also work when make is launched from PowerShell or Git Bash.
ifeq ($(OS),Windows_NT)
SHELL := cmd.exe
.SHELLFLAGS := /D /C
# npm is a .cmd shim on Windows. Explicitly use cmd so native GNU Make
# does not try to launch it directly with CreateProcess.
NPM ?= cmd.exe /D /C npm.cmd
export PATH := $(subst /,\,$(CURDIR)/.tools/node);$(subst /,\,$(CURDIR)/.tools/node/bin);$(PATH)
else
NPM ?= npm
export PATH := $(CURDIR)/.tools/node/bin:$(PATH)
endif

.PHONY: check lint typecheck hooks-install help venv install backend-install dev backend-dev frontend-install run run-api run-frontend clean

help:
	@echo "Available targets:"
	@echo "  make check  Run Ruff lint, formatting checks, and mypy"
	@echo "  make hooks-install  Install commit checks for this checkout"
	@echo "  make venv    Create .venv (install also creates it automatically)"
	@echo "  make install  Install backend and frontend dependencies"
	@echo "  make dev    Install backend, dev extra, and frontend dependencies"
	@echo "  make backend-install  Install backend dependencies with uv"
	@echo "  make frontend-install  Install frontend dependencies with npm ci"
	@echo "  make run    Start both development servers (Ctrl+C to stop)"
	@echo "  make run-api  Run the FastAPI development server on port 8000"
	@echo "  make run-frontend  Run the Vite development server on port 5173"
	@echo "  make clean   Remove project cache directories"

venv:
	$(UV) venv

install: backend-install frontend-install

backend-install:
	$(UV) sync

dev: backend-dev frontend-install

backend-dev:
	$(UV) sync --extra dev
	$(MAKE) hooks-install

frontend-install:
	$(NPM) --prefix frontend ci

run:
	$(MAKE) -j2 run-api run-frontend

run-api:
	$(UV) run uvicorn training_planner.api.app:app --reload --host 127.0.0.1 --port 8000

run-frontend:
	$(NPM) --prefix frontend run dev

clean:
	$(UV) run --no-sync python -c "from pathlib import Path; import shutil; root=Path('.'); names={'.pytest_cache', '.ruff_cache', '.mypy_cache', '__pycache__'}; paths=sorted((p for p in root.rglob('*') if p.is_dir() and p.name in names and '.venv' not in p.parts and '.git' not in p.parts), key=lambda p: len(p.parts), reverse=True); [shutil.rmtree(p, ignore_errors=True) for p in paths]"

check: lint typecheck

lint:
	$(UV) run --extra dev ruff check src tests
	$(UV) run --extra dev ruff format --check src tests

typecheck:
	$(UV) run --extra dev mypy src tests

hooks-install:
	$(UV) run --extra dev pre-commit install
