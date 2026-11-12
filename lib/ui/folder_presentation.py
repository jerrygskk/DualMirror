"""資料夾清單的單側顏色與子項目彙整；不改快速／內容比較結果。"""
from pathlib import Path

COLORS = {'same': '#000000', 'different': '#ff0000', 'left': '#285b83',
          'right': '#285b83', 'conflict': '#ff0000'}
FOLDER_DESCRIPTIONS = {
    'gray': '無較新或單側項目', 'red': '包含較新或不同的項目',
    'purple': '項目僅存在於此側', 'gray_purple': '包含單側項目及相同或較舊項目',
    'red_purple': '包含較新或不同項目，以及單側項目',
}


def file_color(row, side):
    color = COLORS[row.status]
    if row.status == 'different':
        try:
            times = (row.stamp[0][1], row.stamp[1][1])
            if times[side] < times[1 - side]: return '#808080'
        except (TypeError, IndexError): pass
    return color


def summarize_folders(rows):
    flags = {row.relative: [0, 0] for row in rows if row.directory}
    totals = {name: [0, 0] for name in flags}
    for row in sorted(rows, key=lambda item: len(Path(item.relative).parts), reverse=True):
        values, sizes = [0, 0], [row.left_size or 0, row.right_size or 0]
        for side in (0, 1):
            present = row.stamp[side] is not None if row.stamp else (row.left, row.right)[side].exists()
            if not present: continue
            if row.directory:
                values[side] = flags[row.relative][side]
                if row.status in ('left', 'right'): values[side] |= 4
                elif row.status == 'conflict': values[side] |= 2
                if not values[side]: values[side] = 1
                flags[row.relative][side] = values[side]
                sizes[side] += totals[row.relative][side]
                totals[row.relative][side] = sizes[side]
            else:
                color = file_color(row, side)
                values[side] = 4 if row.status in ('left', 'right') else 2 if color == '#ff0000' else 1
        parent = Path(row.relative).parent.as_posix()
        if parent in flags:
            for side in (0, 1):
                flags[parent][side] |= values[side]
                totals[parent][side] += sizes[side]
    def style(value):
        if value & 2: return 'red_purple' if value & 4 else 'red'
        if value & 4: return 'gray_purple' if value & 1 else 'purple'
        return 'gray'
    return {name: tuple(style(value) for value in pair) for name, pair in flags.items()}, {name: tuple(pair) for name, pair in totals.items()}
