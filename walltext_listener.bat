@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0walltext_listener.ps1" %*
