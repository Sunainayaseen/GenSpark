@echo off
setlocal
set SRC=%~dp0..\vendor dashboard\models\best.pt
set DST=%~dp0best.pt
if not exist "%SRC%" (
  echo Missing: %SRC%
  echo Train first: tools\train_yolov8.py  or  tools\train_monitor.bat
  exit /b 1
)
copy /Y "%SRC%" "%DST%"
echo Copied to %DST%
if not exist "%~dp0uploads" mkdir "%~dp0uploads"
echo uploads\ folder ready.
