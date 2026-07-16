@echo off
chcp 65001 > nul
title Cardinal_Multi — Установка

echo.
echo ╔══════════════════════════════════════════╗
echo ║      CARDINAL MULTI — Установка          ║
echo ╚══════════════════════════════════════════╝
echo.

:: ═══════════════════════════════════════════════════════
:: ШАГ 1: Проверка Python 3.12+
:: ═══════════════════════════════════════════════════════
echo [1/5] Проверка Python 3.12+...

python --version >nul 2>&1
if errorlevel 1 goto no_python

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set PYMAJ=%%a
    set PYMIN=%%b
)

if %PYMAJ% LSS 3 goto no_python
if %PYMAJ% EQU 3 if %PYMIN% LSS 12 goto no_python

echo     OK  Python %PYVER% найден.
goto check_git

:no_python
echo.
echo     ОШИБКА  Python 3.12+ не найден!
echo.
echo     Открываю страницу загрузки python.org...
start https://www.python.org/downloads/
echo.
echo     1. Скачай и установи Python 3.12 или новее.
echo     2. При установке поставь галочку "Add Python to PATH".
echo     3. После установки перезапусти setup.bat.
echo.
pause
exit /b 1

:: ═══════════════════════════════════════════════════════
:: ШАГ 2: Проверка Git
:: ═══════════════════════════════════════════════════════
:check_git
echo [2/5] Проверка Git...

git --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo     ПРЕДУПРЕЖДЕНИЕ  Git не найден!
    echo     Открываю страницу загрузки git-scm.com...
    start https://git-scm.com/downloads
    echo.
    echo     Git рекомендован для обновлений Cardinal_Multi.
    echo     Установи Git и перезапусти setup.bat.
    echo     Или нажми любую клавишу чтобы продолжить без Git.
    echo.
    pause
) else (
    for /f "tokens=3" %%v in ('git --version 2^>^&1') do set GITVER=%%v
    echo     OK  Git %GITVER% найден.
)

:: ═══════════════════════════════════════════════════════
:: ШАГ 3: pip install -r requirements.txt
:: ═══════════════════════════════════════════════════════
echo [3/5] Установка зависимостей из requirements.txt...
echo.

python -m pip install --upgrade pip -q
if errorlevel 1 (
    echo     ПРЕДУПРЕЖДЕНИЕ  Не удалось обновить pip. Продолжаю...
)

python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo     ОШИБКА  Не удалось установить зависимости!
    echo.
    echo     Возможные причины:
    echo       - Нет подключения к интернету
    echo       - Повреждён файл requirements.txt
    echo       - Недостаточно прав (попробуй запустить от администратора)
    echo.
    echo     Попробуй вручную:
    echo       python -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo.
echo     OK  Все зависимости установлены.

:: ═══════════════════════════════════════════════════════
:: ШАГ 4: playwright install chromium
:: ═══════════════════════════════════════════════════════
echo [4/5] Установка Playwright Chromium...
echo.
echo     Это может занять несколько минут.
echo     Chromium нужен для модуля Lolzteam автозакупки.
echo.

python -m playwright install chromium
if errorlevel 1 (
    echo.
    echo     ПРЕДУПРЕЖДЕНИЕ  Playwright Chromium не установлен!
    echo.
    echo     Модуль Lolzteam будет недоступен.
    echo     Чтобы установить вручную позже, выполни:
    echo       python -m playwright install chromium
    echo.
    echo     Продолжаю установку без Playwright...
    echo.
) else (
    echo.
    echo     OK  Playwright Chromium установлен.
)

:: ═══════════════════════════════════════════════════════
:: ШАГ 5: python setup.py (мастер настройки)
:: ═══════════════════════════════════════════════════════
echo [5/5] Запуск мастера первоначальной настройки...
echo.

python setup.py
if errorlevel 1 (
    echo.
    echo     ОШИБКА  Мастер настройки завершился с ошибкой!
    echo.
    echo     Проверь логи: logs\cardinal_multi.log
    echo     Или запусти повторно: python setup.py
    echo.
    pause
    exit /b 1
)

:: ═══════════════════════════════════════════════════════
:: ЗАВЕРШЕНИЕ
:: ═══════════════════════════════════════════════════════
echo.
echo ╔══════════════════════════════════════════╗
echo ║                                          ║
echo ║   Установка успешно завершена!           ║
echo ║                                          ║
echo ║   Для запуска используй: start.bat       ║
echo ║                                          ║
echo ╚══════════════════════════════════════════╝
echo.
pause
exit /b 0