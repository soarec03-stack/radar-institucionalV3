# ============================================
# RADAR INSTITUCIONAL
# Atualização automática do radar.json
# ============================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================"
Write-Host " ATUALIZAÇÃO DO RADAR INSTITUCIONAL"
Write-Host "============================================"
Write-Host ""

# Garantir que estamos na raiz do projeto
Set-Location "$PSScriptRoot\.."

Write-Host "[1/4] Validando e gerando radar.json..."
python automation\validate_radar.py input\radar_input.txt --output radar.json

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERRO: a validação do Radar falhou." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[2/4] Adicionando radar.json ao Git..."
git add radar.json

Write-Host ""
Write-Host "[3/4] Criando commit..."
git commit -m "Atualiza radar institucional"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Nenhuma alteração para publicar."
    exit 0
}

Write-Host ""
Write-Host "[4/4] Enviando para o GitHub..."
git push

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERRO: não foi possível executar o git push." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "============================================"
Write-Host " RADAR PUBLICADO COM SUCESSO"
Write-Host "============================================"
Write-Host ""