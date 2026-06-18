#Requires -Version 5.1
<#
.SYNOPSIS
  Déploie LBG Launchpad + clients PreCu/Prime sur un PC Windows vierge.

.DESCRIPTION
  Copie le launchpad, les installations jeu (robocopy), ajuste launchpad.config.json
  et applique les patches HTTP (manifest MD5) depuis la VM 245.

.PARAMETER TargetRoot
  Racine cible (ex. J:\swgemu ou D:\Games\swgemu).

.PARAMETER SourceRoot
  Partage ou disque source contenant dist\win-unpacked, StarWarsGalaxies, clients\prime-lbg.

.PARAMETER PatchServerUrl
  URL de base du serveur de patches (sans slash final).

.PARAMETER SkipGameCopy
  Ne copie que le launchpad (jeu déjà présent).

.EXAMPLE
  .\deploy_client_new_pc.ps1 -SourceRoot \\192.168.0.245\swgemu -TargetRoot D:\swgemu
#>
[CmdletBinding()]
param(
    [string] $TargetRoot = 'D:\swgemu',
    [Parameter(Mandatory = $true)]
    [string] $SourceRoot,
    [string] $PatchServerUrl = 'http://192.168.0.245:8080',
    [string] $StatusApiUrl = 'http://192.168.0.245:8792/api/servers',
    [int] $MinFreeGb = 40,
    [switch] $SkipGameCopy
)

$ErrorActionPreference = 'Stop'

function Write-Step([string]$Message) {
    Write-Host "[deploy] $Message" -ForegroundColor Cyan
}

function Get-DriveFreeGb([string]$Path) {
    $root = [System.IO.Path]::GetPathRoot($Path)
    if (-not $root) { return $null }
    $drive = Get-PSDrive -Name ($root.TrimEnd('\').TrimEnd(':')) -ErrorAction SilentlyContinue
    if ($drive) { return [math]::Round($drive.Free / 1GB, 1) }
    $di = New-Object System.IO.DriveInfo($root)
    if ($di.IsReady) { return [math]::Round($di.AvailableFreeSpace / 1GB, 1) }
    return $null
}

function Invoke-RobocopyMirror {
    param(
        [string]$Source,
        [string]$Destination,
        [string]$Label
    )
    if (-not (Test-Path -LiteralPath $Source)) {
        throw "Source introuvable ($Label): $Source"
    }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Write-Step "Robocopy $Label → $Destination"
    $args = @(
        $Source, $Destination,
        '/MIR', '/R:2', '/W:5',
        '/MT:8', '/NFL', '/NDL', '/NP',
        '/XD', 'win-unpacked\resources', 'node_modules'
    )
    & robocopy @args | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "Robocopy échec ($Label), code $LASTEXITCODE"
    }
}

function Set-LoginPort {
    param(
        [string]$CfgPath,
        [int]$Port,
        [string]$LoginAddress = '192.168.0.245'
    )
    if (-not (Test-Path -LiteralPath $CfgPath)) { return }
    $text = Get-Content -LiteralPath $CfgPath -Raw
    $text = $text -replace 'loginServerPort\d*=.*', "loginServerPort0=$Port"
    $text = $text -replace 'loginServerAddress\d*=.*', "loginServerAddress0=$LoginAddress"
    if ($text -notmatch 'loginServerAddress') {
        $text = "[ClientGame]`r`nloginServerAddress0=$LoginAddress`r`nloginServerPort0=$Port`r`n" + $text
    }
    Set-Content -LiteralPath $CfgPath -Value $text.TrimEnd() -NoNewline -Encoding ASCII
    Write-Step "Login $LoginAddress`:$Port → $CfgPath"
}

function Get-FileMd5([string]$Path) {
    $hash = Get-FileHash -LiteralPath $Path -Algorithm MD5
    return $hash.Hash.ToLowerInvariant()
}

function Apply-PatchManifest {
    param(
        [string]$Channel,
        [string]$GameDir
    )
    $manifestUrl = "$PatchServerUrl/patches/$Channel/manifest.json"
    Write-Step "Patches $Channel depuis $manifestUrl"
    try {
        $manifest = Invoke-RestMethod -Uri $manifestUrl -TimeoutSec 15
    } catch {
        Write-Warning "Manifest $Channel indisponible: $_"
        return
    }
    if (-not $manifest.files -or $manifest.files.Count -eq 0) {
        Write-Warning "Manifest $Channel vide — rien à télécharger."
        return
    }
    foreach ($file in $manifest.files) {
        $dest = Join-Path $GameDir $file.name
        $need = $true
        if (Test-Path -LiteralPath $dest) {
            $local = Get-FileMd5 $dest
            if ($local -eq $file.hash) { $need = $false }
        }
        if (-not $need) { continue }
        $dir = Split-Path -Parent $dest
        if ($dir -and -not (Test-Path -LiteralPath $dir)) {
            New-Item -ItemType Directory -Force -Path $dir | Out-Null
        }
        $urls = @(
            "$PatchServerUrl/patches/$Channel/$($file.name)",
            "$PatchServerUrl/$($file.name)"
        )
        $ok = $false
        foreach ($url in $urls) {
            try {
                Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing -TimeoutSec 120
                $ok = $true
                break
            } catch {
                Write-Verbose "Échec $url : $_"
            }
        }
        if (-not $ok) { throw "Téléchargement impossible: $($file.name)" }
        Write-Step "  patché $($file.name)"
    }
}

# --- Préchecks ---
$SourceRoot = $SourceRoot.TrimEnd('\')
$TargetRoot = $TargetRoot.TrimEnd('\')

$free = Get-DriveFreeGb $TargetRoot
if ($null -ne $free -and $free -lt $MinFreeGb) {
    Write-Warning "Espace libre ~${free} Go sur $(Split-Path $TargetRoot -Qualifier) — ${MinFreeGb} Go recommandés."
}

$launchSrc = Join-Path $SourceRoot 'dist\win-unpacked'
$precuSrc = Join-Path $SourceRoot 'StarWarsGalaxies'
$primeSrc = Join-Path $SourceRoot 'clients\prime-lbg'

$launchDst = Join-Path $TargetRoot 'dist\win-unpacked'
$precuDst = Join-Path $TargetRoot 'StarWarsGalaxies'
$primeDst = Join-Path $TargetRoot 'clients\prime-lbg'

# --- Launchpad ---
Invoke-RobocopyMirror -Source $launchSrc -Destination $launchDst -Label 'Launchpad'

# --- Jeux ---
if (-not $SkipGameCopy) {
    Invoke-RobocopyMirror -Source $precuSrc -Destination $precuDst -Label 'PreCu (StarWarsGalaxies)'
    Invoke-RobocopyMirror -Source $primeSrc -Destination $primeDst -Label 'Prime (prime-lbg)'
}

# --- Ports login (sécurité si robocopy a copié une cfg erronée) ---
Set-LoginPort -CfgPath (Join-Path $precuDst 'swgemu_login.cfg') -Port 44453 -LoginAddress '192.168.0.245'
Set-LoginPort -CfgPath (Join-Path $primeDst 'swgemu_login.cfg') -Port 44553 -LoginAddress '192.168.0.246'

# --- launchpad.config.json ---
$configPath = Join-Path $launchDst 'launchpad.config.json'
$precuDir = $precuDst -replace '\\', '\\'
$primeDir = $primeDst -replace '\\', '\\'
$config = @{
    launchpadVersion = '2.0.0'
    statusApiUrl       = $StatusApiUrl
    patchServerUrl     = $PatchServerUrl
    patchServerUrlNas  = ''
    diskSpaceWarningGb = $MinFreeGb
    defaultProfileId   = 'prime'
    profiles           = @(
        @{
            id           = 'precu'
            label        = 'SWGEmu PreCu (original)'
            gameDir        = $precuDst
            gameExe        = 'SWGEmu.exe'
            configFile     = 'swgemu.cfg'
            patchChannel   = 'precu'
            servers        = @(@{
                id        = 'precu'
                label     = 'LBG SWGEMU PreCu'
                ip        = '192.168.0.245'
                loginPort = 44453
            })
        },
        @{
            id           = 'prime'
            label        = 'LBG Prime'
            gameDir        = $primeDst
            gameExe        = 'lbgemu.exe'
            configFile     = 'swgemu.cfg'
            patchChannel   = 'prime'
            servers        = @(@{
                id        = 'prime'
                label     = 'LBG MMO Serveur Prime'
                ip        = '192.168.0.246'
                loginPort = 44553
            })
        }
    )
}
$config | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $configPath -Encoding UTF8
Write-Step "Config launchpad → $configPath"

# --- Patches HTTP ---
if (-not $SkipGameCopy) {
    Apply-PatchManifest -Channel 'precu' -GameDir $precuDst
    Apply-PatchManifest -Channel 'prime' -GameDir $primeDst
}

Write-Host ""
Write-Host "Déploiement terminé." -ForegroundColor Green
Write-Host "  Lancer : $launchDst\LBG Launchpad.exe"
Write-Host "  PreCu  : $precuDst  (port 44453)"
Write-Host "  Prime  : $primeDst  (port 44553)"
Write-Host ""
Write-Host "Publier les patches sur la VM : infra/scripts/install_client_patch_server_245.sh" -ForegroundColor Yellow
