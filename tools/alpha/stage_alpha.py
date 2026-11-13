"""Developer side: assembles the Ocarina Reborn install folder (what the installer copies) from this machine's tools.

    python tools/alpha/stage_alpha.py --work <du-h/work> --out <stage dir>

Contents: python/ (CPython 3.11 with numpy, lz4, zstandard, zbic), llvm/ (llvm-mingw), deps/ (runtime-deps), bin/ninja.exe,
src/ (the repository's tools and the dkb lifter, runtime and tools), data/, game-files/ (DLLs, shader translator,
default totk.ini). Nothing derived from a game dump is copied: check_content's marker is searched for at the end.
"""
import argparse
import re
import time
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP = shutil.ignore_patterns('__pycache__', '*.pyc', 'build', 'refs', 'generated', 'toolchain', '.venv*', '*.log',
                              'p22-*', 'tests', 'licensing-server', 'keys', 'database', 'icon', 'exe')


def copy(src, dst, ignore=None):
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=ignore)


# What the player sees of the game: the window, its icon, message boxes and the in-game menu's heading say Ocarina
# Reborn. Only user-facing strings change; the GPL notices and the source's attribution stay (NOTICE-OCARINA-REBORN.txt).
# (Ocarina Reborn) the start-up screen's text in the game's language (gpu/vk/vk_progress.h ocr_tr; REBRAND below). Only languages
# whose letters the start-up font has (Latin-1); the others keep the English
STARTUP_TR = {
    'de': ['Ein paar Sekunden', 'noch etwa %d s', 'noch etwa %d min', 'Wird beendet', 'Der vorbereitete Stand bleibt f\u00fcr den n\u00e4chsten Start',
           'Spiel wird gestartet', 'SCHRITT 1 VON 2', 'SCHRITT 2 VON 2', 'Shader werden vorbereitet', 'Pipelines werden gebaut',
           'Pipelines werden geladen', 'Das passiert nach einem Update nur einmal. Schlie\u00dft du das Fenster, bleibt der Stand erhalten.',
           'Shader des Spiels werden gelesen', 'Pipeline-Notizen werden gelesen', 'Shader-Cache wird geladen', ' Pipelines', ' Shader'],
    'fr': ['Quelques secondes', 'environ %d s restantes', 'environ %d min restantes', 'Fermeture', 'Ce qui est pr\u00e9par\u00e9 est gard\u00e9 pour le prochain lancement',
           'Lancement du jeu', '\u00c9TAPE 1 SUR 2', '\u00c9TAPE 2 SUR 2', 'Pr\u00e9paration des shaders', 'Construction des pipelines',
           'Chargement des pipelines', 'Cela n\u2019arrive qu\u2019une fois apr\u00e8s une mise \u00e0 jour. Fermer la fen\u00eatre garde la progression.'.replace('\u2019', "'"),
           'Lecture des shaders du jeu', 'Lecture des notes de pipelines', 'Chargement du cache de shaders', ' pipelines', ' shaders'],
    'es': ['Unos segundos', 'quedan unos %d s', 'quedan unos %d min', 'Cerrando', 'Lo preparado se guarda para el pr\u00f3ximo inicio',
           'Iniciando el juego', 'PASO 1 DE 2', 'PASO 2 DE 2', 'Preparando shaders', 'Creando pipelines',
           'Cargando pipelines', 'Esto solo ocurre una vez tras una actualizaci\u00f3n. Cerrar la ventana conserva el progreso.',
           'Leyendo los shaders del juego', 'Leyendo las notas de pipelines', 'Cargando la cach\u00e9 de shaders', ' pipelines', ' shaders'],
    'it': ['Pochi secondi', 'circa %d s rimanenti', 'circa %d min rimanenti', 'Chiusura', 'Quanto preparato resta per il prossimo avvio',
           'Avvio del gioco', 'PASSO 1 DI 2', 'PASSO 2 DI 2', 'Preparazione degli shader', 'Creazione delle pipeline',
           'Caricamento delle pipeline', 'Succede solo una volta dopo un aggiornamento. Chiudere la finestra mantiene i progressi.',
           'Lettura degli shader del gioco', 'Lettura delle note delle pipeline', 'Caricamento della cache degli shader', ' pipeline', ' shader'],
    'pt': ['Alguns segundos', 'cerca de %d s restantes', 'cerca de %d min restantes', 'Fechando', 'O que foi preparado fica para o pr\u00f3ximo in\u00edcio',
           'Iniciando o jogo', 'ETAPA 1 DE 2', 'ETAPA 2 DE 2', 'Preparando shaders', 'Criando pipelines',
           'Carregando pipelines', 'Isso s\u00f3 acontece uma vez ap\u00f3s uma atualiza\u00e7\u00e3o. Fechar a janela mant\u00e9m o progresso.',
           'Lendo os shaders do jogo', 'Lendo as notas de pipelines', 'Carregando o cache de shaders', ' pipelines', ' shaders'],
    'nl': ['Een paar seconden', 'nog ongeveer %d s', 'nog ongeveer %d min', 'Afsluiten', 'Wat klaar is, blijft bewaard voor de volgende start',
           'Spel wordt gestart', 'STAP 1 VAN 2', 'STAP 2 VAN 2', 'Shaders voorbereiden', 'Pipelines bouwen',
           'Pipelines laden', 'Dit gebeurt maar \u00e9\u00e9n keer na een update. Het venster sluiten bewaart de voortgang.',
           'Shaders van het spel lezen', 'Pipeline-notities lezen', 'Shader-cache laden', ' pipelines', ' shaders'],
}
STARTUP_EN = ['a few seconds left', 'about %d s left', 'about %d min left', 'Closing', 'Keeping what is prepared for the next start',
              'Starting the game', 'STEP 1 OF 2', 'STEP 2 OF 2', 'Preparing shaders', 'Building pipelines', 'Loading pipelines',
              'This happens once after an update. Closing the window keeps what is done.',
              "Reading the game's shaders", 'Reading the pipeline notes', 'Loading the shader cache', ' pipelines', ' shaders']


def _c(s):
    return '"' + s.replace(chr(92), chr(92) * 2).replace('"', chr(92) + '"') + '"'


STARTUP_TR_C = (
    '/// (Ocarina Reborn) the text in the game\'s language (HOS_LANGUAGE: the launcher\'s Game language), else as it is\n'
    'inline const char* ocr_tr(const char* en) {\n'
    '    static const char* const en_[] = {' + ', '.join(_c(s) for s in STARTUP_EN) + '};\n'
    + ''.join('    static const char* const %s_[] = {%s};\n' % (k, ', '.join(_c(s) for s in v)) for k, v in STARTUP_TR.items()) +
    '    static const char* const* const lang = [] () -> const char* const* {\n'
    '        const char* l = getenv("HOS_LANGUAGE");\n'
    '        if (!l) return nullptr;\n'
    + ''.join('        if (!strncmp(l, "%s", 2)) return %s_;\n' % (k, k) for k in STARTUP_TR) +
    '        return nullptr;\n'
    '    }();\n'
    '    if (lang)\n'
    '        for (size_t i = 0; i < sizeof en_ / sizeof *en_; i++)\n'
    '            if (!strcmp(en, en_[i])) return lang[i];\n'
    '    return en;\n'
    '}\n')
assert all(len(v) == len(STARTUP_EN) for v in STARTUP_TR.values())


REBRAND = {
    'host/hos.h': [('#define HOS_GAME_TITLE "Hookshot"', '#define HOS_GAME_TITLE "Ocarina Reborn"')],
    # Hookshot's own update offer ("A new version of Hookshot is out ... Hookshot Builder") never shows: Ocarina Reborn updates
    # through its launcher. Off in the game itself, not only through the launcher's HOOKSHOT_NO_UPDATE_CHECK, and its words
    # changed too in case a later Hookshot moves the switch
    'host/hos_update.c': [('void hos_update_check(void) {\n', 'void hos_update_check(void) {\n    if (1) return;   /* (Ocarina Reborn: the launcher updates) */\n'),
                          ('L"Hookshot update"', 'L"Ocarina Reborn"'),
                          ('A new version of Hookshot is out', 'A new version of Ocarina Reborn is out'),
                          ('Hookshot Builder', 'the Ocarina Reborn launcher')],
    'host/nn_video.c': [('"Hookshot", MB_YESNO', '"Ocarina Reborn", MB_YESNO')],
    'host/display.c': [('"Hookshot"', '"OcarinaReborn"')],   # (the window class: one name, both places)
    'host/discord_rpc.c': [('\\"state\\":\\"Hookshot %s\\"', '\\"state\\":\\"Ocarina Reborn %s\\"'),
                           ('\\"Hookshot %s\\"}}}}', '\\"Ocarina Reborn %s\\"}}}}')],
    'gpu/vk/vk_progcache.cpp': [('another Hookshot is using it', 'another Ocarina Reborn is using it')],   # (v2.2.0: the program cache's own file)
    'host/hos_main.c': [("L\"Hookshot can't open", "L\"Ocarina Reborn can't open"),
                        ('C:\\\\Games\\\\Hookshot', 'C:\\\\Games\\\\OcarinaReborn'),
                        ('text, L"Hookshot", MB_OK', 'text, L"Ocarina Reborn", MB_OK'),
                        ('MessageBoxA(NULL, text, "Hookshot", MB_OK', 'MessageBoxA(NULL, text, "Ocarina Reborn", MB_OK'),
                        ('"Hookshot\'s saves are now in', '"Ocarina Reborn\'s saves are now in')],
    'host/mkw_glue.c': [('so Hookshot may close', 'so Ocarina Reborn may close'),
                        ('"Hookshot: out of memory"', '"Ocarina Reborn: out of memory"')],
    'host/mf_av1.c': [('"Hookshot\'s movies need', '"Ocarina Reborn\'s movies need'),
                      ('"Hookshot", MB_YESNO', '"Ocarina Reborn", MB_YESNO')],
    # (the launcher starts the game with HOS_DISCORD=0: Discord would show Hookshot's own Discord application)
    'gpu/vk/vk_menu.cpp': [(r'"Shows \"Playing Hookshot\" and the time played in your Discord status, while Discord runs on this PC."',
                            r'"Off in Ocarina Reborn: nothing is shown in your Discord status."')],
    'gpu/vk/vk_main.cpp': [('SetConsoleTitleA("Hookshot")', 'SetConsoleTitleA("Ocarina Reborn")'),
                           ('"Hookshot: graphics card"', '"Ocarina Reborn: graphics card"'),
                           (r'\n\nHookshot needs a GPU', r'\n\nOcarina Reborn needs a GPU')],
    # (the start-up screen is drawn by vk_menu.cpp's draw_startup now: hud_v21.py)
    # (gpu/vk/vk_progress.h, the start-up screen: in the game's language (HOS_LANGUAGE, which the launcher sets from its Game
    # language), UTF-8. It was German for everyone, in Latin-1 bytes the font showed as "schlie?n beh?": STARTUP_TR below)
    'gpu/vk/vk_progress.h': [
        ('inline std::string left_text(double secs) {', STARTUP_TR_C + 'inline std::string left_text(double secs) {'),
        ('return "a few seconds left";', 'return ocr_tr("a few seconds left");'),
        ('snprintf(b, sizeof b, "about %d s left",', 'snprintf(b, sizeof b, ocr_tr("about %d s left"),'),
        ('snprintf(b, sizeof b, "about %d min left",', 'snprintf(b, sizeof b, ocr_tr("about %d min left"),'),
        ('v.title = "Closing";', 'v.title = ocr_tr("Closing");'),
        ('v.left = "Keeping what is prepared for the next start";', 'v.left = ocr_tr("Keeping what is prepared for the next start");'),
        ('v.title = "Starting the game";', 'v.title = ocr_tr("Starting the game");'),
        ('v.step = pipelines ? "STEP 2 OF 2" : "STEP 1 OF 2";', 'v.step = ocr_tr(pipelines ? "STEP 2 OF 2" : "STEP 1 OF 2");'),
        ('v.title = !pipelines ? "Preparing shaders" : s.prepared ? "Building pipelines" : "Loading pipelines";',
         'v.title = ocr_tr(!pipelines ? "Preparing shaders" : s.prepared ? "Building pipelines" : "Loading pipelines");'),
        ('v.hint = "This happens once after an update. Closing the window keeps what is done.";',
         'v.hint = ocr_tr("This happens once after an update. Closing the window keeps what is done.");'),
        ('v.left = !pipelines ? "Reading the game\'s shaders" : s.stage == 1 ? "Reading the pipeline notes" : "Loading the shader cache";',
         'v.left = ocr_tr(!pipelines ? "Reading the game\'s shaders" : s.stage == 1 ? "Reading the pipeline notes" : "Loading the shader cache");'),
        ('(pipelines ? " pipelines" : " shaders");', 'ocr_tr(pipelines ? " pipelines" : " shaders");')],
}

# Ocarina Reborn's own additions to the game, applied after REBRAND:
# - Enemy damage (Cheats page, x1 to x5): every hit on Link takes that many times the life. The place is Hookshot's own heart
#   protection hook (nx2/oot_patches.py patch_life: Link's life written by a compare-and-swap in f_804bd8c0); the new value
#   is computed by host/hos_main.c hos_oot_enemy_damage from the menu's choice (vk_menu.cpp, read through rx_option).
MODS = {
    'gpu/vk/vk_api.h': [
        ('enum { HOS_OPT_CHEAT_HEARTS = 32, HOS_OPT_CHEAT_FLIGHT, HOS_OPT_CHEAT_ACTION, HOS_OPT_CHEAT_CAMERA, HOS_OPT_CHEAT_SPEED };',
         'enum { HOS_OPT_CHEAT_HEARTS = 32, HOS_OPT_CHEAT_FLIGHT, HOS_OPT_CHEAT_ACTION, HOS_OPT_CHEAT_CAMERA, HOS_OPT_CHEAT_SPEED,\n'
         '       HOS_OPT_ENEMY_DAMAGE /* (Ocarina Reborn) */ };')],
    'gpu/vk/vk_menu.h': [
        ('int menu_heart_protection();', 'int menu_heart_protection();\nint menu_enemy_damage();   // (Ocarina Reborn) 1 to 5')],
    'gpu/vk/vk_menu.cpp': [
        ('std::atomic<int> protect_hearts{-1};',
         'std::atomic<int> protect_hearts{-1};\n'
         '// (Ocarina Reborn) the damage to Link, times 1 to 5. Starts at the launcher\'s Difficulty choice: it started at x1, and with\n'
         '// the Debug tools row on (saved in the options file, so on at every start) that x1 replaced the launcher\'s x5 (1.0.0)\n'
         'static int launcher_enemy_damage() { const char* e = getenv("OCARINA_ENEMY_DAMAGE"); return e ? std::clamp(atoi(e), 1, 5) : 1; }\n'
         'std::atomic<int> enemy_damage{launcher_enemy_damage()};'),
        ('    {TAB_DEBUG, "Developer", nullptr, 0, 0, 0, nullptr, nullptr, nullptr, false, true, -1, true},',
         '    {TAB_DEBUG, "Enemy damage", nullptr, 0, 0, 0, nullptr,   // (Ocarina Reborn: tool 12)\n'
         '     "Enemies hit Link this many times harder: x1 is the normal game, x5 the hardest. Choose with Left or Right.", nullptr,\n'
         '     false, true, 12},\n'
         '    {TAB_DEBUG, "Developer", nullptr, 0, 0, 0, nullptr, nullptr, nullptr, false, true, -1, true},'),
        ('constexpr int kCheatRows = 12;', 'constexpr int kCheatRows = 13;   // (Ocarina Reborn: + Enemy damage, 12)'),
        ('    case 11: return link_speed_names[std::clamp(link_speed.load(), 0, kLinkSpeeds - 1)];',
         '    case 11: return link_speed_names[std::clamp(link_speed.load(), 0, kLinkSpeeds - 1)];\n'
         '    case 12: return snprintf(t, sizeof t, "x%d", std::clamp(enemy_damage.load(), 1, 5)), t;'),
        ('bool cheat_chooses(int i) { return i == 4 || i == 5 || i == 6 || i == 11; }',
         'bool cheat_chooses(int i) { return i == 4 || i == 5 || i == 6 || i == 11 || i == 12; }'),
        ('constexpr int debug_tools_order[] = {0, 1, 11, 9, 10, 8, 2, 3, 7, 4};',
         'constexpr int debug_tools_order[] = {0, 1, 11, 12, 9, 10, 8, 2, 3, 7, 4};   // (Ocarina Reborn: Enemy damage with the Player\'s)'),
        ('constexpr DebugGroup debug_groups[] = {{"Player", 0, 5}, {"Travel", 5, 8}, {"Camera & world", 8, 10}};',
         'constexpr DebugGroup debug_groups[] = {{"Player", 0, 6}, {"Travel", 6, 9}, {"Camera & world", 9, 11}};'),
        ('    if (i == 11 && (press[3] || press[4])) {   // (Movement speed: stops at 1x and 3x)\n',
         '    if (i == 12 && (press[3] || press[4])) {   // (Ocarina Reborn) Enemy damage: stops at x1 and x5\n'
         '        enemy_damage.store(std::clamp(enemy_damage.load() + (press[4] ? 1 : -1), 1, 5));\n'
         '        changed = true;\n'
         '    }\n'
         '    if (i == 11 && (press[3] || press[4])) {   // (Movement speed: stops at 1x and 3x)\n'),
        ('int menu_free_camera() { return cheats_on() ? free_camera.load(std::memory_order_relaxed) : 0; }',
         'int menu_free_camera() { return cheats_on() ? free_camera.load(std::memory_order_relaxed) : 0; }\n'
         'int menu_enemy_damage() {   // (the debug tools\' choice with cheats on, which starts at the launcher\'s; else the launcher\'s)\n'
         '    static const int launcher = launcher_enemy_damage();\n'
         '    return cheats_on() ? std::clamp(enemy_damage.load(std::memory_order_relaxed), 1, 5) : launcher;\n'
         '}')],
    # The shader preparation's progress: the same per-mille again after 30 s while programs still complete. It was said only when
    # the per-mille changed (about 55 programs), and on an Intel Arc 140V some programs take 10 s each: 15 minutes passed without a
    # line, the builder took the preparation for hung and stopped it although it was working (a tester's build, 2026-11-11). A
    # preparation where no program completes for 15 minutes is still stopped
    'gpu/vk/vk_main.cpp': [
        ('            if (at == last) return;\n            last = at;\n            printf("@@progress %.3f\\n", at / 1000.0);\n',
         '            static auto said = std::chrono::steady_clock::now();\n'
         '            const auto now = std::chrono::steady_clock::now();\n'
         '            if (at == last && now - said < std::chrono::seconds(30)) return;   // (Ocarina Reborn: again after 30 s)\n'
         '            last = at, said = now;\n'
         '            printf("@@progress %.3f\\n", at / 1000.0);\n')],
    'gpu/vk/vk_replay.cpp': [
        ('if (id == HOS_OPT_CHEAT_CAMERA) return menu_free_camera();',
         'if (id == HOS_OPT_CHEAT_CAMERA) return menu_free_camera();\n        if (id == HOS_OPT_ENEMY_DAMAGE) return menu_enemy_damage();')],
    'host/hos_main.c': [
        ('    return menu < 0 ? hos_oot_protect_hearts : menu;\n}\n',
         '    return menu < 0 ? hos_oot_protect_hearts : menu;\n}\n\n'
         '/* (Ocarina Reborn) the Cheats page\'s Enemy damage: a hit that takes Link from before to after takes n times as much */\n'
         'uint64_t hos_oot_enemy_damage(uint32_t before, uint32_t after) {\n'
         '    int rx_option(int id, int otherwise);\n'
         '    const int n = rx_option(HOS_OPT_ENEMY_DAMAGE, 1);\n'
         '    if (n <= 1 || n > 5 || after >= before) return after;\n'
         '    const uint64_t hit = (uint64_t)(before - after) * (uint64_t)n;\n'
         '    return hit >= before ? 0 : before - hit;\n}\n\n'
         '/* (Ocarina Reborn) every change of Link\'s life through f_804bd8c0 (both ways): Enemy damage and the launcher\'s\n'
         '   One-hit mode (OCARINA_ONE_HIT=1: any hit empties the hearts) on a loss, and a log of the changes (the first 48 and\n'
         '   each that reaches 0): what heals, in what steps, and what a fairy does at 0, for the next gameplay modes */\n'
         'uint64_t hos_oot_life_change(uint32_t before, uint32_t after) {\n'
         '    static int one_hit = -1;   /* (read once: C has no run-time static initializers) */\n'
         '    if (one_hit < 0) one_hit = getenv("OCARINA_ONE_HIT") && atoi(getenv("OCARINA_ONE_HIT")) != 0;\n'
         '    uint32_t now = after;\n'
         '    if (after < before) now = one_hit ? 0 : (uint32_t)hos_oot_enemy_damage(before, after);\n'
         '    /* the Death counter row (vk_menu.cpp, OCR_OPT_DEATHS 4089). A bottled fairy revives through this same write,\n'
         '       0 -> 20 right after "hearts empty" (Pascal\'s fairy test, 2026-11-12); a real game over refills without it.\n'
         '       So 0 counts a death, and a raise from 0 takes it back: a fairy saved Link */\n'
         '    void rx_option_set(int id, int value);\n'
         '    static volatile LONG deaths;\n'
         '    if (now == 0 && before > 0)\n'
         '        rx_option_set(4089, (int)InterlockedIncrement(&deaths));\n'
         '    else if (before == 0 && now > 0 && deaths > 0)\n'
         '        rx_option_set(4089, (int)InterlockedDecrement(&deaths));\n'
         '    static volatile LONG said;\n'
         '    if (now != before && (InterlockedIncrement(&said) <= 48 || now == 0 || before == 0))\n'
         '        hos_log("[OcarinaReborn/LIFE] Link %u -> %u (the game asked %u)%s", before, now, after,\n'
         '                now == 0 ? (one_hit ? ": one-hit mode" : ": hearts empty") : before == 0 ? ": fairy revive" : "");\n'
         '    return now;\n}\n')],
    'nx2/oot_patches.py': [
        (r'''    guard = ("    if ((uint32_t)c->x[12] < (uint32_t)c->x[11] && hos_oot_hearts_enabled() &&\n"''',
         r'''    guard = ("    if ((uint32_t)c->x[12] != (uint32_t)c->x[11] && hos_oot_is_player(c, c->x[19]) &&\n"''' '\n'
         r'''             "        c->x[13] == recomp_load64(c,c->x[19] + 7184) + 8)\n"''' '\n'
         r'''             "        c->x[12] = hos_oot_life_change((uint32_t)c->x[11], (uint32_t)c->x[12]);   /* (Ocarina Reborn) */\n"''' '\n'
         r'''             "    if ((uint32_t)c->x[12] < (uint32_t)c->x[11] && hos_oot_hearts_enabled() &&\n"'''),
        (r"""'extern int hos_oot_is_player(Ctx *c, uint64_t actor);\n'""",
         r"""'extern int hos_oot_is_player(Ctx *c, uint64_t actor);\n'""" '\n'
         r"""        'extern uint64_t hos_oot_life_change(uint32_t before, uint32_t after);\n'""")],
}
# The in-game menu (Insert) in Ocarina Reborn's colours (the user's design, 2026-11-10): Hookshot's green-grey panel becomes
# night blue with a glowing blue frame, blue tabs and selection, blue-white text; gold and white stay. Only colours change.
MENU_COLOURS = {
    (16, 20, 18): (8, 16, 38), (96, 176, 112): (60, 140, 255), (104, 186, 124): (70, 150, 255), (44, 72, 54): (24, 70, 160),
    (30, 40, 34): (18, 30, 62), (196, 204, 198): (205, 214, 235), (176, 186, 180): (170, 184, 215),
    (140, 150, 144): (130, 145, 180), (236, 240, 236): (236, 240, 250), (210, 225, 215): (210, 220, 245),
    (110, 135, 120): (100, 125, 175), (96, 210, 120): (80, 170, 255), (72, 255, 110): (90, 190, 255),
    (70, 120, 84): (50, 100, 200), (60, 80, 68): (44, 62, 110), (6, 8, 6): (4, 8, 20), (52, 68, 58): (40, 56, 100),
    (52, 64, 56): (40, 52, 92), (38, 64, 48): (26, 54, 120), (30, 46, 37): (20, 36, 78), (226, 232, 226): (226, 232, 248),
    (22, 28, 25): (12, 22, 50), (215, 225, 218): (215, 224, 245), (150, 166, 156): (140, 160, 200),
    (135, 150, 142): (125, 145, 190)}
MENU_FRAME = ('    fill(dc, 0, 0, (int)w, 2 * s, RGB(60, 140, 255));\n',
              '    fill(dc, 0, 0, (int)w, 2 * s, RGB(60, 140, 255));   // (Ocarina Reborn: a glowing blue frame all round)\n'
              '    fill(dc, 0, (int)h - 2 * s, (int)w, 2 * s, RGB(60, 140, 255));\n'
              '    fill(dc, 0, 0, 2 * s, (int)h, RGB(60, 140, 255));\n'
              '    fill(dc, (int)w - 2 * s, 0, 2 * s, (int)h, RGB(60, 140, 255));\n'
              '    fill(dc, 2 * s, 2 * s, (int)w - 4 * s, 1 * s, RGB(30, 80, 170));\n')


HUD = Path(__file__).resolve().parent / 'hud'


def apply_hud(H):
    """the Ocarina Reborn HUD in the game's menu (hud/hud_paint.inc): the header with the Triforce, RESUME and X, Powered by
    Sorax and no version; the glowing frame; RESUME and X under the mouse; the HUD unfolding from its middle as it opens and
    folding as it closes"""
    f = H / 'gpu/vk/vk_menu.cpp'
    t = f.read_text(encoding='utf-8')

    def swap(old, new, count=1, regex=False):
        nonlocal t
        t2, n = (re.subn(old, lambda m: new, t, count=count, flags=re.S) if regex else (t.replace(old, new, count), t.count(old)))
        if not n:
            raise SystemExit(f'apply_hud: vk_menu.cpp no longer has {old[:80]!r} (Hookshot changed: update apply_hud)')
        t = t2
    swap('void paint_menu(HDC dc, uint32_t w, uint32_t h, int s) {\n', (HUD / 'hud_paint.inc').read_text(encoding='utf-8'))
    # the title and the build's version beside it: the HUD's header in their place (the version stays in the log's first line)
    swap(r'    TextOutA\(dc, 16 \* s, 12 \* s, heading, \(int\)strlen\(heading\)\);\n    \{   // \(which build.*?        DeleteObject\(small\);\n    \}\n',
         '    hud::header(dc, (int)w, s, page == 0 ? "OCARINA REBORN" : page == 1 ? "Controls" : heading, page == 0);\n', regex=True)
    swap('        TextOutA(dc, 16 * s + 110 * s, 12 * s + 4 * s, "Controls", 8);\n', '')   # (the header says it now)
    # RESUME and X: under the cursor lit, a click closes the HUD as Insert does (the restart question first, when it is due)
    swap('    // (closing with a setting that takes a restart changed: the restart question first, Later already chosen on it)\n',
         '    if (open_now.load() && page == 0 && mouse) {   // (Ocarina Reborn) the header\'s RESUME and X\n'
         '        const int b = hud::button_at(mx, my, mw, scale);\n'
         '        if (b != hud_hover) hud_hover = b, changed = true;\n'
         '        if (b >= 0 && (ptr.pressed & HOS_MOUSE_LEFT)) press[0] = true, ptr.pressed &= ~HOS_MOUSE_LEFT;\n'
         '    } else if (hud_hover >= 0) {\n'
         '        hud_hover = -1;\n'
         '    }\n'
         '    // (closing with a setting that takes a restart changed: the restart question first, Later already chosen on it)\n')
    # the copy: a band of the menu's rows from its middle, so it unfolds (180 ms, easing out) and folds away (120 ms)
    swap('void copy_over(VkCommandBuffer cmd, VkImage dst, Bitmap& b, Upload& u, int x, int y, uint32_t w, uint32_t h) {\n',
         'void copy_over(VkCommandBuffer cmd, VkImage dst, Bitmap& b, Upload& u, int x, int y, uint32_t w, uint32_t h,\n'
         '               uint32_t row0 = 0, uint32_t rows = 0) {\n')
    # (a menu taller than the picture was not copied at all: the check below returned, and F1 seemed to do nothing. Now
    # only the rows asked for need to fit)
    swap('    if (!b.w || (uint32_t)x + b.w > w || (uint32_t)y + b.h > h) return;\n',
         '    if (!b.w || (uint32_t)x + b.w > w || (uint32_t)y + (rows ? row0 + rows : b.h) > h) return;\n')
    swap('        menu_hit::origin((int)dev.swap_extent.width, (int)dev.swap_extent.height, mw, mh, &x0, &y0);\n',
         '        menu_hit::origin((int)dev.swap_extent.width, (int)dev.swap_extent.height, mw, mh, &x0, &y0);\n'
         '        if (mh > (int)dev.swap_extent.height) y0 = 0;   // (Ocarina Reborn: a menu taller than the picture sits at its top)\n')
    swap('    c.imageOffset = {x, y, 0};\n    c.imageExtent = {b.w, b.h, 1};\n',
         '    c.imageOffset = {x, y, 0};\n    c.imageExtent = {b.w, b.h, 1};\n'
         '    if (rows && row0 + rows <= b.h)   // (Ocarina Reborn: only those rows, where they are in the whole)\n'
         '        c.bufferOffset = (uint64_t)row0 * b.w * 4, c.imageOffset.y = y + (int)row0, c.imageExtent.height = rows;\n')
    swap('    if (open_now.load(std::memory_order_relaxed)) {\n        std::unique_lock lk(bmp_mu);\n        const uint32_t mw = menu_bmp.w, mh = menu_bmp.h;\n',
         '    static bool hud_was_open = false;   // (Ocarina Reborn) the HUD\'s opening and closing\n'
         '    static int64_t hud_since = 0;\n'
         '    const bool hud_open = open_now.load(std::memory_order_relaxed);\n'
         '    if (hud_open != hud_was_open) hud_was_open = hud_open, hud_since = prof_now();\n'
         '    const double hud_t = std::min(1.0, (double)(prof_now() - hud_since) / (hud_open ? 1.8e8 : 1.2e8));\n'
         '    const double hud_k = hud_open ? 1 - (1 - hud_t) * (1 - hud_t) * (1 - hud_t) : (1 - hud_t) * (1 - hud_t);\n'
         '    if (hud_open || hud_t < 1) {\n        std::unique_lock lk(bmp_mu);\n        const uint32_t mw = menu_bmp.w, mh = menu_bmp.h;\n')
    swap('        if (mw) copy_over(cmd, dst, menu_bmp, ups[0][slot], (int)(w - mw) / 2, (int)(h - mh) / 2, w, h);\n',
         '        const uint32_t vis = std::min(mh, h);   // (taller than the picture: its top part, from the picture\'s top)\n'
         '        const uint32_t band = hud_k >= 1 ? vis : std::min(vis, std::max(2u, (uint32_t)(vis * hud_k) & ~1u));\n'
         '        static uint32_t told_w, told_h, told_mh;\n'
         '        if (mw && hud_open && (told_w != w || told_h != h || told_mh != mh)) {\n'
         '            told_w = w, told_h = h, told_mh = mh;\n'
         '            logf("[OcarinaReborn/HUD] shown: menu %ux%u on a %ux%u picture%s", mw, mh, w, h, mh > h ? " (taller: its top part)" : "");\n'
         '        }\n'
         '        if (mw) copy_over(cmd, dst, menu_bmp, ups[0][slot], (int)(w - mw) / 2, mh > h ? 0 : (int)(h - mh) / 2, w, h,\n'
         '                          (vis - band) / 2, band);\n')
    f.write_text(t, encoding='utf-8', newline='')
    print('hud: header, frame, RESUME/X, open and close')


def patch_file(H, rel, swaps, what):
    """each (old, new) of swaps in H/rel once; a missing old stops the build (Hookshot changed: update that place)"""
    f = H / rel
    t = f.read_text(encoding='utf-8')
    for old, new in swaps:
        if old not in t:
            raise SystemExit(f'{what}: {rel} no longer has {old[:80]!r} (Hookshot changed: update {what})')
        t = t.replace(old, new, 1)
    f.write_text(t, encoding='utf-8', newline='')


# The F1 menu's Graphics tab: rows for what the renderer itself decides (the game's own effects, its shadows, fog, bloom, are
# its shaders, not settings). Each row is the renderer's real switch, read at the start (ocr_options.h):
#   Anisotropic filtering  sampler_make: maxAnisotropy for the linear, mipmapped samplers (was RX_VK_ANISO), up to the GPU's limit
#   Texture detail         sampler_make: the level-of-detail bias, 0 / -0.5 / -1
#   Texture filtering      sampler_make: the game's nearest samplers made linear (was RX_VK_FORCE_LINEAR)
#   Soft shadows           sampler_make: depth-compare samplers linear, 4-tap PCF (was RX_VK_SHADOW_PCF, on by default)
#   V-Sync                 create_swapchain: FIFO instead of mailbox/immediate (was RX_VK_FIFO)
GFX_ROWS = (
    '    {TAB_GRAPHICS, "Anisotropic filtering", &gfx_aniso, 0, 4, 1, tx_aniso,\n'
    '     "Sharper textures at steep angles: floors and paths into the distance. Low performance cost. Applies after a restart.",\n'
    '     nullptr, true, true},\n'
    '    {TAB_GRAPHICS, "Texture detail", &gfx_tex_detail, 0, 2, 1, tx_tex_detail,\n'
    '     "Finer texture levels further away. Ultra can shimmer on fine patterns. Applies after a restart.", nullptr, true, true},\n'
    '    {TAB_GRAPHICS, "Texture filtering", &gfx_smooth, 0, 1, 1, tx_smooth,\n'
    '     "Smooth: every texture filtered, no blocky halos in smoke, fog and glows. Applies after a restart.", nullptr, true, true},\n'
    '    {TAB_GRAPHICS, "Soft shadows", &gfx_soft_shadows, 0, 1, 1, tx_onoff,\n'
    '     "Shadow edges blended over four samples instead of hard steps. Applies after a restart.", nullptr, true, true},\n'
    '    {TAB_GRAPHICS, "VSync", &gfx_vsync, 0, 1, 1, tx_onoff,\n'
    '     "Frames wait for the display: no tearing, more input delay. Not with frame generation. Applies after a restart.", nullptr, true, true},\n'
    '    {TAB_GRAPHICS, "Texture memory", &gfx_tex_mem, 0, 6, 1, tx_tex_mem,\n'
    '     "Most video memory for textures. Higher keeps more in memory, fewer reloads; held under 3/4 of your card. Applies after a restart.",\n'
    '     nullptr, true, true},\n'
    '    {TAB_GRAPHICS, "Pipeline precompile", &gfx_precompile, 0, 1, 1, tx_onoff,\n'
    '     "Builds the pipelines the game used before, at the start: less stutter. Applies after a restart.", nullptr, true, true},\n'
    '    {TAB_GRAPHICS, "Shader cache", &gfx_shader_cache, 0, 1, 1, tx_onoff,\n'
    '     "Keeps compiled shaders on disk. Off compiles every shader again each start. Applies after a restart.", nullptr, true, true},\n'
    '    {TAB_GRAPHICS, "Shader threads", &gfx_threads, 0, 4, 1, tx_threads,\n'
    '     "CPU threads compiling shaders. More is faster, but can slow the game while it plays. Applies after a restart.",\n'
    '     nullptr, true, true},\n')
GFX_DECLS = (
    '// (Ocarina Reborn) the renderer\'s own graphics rows (ocr_options.h reads them where they are used)\n'
    'int gfx_aniso = 0, gfx_tex_detail = 0, gfx_smooth = 0, gfx_soft_shadows = 1, gfx_vsync = 0;\n'
    'int gfx_tex_mem = 0, gfx_precompile = 1, gfx_shader_cache = 1, gfx_threads = 0;\n'
    'const char* tx_tex_mem(int v) { static const char* t[] = {"Auto", "2 GB", "4 GB", "6 GB", "8 GB", "12 GB", "16 GB"}; return t[std::clamp(v, 0, 6)]; }\n'
    'const char* tx_threads(int v) { static const char* t[] = {"Auto", "2", "4", "6", "8"}; return t[std::clamp(v, 0, 4)]; }\n'
    'const char* tx_aniso(int v) { static const char* t[] = {"Off", "2x", "4x", "8x", "16x"}; return t[std::clamp(v, 0, 4)]; }\n'
    'const char* tx_tex_detail(int v) { static const char* t[] = {"Standard", "High", "Ultra"}; return t[std::clamp(v, 0, 2)]; }\n'
    'const char* tx_smooth(int v) { return v ? "Smooth" : "The game\'s"; }\n'
    'constexpr int kVisibleRows = 14;   // (a tab shows this many rows, and scrolls: the menu fits a 720-line picture)\n')


def apply_gfx(H):
    """the Graphics tab's renderer rows (GFX_ROWS), the renderer reading them, and the tab's list scrolling"""
    shutil.copy2(HUD / 'ocr_options.h', H / 'gpu/vk/ocr_options.h')
    patch_file(H, 'gpu/vk/vk_draw.cpp', [
        ('#include "vk_paths.h"\n', '#include "vk_paths.h"\n#include "ocr_options.h"\n'),
        ('    static const uint32_t n = getenv("RX_VK_ANISO") ? (uint32_t)std::clamp(atoi(getenv("RX_VK_ANISO")), 0, 16) : 0u;\n',
         '    static const uint32_t n = (uint32_t)std::clamp(ocr_anisotropy(), 0, 16);   // (Ocarina Reborn: the menu\'s row, or RX_VK_ANISO)\n'
         '    static const bool told = (logf("[OcarinaReborn/GFX] anisotropic filtering %ux (GPU limit %g), texture bias %g", n,\n'
         '                                   (double)dev.props.limits.maxSamplerAnisotropy, (double)ocr_texture_bias()), true);\n'
         '    (void)told;\n'),
        ('        static const bool force_linear = getenv("RX_VK_FORCE_LINEAR") != nullptr;\n',
         '        static const bool force_linear = getenv("RX_VK_FORCE_LINEAR") != nullptr || ocr_option(nullptr, "texture_filtering", 0) == 1;\n'),
        ('    ci.mipLodBias = std::clamp(p.lod_bias, ', '    ci.mipLodBias = std::clamp(p.lod_bias + ocr_texture_bias(), '),
        ('        static const bool pcf = !getenv("RX_VK_SHADOW_PCF") || atoi(getenv("RX_VK_SHADOW_PCF")) != 0;\n',
         '        static const bool pcf = ocr_option("RX_VK_SHADOW_PCF", "soft_shadows", 1) != 0;   // (Ocarina Reborn: the Soft shadows row)\n'),
        # Shader cache (the program cache on disk) and Shader precompile and Shader threads (the compile workers)
        ('    static const bool off = getenv("RX_VK_NO_PROGRAM_CACHE") != nullptr;\n', '    static const bool off = ocr_program_cache_off();\n'),
        ('    static const bool off = getenv("RX_VK_NO_PROGRAM_CACHE") != nullptr;\n', '    static const bool off = ocr_program_cache_off();\n'),
        ('    if (!getenv("RX_VK_NO_PROGRAM_CACHE")) {', '    if (!ocr_program_cache_off()) {'),
        ('    if (const char* e = getenv("RX_VK_PRECOMPILE")) on = atoi(e) != 0;\n',
         '    if (const char* e = getenv("RX_VK_PRECOMPILE")) on = atoi(e) != 0;\n'
         '    else on = ocr_option(nullptr, "pipeline_precompile", on ? 1 : 0) != 0;   // (Ocarina Reborn: the Pipeline precompile row)\n'),
        ('    for (unsigned i = 0; i < std::clamp(cpus / 2, 1u, 32u); i++) threads.emplace_back(worker);',
         '    for (unsigned i = 0; i < ocr_shader_workers(std::clamp(cpus / 2, 1u, 32u)); i++) threads.emplace_back(worker);'),
        ('    for (unsigned i = 0; i < std::clamp(cpus / 2, 1u, 32u); i++) threads.emplace_back(variant_worker);',
         '    for (unsigned i = 0; i < ocr_shader_workers(std::clamp(cpus / 2, 1u, 32u)); i++) threads.emplace_back(variant_worker);'),
        ('    const unsigned workers = background ? std::clamp(cpus / 4, 2u, 4u) : std::clamp(cpus / 2, 1u, 32u);',
         '    const unsigned workers = ocr_shader_workers(background ? std::clamp(cpus / 4, 2u, 4u) : std::clamp(cpus / 2, 1u, 32u));'),
        ('    for (unsigned i = 0; i < std::min(cpus, 64u); i++) threads.emplace_back(worker);',
         '    for (unsigned i = 0; i < ocr_shader_workers(std::min(cpus, 64u)); i++) threads.emplace_back(worker);'),
        ('    for (unsigned i = 0; i < std::clamp(cpus / 2, 1u, 32u); i++) threads.emplace_back(worker);',
         '    for (unsigned i = 0; i < ocr_shader_workers(std::clamp(cpus / 2, 1u, 32u)); i++) threads.emplace_back(worker);'),
    ], 'apply_gfx')
    patch_file(H, 'gpu/vk/vk_shader.cpp', [
        ('#include "shader_recompiler/ir_opt/passes.h"\n', '#include "shader_recompiler/ir_opt/passes.h"\n#include "ocr_options.h"\n'),
        ('        if (getenv("RX_VK_NO_PROGRAM_CACHE")) return;', '        if (ocr_program_cache_off()) return;   // (Ocarina Reborn: the Shader cache row)'),
    ], 'apply_gfx')
    # Texture memory: the texture cache's budget, kept under 3/4 of what the driver allows (the clamp below the change)
    patch_file(H, 'gpu/vk/vk_texture.cpp', [
        ('#include "vk_jobs.h"\n', '#include "vk_jobs.h"\n#include "ocr_options.h"\n'),
        ('    const bool preset_budget = opts.vram_mb > 0 && preset_caps_memory();   // (a smaller preset on a bigger card: the card\'s own)\n'
         '    uint64_t budget = preset_budget ? ((uint64_t)opts.vram_mb << 20) : own;\n',
         '    const int ocr_gb = ocr_texture_budget_gb();   // (Ocarina Reborn: the Texture memory row, Auto 0)\n'
         '    const bool preset_budget = ocr_gb > 0 || (opts.vram_mb > 0 && preset_caps_memory());   // (a smaller preset on a bigger card: the card\'s own)\n'
         '    uint64_t budget = ocr_gb > 0 ? ((uint64_t)ocr_gb << 30) : preset_budget ? ((uint64_t)opts.vram_mb << 20) : own;\n'
         '    {\n'
         '        static bool told;\n'
         '        if (!told && ocr_gb > 0) told = true, logf("[OcarinaReborn/GFX] texture memory %d GB (held under 3/4 of what the driver allows)", ocr_gb);\n'
         '    }\n'),
    ], 'apply_gfx')
    patch_file(H, 'gpu/vk/vk_main.cpp', [
        ('#include "vk_paths.h"\n', '#include "vk_paths.h"\n#include "ocr_options.h"\n'),
        ('    const bool force_fifo = getenv("RX_VK_FIFO") != nullptr;',
         '    const bool force_fifo = getenv("RX_VK_FIFO") != nullptr || ocr_option(nullptr, "vsync", 0) == 1;   // (Ocarina Reborn: VSync)'),
        ('    VkSwapchainCreateInfoKHR ci{VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR};\n',
         '    if (force_fifo && !getenv("RX_VK_FIFO")) {   // (Ocarina Reborn) VSync: relaxed where the driver has it, so a late frame\n'
         '        // shows at once instead of a whole refresh later: plain FIFO held a game under the display rate at half of it\n'
         '        for (auto m : modes)\n'
         '            if (m == VK_PRESENT_MODE_FIFO_RELAXED_KHR) mode = m;\n'
         '        logf("[OcarinaReborn/GFX] vsync on: %s", mode == VK_PRESENT_MODE_FIFO_RELAXED_KHR ? "fifo relaxed" : "fifo (no relaxed mode here)");\n'
         '    }\n'
         '    VkSwapchainCreateInfoKHR ci{VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR};\n'),
    ], 'apply_gfx')
    # HDR made testable: what the display offers (Windows' "Use HDR" on is what makes it list an HDR10 surface), and the output each
    # swapchain really has; the F1 menu's HDR row says when its choice is not active (no HDR10 surface: SDR is presented)
    patch_file(H, 'gpu/vk/vk_main.cpp', [
        ('    vkGetPhysicalDeviceSurfaceFormatsKHR(dev.physical, dev.surface, &n, formats.data());\n',
         '    vkGetPhysicalDeviceSurfaceFormatsKHR(dev.physical, dev.surface, &n, formats.data());\n'
         '    {   // (Ocarina Reborn) the surface formats, once: an HDR10 one is listed only while Windows HDR is on for this display\n'
         '        static bool listed;\n'
         '        if (!listed) {\n'
         '            listed = true;\n'
         '            std::string all;\n'
         '            bool hdr10 = false;\n'
         '            for (const auto& f : formats) {\n'
         '                char b[32];\n'
         '                snprintf(b, sizeof b, "%s%d/%d", all.empty() ? "" : ", ", (int)f.format, (int)f.colorSpace);\n'
         '                all += b;\n'
         '                hdr10 = hdr10 || f.colorSpace == VK_COLOR_SPACE_HDR10_ST2084_EXT;\n'
         '            }\n'
         '            logf("[HDR] surface formats (VkFormat/VkColorSpaceKHR): %s", all.c_str());\n'
         '            logf("[HDR] Windows HDR: %s", hdr10 ? "enabled (the display offers an HDR10 surface)"\n'
         '                                              : "off (no HDR10 surface: Use HDR is off, or the display has none)");\n'
         '        }\n'
         '    }\n'),
        ('    // mailbox when the driver has it (latest frame, no tear).',
         '    {   // (Ocarina Reborn) the output this swapchain has, said when it changes\n'
         '        static int said = -1;\n'
         '        const int now = dev.hdr ? 1 : 0;\n'
         '        if (said != now) {\n'
         '            said = now;\n'
         '            if (dev.hdr)\n'
         '                logf("[HDR] HDR output active: format %d, colour space HDR10 ST2084, paper white %d nits, peak %d nits", (int)fmt.format,\n'
         '                     opts.hdr_white, opts.hdr_peak);\n'
         '            else\n'
         '                logf("[HDR] output: SDR (format %d)%s", (int)fmt.format, opts.hdr ? ": HDR is chosen but the display offers no HDR10 surface" : "");\n'
         '        }\n'
         '    }\n'
         '    // mailbox when the driver has it (latest frame, no tear).'),
    ], 'apply_gfx')
    patch_file(H, 'gpu/vk/vk_menu.h', [
        ('int hdr_peak = 1000;', 'int hdr_peak = 1000;\n    int hdr_ui = 200;   /* (Ocarina Reborn) the overlays\' white in nits with HDR on */')],
        'apply_gfx')
    patch_file(H, 'gpu/vk/menu_restart.h', [
        ('constexpr int kMax = 8;', 'constexpr int kMax = 16;   // (Ocarina Reborn: + its Graphics rows)')], 'apply_gfx')
    f = H / 'gpu/vk/vk_menu.cpp'
    t = f.read_text(encoding='utf-8')

    def swap(old, new):
        nonlocal t
        if old not in t:
            raise SystemExit(f'apply_gfx: vk_menu.cpp no longer has {old[:80]!r} (Hookshot changed: update apply_gfx)')
        t = t.replace(old, new, 1)
    swap('Row rows[] = {\n', GFX_DECLS + 'Row rows[] = {\n')
    swap('void gdi_draw(Bitmap& out, uint32_t w, uint32_t h, void (*paint)(HDC, uint32_t, uint32_t, int), int scale) {\n',
         '// (Ocarina Reborn) the GDI overlays on an HDR10 swapchain: their sRGB pixels as PQ codes in A2B10G10R10, so the menu keeps\n'
         '// its own colours instead of being read as PQ. ui_nits is what white in the overlay is worth (the HDR UI brightness row)\n'
         'int hdr_ui_nits = 200;\n'
         'uint32_t srgb_to_pq10(uint8_t b8, uint8_t g8, uint8_t r8) {\n'
         '    auto lin = [](uint8_t v) {\n'
         '        const double c = v / 255.0;\n'
         '        return c <= 0.04045 ? c / 12.92 : std::pow((c + 0.055) / 1.055, 2.4);\n'
         '    };\n'
         '    const double r = lin(r8), g = lin(g8), b = lin(b8);\n'
         '    // Rec. 709 -> Rec. 2020 (the HDR10 primaries), then white at the UI\'s nits on PQ\'s 10000 nit scale\n'
         '    const double k = std::clamp(hdr_ui_nits, 80, 1000) / 10000.0;\n'
         '    const double c2020[3] = {(0.6274 * r + 0.3293 * g + 0.0433 * b) * k,\n'
         '                             (0.0691 * r + 0.9195 * g + 0.0114 * b) * k,\n'
         '                             (0.0164 * r + 0.0880 * g + 0.8956 * b) * k};\n'
         '    auto pq = [](double y) {\n'
         '        const double m1 = 0.1593017578125, m2 = 78.84375, c1 = 0.8359375, c2 = 18.8515625, c3 = 18.6875;\n'
         '        const double yp = std::pow(std::max(0.0, std::min(1.0, y)), m1);\n'
         '        return std::pow((c1 + c2 * yp) / (1.0 + c3 * yp), m2);\n'
         '    };\n'
         '    const uint32_t R = (uint32_t)std::lround(pq(c2020[0]) * 1023.0), G = (uint32_t)std::lround(pq(c2020[1]) * 1023.0),\n'
         '                   B = (uint32_t)std::lround(pq(c2020[2]) * 1023.0);\n'
         '    return (3u << 30) | (B << 20) | (G << 10) | R;   // (A2B10G10R10_UNORM_PACK32: alpha, then B, G, R)\n'
         '}\n'
         'void gdi_draw(Bitmap& out, uint32_t w, uint32_t h, void (*paint)(HDC, uint32_t, uint32_t, int), int scale) {\n')
    # the finished bitmap: PQ codes for an HDR10 swapchain, the plain bytes otherwise (the swap below is the SDR one)
    swap('    for (size_t i = 0; i < out.px.size(); i += 4) {\n'
         '        if (rgba) std::swap(out.px[i], out.px[i + 2]);\n'
         '        out.px[i + 3] = 255;\n'
         '    }\n',
         '    if (dev.hdr) {   // (Ocarina Reborn) HDR10: every pixel converted once here, the copy stays a plain one\n'
         '        static std::unordered_map<uint32_t, uint32_t> cache;   // (the overlays use few colours: each converted once)\n'
         '        for (size_t i = 0; i < out.px.size(); i += 4) {\n'
         '            const uint32_t key = (uint32_t)out.px[i] | (uint32_t)out.px[i + 1] << 8 | (uint32_t)out.px[i + 2] << 16;\n'
         '            auto it = cache.find(key);\n'
         '            if (it == cache.end()) it = cache.emplace(key, srgb_to_pq10(out.px[i], out.px[i + 1], out.px[i + 2])).first;\n'
         '            std::memcpy(out.px.data() + i, &it->second, 4);\n'
         '        }\n'
         '    } else {\n'
         '        for (size_t i = 0; i < out.px.size(); i += 4) {\n'
         '            if (rgba) std::swap(out.px[i], out.px[i + 2]);\n'
         '            out.px[i + 3] = 255;\n'
         '        }\n'
         '    }\n')
    # the overlays are drawn again when HDR comes or goes, and when the UI brightness changes
    swap('    bool changed = scale != cur_scale || menu_refresh;\n',
         '    static bool hdr_was = false;\n'
         '    static int ui_nits_was = -1;\n'
         '    hdr_ui_nits = opts.hdr_ui;\n'
         '    bool changed = scale != cur_scale || menu_refresh || hdr_was != dev.hdr || ui_nits_was != opts.hdr_ui;\n'
         '    hdr_was = dev.hdr, ui_nits_was = opts.hdr_ui;\n')

    swap('    {TAB_GRAPHICS, "HDR peak brightness"',
         '    {TAB_GRAPHICS, "HDR UI brightness", &opts.hdr_ui, 100, 300, 20, tx_nits,\n'
         '     "How bright the F1 menu and the FPS counter are with HDR on. Lower if they glare; 200 suits most displays.",\n'
         '     nullptr, false, true},\n'
         '    {TAB_GRAPHICS, "HDR peak brightness"')

    # the HDR row: its choice, and "inactive" while the swapchain is SDR (Windows HDR off: no HDR10 surface)
    swap('const char* tx_hdr(int v) { return v == 1 ? "Expanded" : v == 2 ? "Native (the game\'s)" : "Off"; }',
         'const char* tx_hdr(int v) {   // (Ocarina Reborn: what the swapchain really is)\n'
         '    if (v && dev.swap_extent.width && !dev.hdr) return v == 1 ? "Expanded (inactive: Windows HDR off)" : "Native (inactive: Windows HDR off)";\n'
         '    return v == 1 ? "Expanded" : v == 2 ? "Native (the game\'s)" : "Off";\n'
         '}')
    swap('    {TAB_GRAPHICS, "Handheld profile"', GFX_ROWS + '    {TAB_GRAPHICS, "Handheld profile"')
    swap('int tab_selected[TAB_COUNT + 1] = {0, 0, 0, 0, 0};',
         'int tab_selected[TAB_COUNT + 1] = {0, 0, 0, 0, 0};\nint tab_scroll[TAB_COUNT + 1] = {};   // (Ocarina Reborn) the first row a tab shows')
    swap('int max_tab_rows() {\n    int most = 0;\n    for (int t = 0; t < TAB_COUNT; t++) most = std::max(most, tab_row_count(t));\n    return most;\n}\n',
         'int max_tab_rows() {\n    int most = 0;\n    for (int t = 0; t < TAB_COUNT; t++) most = std::max(most, tab_row_count(t));\n    return most;\n}\n'
         '/// (Ocarina Reborn) the rows the tabs show at once: the longest tab\'s, kVisibleRows at most (the rest scrolls)\n'
         'int visible_rows() { return std::min(max_tab_rows(), kVisibleRows); }\n')
    # the list: the rows from tab_scroll on, kVisibleRows of them; the mouse's arrays by their place in it
    head = ('    for (int i = 0; i < tab_count; i++) {\n        const Row& r = rows[tab_row_to_global(cur_tab, i)];\n'
            '        const int y = top + i * rh;\n')
    start = t.find(head)
    end = t.find('    const int help_top = top + max_tab_rows() * rh + 8 * s;', start)
    if start < 0 or end < 0:
        raise SystemExit('apply_gfx: the options list moved (Hookshot changed: update apply_gfx)')
    body = t[start + len(head):end]
    body = body.replace('row_value_l[i]', 'row_value_l[at]').replace('row_slider[i]', 'row_slider[at]')
    t = (t[:start] +
         '    const int first = tab_scroll[cur_tab], last = std::min(tab_count, first + kVisibleRows);\n'
         '    for (int i = first; i < last; i++) {\n        const int at = i - first;   // (Ocarina Reborn: its place in the shown list)\n'
         '        const Row& r = rows[tab_row_to_global(cur_tab, i)];\n        const int y = top + at * rh;\n' + body +
         '    if (first > 0) hud::arrow(dc, (int)w - 12 * s, top - 7 * s, true, s);   // (more above)\n'
         '    if (last < tab_count) hud::arrow(dc, (int)w - 12 * s, top + kVisibleRows * rh + 2 * s, false, s);   // (more below)\n'
         + t[end:])
    swap('    const int help_top = top + max_tab_rows() * rh + 8 * s;', '    const int help_top = top + visible_rows() * rh + 8 * s;')
    swap('(44 + 32 + 8 + max_tab_rows() * 28 + 8 + 10 + 30 + 6) * s', '(44 + 32 + 8 + visible_rows() * 28 + 8 + 10 + 30 + 6) * s')
    swap('            const menu_hit::Hit hit = menu_hit::options(mx, my, scale, mw, mh, TAB_COUNT, count, row_value_l, row_slider);\n',
         '            menu_hit::Hit hit = menu_hit::options(mx, my, scale, mw, mh, TAB_COUNT, std::min(count - tab_scroll[cur_tab], kVisibleRows),\n'
         '                                                  row_value_l, row_slider);\n'
         '            if (hit.part == menu_hit::kRow || hit.part == menu_hit::kSlider) hit.index += tab_scroll[cur_tab];   // (Ocarina Reborn)\n')
    swap('        if (press[2]) selected = (selected + 1) % tab_count, changed = true;\n',
         '        if (press[2]) selected = (selected + 1) % tab_count, changed = true;\n'
         '        {   // (Ocarina Reborn) the shown list follows the selection\n'
         '            int& sc = tab_scroll[cur_tab];\n'
         '            const int before = sc;\n'
         '            if (selected < sc) sc = selected;\n'
         '            if (selected >= sc + kVisibleRows) sc = selected - kVisibleRows + 1;\n'
         '            sc = std::max(0, std::min(sc, tab_count - kVisibleRows));\n'
         '            if (sc != before) changed = true;\n'
         '        }\n')
    f.write_text(t, encoding='utf-8', newline='')
    print('gfx: anisotropic filtering, texture detail, texture filtering, soft shadows, vsync; scrolling tabs')


def recolour_menu(H):
    f = H / 'gpu/vk/vk_menu.cpp'
    t = f.read_text(encoding='utf-8')
    n = 0
    for old, new in MENU_COLOURS.items():
        a, b = 'RGB(%d, %d, %d)' % old, 'RGB(%d, %d, %d)' % new
        n += t.count(a)
        t = t.replace(a, b)
    if MENU_FRAME[0] not in t:
        raise SystemExit('recolour_menu: the menu background line moved (Hookshot changed: update MENU_FRAME)')
    t = t.replace(MENU_FRAME[0], MENU_FRAME[1], 1)
    f.write_text(t, encoding='utf-8', newline='')
    print(f'menu: {n} colours changed')


LOGO = Path(__file__).resolve().parent / 'startup-logo.png'   # the Ocarina Reborn logo on transparency, 912 px wide


# The files the build makes and the game keeps (hookshot.exe, hookshot_vk.dll, hookshot_log.txt, hookshot_options.ini,
# .hookshot_exefs, ...): every lowercase "hookshot" that starts such a name, in the build scripts and the game's source alike,
# becomes "ocarina_reborn", and the tools' own files of those names are renamed with them. Upper case (the HOOKSHOT_* switches)
# and "Hookshot" (the item, Item_Hookshot) are left alone. Comments change too, which is harmless.
# Source checks include the same renamed headers and cache filenames as the engine.
RENAME_IN = ('host', 'gpu', 'nx2', 'scripts', 'tests', 'third_party/a64-kit')
RENAME_EXT = ('.c', '.h', '.cpp', '.hpp', '.inc', '.py', '.rc', '.txt', '.json', '.ps1', '.sh')
RENAME_RE = re.compile(r'(?<![A-Za-z0-9])hookshot(?=[_.\-"\\/ ]|$)')


def rename_files(H):
    n_files = n_subs = 0
    for top in RENAME_IN:
        for f in (H / top).rglob('*'):
            if not f.is_file() or f.suffix.lower() not in RENAME_EXT:
                continue
            try:
                t = f.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                continue
            new, k = RENAME_RE.subn('ocarina_reborn', t)
            # (a copy of a fixed length counted for the old, shorter name: "hookshot_log.txt", 17 cut the new name short and
            # left it unterminated: the log went to "ocarina_reborn_lo" + a stray byte. The length now follows the name)
            new = re.sub(r'(memcpy\([^;]*?"(ocarina_reborn[^"]*)"), \d+\)', lambda m: f'{m.group(1)}, sizeof "{m.group(2)}")', new)
            if k:
                f.write_text(new, encoding='utf-8', newline='')
                n_files += 1
                n_subs += k
    for f in list(H.rglob('*hookshot*')):   # (work/hookshot.ico, .res, _pieces.prof; assets/hookshot.png)
        if f.is_file() and '__pycache__' not in f.parts:
            f.rename(f.with_name(f.name.replace('hookshot', 'ocarina_reborn')))
    print(f'rename: {n_subs} names in {n_files} files')
    if n_subs < 100:
        raise SystemExit('rename: fewer names than expected; Hookshot changed (check RENAME_RE)')


ENGINE_FIXES = Path(__file__).resolve().parent / 'engine-fixes.patch'


def apply_engine_fixes(H):
    """the bug fixes and options taken from later Hookshot work onto the pinned v2.0.12 engine, one by one (engine-fixes.patch:
    #1730 #1552 #1627 #1776 #1765 #1731 #1568 #1754, the AMD pipeline retry of #1747, AMD Anti-Lag 2 of #1729 in our own
    menu). Before the rebrand: its places are the engine's own text. Nothing of Hookshot's newer menu or name comes with them"""
    import os
    import subprocess
    # (the stage is inside this repository: git apply took the paths as the repository's and left every one out, silently.
    # With the folders above H out of git's search it patches H itself)
    env = dict(os.environ, GIT_CEILING_DIRECTORIES=str(Path(H).resolve().parent))
    r = subprocess.run(['git', 'apply', '-p1', '--whitespace=nowarn', str(ENGINE_FIXES)], cwd=str(H), capture_output=True,
                       text=True, env=env)
    if r.returncode:
        raise SystemExit('engine fixes did not apply: ' + r.stderr[:400])
    # (applied for real: a file the patch adds, and a line it puts in)
    if not (H / 'gpu/vk/vk_antilag.cpp').is_file() or             'recovered with optimization disabled' not in (H / 'gpu/vk/vk_draw.cpp').read_text(encoding='utf-8'):
        raise SystemExit('engine fixes: git apply said yes, but the engine is unchanged')
    print(f'engine fixes: {sum(1 for l in ENGINE_FIXES.read_text(encoding="utf-8").splitlines() if l.startswith("diff --git"))} files, checked')


def rebrand(H, icon):
    import subprocess
    for rel, pairs in list(REBRAND.items()) + list(MODS.items()):
        f = H / rel
        t = f.read_text(encoding='utf-8')
        for old, new in pairs:
            if old not in t:
                raise SystemExit(f'rebrand: {rel} no longer has {old!r} (Hookshot changed: update REBRAND)')
            t = t.replace(old, new)
        f.write_text(t, encoding='utf-8', newline='')
    (H / 'assets').mkdir(exist_ok=True)
    shutil.copy2(LOGO, H / 'assets' / 'hookshot.png')   # nx2/logo_rgba.py reads the start-up logo from here
    # make_icon.py needs Pillow, which Hookshot's own Python lacks: a developer Python that has it (PILLOW_PYTHON)
    import os
    py = os.environ.get('PILLOW_PYTHON', sys.executable)
    r = subprocess.run([py, '-I', str(H / 'nx2/make_icon.py'), str(icon), str(H / 'work')],
                       capture_output=True, text=True)
    if r.returncode:
        raise SystemExit('rebrand: make_icon.py failed: ' + r.stdout + r.stderr)
    import hud_v21
    import engine_v21
    engine_v21.apply_light_tables(H)
    hud_v21.apply(H)
    engine_v21.apply_gfx(H)
    engine_v21.apply_perf(H)
    engine_v21.apply_mem(H)
    engine_v21.apply_look(H)
    engine_v21.apply_timer(H)
    engine_v21.apply_dynres(H)
    engine_v21.apply_view(H)
    engine_v21.apply_counters(H)
    import engine_tunic
    engine_tunic.apply(H)
    rename_files(H)
    (H / 'NOTICE-OCARINA-REBORN.txt').write_text(
        'Ocarina Reborn builds the game with Hookshot (https://github.com/NotRexed/Hookshot), GPL-3.0 (LICENSE).\n'
        'Changes: the window title, message boxes, menu heading, icon and start-up screen say Ocarina Reborn, the files the build\n'
        'makes are named ocarina_reborn* instead of hookshot*, and the Cheats page has Enemy damage (tools/alpha/stage_alpha.py).\n'
        'Where the view distances sit in the game\'s memory (host/ocr_view.c) was found by hotoni (Graphics-Menu mod).\n'
        'Per-light shadow map fix: YakuzaFanA / Hookshot PR #3047, commit 9c75b3214262844b644c0a8cdbbe9b2bde590ace.\n'
        'https://github.com/NotRexed/Hookshot/pull/3047 (upstream patch and license headers preserved).\n'
        'The Hookshot copyright and license notices are kept as the GPL requires.\n')


# SDL for every controller that is not an Xbox pad (PlayStation, Switch Pro, Steam Controller ...): nx2/build.py copies
# third_party/sdl2/SDL2.dll (sdl2-compat) and SDL3.dll beside the game only when they are there, and Hookshot's tools folder
# as pinned here has their LICENSE and VERSION but not the DLLs. A game folder built fresh had none: "sdl: no SDL3 or SDL2
# found", only XInput pads, and a player with another controller stuck on the title screen (debug package 2026-11-11 22:24,
# RTX 5060 Ti). Older game folders kept the DLLs of earlier builders, which hid it. The versions VERSION.txt names, checked
SDL_RUNTIME = ROOT / 'build/alpha/sdl-2.32.74-3.4.20'
SDL_SHA256 = {'SDL2.dll': '60cc728ebfd0915c94760916cb26c240bd152361b13b3692154ac5794be91ebf',   # sdl2-compat 2.32.74 win32-x64
              'SDL3.dll': '66844f10251cc1c10619ed5d8e4e3224f564900ee6d69ba87d63de782addae40'}   # SDL 3.4.20 win32-x64


def sdl_runtime(E):
    import hashlib
    dst = E / 'third_party/sdl2'
    dst.mkdir(parents=True, exist_ok=True)
    for name, sha in SDL_SHA256.items():
        src = SDL_RUNTIME / name
        if not src.is_file() or hashlib.sha256(src.read_bytes()).hexdigest() != sha:
            raise SystemExit(f'SDL runtime: {src} is missing or not the pinned build (controllers other than Xbox pads would not work)')
        shutil.copy2(src, dst / name)
    print('SDL runtime: SDL2.dll (sdl2-compat 2.32.74) and SDL3.dll (3.4.20) for the game folder')


PROMPT_IMPORTS = ('fontTools', 'PIL', 'astc_encoder', 'archspec', 'texture2ddecoder')


def prompt_packages(E):
    """nx2/prompt_assets.py draws the PlayStation/Xbox prompts (ocarina notes, button letters) with these; without them the
    build still succeeds but keeps the Switch's icons. ocarina_prepare.py runs make_game.py with engine/python/python.exe -I
    (3.14), not the launcher's Python, so they belong in ITS site-packages. Until 1.0.0 they went into the launcher's
    Python and the engine's lacked archspec (astc-encoder-py's dependency): 'no astc_encoder' in build.log.
    Missing ones are fetched as wheels for that interpreter (pip has no pip of its own there), then all are imported with
    exactly that interpreter; a failure stops the build."""
    py = E / 'python/python.exe'
    sp = E / 'python/Lib/site-packages'
    ver = subprocess.run([str(py), '-I', '-c', 'import sys; print("%d.%d" % sys.version_info[:2])'],
                         capture_output=True, text=True, check=True).stdout.strip()
    req = E / 'nx2/prompt_requirements.txt'
    pkgs = [l.split('#')[0].strip() for l in req.read_text().splitlines() if l.split('#')[0].strip()]
    norm = lambda n, v: n.lower().replace('_', '-') + '==' + v
    have = {norm(*p.name.removesuffix('.dist-info').rsplit('-', 1)) for p in sp.glob('*.dist-info') if '-' in p.name}
    missing = [p for p in pkgs if norm(*p.split('==', 1)) not in have]
    if missing:
        r = subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--no-deps', '--only-binary=:all:',
                            '--python-version', ver, '--implementation', 'cp', '--platform', 'win_amd64',
                            '--target', str(sp), *missing], capture_output=True, text=True)
        if r.returncode:
            raise SystemExit('prompt packages: pip failed: ' + r.stdout + r.stderr)
        print('prompt packages added to the engine Python', ver + ':', ', '.join(missing))
    r = subprocess.run([str(py), '-I', '-c', 'import ' + ', '.join(PROMPT_IMPORTS)], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit('prompt packages: the engine Python cannot import them (the game would keep the Switch icons):\n'
                         + r.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--hookshot', type=Path, required=True, help="Hookshot Builder's tools folder")
    ap.add_argument('--server', default='', help='activation server base URL; empty for offline activation (PC-ID -> license.dat)')
    ap.add_argument('--commit', default='unknown')
    a = ap.parse_args()
    W, O = a.work.resolve(), a.out.resolve()
    O.mkdir(parents=True, exist_ok=True)
    # Old output directories can retain files that copytree no longer supplies.
    for rel in ('data/voices/OOT_YoungLink.zip', 'data/voices/OOT_AdultLink.zip',
                'launcher/assets/music.wav', 'launcher/assets/music.mp3', 'launcher/assets/fairy.bin',
                'engine/docs/images/linux-builder-newer-game.png',
                'engine/docs/images/setup-runtime-incomplete.png',
                'engine/docs/images/windows-portable-folders.png'):
        stale = (O / rel).resolve()
        if not stale.is_relative_to(O):
            raise SystemExit('Output path escaped the stage')
        stale.unlink(missing_ok=True)
    base = Path(sys.base_prefix)
    copy(base, O / 'python', shutil.ignore_patterns('site-packages', '__pycache__', 'test', 'Doc', 'Scripts',
                                                     'Tools', 'idlelib', 'turtledemo', 'include', 'libs'))
    sp = O / 'python/Lib/site-packages'
    sp.mkdir(parents=True, exist_ok=True)
    vsp = W / 'venv/Lib/site-packages'
    for name in ('numpy', 'numpy.libs', 'lz4', 'zstandard'):
        copy(vsp / name, sp / name, shutil.ignore_patterns('__pycache__', 'tests'))
    for f in vsp.glob('zbic*.pyd'):   # nxnative/nso_reader.py: the ZBIC (zstd) segments of the game's NSOs
        shutil.copy2(f, sp / f.name)
    # the game backend: Hookshot's build tools as its builder installs them (GPL-3.0; source, LICENSE and toolchain)
    for old in ('llvm', 'deps', 'bin', 'src', 'game-files'):
        if (O / old).exists():
            shutil.rmtree(O / old)
    if (O / 'hookshot').exists():   # (the folder's name before 2026-11-10)
        shutil.rmtree(O / 'hookshot')
    copy(a.hookshot, O / 'engine', shutil.ignore_patterns('emsdk', '__pycache__'))
    shutil.copy2(a.hookshot.parent / 'LICENSE', O / 'engine' / 'LICENSE')
    rebrand(O / 'engine', ROOT / 'tools/alpha/ocarina-icon.png')
    sdl_runtime(O / 'engine')
    prompt_packages(O / 'engine')
    copy(ROOT / 'tools/alpha/data', O / 'data')
    # AMD FSR 4's runtime (FidelityFX SDK v2.4.0, Kits/FidelityFX/signedbin: AMD-signed, redistributable in binary form with
    # its license, LICENSE.md beside them). The game finds them through RX_VK_FSR_DIR, which the launcher sets
    fsr = ROOT / 'build/alpha/amd-fsr4-v2.4.0'
    for f in ('amd_fidelityfx_loader_vk.dll', 'amd_fidelityfx_upscaler_vk.dll', 'LICENSE.md'):
        if not (fsr / f).is_file():
            raise SystemExit(f'AMD FSR 4 is missing {f} in {fsr}')
    copy(fsr, O / 'amd-fsr4')
    shutil.copy2(ROOT / 'tools/alpha/ocarina_prepare.py', O / 'ocarina_prepare.py')
    A = ROOT / 'tools/alpha'
    shutil.copy2(A / 'CREDITS.txt', O / 'CREDITS.txt')
    copy(A / 'launcher', O / 'launcher', shutil.ignore_patterns('__pycache__'))
    shutil.copy2(A / 'exe/OcarinaReborn.exe', O / 'OcarinaReborn.exe')
    shutil.copy2(A / 'OcarinaReborn.ico', O / 'OcarinaReborn.ico')
    shutil.copy2(A / 'licensing-server/keys/public.hex', O / 'data/license-public.hex')   # the PUBLIC key only
    (O / 'data/activation-server.txt').write_text(a.server)
    import json
    (O / 'build-info.json').write_text(json.dumps(dict(name='Ocarina Reborn', version=(A / 'VERSION').read_text().strip(),
        build_id='ocarina-reborn-alpha-001', commit=a.commit, platform='windows-x64', release_type='public',
        stamp=time.strftime('%Y%m%d-%H%M%S')),   # (each installer its own: the launcher offers an update when it changes)
        indent=2))
    secret = (A / 'licensing-server/keys/signing.key').read_text().strip().encode()
    leaked = [p for p in O.rglob('*') if p.is_file() and p.stat().st_size < 50e6 and secret in p.read_bytes()]
    if leaked or any(O.rglob('signing.key')):
        raise SystemExit(f'the private signing key is in the stage: {leaked[:3]}')
    # nothing game-derived: generated files carry this marker
    sys.path.insert(0, str(ROOT / 'third_party/dkb/tools'))
    from check_content import GENERATED_MARKER
    bad = [p for p in O.rglob('*') if p.is_file() and p.suffix in ('.c', '.h', '.json', '.bin') and p.stat().st_size < 50e6
           and GENERATED_MARKER.encode() in p.read_bytes()]
    if bad:
        raise SystemExit(f'game-derived files in the stage: {bad[:5]}')
    from distribution_guard import check as check_distribution
    media = json.loads((A / 'MEDIA-PROVENANCE.json').read_text(encoding='utf-8'))
    for rel in media['files']:
        if rel.startswith('engine/') and (O / rel).parent.is_dir():
            shutil.copy2(ROOT / rel, O / rel)
    check_distribution(O)
    print('staged', O)


if __name__ == '__main__':
    main()
