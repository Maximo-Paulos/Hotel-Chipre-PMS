$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (Test-Path $venvPython) {
    $python = $venvPython
} else {
    $python = "python"
}

Push-Location $projectRoot
try {
    & $python "tests\smoke\run_smoke.py"
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
