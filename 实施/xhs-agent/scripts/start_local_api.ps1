param(
  [string]$HostName = "127.0.0.1",
  [int]$Port = 8010,
  [string]$Python = "",
  [string]$CollectorMode = "mock",
  [string]$LLMModelName = "mock",
  [string]$ApiToken = $env:XHS_AGENT_API_TOKEN,
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

$env:COLLECTOR_MODE = $CollectorMode
$env:LLM_MODEL_NAME = $LLMModelName
$env:XHS_AGENT_RUN_QUEUE = "local"
$env:XHS_AGENT_API_TOKEN = $ApiToken

Write-Host "Using Python: $pythonCommand"
Write-Host "Mode: local API, collector=$CollectorMode, llm=$LLMModelName, host=$HostName, port=$Port"

if ($CheckOnly) {
  & $pythonCommand ".\scripts\check_runtime_config.py" "--profile" "local"
  exit $LASTEXITCODE
}

& $pythonCommand ".\scripts\run_api.py" "--host" $HostName "--port" $Port
exit $LASTEXITCODE
