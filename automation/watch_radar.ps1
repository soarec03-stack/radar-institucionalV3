# ============================================
# RADAR INSTITUCIONAL
# Monitor automático do radar_input.txt
# ============================================

$ErrorActionPreference = "Stop"

Set-Location "$PSScriptRoot\.."

$arquivo = Join-Path (Get-Location) "input\radar_input.txt"

Write-Host ""
Write-Host "============================================"
Write-Host " MONITOR DO RADAR INSTITUCIONAL"
Write-Host "============================================"
Write-Host ""
Write-Host "Monitorando:"
Write-Host $arquivo
Write-Host ""
Write-Host "Verificação a cada 2 segundos."
Write-Host "Pressione CTRL+C para encerrar."
Write-Host ""

$ultimaData = (Get-Item $arquivo).LastWriteTime

while ($true) {

    Start-Sleep -Seconds 2

    $dataAtual = (Get-Item $arquivo).LastWriteTime

    if ($dataAtual -ne $ultimaData) {

        $ultimaData = $dataAtual

        Write-Host ""
        Write-Host "============================================"
        Write-Host " ALTERAÇÃO DETECTADA"
        Write-Host "============================================"
        Write-Host ""

        Write-Host "Executando atualização do Radar..."
        Write-Host ""

        & "$PSScriptRoot\update_radar.ps1"

        Write-Host ""
        Write-Host "============================================"
        Write-Host " MONITORAMENTO CONTINUA ATIVO"
        Write-Host "============================================"
        Write-Host ""
    }
}