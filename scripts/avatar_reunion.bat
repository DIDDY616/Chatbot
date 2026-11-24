@echo off
rem Abre el avatar en modo reunion, en una ventana propia lista para capturar con OBS.
rem
rem Uso:  scripts\avatar_reunion.bat            (asistente predeterminado)
rem       scripts\avatar_reunion.bat asesor-itc (otro asistente, por su identificador)
rem
rem La API debe estar encendida (puerto 8000).
rem
rem Usa un perfil de navegador aparte para que las opciones de abajo se apliquen aunque ya
rem tengas Chrome abierto. Esas opciones evitan que el navegador deje de dibujar al avatar
rem cuando otra ventana (Teams, por ejemplo) lo tapa.
setlocal

set "URL=http://127.0.0.1:8000/avatar/?reunion=1&auto=1"
if not "%~1"=="" set "URL=%URL%&perfil=%~1"
set "DATOS=%LOCALAPPDATA%\AsistenteTec\navegador"

set "NAVEGADOR=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%NAVEGADOR%" set "NAVEGADOR=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not exist "%NAVEGADOR%" set "NAVEGADOR=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
if not exist "%NAVEGADOR%" set "NAVEGADOR=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not exist "%NAVEGADOR%" set "NAVEGADOR=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
if not exist "%NAVEGADOR%" goto sin_navegador

start "" "%NAVEGADOR%" "--app=%URL%" "--user-data-dir=%DATOS%" --window-size=1280,760 ^
  --disable-features=CalculateNativeWinOcclusion --disable-backgrounding-occluded-windows ^
  --disable-renderer-backgrounding --disable-background-timer-throttling ^
  --autoplay-policy=no-user-gesture-required
exit /b 0

:sin_navegador
echo No se encontro Chrome ni Edge en este equipo.
pause
exit /b 1
