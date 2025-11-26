@echo off
echo ==================================================
echo Universal Refactory Setup
echo ==================================================

REM Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.8+ and try again.
    pause
    exit /b 1
)

echo [1/4] Creating virtual environment...
if not exist venv (
    python -m venv venv
    echo    [+] Virtual environment created.
) else (
    echo    [!] Virtual environment already exists.
)

echo [2/4] Activating virtual environment...
call venv\Scripts\activate
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

echo [3/4] Installing dependencies...
pip install --upgrade pip
pip install -r re_agent_project/requirements.txt
pip install tkinterdnd2

echo [4/4] Verifying installation...
python -c "import tkinterdnd2; print('   [+] tkinterdnd2 installed successfully')"
if %errorlevel% neq 0 (
    echo [ERROR] Failed to verify installation.
    pause
    exit /b 1
)

echo ==================================================
echo Setup Complete!
echo You can now run the launcher using:
echo    venv\Scripts\python launcher.py
echo ==================================================
pause