"""視窗重新啟用時，逐側確認目前內容分頁的外部變更。"""
import hashlib

from PySide6.QtCore import QObject, QEvent, QTimer
from PySide6.QtWidgets import QApplication

from lib.core.core import TextFile, pair_stamp
from lib.core.binary_alignment import align_binary
from lib.ui.hex_compare import HexCompare, load_binary_pair
from lib.ui.text_compare import TextCompare
from lib.ui.ui_common import confirmBox, msgInfo


def signature(data):
    return hashlib.sha256(data).digest() if data is not None else None


class ExternalReload(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.pending = False
        self.working = False
        self.ready = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.process)
        window.installEventFilter(self)

    @property
    def idle(self):
        return not (self.pending or self.working or self.ready or self.timer.isActive())

    def eventFilter(self, target, event):
        if event.type() == QEvent.WindowActivate and isinstance(self.window.tabs.currentWidget(), (TextCompare, HexCompare)):
            self.request()
        return False

    def request(self, *_):
        self.pending = True
        self.timer.start(0)

    def run(self, operation, complete):
        self.working = True
        self.window.run_job(operation, complete)
        self.window.workers[-1].finished.connect(self.finished)

    def finished(self):
        self.working = False
        self.timer.start(0)

    def process(self):
        window = self.window
        if window._closing:
            self.pending = False; self.ready = None
            return
        if self.working or window.busy or window._confirmation_active or QApplication.activeModalWidget(): return
        if self.ready is not None:
            page, baseline, raw = self.ready
            self.ready = None
            if page in window.windows and page is window.tabs.currentWidget() and page.disk_baseline == baseline:
                self.ask(page, baseline, raw)
            if self.pending and not self.working: self.timer.start(0)
        elif self.pending:
            self.pending = False
            page = window.tabs.currentWidget()
            if not isinstance(page, (TextCompare, HexCompare)): return
            pair, baseline = page.file_pair, page.disk_baseline
            def complete(raw): self.ready = (page, baseline, raw)
            self.run(lambda: load_binary_pair(pair), complete)

    def ask(self, page, baseline, raw):
        window = self.window
        if isinstance(page, TextCompare): page.flush_edit()
        seen = getattr(page, '_external_seen', [signature(data) for data in baseline])
        page._external_seen = seen
        approved = []
        window._confirmation_active = True
        try:
            for side, data in enumerate(raw):
                value = signature(data)
                if data == baseline[side]:
                    seen[side] = value
                    continue
                if seen[side] == value: continue
                label = '左側' if side == 0 else '右側'
                text = f'{label}檔案已在外部變更或刪除，是否更新？\n{page.file_pair[side]}'
                if page.dirty[side]: text += f'\n更新將捨棄{label}尚未儲存的修改。'
                if confirmBox('檔案已變更', text, confirm_text='更新', default_confirm=False, parent=window):
                    approved.append(side)
                else: seen[side] = value
        finally:
            window._confirmation_active = False
            if window._refresh_pending: window.refresh_timer.start(0)
        if not approved: return
        pair = page.file_pair
        before_text = tuple(page.texts) if isinstance(page, TextCompare) else None
        codecs = tuple(page.encoding_overrides) if isinstance(page, TextCompare) else None
        original_documents = list(page.docs if codecs is not None else baseline)
        def prepare():
            stamp = pair_stamp(*pair)
            current = load_binary_pair(pair)
            if any(current[side] != raw[side] for side in approved):
                raise OSError('確認期間檔案再次變更，未更新內容，請重新切回視窗檢查。')
            documents = original_documents.copy()
            for side in approved:
                data = raw[side]
                documents[side] = TextFile.from_bytes(pair[side], data, codecs[side]) if codecs is not None and data is not None else data
                if codecs is not None and data is not None and documents[side] is None:
                    raise ValueError('外部檔案無法以文字讀取，請重新開啟比較。')
            alignment = align_binary(*(data or b'' for data in documents)) if codecs is None else None
            if pair_stamp(*pair) != stamp: raise OSError('讀取期間檔案已變更，未更新內容。')
            return documents, alignment, stamp if codecs is None and documents == current else None
        def apply(result):
            if page not in window.windows or page.disk_baseline != baseline: return
            if before_text is not None and tuple(page.texts) != before_text:
                msgInfo('未更新內容', '確認後又有編輯，已保留目前內容，請重新切回視窗檢查。', window)
                return
            documents, alignment, stamp = result
            if before_text is not None: page.apply_side_updates(documents, approved)
            else: page.apply_disk_update((documents, alignment, stamp), baseline)
            for side in approved: seen[side] = signature(raw[side])
            window.update_watches()
        self.run(prepare, apply)
