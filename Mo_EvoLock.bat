@echo off
setlocal
title EvoLock
pushd "%~dp0"
if errorlevel 1 goto directory_error

set "EVOLOCK_PYTHON=%~dp0venv\Scripts\python.exe"
if exist "%EVOLOCK_PYTHON%" goto launch
set "EVOLOCK_PYTHON=%~dp0.venv\Scripts\python.exe"
if exist "%EVOLOCK_PYTHON%" goto launch

echo Khong tim thay Python trong venv hoac .venv.
echo Hay cai moi truong theo README.md roi mo lai file nay.
popd
pause
exit /b 1

:launch
"%EVOLOCK_PYTHON%" "%~dp0main.py"
set "EVOLOCK_EXIT_CODE=%ERRORLEVEL%"
if "%EVOLOCK_EXIT_CODE%"=="0" goto done
echo.
echo EvoLock gap loi. Hay gui noi dung loi phia tren de kiem tra.
pause
:done
popd
exit /b %EVOLOCK_EXIT_CODE%

:directory_error
echo Khong mo duoc thu muc EvoLock.
pause
exit /b 1
