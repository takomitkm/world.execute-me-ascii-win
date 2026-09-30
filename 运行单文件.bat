@echo off
setlocal
set "TARGET=%~dp0world-execute-mv-win.pyz"
if not exist "%TARGET%" set "TARGET=%~dp0dist\world-execute-mv-win.pyz"
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 "%TARGET%" %*
) else (
  python "%TARGET%" %*
)
echo.
echo Exit code %ERRORLEVEL%. Window stays open, press a key...
pause >nul
