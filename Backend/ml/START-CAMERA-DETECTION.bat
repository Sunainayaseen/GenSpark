@echo off
cd /d "%~dp0"
set OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS=0
python live_detect_dshow.py %*
pause
