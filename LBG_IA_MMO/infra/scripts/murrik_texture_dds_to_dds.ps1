<#
.SYNOPSIS
  Pipeline DDS -> ComfyUI (via Agent_IA) -> DDS pour textures Murrik / re-skin SWG.

.DESCRIPTION
  1) Convertit InputDds en PNG (texconv recommande, sinon GIMP batch)
  2) Copie le PNG dans ComfyUI\input
  3) Queue le workflow API via POST /invoke (comfyui_patch_and_queue)
  4) Attend la sortie PNG (history + fallback dossier output)
  5) Reconvertit en DDS et ecrit OutputDds

  Prerequis:
  - ComfyUI demarre (http://127.0.0.1:8188)
  - Agent_IA demarre (run_agent.cmd)
  - LBG_DESKTOP_COMFYUI_ENABLED=1 dans desktop.env
  - Checkpoint DreamShaper_8_pruned.safetensors + control_v11f1e_sd15_tile.pth
  - texconv.exe (recommande) OU GIMP + plugin DDS

.EXAMPLE
  .\murrik_texture_dds_to_dds.ps1 `
    -InputDds "J:\swgemu\MOD_LBG\texture\bth_f_face.dds" `
    -OutputDds "J:\swgemu\MOD_LBG\texture\bth_f_face.dds" `
    -Approval "CHANGE-MOI"
#>
param(
  [Parameter(Mandatory = $true)]
  [string]$InputDds,
  [Parameter(Mandatory = $true)]
  [string]$OutputDds,
  [string]$BaseUrl = "http://127.0.0.1:5005",
  [string]$Approval = "",
  [string]$WorkflowPath = "C:\Agent_IA\workflows\murrik_texture_reskin_tile_v2_api.json",
  [string]$ComfyInputDir = "C:\Users\sdesh\ComfyUI\input",
  [string]$ComfyOutputDir = "C:\Users\sdesh\ComfyUI\output",
  [string]$WorkDir = "",
  [ValidateSet("face", "body", "auto")]
  [string]$TextureKind = "auto",
  [int]$Seed = 0,
  [double]$Denoise = -1,
  [ValidateSet("auto", "BC1", "BC3")]
  [string]$DdsFormat = "auto",
  [string]$TexconvPath = "",
  [string]$GimpPath = "",
  [string]$GimpSchemePath = "C:\Agent_IA\tools\gimp_dds_convert.scm",
  [string]$ClientId = "murrik-dds-pipeline",
  [int]$PollEveryMs = 800,
  [int]$TimeoutS = 600
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

function Invoke-DesktopAgent([hashtable]$payload) {
  $body = $payload | ConvertTo-Json -Depth 50
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

function Enum-Keys([object]$map) {
  if ($null -eq $map) { return @() }
  if ($map -is [System.Collections.IDictionary]) { return @($map.Keys) }
  try { return @($map.PSObject.Properties.Name) } catch { return @() }
}

function Get-Prop([object]$obj, [string]$name) {
  if ($null -eq $obj) { return $null }
  if ($obj -is [System.Collections.IDictionary]) {
    if ($obj.Contains($name)) { return $obj[$name] }
    return $null
  }
  if ($obj.PSObject.Properties.Name -contains $name) { return $obj.$name }
  return $null
}

function Get-HistoryEntry([object]$hist, [string]$promptId) {
  $hist = ConvertFrom-JsonSafe $hist
  if (-not $hist) { return $null }
  if (Get-Prop $hist "outputs") { return $hist }
  $byId = Get-Prop $hist $promptId
  if ($byId) { return $byId }
  $ks = Enum-Keys $hist
  if ($ks.Count -eq 1) { return (Get-Prop $hist $ks[0]) }
  return $null
}

function Find-FirstOutputImage([object]$entry) {
  $entry = ConvertFrom-JsonSafe $entry
  if (-not $entry) { return $null }
  $outs = ConvertFrom-JsonSafe (Get-Prop $entry "outputs")
  if (-not $outs) { return $null }
  foreach ($nodeId in (Enum-Keys $outs)) {
    $nodeOut = ConvertFrom-JsonSafe (Get-Prop $outs $nodeId)
    $imgs = ConvertFrom-JsonSafe (Get-Prop $nodeOut "images")
    if ($imgs -and $imgs.Count -gt 0) {
      foreach ($img in $imgs) {
        $img = ConvertFrom-JsonSafe $img
        $typ = Get-Prop $img "type"
        $fn = Get-Prop $img "filename"
        if ($typ -eq "output" -and $fn) { return $img }
      }
    }
  }
  foreach ($nodeId in (Enum-Keys $outs)) {
    $nodeOut = ConvertFrom-JsonSafe (Get-Prop $outs $nodeId)
    $imgs = ConvertFrom-JsonSafe (Get-Prop $nodeOut "images")
    if ($imgs -and $imgs.Count -gt 0) {
      return (ConvertFrom-JsonSafe $imgs[0])
    }
  }
  return $null
}

function Resolve-Texconv([string]$hint) {
  if ($hint -and (Test-Path -LiteralPath $hint)) { return (Resolve-Path -LiteralPath $hint).Path }
  $candidates = @(
    $env:TEXCONV,
    "C:\Agent_IA\tools\texconv.exe",
    "C:\Program Files\Microsoft DirectX Texconv\texconv.exe",
    "C:\Tools\texconv.exe"
  ) | Where-Object { $_ -and $_.ToString().Trim().Length -gt 0 }
  foreach ($c in $candidates) {
    if (Test-Path -LiteralPath $c) { return (Resolve-Path -LiteralPath $c).Path }
  }
  $cmd = Get-Command texconv.exe -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  return $null
}

function Resolve-Gimp([string]$hint) {
  if ($hint -and (Test-Path -LiteralPath $hint)) { return (Resolve-Path -LiteralPath $hint).Path }
  $candidates = @(
    "${env:ProgramFiles}\GIMP 2\bin\gimp-console-2.10.exe",
    "${env:ProgramFiles}\GIMP 2\bin\gimp-console.exe",
    "${env:ProgramFiles}\GIMP 3\bin\gimp-console-3.0.exe",
    "${env:ProgramFiles}\GIMP 3\bin\gimp-console.exe"
  )
  foreach ($c in $candidates) {
    if (Test-Path -LiteralPath $c) { return $c }
  }
  return $null
}

function Convert-DdsToPng([string]$dds, [string]$png, [string]$texconv, [string]$gimp, [string]$scheme) {
  $dir = Split-Path -Parent $png
  if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }

  if ($texconv) {
    & $texconv -y -nologo -ft png -o $dir $dds | Out-Null
    $base = [System.IO.Path]::GetFileNameWithoutExtension($dds)
    $produced = Join-Path $dir "$base.png"
    if (-not (Test-Path -LiteralPath $produced)) { throw "texconv n'a pas produit: $produced" }
    if ($produced -ne $png) { Move-Item -LiteralPath $produced -Destination $png -Force }
    return
  }

  if (-not $gimp) { throw "texconv introuvable et GIMP introuvable. Installe texconv (DirectXTex) ou GIMP." }
  if (-not (Test-Path -LiteralPath $scheme)) { throw "Script GIMP introuvable: $scheme" }
  $ddsEsc = $dds.Replace("\", "/")
  $pngEsc = $png.Replace("\", "/")
  $batch = "(load `"$($scheme.Replace('\','/'))`") (lbg-dds-convert `"$ddsEsc`" `"$pngEsc`" 'png) (gimp-quit 0)"
  & $gimp -i -b $batch | Out-Null
  if (-not (Test-Path -LiteralPath $png)) { throw "GIMP n'a pas produit: $png (plugin DDS requis pour lecture .dds)" }
}

function Convert-PngToDds([string]$png, [string]$dds, [string]$format, [string]$texconv, [string]$gimp, [string]$scheme) {
  $dir = Split-Path -Parent $dds
  if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }

  if ($texconv) {
    $flag = if ($format -eq "BC3") { "BC3_UNORM" } else { "BC1_UNORM" }
    # -m 0 = chaine complete de mipmaps (obligatoire pour SWG ; -m 1 provoquait crash client)
    & $texconv -y -nologo -f $flag -m 0 -o $dir $png | Out-Null
    $base = [System.IO.Path]::GetFileNameWithoutExtension($png)
    $produced = Join-Path $dir "$base.dds"
    if (-not (Test-Path -LiteralPath $produced)) { throw "texconv n'a pas produit: $produced" }
    if ($produced -ne $dds) { Move-Item -LiteralPath $produced -Destination $dds -Force }
    return
  }

  if (-not $gimp) { throw "texconv introuvable et GIMP introuvable pour export DDS." }
  if (-not (Test-Path -LiteralPath $scheme)) { throw "Script GIMP introuvable: $scheme" }
  $pngEsc = $png.Replace("\", "/")
  $ddsEsc = $dds.Replace("\", "/")
  $batch = "(load `"$($scheme.Replace('\','/'))`") (lbg-dds-convert `"$pngEsc`" `"$ddsEsc`" 'dds) (gimp-quit 0)"
  & $gimp -i -b $batch | Out-Null
  if (-not (Test-Path -LiteralPath $dds)) { throw "GIMP n'a pas produit: $dds" }
}

if (-not (Test-Path -LiteralPath $InputDds)) { throw "InputDds introuvable: $InputDds" }
if (-not (Test-Path -LiteralPath $WorkflowPath)) { throw "WorkflowPath introuvable: $WorkflowPath" }
if (-not (Test-Path -LiteralPath $ComfyInputDir)) { throw "ComfyInputDir introuvable: $ComfyInputDir" }
if (-not (Test-Path -LiteralPath $ComfyOutputDir)) { throw "ComfyOutputDir introuvable: $ComfyOutputDir" }

$texconv = Resolve-Texconv $TexconvPath
$gimp = Resolve-Gimp $GimpPath
Write-Host "== Murrik DDS pipeline ==" -ForegroundColor Cyan
Write-Host "Input : $InputDds"
Write-Host "Output: $OutputDds"
Write-Host "Agent : $BaseUrl"
Write-Host "texconv: $(if ($texconv) { $texconv } else { '(absent)' })"
Write-Host "gimp  : $(if ($gimp) { $gimp } else { '(absent)' })"

$baseName = [System.IO.Path]::GetFileName($InputDds)
$kind = $TextureKind
if ($kind -eq "auto") {
  if ($baseName -match "face|head|hair") { $kind = "face" } else { $kind = "body" }
}
$ddsFmt = $DdsFormat
if ($ddsFmt -eq "auto") { $ddsFmt = "BC3" }  # SWG bothan: face + body en DXT5

$denoiseVal = if ($Denoise -ge 0) { $Denoise } else { if ($kind -eq "face") { 0.18 } else { 0.14 } }
$seedVal = if ($Seed -ne 0) { $Seed } else { Get-Random -Minimum 1 -Maximum 2147483646 }

if (-not $WorkDir -or $WorkDir.Trim().Length -eq 0) {
  $WorkDir = Join-Path $env:TEMP ("murrik_dds_" + [DateTimeOffset]::UtcNow.ToUnixTimeSeconds())
}
New-Item -ItemType Directory -Path $WorkDir -Force | Out-Null

$workPngIn = Join-Path $WorkDir "input.png"
$workPngOut = Join-Path $WorkDir "output.png"
$comfyInputName = "murrik_work_input.png"
$comfyInputPath = Join-Path $ComfyInputDir $comfyInputName
$savePrefix = "murrik_reskin_out"

Write-Host "`n-- 1) DDS -> PNG --" -ForegroundColor Cyan
Convert-DdsToPng -dds $InputDds -png $workPngIn -texconv $texconv -gimp $gimp -scheme $GimpSchemePath
Copy-Item -LiteralPath $workPngIn -Destination $comfyInputPath -Force
Write-Host "ComfyUI input: $comfyInputPath" -ForegroundColor Green

Write-Host "`n-- 2) Queue ComfyUI via Agent --" -ForegroundColor Cyan
$wfText = Get-Content -LiteralPath $WorkflowPath -Raw -Encoding UTF8
$workflow = $wfText | ConvertFrom-Json
if (-not $workflow) { throw "Workflow JSON invalide: $WorkflowPath" }

$ops = @(
  @{ op = "set_input"; node = "208"; key = "image"; value = $comfyInputName },
  @{ op = "set_input"; node = "205"; key = "seed"; value = $seedVal },
  @{ op = "set_input"; node = "205"; key = "denoise"; value = $denoiseVal },
  @{ op = "set_input"; node = "300"; key = "filename_prefix"; value = $savePrefix }
)

$ctx = @{
  desktop_dry_run = $false
  desktop_action  = @{
    kind      = "comfyui_patch_and_queue"
    workflow  = $workflow
    ops       = $ops
    client_id = $ClientId
  }
}
if ($Approval -and $Approval.Trim().Length -gt 0) { $ctx.desktop_approval = $Approval }

$r = Invoke-DesktopAgent @{ actor_id = "murrik:dds_pipeline"; text = ""; context = $ctx }
$promptId = Get-Prop $r "prompt_id"
if (-not $promptId) {
  $remote = Get-Prop $r "remote"
  $promptId = Get-Prop $remote "prompt_id"
}
if (-not $promptId) {
  throw "Queue echouee (prompt_id manquant): $($r | ConvertTo-Json -Depth 20)"
}
Write-Host "prompt_id: $promptId  seed=$seedVal  denoise=$denoiseVal" -ForegroundColor Green

Write-Host "`n-- 3) Attente sortie PNG --" -ForegroundColor Cyan
$img = $null
$t0 = Get-Date
while ($true) {
  $elapsed = (New-TimeSpan -Start $t0 -End (Get-Date)).TotalSeconds
  if ($elapsed -gt $TimeoutS) { break }

  $ctxH = @{
    desktop_dry_run = $false
    desktop_action  = @{ kind = "comfyui_history"; prompt_id = $promptId }
  }
  if ($Approval -and $Approval.Trim().Length -gt 0) { $ctxH.desktop_approval = $Approval }
  $h = Invoke-DesktopAgent @{ actor_id = "murrik:dds_pipeline"; text = ""; context = $ctxH }
  $hist = Get-Prop $h "history"
  if (-not $hist) { $hist = Get-Prop $h "remote" }
  try {
    $entry = Get-HistoryEntry $hist $promptId
    $img = Find-FirstOutputImage $entry
    if ($img) { break }
  } catch {
    Write-Host "history parse: $($_.Exception.Message)" -ForegroundColor DarkYellow
  }

  $matches = @(Get-ChildItem -LiteralPath $ComfyOutputDir -File -Filter "${savePrefix}*" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending)
  if ($matches.Count -gt 0 -and $matches[0].LastWriteTime -gt $t0) {
    Copy-Item -LiteralPath $matches[0].FullName -Destination $workPngOut -Force
    Write-Host "fallback fichier: $($matches[0].FullName)" -ForegroundColor DarkGray
    break
  }
  Start-Sleep -Milliseconds $PollEveryMs
}

if ($img) {
  $ctxV = @{
    desktop_dry_run = $false
    desktop_action  = @{
      kind      = "comfyui_view"
      filename  = (Get-Prop $img "filename")
      subfolder = (Get-Prop $img "subfolder")
      type      = (Get-Prop $img "type")
      return    = "path"
    }
  }
  if ($Approval -and $Approval.Trim().Length -gt 0) { $ctxV.desktop_approval = $Approval }
  $v = Invoke-DesktopAgent @{ actor_id = "murrik:dds_pipeline"; text = ""; context = $ctxV }
  $dl = Get-Prop $v "path"
  if (-not $dl) { $dl = Get-Prop (Get-Prop $v "remote") "path" }
  if (-not $dl) { throw "comfyui_view sans path: $($v | ConvertTo-Json -Depth 12)" }
  Copy-Item -LiteralPath $dl -Destination $workPngOut -Force
  Write-Host "PNG ComfyUI: $dl" -ForegroundColor Green
} elseif (-not (Test-Path -LiteralPath $workPngOut)) {
  throw "Timeout: aucune image de sortie pour $promptId"
}

Write-Host "`n-- 4) PNG -> DDS --" -ForegroundColor Cyan
$outDir = Split-Path -Parent $OutputDds
if ($outDir -and -not (Test-Path -LiteralPath $outDir)) {
  New-Item -ItemType Directory -Path $outDir -Force | Out-Null
}
Convert-PngToDds -png $workPngOut -dds $OutputDds -format $ddsFmt -texconv $texconv -gimp $gimp -scheme $GimpSchemePath
Write-Host "DDS final: $OutputDds ($ddsFmt)" -ForegroundColor Green
Write-Host "`nOK" -ForegroundColor Cyan
