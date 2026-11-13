"""Checked engine patches for the shared tunic color controls and offline helper."""
import shutil
from pathlib import Path
from engine_v21 import patch

HERE = Path(__file__).parent


def apply(H):
    shutil.copy2(HERE / 'hud/ocr_tunic.c', H / 'host/ocr_tunic.c')
    shutil.copy2(HERE / 'hud/tunic_assets.py', H / 'nx2/tunic_assets.py')
    patch(H, 'host/hos_main.c', [
        ('    hos_mods_init(image);', '    hos_mods_init(image);\n'
         '    void ocr_tunic_init(const char *romfs);\n    ocr_tunic_init(hos_romfs_dir);')])
    with (H / 'host/mods.c').open('a', encoding='utf-8', newline='') as f:
        f.write('''
/* Ocarina Reborn: snapshot the already-resolved mod stack before adding the tunic.
   UTF-8 paths: the game's Windows manifest selects the UTF-8 active code page. */
int hos_mods_export_tunic_sources(const char *path) {
    FILE *f = fopen(path, "wb");
    if (!f) return 0;
    for (size_t i = 0; i < table_cap; ++i) {
        const Entry *e = &table[i];
        if (e->key && !e->is_dir) fprintf(f, "%s\\t%s\\n", e->key, e->host);
    }
    int ok = !ferror(f);
    return fclose(f) == 0 && ok;
}
int hos_mods_add_tunic(const char *path) { return index_romfs(path, "", 0); }
''')
    patch(H, 'nx2/make_game.py', [
        ('    for src, dst in staged:\n',
         '    if not LINUX:\n        import tunic_assets\n'
         '        tunic_assets.ship_runtime(ROOT, out)\n'
         '    for src, dst in staged:\n')])
    patch(H, 'gpu/vk/vk_menu.cpp', [
        ('#include "vk_fsr4.h"\n', '#include "vk_fsr4.h"\n'
         'namespace mkwvk { int ocr_tunic = 0, ocr_tunic_r = 80, ocr_tunic_g = 160, ocr_tunic_b = 75; }\n'),
        ('const char* tx_onoff(int v)',
         'const char* tx_tunic_rgb(int v) { static char b[16]; snprintf(b, sizeof b, "%d", v); return b; }\n'
         'const char* tx_onoff(int v)'),
        ('    {TAB_GAMEPLAY, "FPS counter",',
         '    {TAB_GAMEPLAY, "Custom tunic color", &ocr_tunic, 0, 1, 1,\n'
         '     +[](int v) -> const char* { return v ? "Custom" : "Original"; },\n'
         '     "Recolors young Link and adult tunics. Choose any RGB color below. Original restores the original clothes. Save and restart.", nullptr, true, true},\n'
         + ''.join('    {TAB_GAMEPLAY, "Tunic ' + name + '", &ocr_tunic_' + short + ', 0, 255, 1, tx_tunic_rgb,\n'
                   '     "RGB color component (0-255). Enable Custom tunic color, then save and restart. Lighting affects the result.", nullptr, true, true},\n'
                   for name, short in [('red', 'r'), ('green', 'g'), ('blue', 'b')]) +
         '    {TAB_GAMEPLAY, "FPS counter",'),
        ('bool is_slider(const Row& r) { return ',
         'bool is_slider(const Row& r) { return r.value == &ocr_tunic_r || r.value == &ocr_tunic_g || r.value == &ocr_tunic_b || '),
        ('bool stops_at_ends(const Row& r) { return ',
         'bool stops_at_ends(const Row& r) { return r.value == &ocr_tunic_r || r.value == &ocr_tunic_g || r.value == &ocr_tunic_b || '),
        ('    const std::string tool = r.cheat >= 0 ? cheat_value(r.cheat) : "";',
         '    if (r.value == &ocr_tunic) {\n'
         '        c.d->AddRectFilled(ImVec2(va.x + 4*s, va.y + 9*s), ImVec2(va.x + 27*s, vb.y - 9*s),\n'
         '            ui::rgba(ocr_tunic_r, ocr_tunic_g, ocr_tunic_b), 3*s);\n'
         '        va.x += 32*s;\n    }\n'
         '    const std::string tool = r.cheat >= 0 ? cheat_value(r.cheat) : "";')])
    patch(H, 'gpu/vk/menu_restart.h', [('constexpr int kMax = 16;', 'constexpr int kMax = 32;')])
    print('tunic: shared RGB controls, offline private textures and direct-exe support')
