# Makefile for ADK MCP Server project
.PHONY: help install install-dev test test-unit test-integration test-cov lint format clean run-agent run-eval eval-full eval-category eval-difficulty eval-scenario list-scenarios

# Default target
help:
	@echo "ADK MCP Server - Available commands:"
	@echo ""
	@echo "Installation:"
	@echo "  install      - Install production dependencies"
	@echo "  install-dev  - Install development dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  test         - Run all tests"
	@echo "  test-unit    - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  test-cov     - Run tests with coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint         - Run linting checks"
	@echo "  format       - Format code with black"
	@echo ""
	@echo "Running:"
	@echo "  run-agent    - Start the ADK agent"
	@echo ""
	@echo "Evaluation:"
	@echo "  eval-full    - Run full evaluation suite"
	@echo "  eval-category - Run evaluation for specific category"
	@echo "  eval-difficulty - Run evaluation for specific difficulty"
	@echo "  eval-scenario - Run single scenario"
	@echo "  list-scenarios - List all available scenarios"
	@echo ""
	@echo "Maintenance:"
	@echo "  clean        - Clean up generated files"

# Installation
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

# Testing
test:
	pytest

test-unit:
	pytest tests/ -m "not integration"

test-integration:
	pytest tests/ -m integration

test-cov:
	pytest --cov=local_mcp --cov=evaluation --cov-report=html --cov-report=term

# Code Quality
lint:
	flake8 local_mcp/ evaluation/ tests/
	mypy local_mcp/ evaluation/

format:
	black local_mcp/ evaluation/ tests/

# Running
run-agent:
	adk web

# Evaluation
eval-full:
	python -m evaluation.evaluation --full

eval-category:
	@read -p "Enter category (job_listing, job_status, job_submission, error_handling): " category; \
	python -m evaluation.evaluation --category $$category

eval-scenario:
	@read -p "Enter scenario name: " scenario; \
	python -m evaluation.evaluation --scenario "$$scenario"

list-scenarios:
	python -m evaluation.evaluation --list

# Maintenance
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf evaluation_results/
	rm -rf build/
	rm -rf dist/

# Development workflow
dev-setup: install-dev
	pre-commit install

dev-test: format lint test

# Quick evaluation
quick-eval:
	python -m evaluation.evaluation --category job_listing

# Full development cycle
full-cycle: clean install-dev format lint test eval-full 