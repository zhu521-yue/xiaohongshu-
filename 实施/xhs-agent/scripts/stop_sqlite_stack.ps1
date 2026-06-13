param(
  [switch]$Apply
)

$ErrorActionPreference = "Stop"

function Find-StackProcesses {
  $scriptNames = @(
    "run_api.py",
    "run_worker.py",
    "run_creator_performance_scheduler.py"
  )
  try {
    Get-CimInstance Win32_Process |
      Where-Object {
        $commandLine = [string]$_.CommandLine
        foreach ($scriptName in $scriptNames) {
          if ($commandLine -like "*$scriptName*") {
            return $true
          }
        }
        return $false
      } |
      Select-Object ProcessId, Name, CommandLine
  } catch {
    Write-Warning "Unable to inspect process command lines: $($_.Exception.Message)"
    @()
  }
}

$processes = @(Find-StackProcesses)
Write-Host "Matched stack process count: $($processes.Count)"
$processes | ConvertTo-Json -Depth 3

if ($Apply) {
  foreach ($process in $processes) {
    Write-Host "Stopping PID=$($process.ProcessId) $($process.Name)"
    Stop-Process -Id $process.ProcessId -Force
  }
} else {
  Write-Host "Dry run only. Re-run with -Apply to stop matched processes."
}
exit 0
