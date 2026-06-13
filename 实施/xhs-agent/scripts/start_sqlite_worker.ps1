param(
  [string]$Python = "",
  [string]$DbPath = "data/xhs_agent.sqlite3",
  [string]$WorkerId = "local-worker-1",
  [string]$CollectorMode = "mock",
  [string]$LLMModelName = "mock",
  [double]$HeartbeatIntervalSeconds = 30,
  [int]$HeartbeatTimeoutSeconds = 1800,
  [switch]$Once,
  [switch]$Watchdog,
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

$pythonCommand = Resolve-PythonCommand -ConfiguredPython $Python

$env:XHS_AGENT_RUN_STORE = "sqlite"
$env:XHS_AGENT_RUN_DB_PATH = $DbPath
$env:XHS_AGENT_RUN_QUEUE = "sqlite"
$env:XHS_AGENT_QUEUE_DB_PATH = $DbPath
$env:XHS_AGENT_MEMORY_STORE = "sqlite"
$env:XHS_AGENT_MEMORY_DB_PATH = $DbPath
$env:COLLECTOR_MODE = $CollectorMode
$env:LLM_MODEL_NAME = $LLMModelName
$env:XHS_AGENT_WORKER_ID = $WorkerId
$env:XHS_AGENT_QUEUE_HEARTBEAT_INTERVAL_SECONDS = [string]$HeartbeatIntervalSeconds
$env:XHS_AGENT_QUEUE_HEARTBEAT_TIMEOUT_SECONDS = [string]$HeartbeatTimeoutSeconds

Write-Host "Using Python: $pythonCommand"
Write-Host "Mode: sqlite worker, db=$DbPath, worker_id=$WorkerId, collector=$CollectorMode, llm=$LLMModelName, heartbeat_interval=$HeartbeatIntervalSeconds, heartbeat_timeout=$HeartbeatTimeoutSeconds"

if ($CheckOnly) {
  & $pythonCommand ".\scripts\check_runtime_config.py" "--profile" "sqlite-worker"
  exit $LASTEXITCODE
}

$arguments = @(".\scripts\run_worker.py", "--worker-id", $WorkerId)
if ($Watchdog) {
  $arguments += "--watchdog-loop"
} elseif ($Once) {
  $arguments += "--once"
}

& $pythonCommand @arguments
exit $LASTEXITCODE
