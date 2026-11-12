"""實際執行註冊腳本，只替換會改動 Windows 的 Appx 邊界。"""
import json
from pathlib import Path
import subprocess
import pytest
from lib.integration.shell_integration import POWERSHELL, ROOT


@pytest.mark.parametrize('failure,previous', [('', False), ('', True), ('add', False), ('add', True), ('remove', False), ('remove', True), ('record', False)])
def test_registration_order_and_rollback(tmp_path, monkeypatch, failure, previous):
    root = tmp_path / 'new'; root.mkdir()
    (root / 'AppxManifest.xml').write_text('new', encoding='utf-8')
    old = tmp_path / 'old'; old.mkdir()
    (old / 'AppxManifest.xml').write_text('old', encoding='utf-8')
    data = tmp_path / 'appdata'; (data / 'DualMirror').mkdir(parents=True)
    record = data / 'DualMirror' / 'shell-root.txt'
    if previous or failure == 'record': record.write_text(str(old), encoding='utf-8')
    monkeypatch.setenv('LOCALAPPDATA', str(data))
    monkeypatch.setenv('PROBE_ROOT', str(root)); monkeypatch.setenv('PROBE_OLD', str(old))
    monkeypatch.setenv('PROBE_PREVIOUS', str(previous)); monkeypatch.setenv('PROBE_FAILURE', failure)
    log = tmp_path / 'calls.json'; monkeypatch.setenv('PROBE_LOG', str(log))
    prefix = r'''
$global:calls = [Collections.Generic.List[string]]::new()
$global:registered = $env:PROBE_PREVIOUS -eq 'True'
$global:currentRoot = $env:PROBE_OLD
if ($env:PROBE_FAILURE -eq 'record') {
    $global:locked = [IO.File]::Open((Join-Path $env:LOCALAPPDATA 'DualMirror\shell-root.txt'), 'Open', 'Read', 'Read')
}
function Get-ItemProperty { param($LiteralPath, $ErrorAction) return @{AllowDevelopmentWithoutDevLicense=1} }
function Get-AppxPackage {
    param($Name)
    if ($Name -eq 'Local.FileComparePython' -or $global:registered) {
        return [pscustomobject]@{ Name=$Name; InstallLocation=$env:PROBE_OLD }
    }
}
function Add-AppxPackage {
    param($Register, $ExternalLocation)
    if (-not (Test-Path -LiteralPath $Register)) { throw 'Manifest missing' }
    $global:calls.Add('add:' + $ExternalLocation)
    if ($global:registered -and $ExternalLocation -ne $global:currentRoot) { throw 'Package already installed at a different external location' }
    if ($env:PROBE_FAILURE -eq 'add' -and $ExternalLocation -eq $env:PROBE_ROOT) { throw 'Simulated add failure' }
    $global:registered = $true
    $global:currentRoot = $ExternalLocation
}
function Remove-AppxPackage {
    param([Parameter(ValueFromPipeline=$true)]$Package)
    process {
        $global:calls.Add('remove:' + $Package.Name)
        if ($env:PROBE_FAILURE -eq 'remove' -and $Package.Name -eq 'Local.FileComparePython') { throw 'Simulated removal failure' }
        if ($Package.Name -eq 'Local.DualMirror') { $global:registered = $false }
    }
}
try {
    & {
'''
    suffix = r'''
    } -Mode Install -Root $env:PROBE_ROOT
} finally {
    if ($global:locked) { $global:locked.Dispose() }
    [IO.File]::WriteAllText($env:PROBE_LOG, (ConvertTo-Json -InputObject @($global:calls)), [Text.UTF8Encoding]::new($false))
}
'''
    result = subprocess.run([str(POWERSHELL), '-NoProfile', '-NonInteractive', '-Command',
        prefix + (ROOT / 'shell/manage.ps1').read_text(encoding='utf-8') + suffix], capture_output=True, timeout=20)
    calls = json.loads(log.read_text(encoding='utf-8'))
    assert calls[0] == ('remove:Local.DualMirror' if previous else 'add:' + str(root))
    if not failure:
        assert result.returncode == 0, result.stderr
        expected = ['add:' + str(root), 'remove:Local.FileComparePython']
        if previous: expected.insert(0, 'remove:Local.DualMirror')
        assert calls == expected
        assert record.read_text(encoding='utf-8') == str(root)
    else:
        assert result.returncode != 0
        if previous:
            assert calls[-1] == 'add:' + str(old)
            assert record.read_text(encoding='utf-8') == str(old)
        else:
            if failure == 'record':
                assert 'remove:Local.FileComparePython' not in calls
                assert record.read_text(encoding='utf-8') == str(old)
            else: assert not record.exists()
            if failure != 'add': assert calls[-1] == 'remove:Local.DualMirror'
