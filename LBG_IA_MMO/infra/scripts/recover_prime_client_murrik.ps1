# Désactive patch_murrik_00.tre si le client Prime ne démarre plus.
# Usage:
#   .\recover_prime_client_murrik.ps1
#   .\recover_prime_client_murrik.ps1 -GameDir "J:\swgemu\clients\prime-lbg"

param(
    [string]$GameDir = "J:\swgemu\clients\prime-lbg"
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host ">> $msg" -ForegroundColor Cyan }

if (-not (Test-Path $GameDir)) { throw "Dossier introuvable: $GameDir" }

Write-Step "Retrait patch_murrik des .cfg"
foreach ($name in @("user.cfg", "swgemu_live.cfg")) {
    $path = Join-Path $GameDir $name
    if (-not (Test-Path $path)) { continue }
    $bak = "$path.bak_murrik"
    if (Test-Path $bak) {
        Copy-Item -Force $bak $path
        Write-Host "  Restauré depuis $name.bak_murrik"
        continue
    }
    $text = Get-Content $path -Raw
    $text = $text -replace '(?m)^\s*searchTree_00_26=patch_murrik_00\.tre\s*\r?\n', ''
    $text = $text -replace 'maxSearchPriority=26', 'maxSearchPriority=25'
    Set-Content -Path $path -Value $text -NoNewline
    Write-Host "  Nettoyé $name"
}

$tre = Join-Path $GameDir "patch_murrik_00.tre"
if (Test-Path $tre) {
    Move-Item -Force $tre "$tre.bak"
    Write-Step "patch_murrik_00.tre -> patch_murrik_00.tre.bak"
}

Write-Host ""
Write-Host "Relance le client Prime. Si OK, le souci venait du TRE ou du .cfg Murrik."
