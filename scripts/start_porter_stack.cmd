@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_porter_stack.ps1" %*
exit /b %ERRORLEVEL%
