param(
  [string]$BaseUrl = "http://127.0.0.1:5005",
  [switch]$Real,
  [string]$Approval = "",
  [string]$Url = "https://example.org",
  [int]$WaitMs = 800
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-DesktopAgent([hashtable]$payload) {
  $body = $payload | ConvertTo-Json -Depth 12
  return Invoke-RestMethod "$BaseUrl/invoke" -Method Post -ContentType "application/json" -Body $body
}

Write-Host "== Desktop Agent smoke ==" -ForegroundColor Cyan
Write-Host "BaseUrl: $BaseUrl"
Write-Host "Mode: " -NoNewline
if ($Real) { Write-Host "REAL" -ForegroundColor Yellow } else { Write-Host "DRY-RUN" -ForegroundColor Green }

Write-Host "`n-- healthz --" -ForegroundColor Cyan
$hz = Invoke-RestMethod "$BaseUrl/healthz"
$hz | ConvertTo-Json -Depth 10 | Write-Host

$dryRun = -not $Real

Write-Host "`n-- run_steps: open_url -> wait_ms -> observe_screen --" -ForegroundColor Cyan
$ctx = @{
  desktop_dry_run = $dryRun
  desktop_action  = @{
    kind         = "run_steps"
    stop_on_fail = $false
    steps        = @(
      @{ kind = "open_url"; url = $Url },
      @{ kind = "wait_ms"; ms = $WaitMs },
      @{ kind = "observe_screen" }
    )
  }
}
if ($Approval -and $Approval.Trim().Length -gt 0) {
  $ctx.desktop_approval = $Approval
}

$r = Invoke-DesktopAgent @{
  actor_id = "smoke"
  text     = ""
  context  = $ctx
}

$r | ConvertTo-Json -Depth 12 | Write-Host

if ($r.step_outputs -and $r.step_outputs.Count -gt 0) {
  $last = $r.step_outputs[$r.step_outputs.Count - 1]
  if ($last.path) {
    Write-Host "`nScreenshot path: $($last.path)" -ForegroundColor Green
  }
}

if ($r.errors -and $r.errors.Count -gt 0) {
  Write-Host "`nErrors:" -ForegroundColor Red
  $r.errors | ConvertTo-Json -Depth 8 | Write-Host
}

