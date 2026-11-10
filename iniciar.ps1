$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    throw 'Primero ejecuta .\instalar.ps1.'
}
& ./.venv/Scripts/python.exe -m streamlit run app.py
