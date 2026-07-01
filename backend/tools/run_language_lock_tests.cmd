@echo off
setlocal
cd /d %~dp0\..
.venv\Scripts\python.exe -m pytest tests\test_ai_language_lock.py -q --no-cov
endlocal
