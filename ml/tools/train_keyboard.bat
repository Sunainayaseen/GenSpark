@echo off
cd /d "%~dp0.."
echo Importing latest keyboard assets...
"vendor dashboard\.venv\Scripts\python.exe" tools\import_keyboard_assets.py
echo Validating dataset...
"vendor dashboard\.venv\Scripts\python.exe" tools\validate_yolo_dataset.py
if errorlevel 1 exit /b 1
echo Training YOLOv8 (deploys to vendor dashboard\models\best.pt)...
"vendor dashboard\.venv\Scripts\python.exe" tools\train_yolov8.py --epochs 100 --imgsz 640 --batch 8 --name genspark_fyp
pause
