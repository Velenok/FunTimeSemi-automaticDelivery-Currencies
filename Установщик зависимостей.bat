@echo off
title AutoPay Bot Installer & Launcher

:: --- 1. Проверка наличия Python ---
echo --- Checking for Python ---
python --version >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in your system PATH.
    echo Please install Python from python.org and make sure to check the "Add to PATH" option during installation.
    echo.
    pause
    exit /b
)
echo [OK] Python found.
echo.

:: --- 2. Установка зависимостей через pip ---
echo --- Installing required Python libraries ---
echo This may take a few minutes...
python -m pip install customtkinter python-telegram-bot keyboard pyautogui Pillow
echo.
echo --- All libraries are ready. ---
echo.

echo.
echo The bot application has been closed.
pause