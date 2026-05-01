param(
  # Desktop agent Windows (Agent_IA)
  [string]$BaseUrl = "http://127.0.0.1:5005",
  # Approval token (requis si LBG_DESKTOP_APPROVAL_TOKEN est défini côté worker)
  [string]$Approval = "",
  # Chemin vers un workflow ComfyUI exporté en JSON "API" (pas le .json UI)
  [Parameter(Mandatory=$true)]
  [string]$WorkflowPath,
  # Optionnel : forcer un client_id pour corrélation côté ComfyUI
  [string]$ClientId = "smoke-comfyui",
  # Optionnel : patcher un champ seed sur un node ID
  [string]$SeedNode = "",
  [int]$Seed = 42,
  # Répertoire de sortie côté Windows (doit correspondre à LBG_COMFYUI_DOWNLOAD_DIR)
  [string]$DownloadDir = "C:\Agent_IA\comfyui_downloads",
  # Polling
  [int]$PollEveryMs = 800,
  [int]$TimeoutS = 180
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-DesktopAgent([hashtable]$payload) {
  $body = $payload | ConvertTo-Json -Depth 30
  return Invoke-RestMethod "$BaseUrl/invoke" -Method Post -ContentType "application/json" -Body $body
}

if (-not (Test-Path -LiteralPath $WorkflowPath)) {
  throw "WorkflowPath introuvable: $WorkflowPath"
}

Write-Host "== Smoke ComfyUI via Desktop Agent ==" -ForegroundColor Cyan
Write-Host "BaseUrl: $BaseUrl"
Write-Host "WorkflowPath: $WorkflowPath"
Write-Host "ClientId: $ClientId"
Write-Host "SeedNode: $SeedNode  Seed: $Seed"

$wfText = Get-Content -LiteralPath $WorkflowPath -Raw -Encoding UTF8
$workflow = $wfText | ConvertFrom-Json
if (-not $workflow) { throw "Impossible de parser le JSON du workflow." }

# Construire ops patch (optionnel)
$ops = @()
if ($SeedNode -and $SeedNode.Trim().Length -gt 0) {
  $ops += @{
    op   = "set_input"
    node = $SeedNode
    key  = "seed"
    value = $Seed
  }
}

Write-Host "`n-- queue (patch_and_queue si ops, sinon queue) --" -ForegroundColor Cyan
$ctx = @{
  desktop_dry_run = $false
  desktop_action  = $null
}
if ($Approval -and $Approval.Trim().Length -gt 0) {
  $ctx.desktop_approval = $Approval
}

if ($ops.Count -gt 0) {
  $ctx.desktop_action = @{
    kind = "comfyui_patch_and_queue"
    workflow = $workflow
    ops = $ops
    client_id = $ClientId
  }
} else {
  $ctx.desktop_action = @{
    kind = "comfyui_queue"
    workflow = $workflow
    client_id = $ClientId
  }
}

$r = Invoke-DesktopAgent @{
  actor_id = "smoke:comfyui"
  text     = ""
  context  = $ctx
}

$promptId = $r.prompt_id
if (-not $promptId) {
  Write-Host ($r | ConvertTo-Json -Depth 20) -ForegroundColor Yellow
  throw "Réponse sans prompt_id (queue a échoué)."
}
Write-Host "prompt_id: $promptId" -ForegroundColor Green

Write-Host "`n-- poll history --" -ForegroundColor Cyan
$t0 = Get-Date
$history = $null
while ($true) {
  $elapsed = (New-TimeSpan -Start $t0 -End (Get-Date)).TotalSeconds
  if ($elapsed -gt $TimeoutS) { throw "Timeout après ${TimeoutS}s en attente du history pour $promptId" }

  $ctx2 = @{
    desktop_dry_run = $false
    desktop_action  = @{ kind = "comfyui_history"; prompt_id = $promptId }
  }
  if ($Approval -and $Approval.Trim().Length -gt 0) {
    $ctx2.desktop_approval = $Approval
  }
  $h = Invoke-DesktopAgent @{
    actor_id = "smoke:comfyui"
    text     = ""
    context  = $ctx2
  }
  $history = $h.history
  if ($history) { break }
  Start-Sleep -Milliseconds $PollEveryMs
}

# Extraire le premier output image du history
$outFile = $null
$outSub = ""
$outType = "output"

try {
  foreach ($nodeId in $history.outputs.PSObject.Properties.Name) {
    $nodeOut = $history.outputs.$nodeId
    if ($nodeOut -and $nodeOut.images -and $nodeOut.images.Count -gt 0) {
      $img0 = $nodeOut.images[0]
      if ($img0.filename) {
        $outFile = $img0.filename
        $outSub = $img0.subfolder
        $outType = $img0.type
        break
      }
    }
  }
} catch {
  # no-op, handled below
}

if (-not $outFile) {
  Write-Host ($history | ConvertTo-Json -Depth 30) -ForegroundColor Yellow
  throw "Impossible de trouver un output image dans history (outputs.images[0])."
}

Write-Host "output: filename=$outFile subfolder=$outSub type=$outType" -ForegroundColor Green

Write-Host "`n-- comfyui_view (download) --" -ForegroundColor Cyan
$ctx3 = @{
  desktop_dry_run = $false
  desktop_action  = @{
    kind = "comfyui_view"
    filename = $outFile
    subfolder = $outSub
    type = $outType
    return = "path"
  }
}
if ($Approval -and $Approval.Trim().Length -gt 0) {
  $ctx3.desktop_approval = $Approval
}

$v = Invoke-DesktopAgent @{
  actor_id = "smoke:comfyui"
  text     = ""
  context  = $ctx3
}

if ($v.path) {
  Write-Host "Téléchargé: $($v.path)" -ForegroundColor Green
} else {
  Write-Host ($v | ConvertTo-Json -Depth 12) -ForegroundColor Yellow
  Write-Host "Note: return=path exige que LBG_COMFYUI_DOWNLOAD_DIR existe et soit writable." -ForegroundColor Yellow
}

Write-Host "`nOK" -ForegroundColor Cyan

