<#
Instala el Asistente Tec en esta computadora. Se puede ejecutar varias veces: salta lo que ya esta.

Uso (desde la carpeta del proyecto, en PowerShell):
    powershell -ExecutionPolicy Bypass -File instalar.ps1

Opciones:
    -Minimo       Solo las voces de espanol e ingles (descarga mas rapida).
    -VozNatural   Agrega la voz natural con clonacion (Chatterbox). Pide unos 3 GB mas de GPU.
    -SoloRevisar  No instala nada: solo dice que falta.

Requisitos que este script NO instala: Python 3.10 o posterior y los controladores de NVIDIA.
Detalles en docs/instalacion.md.
#>
param([switch]$Minimo, [switch]$VozNatural, [switch]$SoloRevisar)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$Modelos = @("gemma3:12b", "bge-m3")
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
$Python = $null
foreach ($Candidato in @("py", "python")) {
    if (Get-Command $Candidato -ErrorAction SilentlyContinue) { $Python = $Candidato; break }
}
if (-not $Python) { Detener "no encontre Python. Instala Python 3.10 o posterior desde python.org y marca 'Add python.exe to PATH'." }
$Version = & $Python -c "import sys; print('%d.%d' % sys.version_info[:2])"
if ([version]$Version -lt [version]"3.10") { Detener "hay Python $Version y se necesita 3.10 o posterior." }
Write-Host "Python $Version"

Paso "2 de 7  Tarjeta grafica"
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    $Gpu = (& nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits | Select-Object -First 1) -split ","
    $Gigas = [math]::Round([int]$Gpu[1].Trim() / 1024)
    Write-Host ("{0} con {1} GB" -f $Gpu[0].Trim(), $Gigas)
    if ($Gigas -lt 12) { Write-Host "Aviso: con menos de 12 GB hay que usar un modelo mas chico (ver docs/instalacion.md)." -ForegroundColor Yellow }
} else {
    Write-Host "Aviso: no hay GPU NVIDIA. El asistente funcionara por CPU, demasiado lento para conversar por voz." -ForegroundColor Yellow
}

Paso "3 de 7  Entorno de Python y librerias"
if (-not (Test-Path $Py)) { & $Python -m venv .venv; Comprobar "al crear el entorno" }
& $Py -m pip install --quiet --upgrade pip; Comprobar "al actualizar pip"
& $Py -m pip install --quiet -r requirements.txt; Comprobar "al instalar las librerias"
if ($VozNatural) {
    & $Py -m pip install --quiet torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124; Comprobar "al instalar PyTorch"
    & $Py -m pip install --quiet -r requirements-voz-natural.txt; Comprobar "al instalar la voz natural"
}
Write-Host "Librerias instaladas"

Paso "4 de 7  Ollama y modelos de lenguaje"
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { Detener "falta Ollama. Instalalo desde https://ollama.com/download y vuelve a ejecutar este script." }
    $Respuesta = Read-Host "Falta Ollama. Lo instalo con winget? (s/n)"
    if ($Respuesta -notmatch "^[sSyY]") { Detener "instala Ollama desde https://ollama.com/download y vuelve a ejecutar este script." }
    winget install --id Ollama.Ollama -e --accept-source-agreements --accept-package-agreements; Comprobar "al instalar Ollama"
    $env:Path += ";$env:LOCALAPPDATA\Programs\Ollama"
}
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

Paso "5 de 7  Voces"
$Voces = $VocesTodas
if ($Minimo) { $Voces = $VocesMinimas }
$Faltan = @($Voces | Where-Object { -not (Test-Path "data\voices\$_.onnx") })
if ($Faltan.Count) { & $Py -m piper.download_voices @Faltan --download-dir data\voices; Comprobar "al descargar las voces" }
Write-Host ("Voces instaladas: {0}" -f @(Get-ChildItem data\voices -Filter *.onnx).Count)
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
