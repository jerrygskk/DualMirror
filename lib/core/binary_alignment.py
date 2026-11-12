"""二進位內容對齊；區段保存原位址，顯示補位不屬於原始資料。"""
from bisect import bisect_right
from difflib import SequenceMatcher


def _chunks(data, start, end):
    tokens, offsets = [], [start]
    origin, rolling = start, 0
    for position in range(start, end):
        rolling = ((rolling << 1) + (data[position] + 1) * 0x9E3779B1) & 0xFFFFFFFF
        size = position + 1 - origin
        if size >= 512 or (size >= 64 and rolling & 127 == 0):
            tokens.append(data[origin:position + 1]); offsets.append(position + 1)
            origin, rolling = position + 1, 0
    if origin < end:
        tokens.append(data[origin:end]); offsets.append(end)
    return tokens, offsets


class BinaryAlignment:
    def __init__(self, documents, opcodes):
        self.segments, self.starts, self.blocks = [], [], []
        self.length = 0
        for tag, a, b, c, d in opcodes:
            width = max(b - a, d - c)
            if not width: continue
            self.starts.append(self.length)
            self.segments.append((self.length, self.length + width, a, b, c, d))
            if tag != 'equal':
                run = None
                for offset in range(width):
                    same = a + offset < b and c + offset < d and documents[0][a + offset] == documents[1][c + offset]
                    if not same and run is None: run = self.length + offset
                    if same and run is not None:
                        self._difference(run, self.length + offset); run = None
                if run is not None: self._difference(run, self.length + width)
            self.length += width

    def _difference(self, start, end):
        if self.blocks and self.blocks[-1][1] == start:
            self.blocks[-1] = (self.blocks[-1][0], end)
        else:
            self.blocks.append((start, end))

    def raw_offset(self, side, position):
        index = bisect_right(self.starts, position) - 1
        if index < 0 or position >= self.length: return None
        start, end, a, b, c, d = self.segments[index]
        origin, limit = (a, b) if side == 0 else (c, d)
        offset = origin + position - start
        return offset if offset < limit else None


def align_binary(left, right):
    """先比共同前後綴，大範圍用內容切塊錨點，小範圍細比位元組。"""
    opcodes = []
    def append(tag, a, b, c, d):
        if a == b and c == d: return
        if opcodes and opcodes[-1][0] == tag and opcodes[-1][2] == a and opcodes[-1][4] == c:
            _, pa, _, pc, _ = opcodes.pop()
            a, c = pa, pc
        opcodes.append((tag, a, b, c, d))

    def refine(a, b, c, d):
        prefix = 0
        while a + prefix < b and c + prefix < d and left[a + prefix] == right[c + prefix]: prefix += 1
        append('equal', a, a + prefix, c, c + prefix)
        a += prefix; c += prefix
        suffix = 0
        while b - suffix > a and d - suffix > c and left[b - suffix - 1] == right[d - suffix - 1]: suffix += 1
        be, de = b - suffix, d - suffix
        if a == be or c == de:
            append('replace', a, be, c, de)
        elif max(be - a, de - c) <= 2048:
            for tag, x, y, z, w in SequenceMatcher(None, left[a:be], right[c:de], autojunk=False).get_opcodes():
                append(tag, a + x, a + y, c + z, c + w)
        else:
            lt, lo = _chunks(left, a, be)
            rt, ro = _chunks(right, c, de)
            for tag, x, y, z, w in SequenceMatcher(None, lt, rt, autojunk=True).get_opcodes():
                if tag == 'equal':
                    append(tag, lo[x], lo[y], ro[z], ro[w])
                else:
                    # 沒有共同錨點時以線性啟發式細比，避免大量重複位元組造成平方級耗時。
                    la, lb, ra, rb = lo[x], lo[y], ro[z], ro[w]
                    for kind, p, q, r, s in SequenceMatcher(None, left[la:lb], right[ra:rb], autojunk=max(lb - la, rb - ra) > 2048).get_opcodes():
                        append(kind, la + p, la + q, ra + r, ra + s)
        append('equal', be, b, de, d)

    refine(0, len(left), 0, len(right))
    return BinaryAlignment((left, right), opcodes)
