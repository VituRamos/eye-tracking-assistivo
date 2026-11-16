$ErrorActionPreference = "Stop"

# Builds the Python sidecar (PyInstaller onedir) and copies it into the
# Tauri resources folder. ASCII only, for Windows PowerShell 5.1.

$app = Split-Path -Parent $PSScriptRoot
$raiz = Split-Path -Parent $app
$python = Join-Path $raiz ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Python virtualenv not found at $python"
}
if (-not (Test-Path (Join-Path $raiz "Ponte.spec"))) {
    throw "Ponte.spec not found at $raiz"
}

Push-Location $raiz
try {
    Write-Host "[1/3] Building eye-core with PyInstaller (onedir)..."
    & $python -m PyInstaller --noconfirm --clean Ponte.spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

$origem = Join-Path $raiz "dist\eye-core"
$destino = Join-Path $app "src-tauri\resources\eye-core"
if (-not (Test-Path $origem)) {
    throw "PyInstaller output not found at $origem"
}

Write-Host "[2/3] Cleaning previous resources..."
if (Test-Path $destino) {
    Remove-Item -Recurse -Force $destino
}
New-Item -ItemType Directory -Force (Split-Path -Parent $destino) | Out-Null

Write-Host "[3/3] Copying eye-core to Tauri resources..."
Copy-Item -Recurse -Force $origem $destino
Write-Host "Done: $destino"
