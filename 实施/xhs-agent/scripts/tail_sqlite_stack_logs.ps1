param(
  [string]$LogDir = "data/logs",
  [int]$Tail = 80,
  [string[]]$LogName = @("api.log", "worker.log", "scheduler.log")
)

$ErrorActionPreference = "Stop"

foreach ($name in $LogName) {
  $path = Join-Path $LogDir $name
  Write-Host "==== $path ===="
  if (-not (Test-Path -LiteralPath $path)) {
    Write-Host "Log file not found."
    continue
  }
  Get-Content -LiteralPath $path -Tail $Tail
}
