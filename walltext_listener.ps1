param(
    [string]$ConfigPath = "",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
)

$ErrorActionPreference = "Stop"

function Get-PythonExecutable {
    $pyCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCommand) {
        $exe = & py -3 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $exe) {
            return $exe.Trim()
        }

        $exe = & py -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $exe) {
            return $exe.Trim()
        }
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $exe = & python -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $exe) {
            return $exe.Trim()
        }
    }

    throw "Python was not found. Run install_dependencies.bat first."
}

if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    $ConfigPath = Join-Path $env:LOCALAPPDATA "walltext\walltext.json"
}

$pythonExecutable = Get-PythonExecutable
$argsList = @("-m", "walltext", "listen", "--config", $ConfigPath) + $ExtraArgs
& $pythonExecutable @argsList
exit $LASTEXITCODE
