from pathlib import Path
import sys
import pytest
import lib.integration.shell_integration as integration


def test_prepare_fixed_resources_and_frozen_launch(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'appdata'))
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    exe = tmp_path / '雙鏡 space.exe'; exe.write_bytes(b'exe')
    monkeypatch.setattr(sys, 'executable', str(exe))
    root = integration.prepare_resources()
    assert root.is_relative_to(tmp_path / 'appdata' / 'DualMirror')
    assert root != integration.ROOT
    assert (root / 'shell' / 'FileCompareShell.dll').read_bytes() == (integration.ROOT / 'shell' / 'FileCompareShell.dll').read_bytes()
    assert integration.launch_configuration() == str(exe) + '\n\n'
    assert integration.prepare_resources() == root


def test_failed_install_restores_previous_launch_config(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    config = tmp_path / 'DualMirror' / 'launcher.txt'
    config.parent.mkdir(); config.write_bytes(b'previous')
    def fail(mode, root=None):
        assert mode == 'Install'
        assert root.is_relative_to(config.parent)
        raise RuntimeError('registration failed')
    monkeypatch.setattr(integration, 'run', fail)
    with pytest.raises(RuntimeError, match='registration failed'): integration.install()
    assert config.read_bytes() == b'previous'
def test_registration_transaction_is_not_killed_by_timeout(monkeypatch):
    import lib.integration.shell_integration as integration
    from types import SimpleNamespace

    calls = []
    monkeypatch.setattr(integration.subprocess, 'run',
                        lambda *args, **kwargs: calls.append(kwargs) or
                        SimpleNamespace(returncode=1, stderr=b'failed', stdout=b''))
    import pytest
    for mode in ('Install', 'Remove', 'Status'):
        with pytest.raises(RuntimeError):
            integration.run(mode)
    assert [call.get('timeout') for call in calls] == [None, None, 60]
