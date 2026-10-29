<#
    reset_demo.ps1 - put the RPA demo back to a known state, in one command.

      powershell -ExecutionPolicy Bypass -File scripts\reset_demo.ps1
      powershell -ExecutionPolicy Bypass -File scripts\reset_demo.ps1 -DryRun

    This is a thin wrapper. The work is in scripts\reset_demo.py, and that is
    deliberate: on this machine any Windows PowerShell 5.1 file operation on the
    deliberately malformed demo resume terminated the whole shell - exit code 0,
    no error record, nothing caught by a trap - which left the reset half done
    and the demo broken. Python's shutil handles the same files without
    complaint, so every file operation now happens there, through
    core\storage.py. See PROGRESS.md Section D #16.

    The .ps1 entry point stays because the team is on Windows and R6 asks for
    this filename. It spawns one process and touches no files itself.

    ASCII-only on purpose: PowerShell 5.1 cannot parse a .ps1 containing
    non-ASCII characters unless the file is saved with a BOM.
#>

param(
    [switch]$DryRun,
    [string]$Python = "python"
)

# $PSScriptRoot is not populated inside a param() default on PowerShell 5.1.
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $scriptDir
$resetPy = Join-Path $scriptDir "reset_demo.py"

if (-not (Test-Path $resetPy)) {
    Write-Host "Missing: $resetPy" -ForegroundColor Red
    exit 1
}

Push-Location $root
try {
    if ($DryRun) {
        & $Python $resetPy --dry-run
    } else {
        & $Python $resetPy
    }
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}

exit $code
