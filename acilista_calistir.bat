@echo off
rem Bilgisayar acilinca calisir: once Ollama ve Excel hazir olsun diye 2 dakika bekler.
rem Bu dosyanin kisayolu Baslangic (shell:startup) klasorune konur.
timeout /t 120 /nobreak >nul
call "%~dp0calistir.bat"
