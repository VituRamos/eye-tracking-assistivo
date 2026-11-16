$ErrorActionPreference = "Stop"

# Prepara um clone recem-baixado: ambiente Python, dependencias do Python e
# da interface Tauri, testes e validacao do modelo.
# ASCII only, para funcionar no Windows PowerShell 5.1.
# Uso:  powershell -ExecutionPolicy Bypass -File .\setup.ps1

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[1/5] Criando ambiente virtual (.venv, Python 3.11)..."
    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -3.11 -m venv .venv
    } else {
        python -m venv .venv
    }
} else {
    Write-Host "[1/5] Reutilizando .venv existente."
}

$python = Join-Path $root ".venv\Scripts\python.exe"

Write-Host "[2/5] Instalando dependencias Python..."
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements-dev.txt

Write-Host "[3/5] Validando modelo e instalacao..."
& $python main.py --check

Write-Host "[4/5] Instalando e compilando a interface (pode demorar na primeira vez)..."
Push-Location (Join-Path $root "app")
try {
    npm install
    npm run build
}
finally {
    Pop-Location
}

Write-Host "[5/5] Rodando testes e lint..."
& $python -m pytest -q
& $python -m ruff check .

Write-Host ""
Write-Host "Pronto: modelo, dependencias e interface preparados."
Write-Host "Aplicativo Python:      .venv\Scripts\python.exe main.py"
Write-Host "Interface (navegador):  cd app; npm run dev"
Write-Host "App desktop:            cd app; npm run tauri dev"
Write-Host "Instalador:             cd app; npm run sidecar; npm run tauri build"
