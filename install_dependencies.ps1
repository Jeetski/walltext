[CmdletBinding()]
param(
    [switch]$NoPrompt,
    [switch]$InstallPythonIfMissing,
    [switch]$EnableListener,
    [switch]$AddCommandToPath
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$installRoot = Join-Path $env:LOCALAPPDATA "walltext"
$binDir = Join-Path $installRoot "bin"
$configFile = Join-Path $installRoot "walltext.json"
$outputFile = Join-Path $installRoot "walltext.png"
$startupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$startupLauncher = Join-Path $startupDir "walltext_listener.cmd"

function Read-YesNo {
    param(
        [string]$Prompt,
        [bool]$Default = $false
    )

    if ($NoPrompt) {
        return $Default
    }

    $suffix = if ($Default) { "[Y/n]" } else { "[y/N]" }
    $response = Read-Host "$Prompt $suffix"
    if ([string]::IsNullOrWhiteSpace($response)) {
        return $Default
    }

    return @("y", "yes").Contains($response.Trim().ToLowerInvariant())
}

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

        return $pythonCommand.Source
    }

    return $null
}

function Install-Python {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "Python was not found and winget is unavailable. Install Python 3.10+ manually, then rerun this script."
    }

    Write-Host "Installing Python 3.12 with winget..."
    & winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "winget failed to install Python."
    }
}

function Write-WalltextCmd {
    param(
        [string]$PythonExecutable,
        [string]$Destination
    )

    $content = @"
@echo off
setlocal
"$PythonExecutable" -m walltext %*
"@
    Set-Content -LiteralPath $Destination -Value $content -Encoding ascii
}

function Write-ListenerPowerShell {
    param(
        [string]$PythonExecutable,
        [string]$Destination,
        [string]$DefaultConfigPath
    )

    $content = @"
param(
    [string]`$ConfigPath = '$DefaultConfigPath',
    [Parameter(ValueFromRemainingArguments = `$true)]
    [string[]]`$ExtraArgs
)

`$ErrorActionPreference = 'Stop'
`$argsList = @(
    '-m',
    'walltext',
    'listen',
    '--config',
    `$ConfigPath
) + `$ExtraArgs

& '$PythonExecutable' @argsList
exit `$LASTEXITCODE
"@
    Set-Content -LiteralPath $Destination -Value $content -Encoding ascii
}

function Write-ListenerCmd {
    param([string]$Destination)

    $content = @"
@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0walltext_listener.ps1" %*
"@
    Set-Content -LiteralPath $Destination -Value $content -Encoding ascii
}

function Write-ManagerPowerShell {
    param(
        [string]$PythonExecutable,
        [string]$Destination,
        [string]$DefaultConfigPath
    )

    $content = @"
param(
    [string]`$ConfigPath = '$DefaultConfigPath',
    [Parameter(ValueFromRemainingArguments = `$true)]
    [string[]]`$ExtraArgs
)

`$ErrorActionPreference = 'Stop'
`$argsList = @(
    '-m',
    'walltext',
    'manager',
    '--config',
    `$ConfigPath
) + `$ExtraArgs

& '$PythonExecutable' @argsList
exit `$LASTEXITCODE
"@
    Set-Content -LiteralPath $Destination -Value $content -Encoding ascii
}

function Write-ManagerCmd {
    param([string]$Destination)

    $content = @"
@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0walltext_manager.ps1" %*
"@
    Set-Content -LiteralPath $Destination -Value $content -Encoding ascii
}

function Write-StartupLauncher {
    param(
        [string]$Destination,
        [string]$ListenerPowerShellPath
    )

    $content = @"
@echo off
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "$ListenerPowerShellPath"
"@
    Set-Content -LiteralPath $Destination -Value $content -Encoding ascii
}

function Ensure-UserPathContains {
    param([string]$DirectoryPath)

    $currentUserPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $entries = @($currentUserPath -split ";" | Where-Object { $_ })
    if ($entries -contains $DirectoryPath) {
        if (-not (($env:Path -split ";") -contains $DirectoryPath)) {
            $env:Path = "$DirectoryPath;$env:Path"
        }
        return
    }

    $newUserPath = if ([string]::IsNullOrWhiteSpace($currentUserPath)) {
        $DirectoryPath
    }
    else {
        "$currentUserPath;$DirectoryPath"
    }

    [Environment]::SetEnvironmentVariable("Path", $newUserPath, "User")
    if (-not (($env:Path -split ";") -contains $DirectoryPath)) {
        $env:Path = "$DirectoryPath;$env:Path"
    }
}

Write-Host "walltext installer"
Write-Host "repo: $repoRoot"

$pythonExecutable = Get-PythonExecutable
if (-not $pythonExecutable) {
    $shouldInstallPython = $InstallPythonIfMissing -or (Read-YesNo "Python was not found. Install it now with winget?")
    if (-not $shouldInstallPython) {
        throw "Python is required."
    }

    Install-Python
    $pythonExecutable = Get-PythonExecutable
    if (-not $pythonExecutable) {
        throw "Python installation finished, but no Python executable was detected. Open a new shell and rerun the installer."
    }
}

Write-Host "python: $pythonExecutable"
Write-Host "Installing package and dependencies..."
& $pythonExecutable -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "pip upgrade failed."
}

& $pythonExecutable -m pip install -e $repoRoot
if ($LASTEXITCODE -ne 0) {
    throw "Package installation failed."
}

& $pythonExecutable -m walltext config init
if ($LASTEXITCODE -ne 0) {
    throw "Default config creation failed."
}

New-Item -ItemType Directory -Force -Path $installRoot | Out-Null
New-Item -ItemType Directory -Force -Path $binDir | Out-Null
New-Item -ItemType Directory -Force -Path $startupDir | Out-Null

$walltextCmdPath = Join-Path $binDir "walltext.cmd"
$listenerCmdPath = Join-Path $binDir "walltext_listener.cmd"
$listenerPsPath = Join-Path $binDir "walltext_listener.ps1"
$managerCmdPath = Join-Path $binDir "walltext_manager.cmd"
$managerPsPath = Join-Path $binDir "walltext_manager.ps1"

Write-WalltextCmd -PythonExecutable $pythonExecutable -Destination $walltextCmdPath
Write-ListenerPowerShell -PythonExecutable $pythonExecutable -Destination $listenerPsPath -DefaultConfigPath $configFile
Write-ListenerCmd -Destination $listenerCmdPath
Write-ManagerPowerShell -PythonExecutable $pythonExecutable -Destination $managerPsPath -DefaultConfigPath $configFile
Write-ManagerCmd -Destination $managerCmdPath

$shouldEnableListener = $EnableListener -or (Read-YesNo "Run the walltext listener in the background at login?")
if ($shouldEnableListener) {
    Write-StartupLauncher -Destination $startupLauncher -ListenerPowerShellPath $listenerPsPath
    Write-Host "Startup listener enabled: $startupLauncher"
}
else {
    Write-Host "Startup listener skipped."
}

$shouldAddCommand = $AddCommandToPath -or (Read-YesNo "Add walltext commands to your user PATH?")
if ($shouldAddCommand) {
    Ensure-UserPathContains -DirectoryPath $binDir
    Write-Host "User PATH updated with: $binDir"
}
else {
    Write-Host "PATH update skipped."
}

Write-Host ""
Write-Host "Installed files:"
Write-Host "  walltext command:  $walltextCmdPath"
Write-Host "  listener command:  $listenerCmdPath"
Write-Host "  listener script:   $listenerPsPath"
Write-Host "  manager command:   $managerCmdPath"
Write-Host "  manager script:    $managerPsPath"
Write-Host "  config file:       $configFile"
Write-Host "  output image:      $outputFile"
