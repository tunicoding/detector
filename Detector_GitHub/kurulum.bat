@echo off
cd /d "%~dp0"
echo === Detector kurulumu ===
echo.

rem --- Python 3.12 ---
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" (
    for /f "delims=" %%i in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "PY=%%i"
)
if not exist "%PY%" (
    echo [1/4] Python 3.12 kuruluyor...
    winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements --silent
    set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)
if not exist "%PY%" (
    echo HATA: Python kurulamadi. python.org adresinden Python 3.12 kurup tekrar deneyin.
    pause
    exit /b 1
)

rem --- Kutuphaneler ---
echo [2/4] Kutuphaneler kuruluyor (birkac dakika surebilir)...
if not exist ".venv\Scripts\python.exe" "%PY%" -m venv .venv
".venv\Scripts\python.exe" -m pip install --upgrade pip -q
".venv\Scripts\python.exe" -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo HATA: Kutuphaneler kurulamadi. Internet baglantinizi kontrol edin.
    pause
    exit /b 1
)

rem --- Yuz modelleri ---
echo [3/4] Yuz tanima modelleri indiriliyor...
if not exist models mkdir models
if not exist "models\face_landmarker.task" powershell -NoProfile -Command "Invoke-WebRequest 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task' -OutFile 'models\face_landmarker.task'"
if not exist "models\face_recognition_sface_2021dec.onnx" powershell -NoProfile -Command "Invoke-WebRequest 'https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx' -OutFile 'models\face_recognition_sface_2021dec.onnx'"
if not exist "models\face_recognition_sface_2021dec.onnx" (
    echo HATA: Modeller indirilemedi.
    pause
    exit /b 1
)

rem --- Video oynatici (ffplay) ---
echo [4/4] Video oynatici kuruluyor...
if not exist "bin\ffplay.exe" (
    winget install -e --id Gyan.FFmpeg --scope user --accept-package-agreements --accept-source-agreements --silent
    if not exist bin mkdir bin
    powershell -NoProfile -Command "$f = Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages') -Recurse -Filter ffplay.exe -ErrorAction SilentlyContinue | Select-Object -First 1; if ($f) { Copy-Item $f.FullName 'bin\' }"
)
if not exist "bin\ffplay.exe" (
    echo HATA: Video oynatici kurulamadi.
    pause
    exit /b 1
)

echo.
echo Kurulum tamam! Simdi detector.bat dosyasina cift tiklayin.
pause
