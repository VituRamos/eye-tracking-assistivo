$ErrorActionPreference = "Stop"

# Build script (ASCII only para funcionar no PowerShell 5.1).
# Uso:  powershell -ExecutionPolicy Bypass -File .\build_exe.ps1

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[1/5] Criando ambiente virtual (.venv, Python 3.11)..."
    py -3.11 -m venv .venv
} else {
    Write-Host "[1/5] Reutilizando .venv existente."
}

$python = Join-Path $root ".venv\Scripts\python.exe"

Write-Host "[2/5] Instalando dependencias de build..."
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements-build.txt

New-Item -ItemType Directory -Force (Join-Path $root "models") | Out-Null
$modelo = Join-Path $root "models\face_landmarker.task"
if (-not (Test-Path $modelo)) {
    Write-Host "[3/5] Baixando modelo face_landmarker.task..."
    & $python -c "from config.loader import carregar_config; from core.model_loader import garantir_modelo_baixado; c=carregar_config(); m=c['modelo']; garantir_modelo_baixado('models/face_landmarker.task', m['url'], m['sha256_esperado'])"
} else {
    Write-Host "[3/5] Modelo ja presente em models\face_landmarker.task."
}

Write-Host "[4/5] Rodando testes..."
& $python -m pytest -q
& $python -m ruff check .

Write-Host "[5/5] Gerando executavel..."
& $python -m PyInstaller --noconfirm --clean EyeTrackingAssistivo.spec

Write-Host ""
Write-Host "Pronto: $root\dist\EyeTrackingAssistivo.exe"
Write-Host "Valide sem webcam:  .\dist\EyeTrackingAssistivo.exe --check"
Write-Host "O diagnostico sera salvo em diagnostico.txt ao lado do .exe."
