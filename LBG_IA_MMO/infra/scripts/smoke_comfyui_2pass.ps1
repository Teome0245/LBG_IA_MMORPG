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
  # ComfyUI output dir (où SaveImage écrit les fichiers)
  [string]$ComfyOutputDir = "C:\Users\sdesh\ComfyUI\output",

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

  # Optionnel : forcer SaveImage à produire un output (évite cache -> outputs {}).
  [string]$SaveNodePass1 = "300",
  [string]$SaveNodePass2 = "300",
  [string]$SavePrefixPass1 = "lbg_map_pass1",
  [string]$SavePrefixPass2 = "lbg_map_pass2",

  # Polling
  [int]$PollEveryMs = 800,
  # Sur GPU petit / low VRAM + décodage VAE (potentiellement long / tiled), une passe peut dépasser 30 minutes.
  [int]$TimeoutS = 3600
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-DesktopAgent([hashtable]$payload) {
  $body = $payload | ConvertTo-Json -Depth 40
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
  return Invoke-RestMethod "$BaseUrl/invoke" -Method Post -ContentType "application/json" -Body $bytes
}

function ConvertFrom-JsonSafe([object]$obj) {
  if ($null -eq $obj) { return $null }
  if ($obj -is [string]) {
    $t = $obj.Trim()
    if ($t.Length -eq 0) { return $null }
    try { return ($t | ConvertFrom-Json) } catch { return $null }
  }
  return $obj
}

function Has-Property([object]$obj, [string]$name) {
  if ($null -eq $obj) { return $false }
  if ($obj -is [System.Collections.IDictionary]) { return $obj.ContainsKey($name) }
  try {
    return ($obj.PSObject.Properties.Name -contains $name)
  } catch {
    return $false
  }
}

function Get-Property([object]$obj, [string]$name) {
  if ($null -eq $obj) { return $null }
  if ($obj -is [System.Collections.IDictionary]) {
    if ($obj.ContainsKey($name)) { return $obj[$name] }
    return $null
  }
  try {
    return $obj.$name
  } catch {
    return $null
  }
}

function Enum-Keys([object]$map) {
  if ($null -eq $map) { return @() }
  if ($map -is [System.Collections.IDictionary]) {
    return @($map.Keys)
  }
  try {
    return @($map.PSObject.Properties.Name)
  } catch {
    return @()
  }
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

function Queue-Workflow2([object]$workflow, [string]$clientId, [string]$seedNode, [int]$seed, [string]$saveNode, [string]$savePrefix) {
  $ops = @()
  if ($seedNode -and $seedNode.Trim().Length -gt 0) {
    $ops += @{ op = "set_input"; node = $seedNode; key = "seed"; value = $seed }
  }

  # Forcer une exécution non-cachée : change filename_prefix à chaque run.
  $prefix = $savePrefix
  if ($saveNode -and $saveNode.Trim().Length -gt 0) {
    $ts = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $prefix = "{0}_{1}_{2}" -f $savePrefix, $seed, $ts
    $ops += @{ op = "set_input"; node = $saveNode; key = "filename_prefix"; value = $prefix }
  }

  $ctx = @{
    desktop_dry_run = $false
    desktop_action  = @{
      kind      = "comfyui_patch_and_queue"
      workflow  = $workflow
      ops       = $ops
      client_id = $clientId
    }
  }
  if ($Approval -and $Approval.Trim().Length -gt 0) { $ctx.desktop_approval = $Approval }

  $r = Invoke-DesktopAgent @{ actor_id="smoke:comfyui"; text=""; context=$ctx }

  $promptIdFound = $null
  if ($r -and ($r.PSObject.Properties.Name -contains "prompt_id")) { $promptIdFound = $r.prompt_id }
  elseif ($r -and ($r.PSObject.Properties.Name -contains "remote") -and $r.remote -and ($r.remote.PSObject.Properties.Name -contains "prompt_id")) { $promptIdFound = $r.remote.prompt_id }
  elseif ($r -and ($r.PSObject.Properties.Name -contains "result") -and $r.result -and ($r.result.PSObject.Properties.Name -contains "prompt_id")) { $promptIdFound = $r.result.prompt_id }

  if (-not $promptIdFound) {
    $dump = $r | ConvertTo-Json -Depth 40
    throw "Queue a échoué (prompt_id introuvable). Réponse agent: $dump"
  }
  return @{ prompt_id = $promptIdFound; filename_prefix = $prefix }
}

function Wait-ForOutputFile([string]$prefix) {
  if (-not (Test-Path -LiteralPath $ComfyOutputDir)) { throw "ComfyOutputDir introuvable: $ComfyOutputDir" }

  $t0 = Get-Date
  while ($true) {
    $elapsed = (New-TimeSpan -Start $t0 -End (Get-Date)).TotalSeconds
    if ($elapsed -gt $TimeoutS) { throw "Timeout après ${TimeoutS}s en attente d'un fichier output prefix=$prefix dans $ComfyOutputDir" }

    $raw = Get-ChildItem -LiteralPath $ComfyOutputDir -File -Filter "$prefix*" -ErrorAction SilentlyContinue |
      Sort-Object LastWriteTime -Descending
    $matches = @($raw)
    if ($matches.Length -gt 0) {
      return $matches[0].FullName
    }

    Start-Sleep -Milliseconds $PollEveryMs
  }
}

function Get-HistoryEntry([string]$promptId) {
  $ctx = @{
    desktop_dry_run = $false
    desktop_action  = @{ kind="comfyui_history"; prompt_id=$promptId }
  }
  if ($Approval -and $Approval.Trim().Length -gt 0) { $ctx.desktop_approval = $Approval }

  $h = Invoke-DesktopAgent @{ actor_id="smoke:comfyui"; text=""; context=$ctx }

  $hist = $null
  if (Has-Property $h "history") { $hist = Get-Property $h "history" }
  elseif (Has-Property $h "remote") {
    $remote = Get-Property $h "remote"
    if (Has-Property $remote "history") { $hist = Get-Property $remote "history" }
  }
  elseif (Has-Property $h "result") {
    $result = Get-Property $h "result"
    if (Has-Property $result "history") { $hist = Get-Property $result "history" }
  }

  $hist = ConvertFrom-JsonSafe $hist
  if (-not $hist) { return $null }

  # ComfyUI /history renvoie souvent un objet { "<prompt_id>": { ... } }
  if (Has-Property $hist $promptId) {
    return (Get-Property $hist $promptId)
  }

  # Si $hist est déjà l'entrée prompt (avec outputs), la renvoyer telle quelle.
  if (Has-Property $hist "outputs") {
    return $hist
  }

  # Sinon tenter la première clé (fallback best-effort)
  $ks = Enum-Keys $hist
  if ($ks.Count -eq 1) {
    return (Get-Property $hist $ks[0])
  }

  return $hist
}

function Try-Extract-FirstImage([object]$history) {
  try {
    return (Extract-FirstImage $history)
  } catch {
    return $null
  }
}

function Wait-HistoryWithImage([string]$promptId) {
  $t0 = Get-Date
  $lastEntry = $null
  $lastEntryDump = $null
  $iter = 0
  while ($true) {
    $elapsed = (New-TimeSpan -Start $t0 -End (Get-Date)).TotalSeconds
    if ($elapsed -gt $TimeoutS) {
      $suffix = ""
      if ($lastEntryDump) { $suffix = "`nDernier history (dump):`n$lastEntryDump" }
      throw "Timeout après ${TimeoutS}s en attente d'une image dans history pour $promptId$suffix"
    }

    $entry = Get-HistoryEntry $promptId
    if ($entry) {
      $lastEntry = $entry
      try { $lastEntryDump = ($entry | ConvertTo-Json -Depth 40) } catch { $lastEntryDump = "<dump failed>" }
      $img = Try-Extract-FirstImage $entry
      if ($img) { return $entry }
    }

    $iter += 1
    if (($iter % 15) -eq 0) {
      $msg = ("poll history: prompt_id={0} elapsed_s={1:n0} has_entry={2}" -f $promptId, $elapsed, [bool]$entry)
      Write-Host $msg -ForegroundColor DarkGray
    }
    Start-Sleep -Milliseconds $PollEveryMs
  }
}

function Extract-FirstImage([object]$history) {
  if (-not $history) { throw "History vide." }

  $history = ConvertFrom-JsonSafe $history

  $outs = Get-Property $history "outputs"
  $outs = ConvertFrom-JsonSafe $outs

  if (-not $outs) {
    throw "History sans champ outputs exploitable: $($history | ConvertTo-Json -Depth 40)"
  }

  foreach ($nodeId in (Enum-Keys $outs)) {
    $nodeOut = Get-Property $outs $nodeId
    $nodeOut = ConvertFrom-JsonSafe $nodeOut

    $imgs = Get-Property $nodeOut "images"
    $imgs = ConvertFrom-JsonSafe $imgs

    if ($imgs -and $imgs.Count -gt 0) {
      $img0 = $imgs[0]
      $img0 = ConvertFrom-JsonSafe $img0
      if ($img0 -and (Get-Property $img0 "filename")) { return $img0 }
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

  $p = $null
  if (Has-Property $v "path") { $p = Get-Property $v "path" }
  elseif (Has-Property $v "remote") {
    $remote = Get-Property $v "remote"
    if (Has-Property $remote "path") { $p = Get-Property $remote "path" }
  }
  elseif (Has-Property $v "result") {
    $result = Get-Property $v "result"
    if (Has-Property $result "path") { $p = Get-Property $result "path" }
  }

  if (-not $p) { throw "comfyui_view n'a pas renvoyé de path: $($v | ConvertTo-Json -Depth 40)" }
  return $p
}

Write-Host "== ComfyUI 2-pass (via Desktop Agent) ==" -ForegroundColor Cyan
Write-Host "BaseUrl: $BaseUrl"
Write-Host "ComfyInputDir: $ComfyInputDir"
Write-Host "Pass1: $WorkflowPass1Path"
Write-Host "Pass2: $WorkflowPass2Path"

$wf1 = Load-Workflow $WorkflowPass1Path
$wf2 = Load-Workflow $WorkflowPass2Path

Write-Host "`n-- PASS 1: queue --" -ForegroundColor Cyan
$q1 = Queue-Workflow2 -workflow $wf1 -clientId "$ClientId:pass1" -seedNode $SeedNodePass1 -seed $SeedPass1 -saveNode $SaveNodePass1 -savePrefix $SavePrefixPass1
$promptIdPass1 = $q1.prompt_id
$prefix1 = $q1.filename_prefix
Write-Host "prompt_id(pass1): $promptIdPass1" -ForegroundColor Green
Write-Host "save_prefix(pass1): $prefix1" -ForegroundColor DarkGray

Write-Host "`n-- PASS 1: wait + download --" -ForegroundColor Cyan
$out1 = Wait-ForOutputFile $prefix1
Write-Host "pass1 output: $out1" -ForegroundColor Green

Write-Host "`n-- PASS 1 -> PASS 2: copy as ComfyUI input --" -ForegroundColor Cyan
if (-not (Test-Path -LiteralPath $ComfyInputDir)) { throw "ComfyInputDir introuvable: $ComfyInputDir" }
$dst = Join-Path $ComfyInputDir $Pass1OutputAsInputName
Copy-Item -LiteralPath $out1 -Destination $dst -Force
Write-Host "copied to: $dst" -ForegroundColor Green

Write-Host "`n-- PASS 2: queue --" -ForegroundColor Cyan
$q2 = Queue-Workflow2 -workflow $wf2 -clientId "$ClientId:pass2" -seedNode $SeedNodePass2 -seed $SeedPass2 -saveNode $SaveNodePass2 -savePrefix $SavePrefixPass2
$promptIdPass2 = $q2.prompt_id
$prefix2 = $q2.filename_prefix
Write-Host "prompt_id(pass2): $promptIdPass2" -ForegroundColor Green
Write-Host "save_prefix(pass2): $prefix2" -ForegroundColor DarkGray

Write-Host "`n-- PASS 2: wait + download final --" -ForegroundColor Cyan
$out2 = Wait-ForOutputFile $prefix2
Write-Host "FINAL output: $out2" -ForegroundColor Green

Write-Host "`nOK" -ForegroundColor Cyan

