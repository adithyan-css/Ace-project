#!/usr/bin/env bash
pip install pytest pytest-asyncio pytest-cov httpx
pytest tests/ -v --tb=short --cov=backend --cov=ai_ml --cov-report=term-missing
exit $?
