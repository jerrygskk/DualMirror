"""同一帳號的後續啟動只傳送請求，不建立第二個主視窗。"""
import hashlib
import json
import time
from pathlib import Path

from PySide6.QtCore import QObject, QLockFile, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class InstanceChannel(QObject):
    requested = Signal(list)

    def __init__(self, directory, parent=None):
        super().__init__(parent)
        directory = Path(directory).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(str(directory).casefold().encode('utf-8')).hexdigest()[:24]
        self.name = 'DualMirror-' + digest
        self.lock = QLockFile(str(directory / 'instance.lock'))
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.UserAccessOption)
        self.server.newConnection.connect(self.accept_connections)
        self.connections = {}
        self.primary = False

    def start(self):
        if not self.lock.tryLock(0):
            if self.lock.error() != QLockFile.LockFailedError:
                raise OSError('無法建立程式啟動鎖定。')
            return False
        # 只有取得鎖定的程序可清理崩潰後留下的通訊端。
        QLocalServer.removeServer(self.name)
        if not self.server.listen(self.name):
            self.lock.unlock()
            raise OSError(self.server.errorString())
        self.primary = True
        return True

    def forward(self, paths):
        # Windows 只允許目前前景程序授權其他程序取得前景。
        # 第二次啟動先授權既有程序，再請它喚回視窗。
        import sys
        if sys.platform == 'win32':
            import ctypes
            pid, _, _ = self.lock.getLockInfo()
            if pid: ctypes.windll.user32.AllowSetForegroundWindow(pid)
        socket = QLocalSocket()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            socket.connectToServer(self.name)
            if socket.waitForConnected(200): break
            socket.abort()
            time.sleep(0.05)
        else:
            return False
        payload = json.dumps(list(map(str, paths)), ensure_ascii=False).encode('utf-8') + b'\n'
        socket.write(payload)
        if not socket.waitForBytesWritten(3000):
            socket.abort()
            return False
        reply = bytearray()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            reply.extend(bytes(socket.readAll()))
            if b'\n' in reply: break
            if not socket.waitForReadyRead(200):
                if socket.state() == QLocalSocket.UnconnectedState: break
        reply.extend(bytes(socket.readAll()))
        socket.abort()
        return bytes(reply) == b'OK\n'

    def accept_connections(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            self.connections[socket] = bytearray()
            socket.readyRead.connect(lambda s=socket: self.read_request(s))
            socket.disconnected.connect(lambda s=socket: self.release(s))
            self.read_request(socket)

    def read_request(self, socket):
        buffer = self.connections.get(socket)
        if buffer is None: return
        buffer.extend(bytes(socket.readAll()))
        if len(buffer) > 65536:
            socket.abort()
            return
        if b'\n' not in buffer: return
        self.connections[socket] = None
        try:
            paths = json.loads(bytes(buffer).decode('utf-8'))
            if not isinstance(paths, list) or len(paths) not in (0, 2):
                raise ValueError('無效的比較請求。')
            if any(not isinstance(path, str) for path in paths):
                raise ValueError('無效的比較路徑。')
        except (ValueError, UnicodeError):
            socket.write(b'ERROR\n')
        else:
            self.requested.emit(paths)
            socket.write(b'OK\n')
        socket.disconnectFromServer()

    def release(self, socket):
        self.connections.pop(socket, None)
        socket.deleteLater()

    def close(self):
        for socket in list(self.connections): socket.abort()
        self.server.close()
        if self.primary:
            self.lock.unlock()
            self.primary = False
