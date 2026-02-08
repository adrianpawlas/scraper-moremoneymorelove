@echo off
REM Run More Money More Love scraper (e.g. daily at midnight via Task Scheduler)
REM Ensure Python and venv are in PATH, or set them here:
REM set PATH=C:\Python311;C:\Python311\Scripts;%PATH%
cd /d "%~dp0"
if exist .venv\Scripts\activate.bat (
  call .venv\Scripts\activate.bat
)
python run_scraper.py
pause
