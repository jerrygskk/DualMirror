"""可選語言與 Pygments 上色；所有座標經原始文字到顯示 UTF-16 映射。"""
from bisect import bisect_right
from pathlib import Path
from pygments.lexers import get_lexer_by_name
from pygments.styles import get_style_by_name
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor


LANGUAGES = [
    ('text', '純文字', ('.txt',)), ('python', 'Python', ('.py', '.pyw')),
    ('c', 'C', ('.c', '.h')), ('cpp', 'C++', ('.cpp', '.hpp', '.cc', '.cxx')),
    ('csharp', 'C#', ('.cs',)), ('java', 'Java', ('.java',)),
    ('javascript', 'JavaScript', ('.js', '.mjs', '.cjs')),
    ('typescript', 'TypeScript', ('.ts', '.tsx')),
    ('html', 'HTML', ('.html', '.htm')), ('css', 'CSS', ('.css',)),
    ('json', 'JSON', ('.json',)), ('xml', 'XML', ('.xml', '.svg', '.xsd')),
    ('yaml', 'YAML', ('.yaml', '.yml')), ('sql', 'SQL', ('.sql',)),
    ('ini', 'INI', ('.ini', '.cfg', '.conf')), ('bash', 'Shell', ('.sh', '.bash')),
    ('powershell', 'PowerShell', ('.ps1', '.psm1')), ('bat', '批次檔', ('.bat', '.cmd')),
    ('markdown', 'Markdown', ('.md', '.markdown')),
]


def detect_language(path, text):
    suffix = Path(path).suffix.lower()
    for alias, label, extensions in LANGUAGES:
        if suffix in extensions: return alias
    scores = [(get_lexer_by_name(alias).analyse_text(text), alias) for alias, _, _ in LANGUAGES if alias != 'text']
    score, alias = max(scores)
    return alias if score >= 0.5 else 'text'


class SyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, editor):
        super().__init__(editor.document())
        self.editor = editor
        self.language = 'text'
        self.starts, self.spans = [], []
        self.style = get_style_by_name('friendly')
        self.formats = {}

    def set_source(self, text, language):
        self.language = language
        self.starts, self.spans = [], []
        if language != 'text':
            for offset, token, value in get_lexer_by_name(language).get_tokens_unprocessed(text):
                if token not in self.formats:
                    fmt = QTextCharFormat()
                    styled = token
                    while styled not in self.style.styles and styled.parent is not None: styled = styled.parent
                    color = self.style.style_for_token(styled)['color']
                    fmt.setForeground(QColor('#' + color if color else '#111111'))
                    self.formats[token] = fmt
                self.starts.append(offset)
                self.spans.append((offset + len(value), self.formats[token]))
        self.rehighlight()

    def highlightBlock(self, text):
        if not self.starts: return
        origin = self.currentBlock().position()
        positions = self.editor.raw_positions
        width = len(text.encode('utf-16-le')) // 2
        run_start, last_format = 0, None
        for index in range(width + 1):
            fmt = None
            if index < width and origin + index < len(positions):
                raw = positions[origin + index]
                token = bisect_right(self.starts, raw) - 1
                if token >= 0 and raw < self.spans[token][0]: fmt = self.spans[token][1]
            if fmt is not last_format:
                if last_format is not None: self.setFormat(run_start, index - run_start, last_format)
                run_start, last_format = index, fmt
