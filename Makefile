# Makefile for ADK MCP Server project
.PHONY: help install install-dev test test-unit test-integration test-cov lint format clean run-agent adk-eval adk-eval-verbose adk-eval-custom test-agent-integration dev-setup dev-test adk-web custom-eval

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
	@echo "  adk-web      - Start ADK web UI for evaluation"
	@echo ""
	@echo "ADK Evaluation:"
	@echo "  adk-eval     - Run ADK evaluation via CLI"
	@echo "  adk-eval-verbose - Run ADK evaluation with detailed results"
	@echo "  adk-eval-custom - Run ADK evaluation with custom config"
	@echo "  custom-eval  - Run custom evaluation with detailed scoring"
	@echo ""
	@echo "Development:"
	@echo "  dev-setup    - Set up development environment"
	@echo "  dev-test     - Run format, lint, and test"
	@echo ""
	@echo "Maintenance:"
	@echo "  clean        - Clean up generated files"

# Installation
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	pip install langchain langchain-evaluation

# Testing
test:
	pytest tests/

test-unit:
	pytest tests/ -m "not integration"

test-integration:
	pytest tests/integration/

test-cov:
	pytest tests/ --cov=local_mcp --cov-report=html --cov-report=term

# Code Quality
lint:
	flake8 local_mcp/ tests/
	mypy local_mcp/

format:
	black local_mcp/ tests/

# Running
run-agent:
	adk web

# ADK Web UI for Evaluation
adk-web:
	adk web local_mcp/

# ADK Evaluation via CLI
adk-eval:
	adk eval local_mcp/ tests/integration/fixture/htcondor_mcp_agent/

adk-eval-verbose:
	adk eval local_mcp/ tests/integration/fixture/htcondor_mcp_agent/ --print_detailed_results

adk-eval-custom:
	@read -p "Enter config file path (default: test_config.json): " config; \
	config=$${config:-test_config.json}; \
	adk eval local_mcp/ tests/integration/fixture/htcondor_mcp_agent/ --config_file_path=$$config --print_detailed_results

# Custom Evaluation with Detailed Scoring
custom-eval:
	python run_custom_evaluation.py

# Maintenance
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf build/
	rm -rf dist/

# Development workflow
dev-setup: install-dev
	pre-commit install

dev-test: format lint test 