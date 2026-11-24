@echo off
rem Abre OBS con la escena del avatar y enciende la camara virtual, para usarla en Teams.
rem
rem Antes, una sola vez:  python scripts\preparar_obs.py
rem Y la ventana del avatar debe estar abierta:  scripts\avatar_reunion.bat
rem
rem OBS se queda con la coleccion y el perfil "Asistente Tec" seleccionados; para volver a
rem los tuyos, cambialos en los menus "Coleccion de escenas" y "Perfil".
setlocal

set "OBS=%ProgramFiles%\obs-studio\bin\64bit"
if not exist "%OBS%\obs64.exe" goto sin_obs

rem OBS solo encuentra sus archivos si arranca desde su propia carpeta.
start "" /d "%OBS%" obs64.exe --collection "Asistente Tec" --profile "Asistente Tec" --startvirtualcam --disable-shutdown-check
exit /b 0

:sin_obs
echo No se encontro OBS Studio en %OBS%.
pause
exit /b 1
