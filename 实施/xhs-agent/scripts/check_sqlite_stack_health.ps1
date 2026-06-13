param(
  [string]$BaseUrl = "http://127.0.0.1:8010",
  [string]$Python = "",
  [string]$DbPath = "data/xhs_agent.sqlite3",
  [string]$CollectorMode = "mock",
  [string]$CreatorMode = "mock",
  [string]$LLMModelName = "mock",
  [string]$ApiToken = $env:XHS_AGENT_API_TOKEN,
  [double]$HeartbeatIntervalSeconds = 30,
  [int]$HeartbeatTimeoutSeconds = 1800,
  [switch]$ConfigOnly,
  [switch]$SkipApi
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

function Invoke-JsonEndpoint {
  param(
    [string]$Url,
    [hashtable]$Headers
  )

  try {
    $result = Invoke-RestMethod -Uri $Url -Headers $Headers -Method Get -TimeoutSec 10
    return [pscustomobject]@{
      ok = $true
      url = $Url
      result = $result
      error = $null
    }
  } catch {
    return [pscustomobject]@{
      ok = $false
      url = $Url
      result = $null
      error = $_.Exception.Message
    }
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
Write-Host "Checking sqlite stack: db=$DbPath, base_url=$BaseUrl"

& $pythonCommand ".\scripts\check_runtime_config.py" "--profile" "sqlite-worker"
$configExitCode = $LASTEXITCODE
if ($configExitCode -ne 0) {
  exit $configExitCode
}
if ($ConfigOnly) {
  exit 0
}

$processes = @(Find-StackProcesses)
Write-Host "Matched stack process count: $($processes.Count)"
$processes | ConvertTo-Json -Depth 3

if ($SkipApi) {
  exit 0
}

$headers = @{}
if ($ApiToken) {
  $headers["Authorization"] = "Bearer $ApiToken"
}

$health = Invoke-JsonEndpoint -Url "$($BaseUrl.TrimEnd('/'))/health" -Headers $headers
$queue = Invoke-JsonEndpoint -Url "$($BaseUrl.TrimEnd('/'))/queue" -Headers $headers

$summary = [pscustomobject]@{
  ok = ($health.ok -and $queue.ok)
  health = $health
  queue = $queue
}
$summary | ConvertTo-Json -Depth 8
if (-not $summary.ok) {
  exit 1
}
exit 0
