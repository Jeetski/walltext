@echo off
setlocal
where py >nul 2>nul
if %errorlevel%==0 (
    py -m walltext %*
    exit /b %errorlevel%
)

where python >nul 2>nul
if %errorlevel%==0 (
    python -m walltext %*
    exit /b %errorlevel%
)

echo Python was not found. Run install_dependencies.bat first.
exit /b 1
