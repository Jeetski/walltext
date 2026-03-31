@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_dependencies.ps1" %*
