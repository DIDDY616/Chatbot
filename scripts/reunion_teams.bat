@echo off
rem Deja todo listo para entrar a una reunion de Teams con el asistente:
rem abre el avatar en modo reunion y OBS con la camara virtual encendida.
rem
rem Uso:  scripts\reunion_teams.bat            (asistente predeterminado)
rem       scripts\reunion_teams.bat asesor-itc (otro asistente)
rem
rem Requisitos: la API encendida (puerto 8000) y haber corrido una vez
rem             python scripts\preparar_obs.py
rem
rem Despues, en Teams elige:  Camara "OBS Virtual Camera",
rem   Microfono "CABLE Output" y Altavoz "Hi-Fi Cable Input".
call "%~dp0avatar_reunion.bat" %*
if errorlevel 1 exit /b 1
rem Da tiempo a que exista la ventana del avatar antes de que OBS la busque.
ping -n 6 127.0.0.1 >nul
call "%~dp0camara_obs.bat"
