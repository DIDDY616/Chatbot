<#
Instala el Asistente Tec en esta computadora. Se puede ejecutar varias veces: salta lo que ya esta.

Uso (desde la carpeta del proyecto, en PowerShell):
    powershell -ExecutionPolicy Bypass -File instalar.ps1

Opciones:
    -Minimo       Solo las voces de espanol e ingles (descarga mas rapida).
    -VozNatural   Agrega la voz natural con clonacion (Chatterbox). Pide unos 3 GB mas de GPU.
    -SoloRevisar  No instala nada: solo dice que falta.

Requisitos que este script NO instala: Python 3.10 a 3.13 de python.org (de preferencia 3.12)
y los controladores de NVIDIA. Detalles en docs/instalacion.md.

La primera vez crea .env a partir de .env.example y elige los modelos segun la memoria de la
GPU. Si ya existe .env, lo respeta.
#>
param([switch]$Minimo, [switch]$VozNatural, [switch]$SoloRevisar)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$VocesMinimas = @("es_MX-claude-high", "en_US-lessac-medium")
$VocesTodas = $VocesMinimas + @(
    "es_MX-ald-medium", "es_ES-davefx-medium", "es_ES-sharvard-medium", "es_AR-daniela-high",
    "en_US-ryan-medium", "en_GB-alba-medium", "fr_FR-siwis-medium", "sv_SE-nst-medium", "de_DE-thorsten-medium")
$Avatares = @("mpfb.glb", "avaturn.glb", "avatarsdk.glb", "brunette.glb", "vroid.glb")
$Py = ".\.venv\Scripts\python.exe"

function Paso([string]$Texto) { Write-Host ""; Write-Host "== $Texto" -ForegroundColor Cyan }
function Detener([string]$Texto) { Write-Host ""; Write-Host "No se pudo continuar: $Texto" -ForegroundColor Red; exit 1 }
function Comprobar([string]$Que) { if ($LASTEXITCODE -ne 0) { Detener "fallo $Que" } }

function OllamaResponde {
    try { $null = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 "http://127.0.0.1:11434/api/tags"; return $true }
    catch { return $false }
}

if ($SoloRevisar) {
    if (-not (Test-Path $Py)) { Detener "todavia no hay instalacion. Ejecuta instalar.ps1 sin -SoloRevisar." }
    & $Py -m scripts.revisar
    exit $LASTEXITCODE
}

Paso "1 de 7  Python"
# Se busca un Python oficial (compilado con MSVC) entre 3.10 y 3.13. El de MSYS2 o Cygwin no
# sirve: no hay paquetes compilados de faster-whisper, onnxruntime ni Piper para el. Y 3.14 es
# demasiado nuevo para varias librerias.
function Test-PythonCandidate([string[]]$Comando) {
    try {
        $Salida = & $Comando[0] @($Comando | Select-Object -Skip 1) -c "import sys; print('%d.%d' % sys.version_info[:2], 'MSC' in sys.version)" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $Salida) { return $null }
        $Partes = "$Salida".Trim() -split " "
        $V = [version]$Partes[0]
        if ($Partes[1] -ne "True" -or $V -lt [version]"3.10" -or $V -ge [version]"3.14") { return $null }
        return $Partes[0]
    } catch { return $null }
}
$Lanzador = (Get-Command py -ErrorAction SilentlyContinue).Source
if (-not $Lanzador -and (Test-Path "$env:LOCALAPPDATA\Programs\Python\Launcher\py.exe")) { $Lanzador = "$env:LOCALAPPDATA\Programs\Python\Launcher\py.exe" }
$Candidatos = @()
if ($Lanzador) { $Candidatos += foreach ($V in "3.12", "3.11", "3.13", "3.10") { ,@($Lanzador, "-$V") } }
$Candidatos += foreach ($V in "312", "311", "313", "310") { ,@("$env:LOCALAPPDATA\Programs\Python\Python$V\python.exe") }
$Candidatos += ,@("python")
$Python = $null; $Version = $null
foreach ($Candidato in $Candidatos) {
    if (-not (Get-Command $Candidato[0] -ErrorAction SilentlyContinue)) { continue }
    $Version = Test-PythonCandidate $Candidato
    if ($Version) { $Python = $Candidato; break }
}
if (-not $Python) { Detener "no encontre Python 3.10 a 3.13 de python.org. Instala Python 3.12 (winget install -e --id Python.Python.3.12) y vuelve a ejecutar este script." }
Write-Host "Python $Version ($($Python -join ' '))"

Paso "2 de 7  Tarjeta grafica y configuracion"
$Gigas = 0
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    $Gpu = (& nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits | Select-Object -First 1) -split ","
    $Gigas = [math]::Round([int]$Gpu[1].Trim() / 1024)
    Write-Host ("{0} con {1} GB" -f $Gpu[0].Trim(), $Gigas)
} else {
    Write-Host "Aviso: no hay GPU NVIDIA. El asistente funcionara por CPU, demasiado lento para conversar por voz." -ForegroundColor Yellow
}
if (-not (Test-Path .env)) {
    if ($Gigas -ge 12) { $Llm = "gemma3:12b"; $Whisper = "large-v3-turbo"; $Extra = @() }
    elseif ($Gigas -ge 6) { $Llm = "gemma3:4b"; $Whisper = "small"; $Extra = @() }
    else { $Llm = "gemma3:4b"; $Whisper = "small"; $Extra = @("WHISPER_DEVICE=cpu", "WHISPER_COMPUTE=int8") }
    $Texto = (Get-Content .env.example -Encoding UTF8) -replace "^LLM_MODEL=.*", "LLM_MODEL=$Llm" -replace "^WHISPER_MODEL=.*", "WHISPER_MODEL=$Whisper"
    $Texto += $Extra
    [IO.File]::WriteAllLines((Join-Path $PSScriptRoot ".env"), $Texto, (New-Object Text.UTF8Encoding $false))
    Write-Host "Se creo .env para $Gigas GB: modelo $Llm, reconocimiento de voz $Whisper. Puedes cambiarlo en .env."
} else {
    Write-Host ".env ya existe: se respeta."
}
$Llm = "gemma3:12b"
foreach ($Linea in Get-Content .env -Encoding UTF8) { if ($Linea -match "^\s*LLM_MODEL\s*=\s*([^#\s]+)") { $Llm = $Matches[1] } }
$Embed = "bge-m3"
foreach ($Linea in Get-Content .env -Encoding UTF8) { if ($Linea -match "^\s*EMBED_MODEL\s*=\s*([^#\s]+)") { $Embed = $Matches[1] } }
$Modelos = @($Llm, $Embed)

# onnxruntime (lo usan Piper y Chroma) necesita el Visual C++ Redistributable 2015-2022. Sin el,
# todo se instala pero la voz falla con "DLL load failed". Muchas computadoras no lo traen.
if (-not (Test-Path "$env:WINDIR\System32\vcruntime140_1.dll")) {
    Write-Host "Falta el Visual C++ Redistributable de Microsoft (lo necesita la voz)." -ForegroundColor Yellow
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { Detener "instalalo desde https://aka.ms/vs/17/release/vc_redist.x64.exe y vuelve a ejecutar este script." }
    $Respuesta = Read-Host "Lo instalo con winget? Windows pedira permiso de administrador (s/n)"
    if ($Respuesta -notmatch "^[sSyY]") { Detener "instalalo desde https://aka.ms/vs/17/release/vc_redist.x64.exe y vuelve a ejecutar este script." }
    winget install -e --id Microsoft.VCRedist.2015+.x64 --accept-source-agreements --accept-package-agreements; Comprobar "al instalar el Visual C++ Redistributable"
}

Paso "3 de 7  Entorno de Python y librerias"
if (-not (Test-Path $Py)) { & $Python[0] @($Python | Select-Object -Skip 1) -m venv .venv; Comprobar "al crear el entorno" }
& $Py -m pip install --quiet --upgrade pip; Comprobar "al actualizar pip"
# Sin --quiet: son unos 3 GB y con las barras de descarga se ve que avanza.
Write-Host "Descargando e instalando unos 3 GB de librerias; tarda de 10 a 25 minutos segun tu internet."
& $Py -m pip install --progress-bar on -r requirements.txt; Comprobar "al instalar las librerias"
if ($VozNatural) {
    & $Py -m pip install --quiet torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124; Comprobar "al instalar PyTorch"
    & $Py -m pip install --quiet -r requirements-voz-natural.txt; Comprobar "al instalar la voz natural"
}
# Que se instalen no basta: se comprueba que carguen (una DLL faltante solo se ve al importar).
& $Py -c "import onnxruntime, faster_whisper, piper, fastapi, streamlit" 2>$null
if ($LASTEXITCODE -ne 0) { Detener "las librerias se instalaron pero no cargan. Instala https://aka.ms/vs/17/release/vc_redist.x64.exe, reinicia la terminal y vuelve a ejecutar este script." }
Write-Host "Librerias instaladas"

Paso "4 de 7  Ollama y modelos de lenguaje"
# Una terminal abierta antes de instalar Ollama no lo tiene en el PATH: se busca en su carpeta.
$OllamaDir = Join-Path $env:LOCALAPPDATA "Programs\Ollama"
if (-not (Get-Command ollama -ErrorAction SilentlyContinue) -and (Test-Path "$OllamaDir\ollama.exe")) { $env:Path += ";$OllamaDir" }
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { Detener "falta Ollama. Instalalo desde https://ollama.com/download y vuelve a ejecutar este script." }
    $Respuesta = Read-Host "Falta Ollama. Lo instalo con winget? (s/n)"
    if ($Respuesta -notmatch "^[sSyY]") { Detener "instala Ollama desde https://ollama.com/download y vuelve a ejecutar este script." }
    winget install --id Ollama.Ollama -e --accept-source-agreements --accept-package-agreements
    # winget devuelve error si ya estaba instalado ("No available upgrade"): cuenta si el programa existe.
    if (-not (Test-Path "$OllamaDir\ollama.exe")) { Detener "fallo al instalar Ollama. Instalalo desde https://ollama.com/download y vuelve a ejecutar este script." }
    $env:Path += ";$OllamaDir"
}
Write-Host "Ollama encontrado"
if (-not (OllamaResponde)) {
    $App = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama app.exe"
    if (Test-Path $App) { Start-Process $App } else { Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden }
    foreach ($i in 1..30) { if (OllamaResponde) { break }; Start-Sleep -Seconds 1 }
    if (-not (OllamaResponde)) { Detener "Ollama no arranco. Abrelo a mano y vuelve a ejecutar este script." }
}
$Instalados = (& ollama list) -join "`n"
foreach ($Modelo in $Modelos) {
    if ($Instalados -match [regex]::Escape($Modelo)) { Write-Host "$Modelo ya estaba" }
    else { Write-Host "Descargando $Modelo (puede tardar varios minutos)"; & ollama pull $Modelo; Comprobar "al descargar $Modelo" }
}

Paso "5 de 7  Voces y reconocimiento de voz"
$Voces = $VocesTodas
if ($Minimo) { $Voces = $VocesMinimas }
# Una descarga cortada deja un archivo vacío o a medias: se borra y se vuelve a bajar.
foreach ($Voz in $Voces) {
    foreach ($Archivo in "data\voices\$Voz.onnx", "data\voices\$Voz.onnx.json") {
        if ((Test-Path $Archivo) -and (Get-Item $Archivo).Length -lt 1024) { Remove-Item $Archivo -Force }
    }
}
$Faltan = @($Voces | Where-Object { -not ((Test-Path "data\voices\$_.onnx") -and (Test-Path "data\voices\$_.onnx.json")) })
if ($Faltan.Count) { & $Py -m scripts.descargar_voces @Faltan; Comprobar "al descargar las voces (vuelve a ejecutar este script para reintentar)" }
Write-Host ("Voces instaladas: {0}" -f @(Get-ChildItem data\voices -Filter *.onnx).Count)
# El modelo de Whisper se baja aquí y no en la primera pregunta: si esa descarga se colgaba,
# el avatar contestaba por escrito pero nunca hablaba.
& $Py -m scripts.descargar_whisper; Comprobar "al descargar el modelo de reconocimiento de voz (vuelve a ejecutar este script)"
if ($VozNatural -and -not (Test-Path "data\voces_clonadas\es_demo-femenina.wav")) {
    & $Py -m scripts.descargar_voces_referencia; Comprobar "al descargar las voces de referencia"
}

Paso "6 de 7  Personajes 3D"
$SinAvatar = @($Avatares | Where-Object { -not (Test-Path "web\avatars\$_") })
if ($SinAvatar.Count) { & $Py -m scripts.descargar_avatares; Comprobar "al descargar los personajes" }
Write-Host ("Personajes instalados: {0}" -f @(Get-ChildItem web\avatars -Filter *.glb).Count)

Paso "7 de 7  Base de conocimiento y revision final"
& $Py -m app.ingest; Comprobar "al indexar los documentos"
& $Py -m scripts.revisar
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host ""
Write-Host "Instalacion terminada. Para encender el asistente ejecuta:  iniciar.bat" -ForegroundColor Green
