"""移植自 PoliceDocSys tools/pyi_prune.py，Git DLL 過濾亦參考 POS.spec。

只排除本工具不使用的 Qt Quick／QML、部分影像外掛及非繁中語系。
保留 Python OpenSSL、雜湊與 Qt 必要平台、圖示及輸入法資源。
"""

_DROP_NAMES = {
    'opengl32sw.dll', 'qt6quick.dll', 'qt6quickwidgets.dll', 'qt6qml.dll',
    'qt6qmlmodels.dll', 'qt6qmlmeta.dll', 'qt6qmlworkerscript.dll', 'qt6virtualkeyboard.dll',
    'qtiff.dll', 'qwebp.dll', 'qicns.dll', 'qtga.dll', 'qwbmp.dll', 'qgif.dll',
    'qdirect2d.dll', 'qoffscreen.dll', 'qminimal.dll',
}
_DROP_PREFIXES = ('pyside6/qml/', 'pyside6/plugins/qmltooling/', 'pyside6/plugins/virtualkeyboard/')
_GIT_DIRS = ('/program files/git/', '/program files (x86)/git/')


def _drop(dest, source):
    dest = dest.replace('\\', '/').lower()
    source = (source or '').replace('\\', '/').lower()
    name = dest.rsplit('/', 1)[-1]
    # PyInstaller 會沿 PATH 誤收工具環境的 ICU／CRT；它們不能取代系統或正式 Python 的 DLL。
    if '/windowsapps/openai.codexprimaryruntime.' in source: return 'foreign-runtime'
    if name.startswith(('libcrypto', 'libssl')) and any(path in source for path in _GIT_DIRS): return 'git-openssl'
    if name in _DROP_NAMES or dest.startswith(_DROP_PREFIXES): return 'unused-qt'
    if '/translations/' in dest and dest.endswith('.qm') and 'zh_tw' not in dest: return 'locale'
    return None


def prune(analysis, verbose=True):
    stats = {}
    for attribute in ('binaries', 'datas'):
        kept = []
        for entry in getattr(analysis, attribute):
            reason = _drop(entry[0], entry[1])
            if reason: stats[reason] = stats.get(reason, 0) + 1
            else: kept.append(entry)
        setattr(analysis, attribute, kept)
    if verbose: print(f'pyi_prune: removed {sum(stats.values())} entries: {stats}')
    return stats
