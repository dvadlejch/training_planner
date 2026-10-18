.DEFAULT_GOAL := help

UV ?= uv
POWERSHELL ?= powershell.exe

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
.PHONY: package-windows installer-windows release-windows

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
	@echo "  make clean   Remove generated builds and caches, preserving local data"
	@echo "  make package-windows    Build the runnable Windows application folder"
	@echo "  make installer-windows  Build the Windows setup executable"
	@echo "  make release-windows    Run checks and tests, then build the Windows installer"

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
	$(UV) run --no-sync python src/training_planner/clean.py

check: lint typecheck

lint:
	$(UV) run --extra dev ruff check src tests
	$(UV) run --extra dev ruff format --check src tests

typecheck:
	$(UV) run --extra dev mypy src tests

hooks-install:
	$(UV) run --extra dev pre-commit install

package-windows:
	$(POWERSHELL) -NoProfile -ExecutionPolicy Bypass -File scripts/build-windows.ps1 -Target package -Uv "$(UV)"

installer-windows:
	$(POWERSHELL) -NoProfile -ExecutionPolicy Bypass -File scripts/build-windows.ps1 -Target installer -Uv "$(UV)"

release-windows:
	$(POWERSHELL) -NoProfile -ExecutionPolicy Bypass -File scripts/build-windows.ps1 -Target release -Uv "$(UV)"
