@echo off
REM Absorber - start the tray app.
REM The interpreter runs from this script's own folder, nothing is hardcoded.
setlocal
cd /d "%~dp0"
set "ABSORBER_PY=python"
where py >nul 2>&1 && set "ABSORBER_PY=py -3"
%ABSORBER_PY% -m absorber %*
endlocal
