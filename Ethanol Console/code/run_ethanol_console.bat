@echo off
REM Mouse Arena Ethanol Console launcher.
REM
REM Runs from the SAME dedicated conda-forge environment "ma-console" as the
REM Data Console (self-consistent Qt6/ICU stack; the pip PySide6 in vras clashed
REM with Anaconda's own Qt6). Create it once with:
REM
REM   conda create -n ma-console -c conda-forge python=3.12 pyside6 matplotlib numpy h5py
REM
REM Optionally pass the aggregate path as the first argument.
setlocal
cd /d "%~dp0"

REM Prefer the env's python directly (no activation needed).
set "ENVPY=%USERPROFILE%\anaconda3\envs\ma-console\python.exe"
if not exist "%ENVPY%" set "ENVPY=%LOCALAPPDATA%\anaconda3\envs\ma-console\python.exe"
if not exist "%ENVPY%" set "ENVPY=%USERPROFILE%\miniconda3\envs\ma-console\python.exe"

if exist "%ENVPY%" (
  "%ENVPY%" "run_ethanol_console.py" %*
) else (
  echo Could not find the ma-console env python; trying "conda run"...
  call conda run -n ma-console python "run_ethanol_console.py" %*
)
if errorlevel 1 pause
endlocal
