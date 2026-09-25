@echo off
rem Windows Gorev Zamanlayicisi bu dosyayi calistirir.
rem Ciktilar veri\gunluk.log dosyasina eklenir.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
rem Ciktilar beklemeden gunluge yazilsin (program surerken de izlenebilsin).
set PYTHONUNBUFFERED=1
if not exist veri mkdir veri
python -m oneri calistir >> veri\gunluk.log 2>&1
