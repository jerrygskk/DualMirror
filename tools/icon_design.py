"""維護者確認的雙色線條 SVG：暖金資料夾、藍色操作、紅色差異。"""
SLATE = "#536476"
UP_ICONS = {
    'imgGutterCopyCustomRight': '<path fill="#d6e8f5" stroke="#536476" stroke-width="1.25" d="M1.5 7h8V3l9 7-9 7v-4h-8z"/>',
    'imgGutterCopyCustomLeft': '<path fill="#d6e8f5" stroke="#536476" stroke-width="1.25" d="M18.5 7h-8V3l-9 7 9 7v-4h8z"/>',
    'imgFolderUp': '<path fill="#fff0c9" stroke="#ad7b28" d="M2 7h5l2 2h9v8H2z"/><path stroke="#2779bd" stroke-width="1.7" d="M11 13V3m-3 3 3-3 3 3"/>',
    'imgBothUp': '<rect fill="#eef5fb" stroke="#bacbda" x="1.5" y="3" width="7" height="14" rx="1"/><rect fill="#eef5fb" stroke="#bacbda" x="11.5" y="3" width="7" height="14" rx="1"/><path stroke="#2779bd" stroke-width="1.7" d="M5 14V6m-2 2 2-2 2 2M15 14V6m-2 2 2-2 2 2"/>',
}

def svg(body):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20"><g fill="none" stroke="{SLATE}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">' + body + '</g></svg>'

ICONS = {'imgCompareContents': '<path d="M2 7h6M2 12h6"/><path stroke="#2779bd" stroke-width="1.7" d="M12 6a3 3 0 1 '
                       '1 5 2c-1.5 1-2.5 1-2.5 3"/><circle fill="#2779bd" stroke="none" cx="14.5" cy="15" '
                       'r="1"/>',
 'imgRefresh': '<path stroke="#2779bd" stroke-width="1.7" d="M16.5 7a7 7 0 1 0 .3 5M16.5 2.8V7h-4.2"/><path '
               'stroke="#9cb5c9" d="M6 5.5a5 5 0 0 0-1.2 6.3"/>',
 'imgTextCompareSession': '<rect fill="#eef5fb" x="2" y="3" width="6" height="14" rx="1"/><rect '
                          'fill="#e0effb" stroke="#2779bd" x="12" y="3" width="6" height="14" rx="1"/><path '
                          'd="M4 7h2m-2 3h2m8-3h2m-2 3h2m-2 3h2"/>',
 'imgDirCompareSession': '<path fill="#e7f1fa" d="M1.5 5h3l1.5 2h3v10H1.5z"/><path fill="#fff0c9" '
                         'stroke="#ad7b28" d="M11 5h3l1.5 2h3v10H11z"/>',
 'imgCopyLeft': '<rect fill="#eef5fb" stroke="#bacbda" x="11" y="3" width="6" height="14" rx="1"/><path '
                'stroke="#2779bd" stroke-width="1.8" d="M17 10H4m4-4-4 4 4 4"/>',
 'imgCopyRight': '<rect fill="#eef5fb" stroke="#bacbda" x="3" y="3" width="6" height="14" rx="1"/><path '
                 'stroke="#2779bd" stroke-width="1.8" d="M3 10h13m-4-4 4 4-4 4"/>',
 'imgUpdateLeft': '<path stroke="#ad7b28" d="M2 4v12"/><path stroke="#2779bd" stroke-width="1.8" d="M17 '
                  '10H4m4-4-4 4 4 4"/>',
 'imgUpdateRight': '<path stroke="#ad7b28" d="M18 4v12"/><path stroke="#2779bd" stroke-width="1.8" d="M3 '
                   '10h13m-4-4 4 4-4 4"/>',
 'imgBrowse': '<path fill="#fff0c9" stroke="#ad7b28" d="M2 5h6l2 2h8v9.5a1 1 0 0 1-1 1H3a1 1 0 0 '
              '1-1-1z"/><path fill="#ffdb85" stroke="#ad7b28" d="M2.5 10h15.8l-2.1 6.5a1 1 0 0 1-1 '
              '.7H2.5z"/>',
 'imgTextFormat': '<path fill="#f2f7fc" d="M4 2.5h7l4 4v11h-11z"/><path d="M11 2.5v4h4"/><path '
                  'stroke="#2779bd" d="M7 10h6m-6 3h4"/>',
 'imgFolderTop0': '<path fill="#fff0c9" stroke="#ad7b28" d="M2 5h6l2 2h8v9.5a1 1 0 0 1-1 1H3a1 1 0 0 '
                  '1-1-1z"/>',
 'imgDiffSectionPrevNone': '<path stroke="#2779bd" stroke-width="1.7" d="M10 17V5m-4 4 4-4 4 4"/><path '
                           'stroke="#cb534c" d="M4 2h12"/>',
 'imgDiffSectionNextNone': '<path stroke="#2779bd" stroke-width="1.7" d="M10 3v12m-4-4 4 4 4-4"/><path '
                           'stroke="#cb534c" d="M4 18h12"/>',
 'imgSave': '<path fill="#e5f1fb" stroke="#2779bd" d="M3 3h12l2 2v12H3z"/><path fill="#ffffff" d="M6 '
            '3v5h8V3M6 12h8v5H6z"/>',
 'imgExpandAll': '<path stroke="#a4b5c3" d="M4 2v13h4M4 6h4"/><rect fill="#e9f3fc" stroke="#2779bd" x="8" '
                 'y="3" width="9" height="7" rx="1"/><path stroke="#2779bd" d="M10.5 6.5h4m-2-2v4M10 '
                 '14h6m-3-2v4"/>',
 'imgCollapseAll': '<path stroke="#a4b5c3" d="M4 2v13h4M4 6h4"/><rect fill="#e9f3fc" stroke="#2779bd" x="8" '
                   'y="3" width="9" height="7" rx="1"/><path stroke="#2779bd" d="M10.5 6.5h4M10 14h6"/>',
 'imgSwap': '<path stroke="#2779bd" stroke-width="1.7" d="M3 6h14l-3-3"/><path stroke-width="1.7" d="M17 '
            '14H3l3 3"/>',
 'imgGutterCopySectionRight': '<path fill="#ffdb85" stroke="#ad7b28" stroke-width="1.25" d="M1.5 7h8V3l9 7-9 7v-4h-8z"/>',
 'imgGutterCopySectionLeft': '<path fill="#ffdb85" stroke="#ad7b28" stroke-width="1.25" d="M18.5 7h-8V3l-9 7 9 7v-4h8z"/>',
 'imgFavAll': '<path stroke="#273b50" stroke-width="1.7" d="M10 3v14M4 6.5l12 7M4 13.5l12-7"/><circle '
              'fill="#2779bd" stroke="none" cx="10" cy="10" r="1.8"/>',
 'imgFavDiff': '<path stroke="#cb534c" stroke-width="1.8" d="m8 3-3 14m10-14-3 14M3 7h14M2 13h14"/>',
 'imgFavSame': '<path stroke="#536476" stroke-width="1.8" d="M4 7h12"/><path stroke="#2779bd" '
               'stroke-width="1.8" d="M4 13h12"/>',
 'imgUndo': '<path stroke="#2779bd" stroke-width="1.7" d="M7 4 3 8l4 4M3 8h8a5 5 0 0 1 0 10"/>',
 'imgRedo': '<path stroke="#2779bd" stroke-width="1.7" d="m13 4 4 4-4 4M17 8H9a5 5 0 0 0 0 10"/>',
 'imgFind': '<circle fill="#edf5fc" cx="8.5" cy="8.5" r="5.5"/><path stroke="#2779bd" stroke-width="2" '
            'd="m13 13 4.5 4.5"/>',
 'imgClose': '<path d="m5 5 10 10M15 5 5 15"/>',
 'imgSettings': '<path stroke="#a4b5c3" d="M3 5h14M3 10h14M3 15h14"/><rect fill="#e3f0fc" stroke="#2779bd" '
                'x="5" y="3" width="3" height="4" rx="1"/><rect fill="#e3f0fc" stroke="#2779bd" x="12" y="8" '
                'width="3" height="4" rx="1"/><rect fill="#e3f0fc" stroke="#2779bd" x="7" y="13" width="3" '
                'height="4" rx="1"/>'}
ICONS.update(UP_ICONS)
ICONS['imgSpinUp'] = '<path d="M3 14 10 6 17 14z" fill="#555555" stroke="none"/>'
ICONS['imgSpinDown'] = '<path d="M3 6h14l-7 8z" fill="#555555" stroke="none"/>'

# Folder icon colors summarize each side's descendants independently.
for _name, _back, _front, _edge, _accent in (
    ('gray', '#ADB3BA', '#D3D6DA', '#666D75', None),
    ('red', '#DD8582', '#F1B5AF', '#9B5451', None),
    ('purple', '#3977A7', '#79ACD2', '#3C6688', None),
    ('gray_purple', '#ADB3BA', '#D3D6DA', '#666D75', '#3977A7'),
    ('red_purple', '#DD8582', '#F1B5AF', '#9B5451', '#3977A7'),
):
    _body = f'<g transform="scale(1.25)" stroke-width="1"><path fill="{_back}" stroke="{_edge}" d="M1.5 12.5V3.5h4l1.5 1.5h7v7.5z"/><path fill="{_front}" stroke="{_edge}" d="M2.5 7h12L13 12.5H1z"/>'
    if _accent:
        _body += f'<path fill="{_accent}" stroke="none" d="M12 7h2.5L13 12.5H4z"/><path fill="none" stroke="{_edge}" d="M2.5 7h12L13 12.5H1z"/>'
    _body += '<path stroke="#fff" stroke-opacity=".45" stroke-width=".65" d="M3 8h10.4"/></g>'
    ICONS['imgFolder_' + _name] = _body
for _name, _color in (('same', '#000000'), ('red', '#ff0000'), ('gray', '#808080'), ('purple', '#285b83')):
    ICONS['imgFile_' + _name] = f'<rect x="6" y="6" width="8" height="8" fill="{_color}" stroke="none"/>'
