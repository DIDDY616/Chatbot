@echo off
rem Enciende el asistente: Ollama, la API y la consola, y abre la consola en el navegador.
rem Para apagarlo, cierra las dos ventanas que se abren ("Asistente Tec - API" y "- Consola").
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto sin_instalar

curl -s -o nul --max-time 3 http://127.0.0.1:11434/api/tags
if not errorlevel 1 goto ollama_listo
echo Abriendo Ollama...
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe" goto abrir_app
start "Ollama" /min ollama serve
goto esperar_ollama
:abrir_app
start "" "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe"
:esperar_ollama
set /a intentos=0
:probar_ollama
ping -n 2 127.0.0.1 >nul
curl -s -o nul --max-time 3 http://127.0.0.1:11434/api/tags
if not errorlevel 1 goto ollama_listo
set /a intentos+=1
if %intentos% lss 30 goto probar_ollama
echo Ollama no respondio. Abrelo a mano y vuelve a ejecutar iniciar.bat.
pause
exit /b 1
:ollama_listo

curl -s -o nul --max-time 3 http://127.0.0.1:8000/health
if not errorlevel 1 goto ya_encendido

echo Encendiendo la API y la consola...
start "Asistente Tec - API" cmd /k ".venv\Scripts\python.exe -m uvicorn app.api:app --port 8000"
start "Asistente Tec - Consola" cmd /k ".venv\Scripts\python.exe -m streamlit run app/consola.py --server.port 8501 --server.headless true"

set /a intentos=0
:probar_api
ping -n 2 127.0.0.1 >nul
curl -s -o nul --max-time 3 http://127.0.0.1:8000/health
if not errorlevel 1 goto abrir
set /a intentos+=1
if %intentos% lss 90 goto probar_api
echo La API no respondio. Revisa la ventana "Asistente Tec - API".
pause
exit /b 1

:ya_encendido
echo El asistente ya estaba encendido.
:abrir
start "" http://localhost:8501
echo.
echo Consola:  http://localhost:8501
echo Avatar:   http://localhost:8000/avatar/
exit /b 0

:sin_instalar
echo Falta instalar. Ejecuta primero:
echo     powershell -ExecutionPolicy Bypass -File instalar.ps1
pause
exit /b 1
