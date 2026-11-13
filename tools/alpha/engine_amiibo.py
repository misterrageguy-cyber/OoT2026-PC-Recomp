"""Checked patches for the read-only amiibo reader and F1 file actions."""
from pathlib import Path
import shutil

HERE = Path(__file__).parent
MARKER = '#include "ocr_amiibo_menu.h"'
CHANGES = (
    ('#include "vk_fsr4.h"', '#include "vk_fsr4.h"\n' + MARKER),
    ('    {TAB_GAMEPLAY, "FPS counter",',
     '    {TAB_GAMEPLAY, "Load amiibo (.bin)", nullptr, 0, 0, 0, nullptr,\n'
     '     "Choose your own raw amiibo .bin (532/540/572 bytes), then close F1 and use the in-game amiibo scan. Read-only: rewards, no tag save writes. Normal game limits apply."},\n'
     '    {TAB_GAMEPLAY, "Remove amiibo", nullptr, 0, 0, 0, nullptr,\n'
     '     "Removes the selected tag from the virtual reader. Your original .bin is unchanged."},\n'
     '    {TAB_GAMEPLAY, "FPS counter",'),
    ('        else if (is_share_row(r)) choice_cell',
     '        else if (!strcmp(r.name, "Load amiibo (.bin)")) choice_cell(c, va, vb, ocr_amiibo_menu::busy ? "Choosing..." : "Choose file", selected, false, false);\n'
     '        else if (!strcmp(r.name, "Remove amiibo")) choice_cell(c, va, vb, "Remove", selected, false, false);\n'
     '        else if (is_share_row(r)) choice_cell'),
    ('    if (&selr == &rows[kBugReportRow]) hint = bug_report_hint();',
     '    const std::string amiibo_hint = ocr_amiibo_menu::message();\n'
     '    if ((!strcmp(selr.name, "Load amiibo (.bin)") || !strcmp(selr.name, "Remove amiibo")) && !amiibo_hint.empty()) hint = amiibo_hint.c_str();\n'
     '    if (&selr == &rows[kBugReportRow]) hint = bug_report_hint();'),
    ('        else if (press[7] && &r == &rows[kBugReportRow])',
     '        else if (press[7] && !strcmp(r.name, "Load amiibo (.bin)")) ocr_amiibo_menu::choose(app_window()), press[7] = false, changed = true;\n'
     '        else if (press[7] && !strcmp(r.name, "Remove amiibo")) ocr_amiibo_menu::clear(), press[7] = false, changed = true;\n'
     '        else if (press[7] && &r == &rows[kBugReportRow])'),
)


def apply(root):
    root = Path(root)
    path = root / 'gpu/vk/vk_menu.cpp'
    source = path.read_text(encoding='utf-8')
    if MARKER in source:
        if not all(new in source for _, new in CHANGES):
            raise RuntimeError('Incomplete amiibo menu patch: ' + str(path))
    else:
        for old, _ in CHANGES:
            if source.count(old) != 1:
                raise RuntimeError('Amiibo patch anchor missing or ambiguous: ' + old)
        for old, new in CHANGES:
            source = source.replace(old, new)
        path.write_text(source, encoding='utf-8', newline='\n')
    for name, destination in (('ocr_amiibo.c', 'host'), ('ocr_amiibo_file.h', 'host'),
                              ('ocr_amiibo_menu.h', 'gpu/vk')):
        shutil.copy2(HERE / 'hud' / name, root / destination / name)
    print('amiibo: read-only .bin reader and F1 file picker')
