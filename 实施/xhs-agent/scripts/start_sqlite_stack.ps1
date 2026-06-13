param(
  [string]$HostName = "127.0.0.1",
  [int]$Port = 8010,
  [string]$Python = "",
  [string]$DbPath = "data/xhs_agent.sqlite3",
  [string]$WorkerId = "local-worker-1",
  [string]$WatchdogWorkerId = "local-watchdog-1",
  [string]$CollectorMode = "mock",
  [string]$CreatorMode = "mock",
  [string]$LLMModelName = "mock",
  [string]$ApiToken = $env:XHS_AGENT_API_TOKEN,
  [double]$HeartbeatIntervalSeconds = 30,
  [int]$HeartbeatTimeoutSeconds = 1800,
  [switch]$NoApi,
  [switch]$NoWorker,
  [switch]$NoWatchdog,
  [switch]$StartScheduler,
  [string[]]$CreatorNoteId = @(),
  [string[]]$RunId = @(),
  [double]$SchedulerIntervalSeconds = 1800,
  [int]$SchedulerMaxRounds = 0,
  [int]$SchedulerMaxConsecutiveFailedRounds = 3,
  [int]$SchedulerLimit = 50,
  [switch]$SchedulerWait,
  [int]$SchedulerAttempts = 5,
  [double]$SchedulerStatusIntervalSeconds = 2,
  [string]$SchedulerNotes = "",
  [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"

function Resolve-PythonCommand {
  param([string]$ConfiguredPython)

  if ($ConfiguredPython) {
    if (-not (Test-Path -LiteralPath $ConfiguredPython)) {
      throw "Configured Python does not exist: $ConfiguredPython"
    }
    return $ConfiguredPython
  }

  if ($env:XHS_AGENT_PYTHON) {
    if (-not (Test-Path -LiteralPath $env:XHS_AGENT_PYTHON)) {
      throw "XHS_AGENT_PYTHON does not exist: $($env:XHS_AGENT_PYTHON)"
    }
    return $env:XHS_AGENT_PYTHON
  }

  $contentSharePython = "D:\Anaconda\envs\ContentShare\python.exe"
  if (Test-Path -LiteralPath $contentSharePython) {
    return $contentSharePython
  }

  return "python"
}

function Add-OptionalRepeatedArgument {
  param(
    [string[]]$Arguments,
    [string]$Name,
    [string[]]$Values
  )

  foreach ($value in $Values) {
    $cleanValue = [string]$value
    $cleanValue = $cleanValue.Trim()
    if ($cleanValue) {
      $Arguments += @($Name, $cleanValue)
    }
  }
  return $Arguments
}

function Start-RuntimeProcess {
  param(
    [string]$Name,
    [string[]]$Arguments
  )

  Write-Host "Starting $Name"
  Write-Host "  $pythonCommand $($Arguments -join ' ')"
  $process = Start-Process -FilePath $pythonCommand -ArgumentList $Arguments -WorkingDirectory (Get-Location) -WindowStyle Hidden -PassThru
  Write-Host "  PID=$($process.Id)"
  $script:startedProcesses += [pscustomobject]@{
    name = $Name
    pid = $process.Id
    arguments = $Arguments -join " "
  }
}

$pythonCommand = Resolve-PythonCommand -ConfiguredPython $Python

$env:XHS_AGENT_RUN_STORE = "sqlite"
$env:XHS_AGENT_RUN_DB_PATH = $DbPath
$env:XHS_AGENT_RUN_QUEUE = "sqlite"
$env:XHS_AGENT_QUEUE_DB_PATH = $DbPath
$env:XHS_AGENT_MEMORY_STORE = "sqlite"
$env:XHS_AGENT_MEMORY_DB_PATH = $DbPath
$env:COLLECTOR_MODE = $CollectorMode
$env:CREATOR_MODE = $CreatorMode
$env:LLM_MODEL_NAME = $LLMModelName
$env:XHS_AGENT_API_TOKEN = $ApiToken
$env:XHS_AGENT_QUEUE_HEARTBEAT_INTERVAL_SECONDS = [string]$HeartbeatIntervalSeconds
$env:XHS_AGENT_QUEUE_HEARTBEAT_TIMEOUT_SECONDS = [string]$HeartbeatTimeoutSeconds

Write-Host "Using Python: $pythonCommand"
Write-Host "Mode: sqlite stack, db=$DbPath, collector=$CollectorMode, creator=$CreatorMode, llm=$LLMModelName, host=$HostName, port=$Port"
Write-Host "Heartbeat: interval=$HeartbeatIntervalSeconds, timeout=$HeartbeatTimeoutSeconds"

if ($CheckOnly) {
  & $pythonCommand ".\scripts\check_runtime_config.py" "--profile" "sqlite-worker"
  exit $LASTEXITCODE
}

$schedulerTargets = @($CreatorNoteId | Where-Object { ([string]$_).Trim() })
$schedulerTargets += @($RunId | Where-Object { ([string]$_).Trim() })
if ($StartScheduler -and $schedulerTargets.Count -eq 0) {
  throw "StartScheduler requires at least one CreatorNoteId or RunId."
}

$startedProcesses = @()

if (-not $NoApi) {
  Start-RuntimeProcess -Name "api" -Arguments @(
    ".\scripts\run_api.py",
    "--host",
    $HostName,
    "--port",
    [string]$Port
  )
}

if (-not $NoWorker) {
  Start-RuntimeProcess -Name "worker" -Arguments @(
    ".\scripts\run_worker.py",
    "--worker-id",
    $WorkerId
  )
}

if (-not $NoWatchdog) {
  Start-RuntimeProcess -Name "watchdog" -Arguments @(
    ".\scripts\run_worker.py",
    "--worker-id",
    $WatchdogWorkerId,
    "--watchdog-loop"
  )
}

if ($StartScheduler) {
  $schedulerArguments = @(
    ".\scripts\run_creator_performance_scheduler.py",
    "--mode",
    $CreatorMode,
    "--schedule-interval-seconds",
    [string]$SchedulerIntervalSeconds,
    "--max-consecutive-failed-rounds",
    [string]$SchedulerMaxConsecutiveFailedRounds,
    "--limit",
    [string]$SchedulerLimit,
    "--attempts",
    [string]$SchedulerAttempts,
    "--status-interval-seconds",
    [string]$SchedulerStatusIntervalSeconds
  )
  if ($SchedulerMaxRounds -gt 0) {
    $schedulerArguments += @("--max-rounds", [string]$SchedulerMaxRounds)
  }
  if ($SchedulerWait) {
    $schedulerArguments += "--wait"
  }
  if ($SchedulerNotes.Trim()) {
    $schedulerArguments += @("--notes", $SchedulerNotes.Trim())
  }
  $schedulerArguments = Add-OptionalRepeatedArgument -Arguments $schedulerArguments -Name "--creator-note-id" -Values $CreatorNoteId
  $schedulerArguments = Add-OptionalRepeatedArgument -Arguments $schedulerArguments -Name "--run-id" -Values $RunId

  Start-RuntimeProcess -Name "performance-scheduler" -Arguments $schedulerArguments
}

Write-Host "Started process count: $($startedProcesses.Count)"
$startedProcesses | ConvertTo-Json -Depth 4
