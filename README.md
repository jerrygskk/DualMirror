# DualMirror

**English** | [繁體中文](README.zh-TW.md)

**A Windows tool for comparing and merging files.**

Compare folders, text files, and binary files side by side. Inspect differences, edit text, and merge changes in a single window.
Multiple comparisons open in tabs. Starting another comparison adds it to the existing window; reopening the same pair returns to its tab.

Current version: **0.1.0**.
Download `DualMirror.exe` from the [GitHub Release](https://github.com/jerrygskk/DualMirror/releases/tag/v0.1.0). No separate Python installation is required.

## Features

| Feature | Description |
| --- | --- |
| Folder comparison | Synchronized expansion, selection, and scrolling in both folder trees, with filters for different, identical, and one-sided files. |
| Two-stage checks | Compare file sizes and modification times first, then verify actual contents when needed. |
| Text comparison and editing | Edit text directly, find and replace, and undo changes. Includes 19 language styles and 26 encoding options. |
| Merging differences | Use arrows to copy entire difference blocks, or select complete lines and copy them to the other side. |
| Binary comparison | Read-only hexadecimal views align insertions and deletions with gaps while preserving each side's original offsets. |
| File operations | Copy to the other side or another folder, rename on one side, or move items to the Windows Recycle Bin. |
| External change monitoring | When returning to the window, confirm updates for the left and right sides separately. Update only approved sides and check the on-disk version again before writing. |
| Windows 11 context menu integration | Compare two selected files or folders in File Explorer, or select the left item first and compare it with another item later. |

## Run from source

Tested on **Windows 11 with 64-bit Python 3.12**.

Download or clone this repository, open a terminal in the project folder, and run:

```powershell
py -3.12 -m pip install -r requirements.txt
py -3.12 main.py
```

You can also double-click `啟動.cmd` in the project root. This launcher uses Python 3.12 from the current user's default installation location. If Python is installed elsewhere, use the commands above.

To compare two files or two folders directly:

```powershell
py -3.12 main.py "C:\Compare\left.txt" "C:\Compare\right.txt"
py -3.12 main.py "C:\Compare\left" "C:\Compare\right"
```

## Basic usage

### Compare folders

1. Choose the left and right folders. File sizes and modification times are compared automatically.
2. Click the detailed comparison button to verify actual contents. If items are selected, only that selection is checked; otherwise, all items are checked.
3. Double-click a file to open its text or hexadecimal comparison in a new tab.

The `=` and `≠` symbols in the center indicate verified content results. A blank means the contents have not been verified, the item exists on only one side, or the row represents a folder.
**Matching sizes and modification times do not prove that file contents are identical.**

### Edit and merge text

- Edit either side directly. Gold arrows copy complete difference blocks.
- Click a text line or drag across line numbers to select complete lines, then use the blue arrow to copy the selection.
- Merging changes the in-memory content first. Files are written only when you save.
- The language selector controls syntax highlighting. The encoding selector reinterprets the file and cannot be changed while either side has unsaved edits.
- Find and replace offer Both sides, Left, and Right radio buttons in that order, with Both sides selected by default. Replacing all on both sides can be undone in one step.
- Use the close button or `Esc` to hide find and replace without clearing your input.

### Drag files into the window

- Drop two files to open a comparison, using their drag order for the left and right sides. Existing pairs reuse their tabs.
- Drop one file onto the left or right content pane of a text or Hex tab to replace that side. Unsaved changes require confirmation.
- Dropping one file onto a toolbar, tab bar, or start screen does not replace anything. Folder drops are not supported.

### External file changes

When you return to the window, the application checks the files in the current tab. If both changed externally, it asks about the left side first, then the right.
Only approved sides are updated. Declining suppresses repeated prompts for the same change. The confirmation warns when updating would discard unsaved edits on that side.

| Shortcut | Action |
| --- | --- |
| `Ctrl+S` | Save the active side |
| `Ctrl+Shift+S` | Save the active side as a new file |
| `Ctrl+F` | Find |
| `Ctrl+H` | Find and replace |
| `Ctrl+Z` / `Ctrl+Y` | Undo / redo |
| `Ctrl+W` | Close the current tab |
| `F5` | Refresh the folder comparison |

### Compare from File Explorer

Choose the context menu registration command in the application's integration menu and confirm to enable the Windows 11 context menu entries.
The current registration method requires Windows Developer Mode. The application does not enable it automatically.
You can unregister the integration at any time; font and comparison settings are preserved.

## Data protection and limitations

- Copy and synchronization keep source files and extra destination files. They do not delete destination files to create an exact mirror. Existing files with the same name may be overwritten after confirmation.
- Saving preserves the current encoding, BOM, and line endings in unchanged sections. Writing stops if the text cannot be encoded.
- Save As writes a separate copy without changing the current comparison pair or clearing the original file's unsaved state.
- Deletion uses the Windows Recycle Bin. Failure does not fall back to permanent deletion. Operations on links are not supported.
- Automatic encoding detection can be ambiguous. Check the displayed text and select an encoding manually when necessary.
- Hexadecimal comparison is read-only and currently keeps entire files in memory. Large files require more memory.
- Repeated content may have multiple valid alignments. The smallest possible number of differences is not guaranteed.

## Development documentation

The following documents are currently in Traditional Chinese:

- [Development, testing, and packaging](docs/DEVELOPER.md)
- [Known issues and fixes](docs/PITFALLS.md)
- [Version history](docs/HISTORY.md)
