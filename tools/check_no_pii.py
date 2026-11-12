"""公開前個資檢查；通用掃描移植自 PoliceDocSys，未帶入其資料庫與種子邏輯。

檢查安全工作樹、暫存區、HEAD、待推送提交及未追蹤但未排除的候選檔。
只輸出命中的檔名，不輸出本機名單中的個資；圖片仍須人工檢查。
"""
import argparse
import codecs
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
_BINARY_EXT = ('.png', '.ico', '.dll', '.exe')


def _git_at(root, *args):
    result = subprocess.run(
        ["git", "-C", os.fspath(root), *args],
        capture_output=True,
    )
    if result.returncode:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"git {' '.join(args)} 失敗：{stderr}")
    return result.stdout


def _is_within_repo(path, root):
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _safe_worktree_blob(root, relative):
    """只讀取解析後每一層都留在 repo 內的工作樹 path。"""
    repo = Path(root).resolve(strict=True)
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        return None

    path = repo.joinpath(*relative_path.parts)
    if not os.path.lexists(path):
        return None

    current = repo
    for part in relative_path.parts:
        current /= part
        try:
            # resolve 同時展開 symlink 與 Windows junction/reparse point。
            resolved = current.resolve(strict=True)
        except (FileNotFoundError, RuntimeError):
            return None
        if not _is_within_repo(resolved, repo):
            return None

    # git 對 final symlink 追蹤的是連結文字，不讀取其 target bytes。
    if path.is_symlink():
        return os.readlink(path).encode("utf-8")
    return path.read_bytes()


def _git_blob(root, object_spec):
    result = subprocess.run(
        ["git", "-C", os.fspath(root), "show", object_spec],
        capture_output=True,
    )
    return result.stdout if result.returncode == 0 else None


def _git_paths(root, *args):
    result = subprocess.run(
        ["git", "-C", os.fspath(root), *args],
        capture_output=True,
    )
    if result.returncode:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"git {' '.join(args)} 失敗：{stderr}")
    return [
        raw.decode("utf-8")
        for raw in result.stdout.split(b"\x00")
        if raw
    ]


def _is_known_binary(relative):
    return relative.lower().endswith(_BINARY_EXT)


def _has_head(root):
    result = subprocess.run(
        ["git", "-C", os.fspath(root), "rev-parse", "--verify", "-q", "HEAD"],
        capture_output=True,
    )
    if result.returncode not in (0, 1):
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"git rev-parse HEAD 失敗：{stderr}")
    return result.returncode == 0


def _text_hits(relative, blob, deny):
    encodings = ('utf-8-sig', 'cp950')
    # UTF-32 LE 的 BOM 與 UTF-16 LE 開頭相同，必須先辨認 UTF-32。
    if blob.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        encodings = ('utf-32',)
    elif blob.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        encodings = ('utf-16',)
    for encoding in encodings:
        try:
            text = blob.decode(encoding)
            if '\x00' in text: continue
            break
        except UnicodeDecodeError:
            continue
    else:
        raise RuntimeError(f'無法辨識文字編碼，請先檢查：{relative}')
    return [relative] if any(name in text for name in deny) else []


def _stable_unique(items):
    return list(dict.fromkeys(items))


def _scan_tracked_text(root, deny):
    """分別掃描安全工作樹、index、HEAD 的所有可解碼追蹤檔。"""
    tracked = set(_git_paths(root, "ls-files", "-z"))
    if _has_head(root):
        tracked.update(
            _git_paths(root, "ls-tree", "-r", "--name-only", "-z", "HEAD")
        )
    hits = []
    for relative in sorted(tracked):
        if _is_known_binary(relative):
            continue
        blobs = (
            _safe_worktree_blob(root, relative),
            _git_blob(root, f":{relative}"),
            _git_blob(root, f"HEAD:{relative}"),
        )
        for blob in blobs:
            if blob is not None:
                hits.extend(_text_hits(relative, blob, deny))
    return _stable_unique(hits)


def _resolve_upstream(root):
    result = subprocess.run(
        [
            "git",
            "-C",
            os.fspath(root),
            "rev-parse",
            "--abbrev-ref",
            "--symbolic-full-name",
            "@{upstream}",
        ],
        capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(
            "目前分支找不到 upstream；首次推送請加 --initial，其餘情況先設定正確的追蹤分支。"
        )
    return result.stdout.decode("utf-8").strip()


def _scan_outgoing_text(root, deny, initial=False):
    """一般掃描 upstream..HEAD；明確指定首次推送時掃描全部本地提交。"""
    revision = "HEAD" if initial else f"{_resolve_upstream(root)}..HEAD"
    commits = _git_at(root, "rev-list", "--reverse", revision)
    hits = []
    for commit in commits.decode("ascii").splitlines():
        paths = _git_paths(
            root, "ls-tree", "-r", "--name-only", "-z", commit
        )
        for relative in paths:
            if _is_known_binary(relative):
                continue
            blob = _git_blob(root, f"{commit}:{relative}")
            if blob is None:
                raise RuntimeError(f"無法讀取 commit {commit} 的 {relative}")
            hits.extend(_text_hits(relative, blob, deny))
    return _stable_unique(hits)


def load_denylist(path):
    terms = [line.strip() for line in Path(path).read_text(encoding='utf-8').splitlines()
             if line.strip() and not line.lstrip().startswith('#')]
    if not terms:
        raise ValueError('本機個資名單為空，未執行掃描。')
    return terms


def scan_repository(root, deny, initial=False):
    if not deny: raise ValueError('本機個資名單為空，未執行掃描。')
    hits = _scan_tracked_text(root, deny)
    for relative in _git_paths(root, 'ls-files', '--others', '--exclude-standard', '-z'):
        if _is_known_binary(relative): continue
        blob = _safe_worktree_blob(root, relative)
        if blob is not None: hits.extend(_text_hits(relative, blob, deny))
    if _has_head(root): hits.extend(_scan_outgoing_text(root, deny, initial))
    return sorted(set(hits))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--denylist', type=Path)
    parser.add_argument('--initial', action='store_true', help='首次推送前明確掃描所有本地提交')
    args = parser.parse_args()
    denylist = args.denylist or args.root / 'tests/pii_denylist.local.txt'
    try:
        hits = scan_repository(args.root, load_denylist(denylist), args.initial)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(2, f'個資檢查未完成：{error}\n')
    if hits:
        print('以下檔案命中本機個資名單，請處理後再推送：')
        print('\n'.join(hits))
        return 1
    print('候選檔、暫存區、HEAD 與待推送提交檢查完成：未命中本機已知個資名單。')
    return 0


if __name__ == '__main__': raise SystemExit(main())
