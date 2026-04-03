.PHONY: install install-ai train backend frontend test test-fast run-vision run-nlp all help

install:
	pip install -r requirements_backend.txt && cd frontend && npm install

install-ai:
	pip install -r requirements_ai.txt

train:
	cd ai_ml/module2 && python train_and_save.py

backend:
	cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

test:
	pytest tests/ -v --tb=short

test-fast:
	pytest tests/ -v -m 'not slow' --tb=short

run-vision:
	python ai_ml/module1/vision_monitor.py --source 0

run-nlp:
	python ai_ml/module2/nlp_parser.py

all:
	@echo "Run backend and frontend in separate terminals:"
	@echo "  1) make backend"
	@echo "  2) make frontend"

help:
	@echo "Available targets:"
	@echo "  install      Install backend Python deps and frontend npm deps"
	@echo "  install-ai   Install AI/ML Python deps"
	@echo "  train        Train and save motor LSTM artifacts"
	@echo "  backend      Start FastAPI backend server"
	@echo "  frontend     Start React frontend dev server"
	@echo "  test         Run full pytest suite"
	@echo "  test-fast    Run pytest suite excluding slow tests"
	@echo "  run-vision   Run YOLO vision monitor"
	@echo "  run-nlp      Run NLP parser"
	@echo "  all          Print one-command run guidance"
	@echo "  help         Print this help message"
