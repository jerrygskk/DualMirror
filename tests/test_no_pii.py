"""公開前保護以隔離 Git 儲存庫及虛構名單驗證。"""
import importlib.util
from pathlib import Path
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]


def tool():
    path = ROOT / 'tools/check_no_pii.py'
    assert path.is_file(), '尚未移植個資掃描工具'
    spec = importlib.util.spec_from_file_location('check_no_pii', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True,
                          capture_output=True, encoding='utf-8').stdout


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, 'init', '-b', 'main')
    git(tmp_path, 'config', 'user.name', 'Test')
    git(tmp_path, 'config', 'user.email', 'test@example.invalid')
    (tmp_path / '.gitignore').write_text('.tmp/\nprivate.txt\n', encoding='utf-8')
    return tmp_path


def commit(root, name, text):
    (root / name).write_text(text, encoding='utf-8')
    git(root, 'add', '--', name)
    git(root, 'commit', '-m', 'test fixture')


def test_initial_scan_catches_untracked_public_file_but_not_ignored(repo):
    (repo / 'public.svg').write_text('虛構禁名', encoding='utf-8')
    (repo / 'private.txt').write_text('虛構禁名', encoding='utf-8')
    assert tool().scan_repository(repo, ['虛構禁名'], initial=True) == ['public.svg']


def test_scans_index_when_worktree_was_cleaned(repo):
    (repo / 'file.txt').write_text('虛構禁名', encoding='utf-8')
    git(repo, 'add', '--', 'file.txt')
    (repo / 'file.txt').write_text('clean', encoding='utf-8')
    assert tool().scan_repository(repo, ['虛構禁名'], initial=True) == ['file.txt']


def test_head_is_checked_even_when_index_and_worktree_are_clean(repo):
    commit(repo, 'file.txt', '虛構禁名')
    (repo / 'file.txt').write_text('clean', encoding='utf-8')
    git(repo, 'add', '--', 'file.txt')
    assert tool().scan_repository(repo, ['虛構禁名'], initial=True) == ['file.txt']


def test_outgoing_deleted_content_still_hits_old_commit(repo):
    commit(repo, 'baseline.txt', 'clean')
    git(repo, 'branch', 'baseline')
    git(repo, 'config', 'branch.main.remote', '.')
    git(repo, 'config', 'branch.main.merge', 'refs/heads/baseline')
    commit(repo, 'gone.txt', '虛構禁名')
    git(repo, 'rm', '--', 'gone.txt'); git(repo, 'commit', '-m', 'remove fixture')
    assert tool().scan_repository(repo, ['虛構禁名']) == ['gone.txt']


def test_commits_before_upstream_are_not_rescanned(repo):
    commit(repo, 'file.txt', '虛構禁名')
    commit(repo, 'file.txt', 'clean')
    git(repo, 'branch', 'baseline')
    git(repo, 'config', 'branch.main.remote', '.')
    git(repo, 'config', 'branch.main.merge', 'refs/heads/baseline')
    assert tool().scan_repository(repo, ['虛構禁名']) == []


def test_existing_commit_requires_upstream_or_explicit_initial(repo):
    commit(repo, 'file.txt', 'clean')
    with pytest.raises(RuntimeError, match='upstream'):
        tool().scan_repository(repo, ['虛構禁名'])
    assert tool().scan_repository(repo, ['虛構禁名'], initial=True) == []


def test_external_symlink_is_not_followed(repo, tmp_path):
    outside = tmp_path.parent / (tmp_path.name + '-outside')
    outside.mkdir(); (outside / 'secret.txt').write_text('虛構禁名', encoding='utf-8')
    try: (repo / 'linked').symlink_to(outside, target_is_directory=True)
    except OSError as error: pytest.skip(f'無法建立測試連結：{error.winerror}')
    assert tool().scan_repository(repo, ['虛構禁名'], initial=True) == []


def test_cli_missing_or_empty_list_fails(repo):
    path = ROOT / 'tools/check_no_pii.py'
    assert path.is_file(), '尚未移植個資掃描工具'
    for name, content in [('missing.txt', None), ('empty.txt', '# empty\n')]:
        deny = repo / name
        if content is not None: deny.write_text(content, encoding='utf-8')
        result = subprocess.run([sys.executable, str(path), '--root', str(repo),
            '--denylist', str(deny), '--initial'], capture_output=True, encoding='utf-8')
        assert result.returncode == 2


def test_cli_does_not_print_sensitive_term(repo):
    path = ROOT / 'tools/check_no_pii.py'
    assert path.is_file(), '尚未移植個資掃描工具'
    private = repo / 'private.txt'; private.write_text('虛構禁名', encoding='utf-8')
    (repo / 'public.py').write_text('虛構禁名', encoding='utf-8')
    result = subprocess.run([sys.executable, str(path), '--root', str(repo),
        '--denylist', str(private), '--initial'], capture_output=True, encoding='utf-8')
    assert result.returncode == 1
    assert 'public.py' in result.stdout
    assert '虛構禁名' not in result.stdout + result.stderr


def test_ignore_rules_exclude_private_data_and_keep_required_sources(repo):
    (repo / '.gitignore').write_bytes((ROOT / '.gitignore').read_bytes())
    excluded = ['.tmp/sample.txt', 'HANDOFF.md', 'tests/pii_denylist.local.txt',
        'data.db', 'data.db-wal', 'backups/file.txt', 'error.log', '.env',
        'secret.key', 'browser-profile/Default/Cookies', 'fonts.json',
        'build/output.exe', 'dist/DualMirror.exe', 'version_info.txt',
        'fix_private.py', 'seed_private.py', 'data.xlsm']
    allowed = ['main.py', 'DualMirror.spec', 'tools/check_no_pii.py',
        'assets/DualMirror.ico', 'shell/CompareLauncher.exe', 'shell/FileCompareShell.dll',
        'DEVELOPER.md', 'PITFALLS.md', 'docs/plan.md', '啟動.cmd']
    for relative in excluded + allowed:
        result = subprocess.run(['git', '-C', str(repo), 'check-ignore', '--no-index', '--', relative],
                                capture_output=True)
        assert result.returncode == (0 if relative in excluded else 1), relative


@pytest.mark.parametrize('encoding', ['utf-8', 'utf-16', 'utf-16-be', 'utf-32', 'cp950'])
def test_known_chinese_encodings_are_scanned_in_index_and_history(repo, encoding):
    import codecs
    raw = '虛構禁名'.encode(encoding)
    if encoding == 'utf-16-be': raw = codecs.BOM_UTF16_BE + raw
    (repo / 'file.txt').write_bytes(raw)
    git(repo, 'add', '--', 'file.txt')
    (repo / 'file.txt').write_text('clean', encoding='utf-8')
    assert tool().scan_repository(repo, ['虛構禁名'], initial=True) == ['file.txt']
    git(repo, 'commit', '-m', 'encoded fixture')
    assert tool().scan_repository(repo, ['虛構禁名'], initial=True) == ['file.txt']


def test_unknown_encoding_does_not_report_clean(repo):
    (repo / 'unknown.txt').write_bytes(b'\xff')
    with pytest.raises(RuntimeError, match='編碼'):
        tool().scan_repository(repo, ['虛構禁名'], initial=True)
