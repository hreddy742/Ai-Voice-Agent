@echo off
setlocal
pushd "%~dp0..\ui"

set "BACKEND_URL=http://127.0.0.1:8001"
set "NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8001"
set "PORT=%~1"
if not defined PORT set "PORT=3022"
npm.cmd run dev -- --port %PORT%
