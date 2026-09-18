@echo off
setlocal
rem El Cercevesi ile Goruntu Efektleri - baslatici
rem Cift tiklayarak ya da komut satirindan calistirilabilir.
rem Ek secenekler programa aynen iletilir, ornek: baslat.bat --effect cartoon

rem Bat dosyasinin bulundugu klasore gec (yol elle yazilmaz, Turkce karakterli yollarda da calisir)
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
set "VENV_PY=.venv\Scripts\python.exe"

rem 1) Sanal ortam yoksa olustur
if not exist "%VENV_PY%" (
    echo Sanal ortam bulunamadi, olusturuluyor...
    py -3 -m venv .venv 2>nul || python -m venv .venv
    if not exist "%VENV_PY%" (
        echo HATA: Python bulunamadi. https://www.python.org adresinden Python kurup tekrar deneyin.
        goto :error
    )
)

rem 2) Paketler eksikse kur
set "PACKAGES_OK=1"
if not exist ".venv\Lib\site-packages\mediapipe\" set "PACKAGES_OK=0"
if not exist ".venv\Lib\site-packages\cv2\" set "PACKAGES_OK=0"
if "%PACKAGES_OK%"=="0" (
    echo Gerekli paketler kuruluyor, bu birkac dakika surebilir...
    "%VENV_PY%" -m pip --version >nul 2>&1 || "%VENV_PY%" -m ensurepip --upgrade
    "%VENV_PY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo HATA: Paketler kurulamadi. Internet baglantinizi kontrol edin.
        goto :error
    )
)

rem 3) Programi calistir
"%VENV_PY%" hand_frame_effects.py %*
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo Program bir hatayla kapandi. Kapatmak icin bir tusa basin.
pause >nul
exit /b 1
