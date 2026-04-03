@echo off
setlocal

set TARGET=%1
if "%TARGET%"=="" set TARGET=help

if "%TARGET%"=="install" goto install
if "%TARGET%"=="install-ai" goto install_ai
if "%TARGET%"=="train" goto train
if "%TARGET%"=="backend" goto backend
if "%TARGET%"=="frontend" goto frontend
if "%TARGET%"=="test" goto test
if "%TARGET%"=="test-fast" goto test_fast
if "%TARGET%"=="run-vision" goto run_vision
if "%TARGET%"=="run-nlp" goto run_nlp
if "%TARGET%"=="all" goto all
if "%TARGET%"=="help" goto help

echo Unknown target: %TARGET%
exit /b 1

:install
pip install -r requirements_backend.txt
if errorlevel 1 exit /b 1
pushd frontend
npm install
set ERR=%ERRORLEVEL%
popd
exit /b %ERR%

:install_ai
pip install -r requirements_ai.txt
exit /b %ERRORLEVEL%

:train
pushd ai_ml\module2
python train_and_save.py
set ERR=%ERRORLEVEL%
popd
exit /b %ERR%

:backend
pushd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
set ERR=%ERRORLEVEL%
popd
exit /b %ERR%

:frontend
pushd frontend
npm run dev
set ERR=%ERRORLEVEL%
popd
exit /b %ERR%

:test
pytest tests/ -v --tb=short
exit /b %ERRORLEVEL%

:test_fast
pytest tests/ -v -m "not slow" --tb=short
exit /b %ERRORLEVEL%

:run_vision
python ai_ml/module1/vision_monitor.py --source 0
exit /b %ERRORLEVEL%

:run_nlp
python ai_ml/module2/nlp_parser.py
exit /b %ERRORLEVEL%

:all
echo Run backend and frontend in separate terminals:
echo   1) make backend
echo   2) make frontend
exit /b 0

:help
echo Available targets:
echo   install      Install backend Python deps and frontend npm deps
echo   install-ai   Install AI/ML Python deps
echo   train        Train and save motor LSTM artifacts
echo   backend      Start FastAPI backend server
echo   frontend     Start React frontend dev server
echo   test         Run full pytest suite
echo   test-fast    Run pytest suite excluding slow tests
echo   run-vision   Run YOLO vision monitor
echo   run-nlp      Run NLP parser
echo   all          Print one-command run guidance
echo   help         Print this help message
exit /b 0
