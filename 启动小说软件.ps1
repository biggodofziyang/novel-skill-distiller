$ErrorActionPreference = "Stop"
$AppUrl = "http://127.0.0.1:8501"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Test-AppReady {
    try {
        $response = Invoke-WebRequest -Uri $AppUrl -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

if (-not (Test-AppReady)) {
    Start-Process -FilePath "py" -ArgumentList @(
        "-m", "streamlit", "run", "app.py",
        "--server.address", "127.0.0.1",
        "--server.port", "8501",
        "--server.headless", "true"
    ) -WorkingDirectory $ProjectDir -WindowStyle Hidden

    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        Start-Sleep -Milliseconds 250
        if (Test-AppReady) {
            break
        }
    }
}

if (-not (Test-AppReady)) {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
        "软件启动失败，请稍后重试。",
        "网文创作Skill蒸馏系统"
    ) | Out-Null
    exit 1
}

Start-Process $AppUrl