param([Parameter(Mandatory=$true)][string]$Zig)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $root
try {
    & $Zig c++ -target x86_64-windows-gnu -shared -O2 -s -o shell/FileCompareShell.dll shell/compare_command.cpp -lole32 -lshell32 -lshlwapi -luuid
    if ($LASTEXITCODE -ne 0) { throw 'DLL build failed' }
    & $Zig c++ -target x86_64-windows-gnu -O2 -s -municode '-Wl,--subsystem,windows' -o shell/CompareLauncher.exe shell/launcher.cpp -lshell32 -luser32
    if ($LASTEXITCODE -ne 0) { throw 'Launcher build failed' }
} finally { Pop-Location }
