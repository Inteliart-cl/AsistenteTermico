$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    $bundledPython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
    if (Test-Path -LiteralPath $bundledPython) {
        & $bundledPython -m venv .venv
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv .venv
    } else {
        throw 'Instala Python 3.12 o superior y vuelve a ejecutar este archivo.'
    }
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno de Python.' }
}
& ./.venv/Scripts/python.exe -m pip install -r requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las bibliotecas.' }
Write-Host 'Aplicación preparada. Ejecuta .\iniciar.ps1 para abrirla.'
