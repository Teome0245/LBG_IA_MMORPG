param(
  # Desktop agent Windows (Agent_IA)
  [string]$BaseUrl = "http://127.0.0.1:5005",
  # Approval token (requis si LBG_DESKTOP_APPROVAL_TOKEN est défini côté worker)
  [string]$Approval = "",

  # Workflows ComfyUI (export API JSON)
  [Parameter(Mandatory=$true)]
  [string]$WorkflowPass1Path,
  [Parameter(Mandatory=$true)]
  [string]$WorkflowPass2Path,

  # ComfyUI input dir (où LoadImage va chercher les fichiers)
  [string]$ComfyInputDir = "C:\Users\sdesh\ComfyUI\input",

  # Nom de fichier à (re)copier dans ComfyUI\input pour la pass 2
  # - pass1 output -> ComfyUI input sous ce nom
  [string]$Pass1OutputAsInputName = "bourg.png",

  # Optionnel : client_id (corrélation côté ComfyUI)
  [string]$ClientId = "smoke-comfyui-2pass",

  # Optionnel : patch seed sur un node ID (par pass)
  [string]$SeedNodePass1 = "205",
  [int]$SeedPass1 = 42,
  [string]$SeedNodePass2 = "205",
  [int]$SeedPass2 = 43,

  # Polling
  [int]$PollEveryMs = 800,
  [int]$TimeoutS = 240
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-DesktopAgent([hashtable]$payload) {
  $body = $payload | ConvertTo-Json -Depth 40
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
  return Invoke-RestMethod "$BaseUrl/invoke" -Method Post -ContentType "application/json" -Body $bytes
}

function Load-Workflow([string]$path) {
  if (-not (Test-Path -LiteralPath $path)) { throw "Workflow introuvable: $path" }
  $wfText = Get-Content -LiteralPath $path -Raw -Encoding UTF8
  $wf = $wfText | ConvertFrom-Json
  if (-not $wf) { throw "Impossible de parser le JSON: $path" }
  return $wf
}

function Queue-Workflow([object]$workflow, [string]$clientId, [string]$seedNode, [int]$seed) {
  $ops = @()
  if ($seedNode -and $seedNode.Trim().Length -gt 0) {
    $ops += @{ op = "set_input"; node = $seedNode; key = "seed"; value = $seed }
  }

  $ctx = @{
    desktop_dry_run = $false
    desktop_action  = $null
  }
  if ($Approval -and $Approval.Trim().Length -gt 0) { $ctx.desktop_approval = $Approval }

  if ($ops.Count -gt 0) {
    $ctx.desktop_action = @{
      kind      = "comfyui_patch_and_queue"
      workflow  = $workflow
      ops       = $ops
      client_id = $clientId
    }
  } else {
    $ctx.desktop_action = @{
      kind      = "comfyui_queue"
      workflow  = $workflow
      client_id = $clientId
    }
  }

  $r = Invoke-DesktopAgent @{ actor_id="smoke:comfyui"; text=""; context=$ctx }

  # L'agent peut renvoyer plusieurs shapes, on supporte:
  # - { prompt_id: "..." }
  # - { remote: { prompt_id: "..." } } (pattern agents HTTP)
  # - { result: { prompt_id: "..." } }
  $promptIdFound = $null
  if ($r -and ($r.PSObject.Properties.Name -contains "prompt_id")) { $promptIdFound = $r.prompt_id }
  elseif ($r -and ($r.PSObject.Properties.Name -contains "remote") -and $r.remote -and ($r.remote.PSObject.Properties.Name -contains "prompt_id")) { $promptIdFound = $r.remote.prompt_id }
  elseif ($r -and ($r.PSObject.Properties.Name -contains "result") -and $r.result -and ($r.result.PSObject.Properties.Name -contains "prompt_id")) { $promptIdFound = $r.result.prompt_id }

  if (-not $promptIdFound) {
    $dump = $r | ConvertTo-Json -Depth 40
    throw "Queue a échoué (prompt_id introuvable). Réponse agent: $dump"
  }
  return $promptIdFound
}

function Wait-History([string]$promptId) {
  $t0 = Get-Date
  while ($true) {
    $elapsed = (New-TimeSpan -Start $t0 -End (Get-Date)).TotalSeconds
    if ($elapsed -gt $TimeoutS) { throw "Timeout après ${TimeoutS}s en attente du history pour $promptId" }

    $ctx = @{
      desktop_dry_run = $false
      desktop_action  = @{ kind="comfyui_history"; prompt_id=$promptId }
    }
    if ($Approval -and $Approval.Trim().Length -gt 0) { $ctx.desktop_approval = $Approval }

    $h = Invoke-DesktopAgent @{ actor_id="smoke:comfyui"; text=""; context=$ctx }

    $hist = $null
    if ($h -and ($h.PSObject.Properties.Name -contains "history")) { $hist = $h.history }
    elseif ($h -and ($h.PSObject.Properties.Name -contains "remote") -and $h.remote -and ($h.remote.PSObject.Properties.Name -contains "history")) { $hist = $h.remote.history }
    elseif ($h -and ($h.PSObject.Properties.Name -contains "result") -and $h.result -and ($h.result.PSObject.Properties.Name -contains "history")) { $hist = $h.result.history }

    if ($hist) {
      # ComfyUI /history renvoie souvent un objet { "<prompt_id>": { ... } }
      # Normaliser pour retourner directement l'entrée du prompt_id quand présent.
      if ($hist -and ($hist.PSObject.Properties.Name -contains $promptId)) {
        return $hist.$promptId
      }
      return $hist
    }
    Start-Sleep -Milliseconds $PollEveryMs
  }
}

function Extract-FirstImage([object]$history) {
  if (-not $history) { throw "History vide." }
  if (-not $history.outputs) { throw "History sans champ outputs: $($history | ConvertTo-Json -Depth 20)" }

  $outs = $history.outputs

  # Supporte PSCustomObject, Hashtable, Dictionary
  $keys = @()
  if ($outs -is [System.Collections.IDictionary]) {
    $keys = @($outs.Keys)
  } else {
    $keys = @($outs.PSObject.Properties.Name)
  }

  foreach ($nodeId in $keys) {
    $nodeOut = $null
    if ($outs -is [System.Collections.IDictionary]) { $nodeOut = $outs[$nodeId] } else { $nodeOut = $outs.$nodeId }
    if ($nodeOut -and $nodeOut.images -and $nodeOut.images.Count -gt 0) {
      $img0 = $nodeOut.images[0]
      if ($img0.filename) { return $img0 }
    }
  }

  throw "Impossible de trouver un output image dans history.outputs.*.images[0]."
}

function Download-Image([object]$img) {
  $ctx = @{
    desktop_dry_run = $false
    desktop_action  = @{
      kind      = "comfyui_view"
      filename  = $img.filename
      subfolder = $img.subfolder
      type      = $img.type
      return    = "path"
    }
  }
  if ($Approval -and $Approval.Trim().Length -gt 0) { $ctx.desktop_approval = $Approval }
  $v = Invoke-DesktopAgent @{ actor_id="smoke:comfyui"; text=""; context=$ctx }
  if (-not $v.path) { throw "comfyui_view n'a pas renvoyé de path: $($v | ConvertTo-Json -Depth 20)" }
  return $v.path
}

Write-Host "== ComfyUI 2-pass (via Desktop Agent) ==" -ForegroundColor Cyan
Write-Host "BaseUrl: $BaseUrl"
Write-Host "ComfyInputDir: $ComfyInputDir"
Write-Host "Pass1: $WorkflowPass1Path"
Write-Host "Pass2: $WorkflowPass2Path"

$wf1 = Load-Workflow $WorkflowPass1Path
$wf2 = Load-Workflow $WorkflowPass2Path

Write-Host "`n-- PASS 1: queue --" -ForegroundColor Cyan
$pid1 = Queue-Workflow -workflow $wf1 -clientId "$ClientId:pass1" -seedNode $SeedNodePass1 -seed $SeedPass1
Write-Host "prompt_id(pass1): $pid1" -ForegroundColor Green

Write-Host "`n-- PASS 1: wait + download --" -ForegroundColor Cyan
$h1 = Wait-History $pid1
$img1 = Extract-FirstImage $h1
$dl1 = Download-Image $img1
Write-Host "pass1 downloaded: $dl1" -ForegroundColor Green

Write-Host "`n-- PASS 1 -> PASS 2: copy as ComfyUI input --" -ForegroundColor Cyan
if (-not (Test-Path -LiteralPath $ComfyInputDir)) { throw "ComfyInputDir introuvable: $ComfyInputDir" }
$dst = Join-Path $ComfyInputDir $Pass1OutputAsInputName
Copy-Item -LiteralPath $dl1 -Destination $dst -Force
Write-Host "copied to: $dst" -ForegroundColor Green

Write-Host "`n-- PASS 2: queue --" -ForegroundColor Cyan
$pid2 = Queue-Workflow -workflow $wf2 -clientId "$ClientId:pass2" -seedNode $SeedNodePass2 -seed $SeedPass2
Write-Host "prompt_id(pass2): $pid2" -ForegroundColor Green

Write-Host "`n-- PASS 2: wait + download final --" -ForegroundColor Cyan
$h2 = Wait-History $pid2
$img2 = Extract-FirstImage $h2
$dl2 = Download-Image $img2
Write-Host "FINAL downloaded: $dl2" -ForegroundColor Green

Write-Host "`nOK" -ForegroundColor Cyan

