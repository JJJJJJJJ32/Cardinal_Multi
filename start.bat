@echo off
chcp 65001 > nul
title Cardinal_Multi

:: Проверяем наличие .env и ключа шифрования
if not exist .env goto need_setup
if not exist data\secret.key goto need_setup

:: Запускаем основное приложение
python main.py
if errorlevel 1 (
    echo.
    echo [ОШИБКА] Cardinal_Multi завершился с ошибкой.
    echo Проверь логи: logs\cardinal_multi.log
)
goto end

:need_setup
echo.
echo Необходима первоначальная настройка.
echo Запускаю setup.bat...
echo.
call setup.bat

:end
echo.
pause