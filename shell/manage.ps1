param(
    [Parameter(Mandatory=$true)][ValidateSet('Status','Install','Remove')][string]$Mode,
    [string]$Root
)
$ErrorActionPreference = 'Stop'
$OutputEncoding = [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
$name = 'Local.DualMirror'
$legacy = 'Local.FileComparePython'
if ($Mode -eq 'Status') {
    if (Get-AppxPackage -Name $name) { Write-Output 'installed' }
    elseif (Get-AppxPackage -Name $legacy) { Write-Output 'legacy' }
    else { Write-Output 'absent' }
    exit 0
}
if ($Mode -eq 'Remove') {
    Get-AppxPackage -Name $name | Remove-AppxPackage
    Get-AppxPackage -Name $legacy | Remove-AppxPackage
    Write-Output 'removed'
    exit 0
}
$resolvedRoot = (Resolve-Path -LiteralPath $Root).Path
$manifest = Join-Path $resolvedRoot 'AppxManifest.xml'
if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) { throw 'Missing AppxManifest.xml' }
$modeSetting = Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock' -ErrorAction SilentlyContinue
if ($modeSetting.AllowDevelopmentWithoutDevLicense -ne 1) {
    throw 'Developer mode is not enabled. This tool will not change Windows security settings.'
}
$previous = Get-AppxPackage -Name $name
$rootRecord = Join-Path $env:LOCALAPPDATA 'DualMirror\shell-root.txt'
$recordBefore = if (Test-Path -LiteralPath $rootRecord) { [IO.File]::ReadAllBytes($rootRecord) } else { $null }
$recordWritten = $false
$recordTemp = $rootRecord + '.tmp'
$previousRemoved = $false
$previousRoot = if (Test-Path -LiteralPath $rootRecord) { [IO.File]::ReadAllText($rootRecord).Trim() } else { $previous.InstallLocation }
if ($previous -and -not (Test-Path -LiteralPath (Join-Path $previousRoot 'AppxManifest.xml'))) {
    throw 'Previous registration resources are missing; remove the integration before installing again.'
}
try {
    # Windows 拒絕同一套件直接變更 ExternalLocation（0x80073D0B）。
    if ($previous -and $previousRoot -ne $resolvedRoot) {
        $previous | Remove-AppxPackage
        $previousRemoved = $true
    }
    Add-AppxPackage -Register $manifest -ExternalLocation $resolvedRoot
    [IO.File]::WriteAllText($recordTemp, $resolvedRoot, (New-Object System.Text.UTF8Encoding $false))
    if (Test-Path -LiteralPath $rootRecord) { [IO.File]::Replace($recordTemp, $rootRecord, [NullString]::Value) }
    else { [IO.File]::Move($recordTemp, $rootRecord) }
    $recordWritten = $true
    # 所有新資源與記錄成功後，最後才移除舊套件。
    Get-AppxPackage -Name $legacy | Remove-AppxPackage
} catch {
    $failure = $_
    try {
        if ($previousRemoved) {
            Get-AppxPackage -Name $name | Remove-AppxPackage
            Add-AppxPackage -Register (Join-Path $previousRoot 'AppxManifest.xml') -ExternalLocation $previousRoot
        } elseif (-not $previous) {
            Get-AppxPackage -Name $name | Remove-AppxPackage
        }
        if ($recordWritten) {
            if ($null -ne $recordBefore) { [IO.File]::WriteAllBytes($rootRecord, [byte[]]$recordBefore) }
            else { Remove-Item -LiteralPath $rootRecord -ErrorAction Stop }
        }
    } catch {
        throw "Registration failed: $failure ; rollback failed: $_"
    }
    throw $failure
} finally {
    if (Test-Path -LiteralPath $recordTemp) { Remove-Item -LiteralPath $recordTemp }
}
Write-Output 'installed'
