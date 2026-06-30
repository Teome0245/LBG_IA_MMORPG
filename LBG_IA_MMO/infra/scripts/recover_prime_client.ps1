# Rollback client Prime si lbgemu.exe ne démarre plus.
# Usage (PowerShell) :
#   .\recover_prime_client.ps1
#   .\recover_prime_client.ps1 -GameDir "D:\swgemu\clients\prime-lbg"

param(
    [string]$GameDir = "J:\swgemu\clients\prime-lbg",
    [string]$PrecuDir = "J:\swgemu\clients\precu-original"
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host ">> $msg" -ForegroundColor Cyan }

if (-not (Test-Path $GameDir)) {
    Write-Error "Dossier Prime introuvable: $GameDir"
}

Write-Step "Désactivation patch_lbg_00.tre dans les .cfg"
$files = @("user.cfg", "swgemu_live.cfg")
foreach ($name in $files) {
    $path = Join-Path $GameDir $name
    if (-not (Test-Path $path)) { continue }
    $text = Get-Content $path -Raw
    $text = $text -replace '(?m)^\s*searchTree_00_99=patch_lbg_00\.tre\s*\r?\n', ''
    $text = $text -replace '(?m)^\s*searchTree_00_25=patch_lbg_00\.tre\s*\r?\n', ''
    $text = $text -replace 'maxSearchPriority=99', 'maxSearchPriority=98'
    $text = $text -replace 'maxSearchPriority=26', 'maxSearchPriority=25'
    Set-Content -Path $path -Value $text -NoNewline
    Write-Host "  OK $name"
}

$badTre = Join-Path $GameDir "patch_lbg_00.tre"
if (Test-Path $badTre) {
    $bak = "$badTre.bak"
    Move-Item -Force $badTre $bak
    Write-Step "patch_lbg_00.tre renommé en patch_lbg_00.tre.bak"
}

$exe = Join-Path $GameDir "lbgemu.exe"
$precuExe = Join-Path $PrecuDir "SWGEmu.exe"
if (Test-Path $precuExe) {
    Write-Step "Restauration lbgemu.exe depuis PreCu"
    Copy-Item -Force $precuExe $exe
    $len = (Get-Item $exe).Length
    Write-Host "  lbgemu.exe = $len octets"
} else {
    Write-Warning "SWGEmu.exe PreCu introuvable: $precuExe — restaure lbgemu.exe à la main"
}

Write-Step "Test de lancement (5 s)"
$cfg = Join-Path $GameDir "swgemu.cfg"
if (-not (Test-Path $cfg)) {
    Write-Error "swgemu.cfg manquant dans $GameDir"
}
$p = Start-Process -FilePath $exe -ArgumentList @("-s", "swgemu.cfg") -WorkingDirectory $GameDir -PassThru
Start-Sleep -Seconds 5
if (-not $p.HasExited) {
    Write-Host "OK — processus toujours actif (PID $($p.Id)). Ferme la fenêtre SWG à la main." -ForegroundColor Green
    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
} else {
    Write-Host "ECHEC — le client s'est fermé (code $($p.ExitCode))." -ForegroundColor Red
    Write-Host "Vérifie patch_fr_00.tre, data_*.tre, antivirus, et lance:"
    Write-Host "  cd `"$GameDir`""
    Write-Host "  .\lbgemu.exe -s swgemu.cfg"
}

Write-Host ""
Write-Host "Ensuite: Launchpad Prime -> Vérifier Mises à Jour (récupère swgemu_live.cfg / user.cfg sans patch_lbg)."
