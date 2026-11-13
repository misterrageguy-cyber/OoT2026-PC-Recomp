"""Ocarina Reborn's renderer rows on the v2.1.0 engine: what each does is the renderer's own switch, read once at the start
(hud/ocr_options.h reads the options file the menu saves). The engine has its own Anisotropic filtering row (16x by default) and
upscaler LOD bias; these add to it:
  Texture detail       sampler_make: the LOD bias -0, -0.5, -1 more (after the upscalers' own)
  Texture filtering    sampler_make: the game's nearest samplers linear (RX_VK_FORCE_LINEAR)
  Soft shadows         sampler_make: the depth-compare samplers linear, 4-tap PCF (RX_VK_SHADOW_PCF; on by default)
  VSync                create_swapchain: FIFO, relaxed where the driver has it (a late frame shows at once, no halving)
  Texture memory       the texture cache's budget, held under 3/4 of what the driver allows
  Pipeline precompile  the prewarm of every pipeline play used before (RX_VK_PRECOMPILE)
  Shader cache         the compiled programs kept on disk (RX_VK_NO_PROGRAM_CACHE)
  Shader threads       the compile workers (Auto, 2 to 8; never past the CPU's threads less one)
and the HDR log lines ([HDR] ...), and the HDR row saying when its choice is not active (Windows' HDR off).
"""
import shutil
from pathlib import Path

HUD = Path(__file__).resolve().parent / 'hud'

GFX_DECLS = (
    '// (Ocarina Reborn) the renderer\'s own graphics rows (ocr_options.h reads them where they are used)\n'
    'int gfx_tex_detail = 1, gfx_smooth = 0, gfx_soft_shadows = 1, gfx_vsync = 0;\n'
    'int gfx_tex_mem = 0, gfx_precompile = 1, gfx_shader_cache = 1, gfx_threads = 0;\n'
    'int gfx_tex_saving = 0;\n'
    'const char* tx_tex_saving(int v) { static const char* t[] = {"Off", "1024 (test)", "512 (test)"}; return t[std::clamp(v, 0, 2)]; }\n'
    'const char* tx_tex_detail(int v) { static const char* t[] = {"Standard", "High", "Ultra"}; return t[std::clamp(v, 0, 2)]; }\n'
    'const char* tx_smooth(int v) { return v ? "Smooth" : "The game\'s"; }\n'
    'const char* tx_tex_mem(int v) { static const char* t[] = {"Auto", "2 GB", "4 GB", "6 GB", "8 GB", "12 GB", "16 GB"}; return t[std::clamp(v, 0, 6)]; }\n'
    'const char* tx_threads(int v) { static const char* t[] = {"Auto", "2", "4", "6", "8"}; return t[std::clamp(v, 0, 4)]; }\n')

GFX_ROWS = (
    '    {TAB_GRAPHICS, "Texture saving", &gfx_tex_saving, 0, 2, 1, tx_tex_saving,\n'
    '     "Experimental: stores large coarse ASTC texture arrays at a smaller size. Softer terrain; other textures stay unchanged. Off restores the original policy. Restart required.", nullptr, true, true},\n'
    '    {TAB_GRAPHICS, "Texture detail", &gfx_tex_detail, 0, 2, 1, tx_tex_detail,\n'
    '     "Finer texture levels further away. Ultra can shimmer on fine patterns. Applies after a restart.", nullptr, true, true},\n'
    '    {TAB_GRAPHICS, "Texture filtering", &gfx_smooth, 0, 1, 1, tx_smooth,\n'
    '     "Smooth: every texture filtered, no blocky halos in smoke, fog and glows. Applies after a restart.", nullptr, true, true},\n'
    '    {TAB_GRAPHICS, "Soft shadows", &gfx_soft_shadows, 0, 1, 1, tx_onoff,\n'
    '     "Shadow edges blended over four samples instead of hard steps. Applies after a restart.", nullptr, true, true},\n'
    '    {TAB_GRAPHICS, "Texture memory", &gfx_tex_mem, 0, 6, 1, tx_tex_mem,\n'
    '     "Most video memory for textures. Higher keeps more in memory, fewer reloads; held under 3/4 of your card. Applies after a "\n'
    '     "restart.", nullptr, true, true},\n'
    '    {TAB_GRAPHICS, "Pipeline precompile", &gfx_precompile, 0, 1, 1, tx_onoff,\n'
    '     "Builds the pipelines the game used before, at the start: less stutter. Applies after a restart.", nullptr, true, true},\n'
    '    {TAB_GRAPHICS, "Shader cache", &gfx_shader_cache, 0, 1, 1, tx_onoff,\n'
    '     "Keeps compiled shaders on disk. Off compiles every shader again each start. Applies after a restart.", nullptr, true, true},\n'
    '    {TAB_GRAPHICS, "Shader threads", &gfx_threads, 0, 4, 1, tx_threads,\n'
    '     "CPU threads compiling shaders. More is faster, but can slow the game while it plays. Applies after a restart.", nullptr,\n'
    '     true, true},\n')


def patch(H, rel, swaps):
    f = H / rel
    t = f.read_text(encoding='utf-8')
    for old, new in swaps:
        if t.count(old) < 1:
            raise SystemExit(f'engine_v21: {rel} no longer has {old[:80]!r} (the engine changed: update engine_v21.py)')
        t = t.replace(old, new, 1)
    f.write_text(t, encoding='utf-8', newline='')


def apply_light_tables(H):
    """Backport Hookshot PR #3047, pinned at 9c75b3214262844b644c0a8cdbbe9b2bde590ace.

    Clustered lights read their own shadow maps instead of a dummy texture. The
    upstream patch, tests and license headers are kept intact. This changes the
    translator and intentionally invalidates the shader cache once.
    """
    import os
    import subprocess
    fix = Path(__file__).resolve().parent / 'engine-light-tables.patch'
    # Do not let git discover the developer repository above the staged engine:
    # otherwise git apply can silently skip every path below this directory.
    env = dict(os.environ, GIT_CEILING_DIRECTORIES=str(Path(H).resolve().parent))
    for flags in (['--check'], []):
        result = subprocess.run(['git', 'apply', '-p1', '--whitespace=nowarn', *flags, str(fix)],
                                cwd=H, env=env, capture_output=True, text=True)
        if result.returncode:
            raise SystemExit('light-table fix did not apply: ' + result.stderr[:1600])
    checks = {
        'gpu/vk/eden/shader_recompiler/ir_opt/texture_pass.cpp': 'bool FindHandleTableIndex(',
        'gpu/vk/vk_draw.cpp': 'stage_handle(s, st, d.handle_program, k)',
        'gpu/vk/vk_shader.cpp': 'uint32_t program, uint32_t element)',
        'tests/test_handle_table.py': 'def run_programs(',
    }
    for rel, marker in checks.items():
        if marker not in (H / rel).read_text(encoding='utf-8'):
            raise SystemExit('light-table fix missing after git apply: ' + rel)
    print('lighting: per-light shadow maps (Hookshot PR #3047), patch applied and checked')


def apply_gfx(H):
    shutil.copy2(HUD / 'ocr_options.h', H / 'gpu/vk/ocr_options.h')
    shutil.copy2(HUD / 'ocr_texture_policy.h', H / 'gpu/vk/ocr_texture_policy.h')
    patch(H, 'gpu/vk/vk_draw.cpp', [
        ('#include "vk_paths.h"\n', '#include "vk_paths.h"\n#include "ocr_options.h"\n'),
        ('        static const bool force_linear = env_on("RX_VK_FORCE_LINEAR");\n',
         '        static const bool force_linear = env_on("RX_VK_FORCE_LINEAR") || ocr_option(nullptr, "texture_filtering", 0) == 1;\n'),
        ('    ci.mipLodBias = std::clamp(p.lod_bias + up_bias, ',
         '    {   // (Ocarina Reborn) the rows the renderer read, said once\n'
         '        static const bool told = (logf("[OcarinaReborn/GFX] texture detail bias %g, smooth filtering %d, soft shadows %d",\n'
         '                                       (double)ocr_texture_bias(), ocr_option(nullptr, "texture_filtering", 0),\n'
         '                                       ocr_option("RX_VK_SHADOW_PCF", "soft_shadows", 1)), true);\n'
         '        (void)told;\n'
         '    }\n'
         '    ci.mipLodBias = std::clamp(p.lod_bias + up_bias + ocr_texture_bias(), '),
        ('        static const bool pcf = !getenv("RX_VK_SHADOW_PCF") || atoi(getenv("RX_VK_SHADOW_PCF")) != 0;\n',
         '        static const bool pcf = ocr_option("RX_VK_SHADOW_PCF", "soft_shadows", 1) != 0;   // (Ocarina Reborn: the Soft shadows row)\n'),
        ('    if (const char* e = getenv("RX_VK_PRECOMPILE")) on = atoi(e) != 0;\n',
         '    if (const char* e = getenv("RX_VK_PRECOMPILE")) on = atoi(e) != 0;\n'
         '    else on = ocr_option(nullptr, "pipeline_precompile", on ? 1 : 0) != 0;   // (Ocarina Reborn: the Pipeline precompile row)\n'),
        ('    const unsigned workers = background ? std::min(quarter, cpus) : std::clamp(half_cpus(), 1u, 32u);',
         '    const unsigned workers = ocr_shader_workers(background ? std::min(quarter, cpus) : std::clamp(half_cpus(), 1u, 32u));'),
    ])
    # (v2.2.0: every copy of the program cache's switch and of the compile workers' counts: the Shader cache and Shader threads rows)
    f = H / 'gpu/vk/vk_draw.cpp'
    t = f.read_text(encoding='utf-8')
    for old, new in (('static const bool off = env_on("RX_VK_NO_PROGRAM_CACHE");', 'static const bool off = ocr_program_cache_off();'),
                     ('if (!env_on("RX_VK_NO_PROGRAM_CACHE")) {', 'if (!ocr_program_cache_off()) {'),
                     ('i < std::clamp(half_cpus(), 1u, 32u); i++) threads.emplace_back(',
                      'i < ocr_shader_workers(std::clamp(half_cpus(), 1u, 32u)); i++) threads.emplace_back('),
                     ('i < std::min(cpus, 64u); i++) threads.emplace_back(worker);',
                      'i < ocr_shader_workers(std::min(cpus, 64u)); i++) threads.emplace_back(worker);')):
        if old not in t:
            raise SystemExit(f'engine_v21: vk_draw.cpp no longer has {old[:80]!r} (the engine changed: update engine_v21.py)')
        t = t.replace(old, new)
    f.write_text(t, encoding='utf-8', newline='')
    patch(H, 'gpu/vk/vk_progcache.cpp', [
        ('#include "vk_paths.h"\n', '#include "vk_paths.h"\n#include "ocr_options.h"\n'),
        ('        if (env_on("RX_VK_NO_PROGRAM_CACHE")) return;', '        if (ocr_program_cache_off()) return;   // (Ocarina Reborn: the Shader cache row)'),
    ])
    patch(H, 'gpu/vk/vk_texture.cpp', [
        ('#include "vk_jobs.h"\n', '#include "vk_jobs.h"\n#include "ocr_options.h"\n#include "ocr_texture_policy.h"\n'),
        ('        if (x.skip) {\n            static int logged;\n',
         '        {   // Ocarina Reborn: opt-in reduction using the existing skip-aware image/upload/view paths.\n'
         '            static const int saving = std::clamp(ocr_option(nullptr, "texture_saving", 0), 0, 2);\n'
         '            const uint32_t old_skip = x.skip;\n'
         '            x.skip = ocr::texture_skip(saving, astc, d.target == NVN_TEXTURE_TARGET_2D_ARRAY,\n'
         '                                       as_target, x.sparse, std::max(1, d.samples), bw, bh,\n'
         '                                       x.width, x.height, x.layers, x.levels, x.skip, bytes_at(0));\n'
         '            if (x.skip > old_skip) {\n'
         '                static unsigned logged = 0;\n'
         '                if (logged++ < 16) logf("[OcarinaReborn/GFX] texture saving %d: ASTC array %ux%u x%u, %u extra mip levels omitted; decoded size estimate %llu -> %llu MB (before BC compression)",\n'
         '                    saving, x.width, x.height, x.layers, x.skip - old_skip,\n'
         '                    (unsigned long long)(bytes_at(old_skip) >> 20), (unsigned long long)(bytes_at(x.skip) >> 20));\n'
         '            }\n'
         '        }\n'
         '        if (x.skip) {\n            static int logged;\n'),
        ('    const bool preset_budget = opts.vram_mb > 0 && !vram_env && preset_caps_memory();\n',
         '    const int ocr_gb = vram_env ? 0 : ocr_texture_budget_gb();   // (Ocarina Reborn: the Texture memory row, Auto 0)\n'
         '    const bool preset_budget = ocr_gb > 0 || (opts.vram_mb > 0 && !vram_env && preset_caps_memory());\n'),
        ('    if (preset_budget && known) {\n        // Safety clamp: do not exceed 75% of driver-allowed memory',
         '    if (ocr_gb > 0) {\n'
         '        budget = (uint64_t)ocr_gb << 30;\n'
         '        static bool told;\n'
         '        if (!told) told = true, logf("[OcarinaReborn/GFX] texture memory %d GB (held under 3/4 of what the driver allows)", ocr_gb);\n'
         '    }\n'
         '    if (preset_budget && known) {\n        // Safety clamp: do not exceed 75% of driver-allowed memory'),
    ])
    patch(H, 'gpu/vk/vk_main.cpp', [
        ('#include "vk_paths.h"\n', '#include "vk_paths.h"\n#include "ocr_options.h"\n'),
        # (Ocarina Reborn) Mesh shaders on Automatic: every AMD RDNA 2 card (RX 6000, device ids 0x73a0-0x743f) on Windows takes
        # the compute path, as Compute does. Native mesh shaders lost the device every few minutes on an RX 6950 XT (Navi 21) with
        # AMD's Windows driver (5 debug packages, 2026-11-12/13); with Compute it played on without one. Hookshot moved only Navi
        # 22's task + mesh draws (issue 996). Native on the row keeps the card's own mesh shaders
        ('    if (mesh_mode_used == 2) dev.mesh_shader = false;\n',
         '#ifdef _WIN32\n'
         '    if (mesh_mode_used == 0 && dev.props.vendorID == 0x1002 && dev.props.deviceID >= 0x73a0 && dev.props.deviceID <= 0x743f) {\n'
         '        mesh_mode_used = 2;\n'
         '        logf("[OcarinaReborn/GFX] mesh shaders: AMD RDNA 2 (device %#x): the compute path (RX_VK_MESH_SHADERS=native: the card\'s own)",\n'
         '             (unsigned)dev.props.deviceID);\n'
         '    }\n'
         '#endif\n'
         '    if (mesh_mode_used == 2) dev.mesh_shader = false;\n'),
        # (VSync: v2.2.0's own V-Sync row, Auto / On / Off (menu_vsync); the launcher writes its line)
        ('    result = vkGetPhysicalDeviceSurfaceFormatsKHR(dev.physical, dev.surface, &n, formats.data());\n',
         '    result = vkGetPhysicalDeviceSurfaceFormatsKHR(dev.physical, dev.surface, &n, formats.data());\n'
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
         '        if (said != (dev.hdr ? 1 : 0)) {\n'
         '            said = dev.hdr ? 1 : 0;\n'
         '            if (dev.hdr)\n'
         '                logf("[HDR] HDR output active: format %d, colour space HDR10 ST2084, paper white %d nits, peak %d nits", (int)fmt.format,\n'
         '                     opts.hdr_white, opts.hdr_peak);\n'
         '            else\n'
         '                logf("[HDR] output: SDR (format %d)%s", (int)fmt.format, opts.hdr ? ": HDR is chosen but the display offers no HDR10 surface" : "");\n'
         '        }\n'
         '    }\n'
         '    // mailbox when the driver has it (latest frame, no tear).'),
    ])
    f = H / 'gpu/vk/vk_menu.cpp'
    t = f.read_text(encoding='utf-8')
    for old, new in (
            ('Row rows[] = {\n', GFX_DECLS + 'Row rows[] = {\n'),
            ('    {TAB_GRAPHICS, "GPU and memory"', GFX_ROWS + '    {TAB_GRAPHICS, "GPU and memory"'),
            ('const char* tx_hdr(int v) { return v == 1 ? "Expanded" : v == 2 ? "Native (the game\'s)" : "Off"; }',
             'const char* tx_hdr(int v) {   // (Ocarina Reborn: what the swapchain really is)\n'
             '    if (v && dev.swap_extent.width && !dev.hdr) return v == 1 ? "Expanded (inactive: Windows HDR off)" : "Native (inactive: Windows HDR off)";\n'
             '    return v == 1 ? "Expanded" : v == 2 ? "Native (the game\'s)" : "Off";\n'
             '}')):
        if old not in t:
            raise SystemExit(f'engine_v21: vk_menu.cpp no longer has {old[:80]!r} (the engine changed: update engine_v21.py)')
        t = t.replace(old, new, 1)
    f.write_text(t, encoding='utf-8', newline='')
    print('gfx: texture detail, texture filtering, soft shadows, vsync, texture memory, pipeline precompile, shader cache and '
          'threads; HDR log lines')

PERF = (HUD / 'ocr_perf.inc').read_text(encoding='utf-8')


# (Ocarina Reborn) the Reborn look row (F1 > Graphics, live): a colour grade in the window pass, after the sharpen
# (hud/ocr_fg_scale.comp, its SPIR-V hud/ocr_fg_scale_comp_spv.h made with glslang 16.6.0 -V --target-env vulkan1.2
# --vn FG_SCALE_COMP_SPV, the same tool and flags that reproduce Hookshot's own header byte for byte). Off: as Hookshot draws it
LOOKS = '{1.0f, 1.0f, 0.0f, 0.0f}, {1.12f, 1.06f, 0.03f, 0.18f}, {1.25f, 1.10f, 0.0f, 0.0f}, {1.05f, 1.03f, 0.07f, 0.12f}, ' \
        '{1.05f, 1.04f, -0.05f, 0.10f}, {0.92f, 1.12f, 0.02f, 0.30f}'
LOOK_NAMES = '"Off", "Reborn", "Vivid", "Warm", "Cool", "Cinematic"'


def apply_look(H):
    shutil.copy2(HUD / 'ocr_fg_scale.comp', H / 'gpu/vk/shaders/fg_scale.comp')
    shutil.copy2(HUD / 'ocr_fg_scale_comp_spv.h', H / 'gpu/vk/shaders/fg_scale_comp_spv.h')
    # (v2.2.0: the same source with FG_SCALE_PQ is the 10-bit pass for the game's own HDR10 picture, fg_scale_pq_comp_spv.h)
    shutil.copy2(HUD / 'ocr_fg_scale_pq_comp_spv.h', H / 'gpu/vk/shaders/fg_scale_pq_comp_spv.h')
    patch(H, 'gpu/vk/vk_framegen.cpp', [
        ('namespace mkwvk {\n', 'namespace mkwvk {\nint ocr_look = 0, ocr_bloom = 0, ocr_fxaa = 0;   // (Ocarina Reborn: the Reborn look, Bloom and FXAA rows, vk_menu.cpp)\n'),
        ('make_pipe(scale.pipe, FG_SCALE_COMP_SPV, sizeof FG_SCALE_COMP_SPV, {S, I, S}, 20)',
         'make_pipe(scale.pipe, FG_SCALE_COMP_SPV, sizeof FG_SCALE_COMP_SPV, {S, I, S}, 48)'),
        ('make_pipe(scale.pipe_pq, FG_SCALE_PQ_COMP_SPV, sizeof FG_SCALE_PQ_COMP_SPV, {S, I, S}, 20)',
         'make_pipe(scale.pipe_pq, FG_SCALE_PQ_COMP_SPV, sizeof FG_SCALE_PQ_COMP_SPV, {S, I, S}, 48)'),
        ('    if (!opts.upscale && !opts.sharpness && !wide.side) return VK_NULL_HANDLE;',
         '    // (Ocarina Reborn: a look or bloom needs the pass too. Not on the game\'s own HDR10 picture (pq): its PQ codes are not\n'
         '    // the colours the grade, the glow and FXAA are made for)\n'
         '    const int look = pq ? 0 : std::clamp(ocr_look, 0, 5);\n'
         '    static const float blooms[4] = {0.0f, 0.25f, 0.5f, 0.85f};\n'
         '    const float bloom = pq ? 0.0f : blooms[std::clamp(ocr_bloom, 0, 3)];\n'
         '    const int fxaa = !pq && ocr_fxaa ? 1 : 0;\n'
         '    if (!opts.upscale && !opts.sharpness && !wide.side && !look && bloom <= 0 && !fxaa) return VK_NULL_HANDLE;'),
        ('    struct { int mode; float sharp; float x0, x1; int side; } pc{opts.upscale, opts.sharpness / 100.0f, wide.x0, 1.0f - wide.x0, wide.side};',
         '    static const float looks[6][4] = {' + LOOKS + '};\n'
         '    struct { int mode; float sharp; float x0, x1; int side; float sat, contrast, warm, vignette; int look; float bloom; int fxaa; } pc{\n'
         '        opts.upscale, opts.sharpness / 100.0f, wide.x0, 1.0f - wide.x0, wide.side,\n'
         '        looks[look][0], looks[look][1], looks[look][2], looks[look][3], look, bloom, fxaa};'),
        # (Bloom reads the picture at 1/8 that the blurred sides make: made for it too, and bound as "small")
        ('    if (wide.side == 1) {   // (the blurred sides: first the picture at 1/8',
         '    if (wide.side == 1 || bloom > 0) {   // (the blurred sides, and Ocarina Reborn\'s Bloom: first the picture at 1/8'),
        ('        full_barrier(cmd);\n        pc.side = 1;\n',
         '        full_barrier(cmd);\n        pc.side = wide.side;   // (Ocarina Reborn: 0 when only Bloom asked for the small picture)\n'),
        ('{wide.side == 1 ? scale.small.view : src, scale.linear}}',
         '{wide.side == 1 || bloom > 0 ? scale.small.view : src, scale.linear}}'),
    ])
    patch(H, 'gpu/vk/vk_menu.cpp', [
        ('#include "vk_fsr4.h"\n', '#include "vk_fsr4.h"\nnamespace mkwvk { extern int ocr_look, ocr_bloom, ocr_fxaa; }   // (vk_framegen.cpp: the Reborn look, Bloom and FXAA rows)\n'),
        ('    {TAB_GRAPHICS, "Anisotropic filtering", &opts.anisotropy',
         '    {TAB_GRAPHICS, "Reborn look", &ocr_look, 0, 5, 1,\n'
         '     +[](int v) -> const char* { static const char* t[] = {' + LOOK_NAMES + '}; return t[std::clamp(v, 0, 5)]; },\n'
         '     "Ocarina Reborn\'s colour grade on the finished picture: richer colour and contrast, a warm or cool tone, a soft '
         'vignette. Off shows the game\'s own colours. Applies at once.", nullptr, false, true},\n'
         '    {TAB_GRAPHICS, "Bloom", &ocr_bloom, 0, 3, 1,\n'
         '     +[](int v) -> const char* { static const char* t[] = {"Off", "Low", "Medium", "High"}; return t[std::clamp(v, 0, 3)]; },\n'
         '     "A soft glow around bright light: the sun, fire, magic. Added by Ocarina Reborn on the finished picture. Applies at once.",\n'
         '     nullptr, false, true},\n'
         '    {TAB_GRAPHICS, "FXAA", &ocr_fxaa, 0, 1, 1, tx_onoff,\n'
         '     "Smooths jagged edges on the finished picture. Light on performance; not needed with FSR, which smooths already. '
         'Applies at once.", nullptr, false, true},\n'
         '    {TAB_GRAPHICS, "Anisotropic filtering", &opts.anisotropy'),
    ])
    print('look: the Reborn look row and its colour grade in the window pass')


def apply_timer(H):
    """(Ocarina Reborn) the Speedrun timer and Death counter rows (F1 > Gameplay, live), drawn in the top left corner.
    Timer: real time in tenths of a second, paused while the F1 menu is open and over the start-up screen; turning the row
    off and on starts it from zero. No splits: the game's events (a boss beaten, an area reached) are not known to the renderer.
    Death counter: each time Link's hearts reach 0 this session (host/hos_main.c hos_oot_life_change sends the count with
    rx_option_set(OCR_OPT_DEATHS)). A fairy that saves him may count too: its behaviour at 0 is not verified yet"""
    patch(H, 'gpu/vk/vk_menu.cpp', [
        ('#include "vk_fsr4.h"\n', '#include "vk_fsr4.h"\n'
         'namespace mkwvk { int ocr_timer = 0, ocr_deaths_row = 0; std::atomic<int> ocr_deaths{0}; }   // (Speedrun timer, Death counter)\n'
         '#define OCR_OPT_DEATHS 4089   /* (Ocarina Reborn) rx_option_set from the game side: the deaths this session */\n'),
        ('    {TAB_GAMEPLAY, "Menu size"',
         '    {TAB_GAMEPLAY, "Speedrun timer", &ocr_timer, 0, 1, 1, tx_onoff,\n'
         '     "Real time in the top left corner, paused while this menu is open. Turn it off and on again to start from zero.",\n'
         '     nullptr, false, true},\n'
         '    {TAB_GAMEPLAY, "Death counter", &ocr_deaths_row, 0, 1, 1, tx_onoff,\n'
         '     "How often Link\'s hearts reached zero since the game started, in the top left corner.", nullptr, false, true},\n'
         '    {TAB_GAMEPLAY, "Menu size"'),
        ('void menu_option_set(int id, int value) {\n',
         'void menu_option_set(int id, int value) {\n'
         '    if (id == OCR_OPT_DEATHS) { ocr_deaths.store(value, std::memory_order_relaxed); return; }   // (Ocarina Reborn)\n'),
        ('/// The start-up screen:',
         '/// (Ocarina Reborn) the top left corner: the Speedrun timer (h:mm:ss.t) and the Death counter under it, white outlined text\n'
         'static bool timer_running = false;   // (false while the timer row is off: the next draw starts from zero)\n'
         'void timer_off() { timer_running = false; }\n'
         'void draw_corner(ui::Ctx& c, bool paused, bool timer, bool deaths) {\n'
         '    float top = c.safe;\n'
         '    const float px = 24 * c.s;\n'
         '    if (timer) {\n'
         '        static int64_t acc = 0, last = 0;\n'
         '        const int64_t now = prof_now();\n'
         '        if (!timer_running) acc = 0, last = now;   // (just turned on: from zero)\n'
         '        timer_running = true;\n'
         '        if (!paused && last) acc += now - last;\n'
         '        last = now;\n'
         '        const int64_t t = acc / 100000000;   // (tenths)\n'
         '        char text[32];\n'
         '        snprintf(text, sizeof text, "%lld:%02lld:%02lld.%lld", (long long)(t / 36000), (long long)(t / 600 % 60),\n'
         '                 (long long)(t / 10 % 60), (long long)(t % 10));\n'
         '        const float tw = ui::size_of(c.f.strong, px, text).x;\n'
         '        outlined_right(c, c.f.strong, px, c.safe + tw, top, paused ? ui::rgba(200, 200, 200) : ui::rgba(255, 255, 255), text);\n'
         '        top += px * 1.25f;\n'
         '    }\n'
         '    if (deaths) {\n'
         '        char text[32];\n'
         '        snprintf(text, sizeof text, "Deaths %d", ocr_deaths.load(std::memory_order_relaxed));\n'
         '        const float dpx = 18 * c.s;\n'
         '        const float tw = ui::size_of(c.f.strong, dpx, text).x;\n'
         '        outlined_right(c, c.f.strong, dpx, c.safe + tw, top, ui::rgba(255, 140, 130), text);\n'
         '    }\n'
         '}\n\n'
         '/// The start-up screen:'),
        ('    const bool fps = opts.show_fps && !start;   // (no game frames yet: not "0 FPS" over the start-up screen)\n'
         '    const bool open = open_now.load(std::memory_order_relaxed);\n'
         '    if (!start && !fps && !open) {',
         '    const bool fps = opts.show_fps && !start;   // (no game frames yet: not "0 FPS" over the start-up screen)\n'
         '    const bool open = open_now.load(std::memory_order_relaxed);\n'
         '    const bool timer = ocr_timer && !start, deaths = ocr_deaths_row && !start;   // (Ocarina Reborn: the corner)\n'
         '    if (!timer) timer_off();\n'
         '    if (!start && !fps && !open && !timer && !deaths) {'),
        ('    if (start) draw_startup(c);   // (under the menu)\n    if (open) draw_menu(c);\n    if (fps) draw_fps(c, open);\n',
         '    if (start) draw_startup(c);   // (under the menu)\n    if (open) draw_menu(c);\n    if (fps) draw_fps(c, open);\n'
         '    if (timer || deaths) draw_corner(c, open, timer, deaths);\n'),
        ('    if (!open && !fps) return;\n    if (!ui::begin(w, h)) return;\n    ui::Ctx c = ui_ctx(w, h);\n    if (open) draw_menu(c);\n'
         '    if (fps) draw_fps(c, open);\n',
         '    const bool started = !startup_on.load(std::memory_order_acquire);\n'
         '    const bool timer = ocr_timer && started, deaths = ocr_deaths_row && started;   // (Ocarina Reborn: the corner)\n'
         '    if (!open && !fps && !timer && !deaths) return;\n    if (!ui::begin(w, h)) return;\n    ui::Ctx c = ui_ctx(w, h);\n'
         '    if (open) draw_menu(c);\n    if (fps) draw_fps(c, open);\n    if (timer || deaths) draw_corner(c, open, timer, deaths);\n'),
    ])
    print('timer: the Speedrun timer and Death counter rows and their corner')


def apply_dynres(H):
    """(Ocarina Reborn) the launcher's FPS target (OCARINA_FPS_TARGET 30/45/60): the render scale follows the GPU's time.
    The game's own dynamic resolution sees a tenth of the GPU's time (RX_VK_TS_SCALE 0.1, vk_replay.cpp: it moved every frame
    and made new render targets each time) and so stays near full scale. This controller is slow on purpose: one step of 0.1
    at most per five-second window of the [perf] line (ocr_perf.inc's GPU time a frame), between 0.5 and the Render
    resolution row's scale (full scale when the row is Auto), so new render targets are rare. Lower when the GPU takes more than
    85% of the target's frame time (+5%), higher when it takes under 55% of it"""
    patch(H, 'gpu/vk/vk_replay.cpp', [
        ('    t.option = [](int id) -> int {',
         '    t.option = [](int id) -> int {\n'
         '        if (id == 4088) return (int)(::mkwvk::ocr_ov_gpu.load(std::memory_order_relaxed) * 1000.0f);   // (Ocarina Reborn: '
         'the GPU\'s time a frame in us, for the FPS target, host/nn_vi.c)'),
    ])
    patch(H, 'host/nn_vi.c', [
        ('    hos_fixed_resolution = !rx_option(2, 1) && hos_dynres_runs >= 30;',
         '    static int ocr_fps_target = -1;   /* (Ocarina Reborn: the FPS target, engine_v21.py apply_dynres) */\n'
         '    if (ocr_fps_target < 0) ocr_fps_target = getenv("OCARINA_FPS_TARGET") ? atoi(getenv("OCARINA_FPS_TARGET")) : 0;\n'
         '    hos_fixed_resolution = (!rx_option(2, 1) || ocr_fps_target > 0) && hos_dynres_runs >= 30;'),
        ('    {\n        static int read_scale;\n',
         '    if (ocr_fps_target > 0 && !getenv("HOS_RES_SCALE")) {   /* (Ocarina Reborn) the FPS target\'s scale */\n'
         '        const int row = rx_option(3, 0);\n'
         '        const float top = row > 0 ? row / 10000.0f : 1.0f;   /* (the Render resolution row: the most) */\n'
         '        static float cur = 0.0f;\n'
         '        static int last_gpu = -1;\n'
         '        if (cur <= 0.0f || cur > top) cur = top;\n'
         '        const int gpu_us = rx_option(4088, 0);\n'
         '        if (gpu_us > 0 && gpu_us != last_gpu) {   /* (a new five-second window) */\n'
         '            last_gpu = gpu_us;\n'
         '            const float budget = 1e6f / (float)ocr_fps_target * 0.85f, was = cur;\n'
         '            if (gpu_us > budget * 1.05f && cur > 0.5f) cur = cur - 0.1f < 0.5f ? 0.5f : cur - 0.1f;\n'
         '            else if (gpu_us < budget * 0.65f && cur < top) cur = cur + 0.1f > top ? top : cur + 0.1f;\n'
         '            if (cur != was)\n'
         '                hos_log("[OcarinaReborn/RES] FPS target %d: GPU %.1f ms a frame, render scale %.2f -> %.2f", ocr_fps_target,\n'
         '                        gpu_us / 1000.0, was, cur);\n'
         '        }\n'
         '        memcpy((void *)&hos_fixed_scale_bits, &cur, 4);\n'
         '    }\n'
         '    {\n        static int read_scale;\n'),
    ])
    print('dynres: the FPS target\'s render scale')


MEM_RETRY = (
    '/* (Ocarina Reborn) a commit Windows refuses with 1455 (commit limit) is tried again for up to ~4 s: a page file that may\n'
    '   grow (system managed, or Initial < Maximum) is grown by Windows after such a refusal, not before it. Without this the\n'
    '   first refusal crashed the game at once although the page file had room left to grow (Debug package 2026-11-12 02:50:\n'
    '   page file 12 of 32 GB allowed, commit 36 GB, crash in Resource Memory). */\n'
    'static void *ocr_commit(void *p, SIZE_T n) {\n'
    '    void *r = VirtualAlloc(p, n, MEM_COMMIT, PAGE_READWRITE);\n'
    '    for (int i = 0; !r && GetLastError() == ERROR_COMMITMENT_LIMIT && i < 40; i++) {\n'
    '        Sleep(i < 10 ? 20 : 120);\n'
    '        r = VirtualAlloc(p, n, MEM_COMMIT, PAGE_READWRITE);\n'
    '        if (r) {\n'
    '            static volatile LONG said;\n'
    '            if (InterlockedIncrement(&said) <= 8)\n'
    '                hos_log("mem: commit of %#llx bytes went through after %d retries (Windows grew the page file)",\n'
    '                        (unsigned long long)n, i + 1);\n'
    '        }\n'
    '    }\n'
    '    return r;   /* (when NULL, GetLastError() is still the last VirtualAlloc\'s: hos_commit logs it) */\n'
    '}\n\n')


def apply_mem(H):
    """the guest memory commits (host/mkw_glue.c): retry when Windows' commit limit is reached, see MEM_RETRY"""
    patch(H, 'host/mkw_glue.c', [
        ('void hos_commit(uint64_t addr, uint64_t size) {', MEM_RETRY + 'void hos_commit(uint64_t addr, uint64_t size) {'),
        ('if (!VirtualAlloc(GP(lo), (SIZE_T)(hi - lo), MEM_COMMIT, PAGE_READWRITE)) {',
         'if (!ocr_commit(GP(lo), (SIZE_T)(hi - lo))) {'),
        ('return VirtualAlloc(GP(guest & ~0xFFFFULL), 0x10000, MEM_COMMIT, PAGE_READWRITE) ? EXCEPTION_CONTINUE_EXECUTION',
         'return ocr_commit(GP(guest & ~0xFFFFULL), 0x10000) ? EXCEPTION_CONTINUE_EXECUTION'),
    ])
    patch(H, 'gpu/vk/vk_texture.cpp', [
        ('    // (hookshot, RX_VK_COMPACT) and the count is held at RX_VK_COMPACT_PCT% of the allowance',
         RAM_GUARD + '    // (hookshot, RX_VK_COMPACT) and the count is held at RX_VK_COMPACT_PCT% of the allowance'),
    ])
    print('mem: commits retried at the commit limit (the page file may grow); RAM guard on the texture budget')


# (Ocarina Reborn) RAM guard: the texture budget also shrinks when Windows' commit (RAM + page file) runs short. On Windows
# the GPU's own memory counts toward the process' commit too (AMD: a 1.0.0 session reached 36 GB of commit with 6 GB of
# textures and crashed at the limit, error 1455). Below OCR_RAM_RESERVE_MB of commit left (0: emergency 512 MB,
# default 1024) the cache is held at a lower size, least recently used first, never under 1.5 GB, and the hold is let go
# slowly once 1 GB more than the reserve is free again.
# (A HOLD, not a cut for one pass: the guard of 1.0.1 lowered the budget for the pass it ran in only; the next pass had the
# normal budget again, the textures came back, the guard cut again. Two players' sessions (RX 9060 XT 01:15-01:32: 97 cuts,
# 32 of 42 windows with frames over 100 ms right after one; RX 7900 XTX 04:52) stuttered from that seesaw)
RAM_GUARD = (
    '#ifdef _WIN32\n'
    '    {   // (Ocarina Reborn) RAM guard: engine_v21.py RAM_GUARD\n'
    '        static const uint64_t reserve = (uint64_t)(getenv("OCR_RAM_RESERVE_MB") ? std::max(512, atoi(getenv("OCR_RAM_RESERVE_MB"))) : 1024) << 20;\n'
    '        static uint64_t held = 0;   // (0: no hold)\n'
    '        static uint64_t said_at = 0, pressure_at = 0;\n'
    '        MEMORYSTATUSEX ms{};\n'
    '        ms.dwLength = sizeof ms;\n'
    '        if (GlobalMemoryStatusEx(&ms)) {\n'
    '            // (Auto texture memory on a PC with little RAM: at most 40% of the RAM. AMD counts video memory toward the\n'
    '            // process\' commit, so a 16 GB PC with a 16 GB card had an 11 GB budget, 8.9 GB of textures, 14 of 15 GB VRAM,\n'
    '            // and lost the device (RX 6950 XT, 16 GB RAM, 2026-11-12). 32 GB of RAM keeps 12.8 GB: unchanged there)\n'
    '            if (!ocr_texture_budget_gb() && !getenv("RX_VK_TEX_MAX_MB")) {\n'
    '                const uint64_t ram_cap = ms.ullTotalPhys / 5 * 2;\n'
    '                static bool said_cap = false;\n'
    '                if (budget > ram_cap) {\n'
    '                    if (!said_cap) said_cap = true, logf("[OcarinaReborn/MEM] Auto texture memory: %llu MB of RAM, budget %llu -> %llu MB",\n'
    '                                                         (unsigned long long)(ms.ullTotalPhys >> 20), (unsigned long long)(budget >> 20),\n'
    '                                                         (unsigned long long)(ram_cap >> 20));\n'
    '                    budget = ram_cap;\n'
    '                }\n'
    '            }\n'
    '            if (frame_no % 600 == 0)\n'
    '                logf("[OcarinaReborn/MEM] system: commit free %llu MB, RAM free %llu MB, reserve %llu MB",\n'
    '                     (unsigned long long)(ms.ullAvailPageFile >> 20), (unsigned long long)(ms.ullAvailPhys >> 20),\n'
    '                     (unsigned long long)(reserve >> 20));\n'
    '            const uint64_t floor = std::min<uint64_t>(1536ull << 20, budget), step = 256ull << 20;\n'
    '            // (and physical RAM: with commit to spare, Windows still pages the game out when RAM runs short, and the whole\n'
    '            // game stops 1-3 s at a time: RTX 4070 SUPER, 31 GB RAM, private bytes 17 -> 29 GB over a session, dozens of\n'
    '            // 2-3 s freezes, the game reading no controller meanwhile, 2026-11-12. Under 1.5 GB of RAM free counts as short)\n'
    '            const uint64_t phys_reserve = std::max<uint64_t>(reserve, 1536ull << 20);\n'
    '            const uint64_t short_commit = ms.ullAvailPageFile < reserve ? reserve - ms.ullAvailPageFile : 0;\n'
    '            const uint64_t short_phys = ms.ullAvailPhys < phys_reserve ? phys_reserve - ms.ullAvailPhys : 0;\n'
    '            // (and the video memory Windows allows the game: over 92% of it, the driver moves memory out to RAM and the game\n'
    '            // stops for 1-3 s at a time, with CPU and GPU idle: RTX 4070 SUPER 2026-11-12, 10.2 of 10.6 GB, freezes of 2 s while\n'
    '            // its textures were already held at 2.5 GB by the RAM guard. Let go again under 85%)\n'
    '            uint64_t vused = 0, vallowed = 0;\n'
    '            const bool vknown = vram_usage(&vused, &vallowed) && vallowed;\n'
    '            const uint64_t vcap = vknown ? vallowed / 100 * 92 : 0;\n'
    '            const uint64_t short_vram = vknown && vused > vcap ? vused - vcap : 0;\n'
    '            const bool roomy = ms.ullAvailPageFile > reserve + (1024ull << 20) && ms.ullAvailPhys > phys_reserve + (1024ull << 20) &&\n'
    '                               (!vknown || vused < vallowed / 100 * 85);\n'
    '            if (short_commit || short_phys || short_vram) {   // (short: the hold one step lower, at most the shortfall)\n'
    '                const uint64_t short_by = std::max(std::max(short_commit, short_phys), short_vram), from = held ? held : std::min(budget, total_bytes);\n'
    '                const uint64_t lower = std::max(from > short_by ? from - short_by : 0, from > step ? from - step : 0);\n'
    '                pressure_at = frame_no;\n'
    '                const uint64_t was = held;\n'
    '                held = std::max(lower, floor);\n'
    '                if (held != was && (frame_no - said_at >= 600 || !said_at))\n'
    '                    said_at = frame_no, logf("[OcarinaReborn/MEM] RAM guard: %llu MB of commit left, %llu MB of RAM free, "\n'
    '                                             "VRAM %llu of %llu MB: textures held at %llu MB", (unsigned long long)(ms.ullAvailPageFile >> 20),\n'
    '                                             (unsigned long long)(ms.ullAvailPhys >> 20), (unsigned long long)(vused >> 20),\n'
    '                                             (unsigned long long)(vallowed >> 20), (unsigned long long)(held >> 20));\n'
    '            } else if (held && roomy && frame_no - pressure_at >= 300 && frame_no - said_at >= 300) {\n'
    '                // (room again: let go slowly, 128 MB every 5 s at the most, so it does not swing back at once)\n'
    '                said_at = frame_no;\n'
    '                held += 128ull << 20;\n'
    '                if (held >= budget) {\n'
    '                    held = 0;\n'
    '                    logf("[OcarinaReborn/MEM] RAM guard: %llu MB of commit left again, textures back to their budget",\n'
    '                         (unsigned long long)(ms.ullAvailPageFile >> 20));\n'
    '                }\n'
    '            }\n'
    '            if (held) budget = std::min(budget, held);\n'
    '        }\n'
    '    }\n'
    '#endif\n')


def apply_perf(H):
    """the performance lines in the game's log (the launcher copies them into its session log), and the in-game overlay's
    numbers: the FPS counter's third choice, Detailed (CPU and GPU time a frame, video memory)"""
    shutil.copy2(HUD / 'ocr_perf_metrics.h', H / 'gpu/vk/ocr_perf_metrics.h')
    patch(H, 'gpu/vk/vk_replay.cpp', [
        ('#include "vk_work.h"   // (after the others: counts the commands that do GPU work, for full_barrier)\n',
         '#include "vk_work.h"   // (after the others: counts the commands that do GPU work, for full_barrier)\n'
         '#include "ocr_perf_metrics.h"\n'
         'namespace mkwvk { std::atomic<float> ocr_ov_cpu{0}, ocr_ov_gpu{0}, ocr_ov_vram{0}, ocr_ov_budget{0}; }   // (the FPS counter: Detailed, vk_menu.cpp)\n'),
        ('uint64_t made_ring[32];\n', PERF + 'uint64_t made_ring[32];\n'),
        ('void log_frame_stats() {\n    log_slow_frame();\n', 'void log_frame_stats() {\n    log_slow_frame();\n    ocr_perf_tick();\n'),
    ])
    # (the FPS counter's Detailed choice of 1.0.2 is gone: v2.2.0's own FPS counter has levels, Off / FPS / Frame time / Graph /
    # Breakdown, with the CPU and GPU time a frame. The launcher's FPS counter row offers those)
    print('perf: [perf] every 5 s, [Performance Warning] lines')


# (Ocarina Reborn) the View distance, Grass and Shadow distance rows (F1 > Graphics, live): hud/ocr_view.c scales the game's
# own distances once a frame from the head of its render setup, hooked by hud/ocr_view.py on the one game build it knows.
# Steps, not sliders; Original on every row leaves the game untouched. Where the values sit in the game was found by hotoni
# (Graphics-Menu mod); the code is ours. Option ids 4080..4082 (rx_option from host/ocr_view.c)
def apply_view(H):
    shutil.copy2(HUD / 'ocr_view.c', H / 'host/ocr_view.c')
    shutil.copy2(HUD / 'ocr_view.py', H / 'nx2/ocr_view.py')
    patch(H, 'nx2/lift.py', [
        ('        import oot_occlusion',
         '        import ocr_view   # (Ocarina Reborn: view distance rows, host/ocr_view.c)\n'
         '        ocr_view.install(L, img, next((m["build_id"] for m in meta["modules"] if m["name"] == "main"), ""))\n'
         '        import oot_occlusion'),
    ])
    # (the option ids are not in gpu/vk/vk_api.h: that header is part of the shader cache's stamp (nx2/build.py), and adding
    # them there had every player compile all shaders again. host/ocr_view.c has the same numbers)
    patch(H, 'gpu/vk/vk_replay.cpp', [
        ('#include <algorithm>\n', '#include <algorithm>\nnamespace mkwvk { extern int ocr_view, ocr_grass, ocr_shadows; }   // (Ocarina Reborn: vk_menu.cpp)\n'
         'enum { OCR_OPT_VIEW = 4080, OCR_OPT_GRASS, OCR_OPT_SHADOWS };   // (Ocarina Reborn: host/ocr_view.c has the same)\n'),
        ('        if (id == 11) return opts.stick_dead_zone;\n',
         '        if (id == 11) return opts.stick_dead_zone;\n'
         '        if (id == OCR_OPT_VIEW) return ocr_view;   // (Ocarina Reborn: host/ocr_view.c)\n'
         '        if (id == OCR_OPT_GRASS) return ocr_grass;\n'
         '        if (id == OCR_OPT_SHADOWS) return ocr_shadows;\n'),
    ])
    patch(H, 'gpu/vk/vk_menu.cpp', [
        ('#include "vk_fsr4.h"\n', '#include "vk_fsr4.h"\nnamespace mkwvk { int ocr_view = 1, ocr_grass = 2, ocr_shadows = 1; }   // (View distance rows)\n'),
        ('    {TAB_GRAPHICS, "GPU and memory"',
         '    {TAB_GRAPHICS, "View distance", &ocr_view, 0, 4, 1,\n'
         '     +[](int v) -> const char* { static const char* t[] = {"Short", "Original", "Far", "Very far", "Max"}; return t[std::clamp(v, 0, 4)]; },\n'
         '     "How far trees, bushes and detailed models reach. Further costs CPU and GPU time. Applies at once.", nullptr, false, true},\n'
         '    {TAB_GRAPHICS, "Grass", &ocr_grass, 0, 4, 1,\n'
         '     +[](int v) -> const char* { static const char* t[] = {"Off", "Less", "Original", "More", "Dense"}; return t[std::clamp(v, 0, 4)]; },\n'
         '     "How much grass grows. Off or Less helps weaker PCs. Applies at once.", nullptr, false, true},\n'
         '    {TAB_GRAPHICS, "Shadow distance", &ocr_shadows, 0, 3, 1,\n'
         '     +[](int v) -> const char* { static const char* t[] = {"Short", "Original", "Far", "Max"}; return t[std::clamp(v, 0, 3)]; },\n'
         '     "How far scenery and characters cast shadows. Further costs GPU time. Applies at once.", nullptr, false, true},\n'
         '    {TAB_GRAPHICS, "GPU and memory"'),
    ])
    print('view: View distance, Grass and Shadow distance rows')


# (Ocarina Reborn, diagnostics for the pickup counter option) hud/ocr_uidiag.c logs each new (layout name hash, caller) the
# UI manager's find-by-name sees: which layout the game shows over Link on a pickup, and where. Remove once found.
def apply_uidiag(H):
    shutil.copy2(HUD / 'ocr_uidiag.c', H / 'host/ocr_uidiag.c')
    shutil.copy2(HUD / 'ocr_uidiag.py', H / 'nx2/ocr_uidiag.py')
    patch(H, 'nx2/lift.py', [
        ('        import oot_occlusion',
         '        import ocr_uidiag   # (Ocarina Reborn: UI layout diagnostics, host/ocr_uidiag.c)\n'
         '        ocr_uidiag.install(L, img, next((m["build_id"] for m in meta["modules"] if m["name"] == "main"), ""))\n'
         '        import oot_occlusion'),
    ])
    print('uidiag: UI layout lookups logged')


# (Ocarina Reborn) the Classic counters row (F1 > Gameplay, live; the launcher's Gameplay page too): no count over Link on a
# pickup, the rupees always shown, as on the N64. hud/ocr_counters.c, hooked by hud/ocr_counters.py. Option id 4083
def apply_counters(H):
    shutil.copy2(HUD / 'ocr_counters.c', H / 'host/ocr_counters.c')
    shutil.copy2(HUD / 'ocr_counters.py', H / 'nx2/ocr_counters.py')
    patch(H, 'nx2/lift.py', [
        ('        import oot_occlusion',
         '        import ocr_counters   # (Ocarina Reborn: Classic counters, host/ocr_counters.c)\n'
         '        ocr_counters.install(L, img, next((m["build_id"] for m in meta["modules"] if m["name"] == "main"), ""))\n'
         '        import oot_occlusion'),
    ])
    patch(H, 'gpu/vk/vk_replay.cpp', [
        ('#include <algorithm>\n', '#include <algorithm>\nnamespace mkwvk { extern int ocr_counters; }   // (Ocarina Reborn: vk_menu.cpp)\n'),
        ('        if (id == 11) return opts.stick_dead_zone;\n',
         '        if (id == 11) return opts.stick_dead_zone;\n'
         '        if (id == 4083) return ocr_counters;   // (Ocarina Reborn: Classic counters, host/ocr_counters.c)\n'),
    ])
    patch(H, 'gpu/vk/vk_menu.cpp', [
        ('#include "vk_fsr4.h"\n', '#include "vk_fsr4.h"\n'
         'namespace mkwvk { int ocr_counters = 0; std::atomic<int> ocr_rupees{-1}; }   // (Classic counters row; the wallet, -1: none)\n'
         '#define OCR_OPT_RUPEES 4084   /* (Ocarina Reborn) rx_option_set from the game side: the wallet, host/ocr_counters.c */\n'),
        ('    {TAB_GAMEPLAY, "Speedrun timer"',
         '    {TAB_GAMEPLAY, "Classic counters", &ocr_counters, 0, 1, 1, tx_onoff,\n'
         '     "As on the N64: no count over Link when he picks something up, and the rupees always shown. Applies at once.",\n'
         '     nullptr, false, true},\n'
         '    {TAB_GAMEPLAY, "Speedrun timer"'),
        ('    if (id == OCR_OPT_DEATHS) { ocr_deaths.store(value, std::memory_order_relaxed); return; }   // (Ocarina Reborn)\n',
         '    if (id == OCR_OPT_DEATHS) { ocr_deaths.store(value, std::memory_order_relaxed); return; }   // (Ocarina Reborn)\n'
         '    if (id == OCR_OPT_RUPEES) { ocr_rupees.store(value, std::memory_order_relaxed); return; }   // (Ocarina Reborn: the wallet)\n'),
        ('/// The start-up screen:',
         '/// (Ocarina Reborn) the bottom left corner, as on the N64: a green rupee and the wallet in white, outlined. The Classic counters\n'
         '/// row; the count from host/ocr_counters.c (OCR_OPT_RUPEES)\n'
         'void draw_rupees(ui::Ctx& c) {\n'
         '    const int v = ocr_rupees.load(std::memory_order_relaxed);\n'
         '    if (v < 0) return;\n'
         '    const float ih = 34 * c.s, iw = ih * 0.56f, px = 32 * c.s;\n'
         '    const float x = c.safe + 8 * c.s, bottom = c.h - c.safe - 6 * c.s, cy = bottom - ih / 2, cx = x + iw / 2;\n'
         '    auto gem = [&](float k, ImVec2* out) {   // (the rupee: a long hexagon, k of its size around the middle)\n'
         '        const float hw = iw / 2 * k, hh = ih / 2 * k, side = ih * 0.22f * k;\n'
         '        out[0] = {cx, cy - hh}, out[1] = {cx + hw, cy - side}, out[2] = {cx + hw, cy + side};\n'
         '        out[3] = {cx, cy + hh}, out[4] = {cx - hw, cy + side}, out[5] = {cx - hw, cy - side};\n'
         '    };\n'
         '    ImVec2 outer[6], inner[6];\n'
         '    gem(1.0f, outer), gem(0.5f, inner);\n'
         '    c.d->AddConvexPolyFilled(outer, 6, ui::rgba(30, 170, 60));\n'
         '    c.d->AddConvexPolyFilled(inner, 6, ui::rgba(130, 245, 140));\n'
         '    for (int i = 0; i < 6; i++) c.d->AddLine(outer[i], inner[i], ui::rgba(20, 110, 40), std::max(1.0f, c.s));\n'
         '    c.d->AddPolyline(outer, 6, ui::rgba(0, 0, 0, 230), ImDrawFlags_Closed, std::max(1.5f, 2 * c.s));\n'
         '    char text[16];\n'
         '    snprintf(text, sizeof text, "%d", v);\n'
         '    const float tw = ui::size_of(c.f.strong, px, text).x;\n'
         '    outlined_right(c, c.f.strong, px, x + iw + 10 * c.s + tw, cy - px * 0.62f, ui::rgba(255, 255, 255), text);\n'
         '}\n'
         '\n'
         '/// The start-up screen:'),
    ])
    # (and drawn where the corner is: in both of the menu's passes, under the menu; the early return also waits for it)
    f = H / 'gpu/vk/vk_menu.cpp'
    t = f.read_text(encoding='utf-8')
    for old, new in (
            ('    const bool timer = ocr_timer && !start, deaths = ocr_deaths_row && !start;   // (Ocarina Reborn: the corner)\n',
             '    const bool timer = ocr_timer && !start, deaths = ocr_deaths_row && !start;   // (Ocarina Reborn: the corner)\n'
             '    const bool rupees = ocr_counters && !start && ocr_rupees.load(std::memory_order_relaxed) >= 0;   // (Classic counters)\n'),
            ('    if (!start && !fps && !open && !timer && !deaths) {', '    if (!start && !fps && !open && !timer && !deaths && !rupees) {'),
            ('    const bool timer = ocr_timer && started, deaths = ocr_deaths_row && started;   // (Ocarina Reborn: the corner)\n',
             '    const bool timer = ocr_timer && started, deaths = ocr_deaths_row && started;   // (Ocarina Reborn: the corner)\n'
             '    const bool rupees = ocr_counters && started && ocr_rupees.load(std::memory_order_relaxed) >= 0;   // (Classic counters)\n'),
            ('    if (!open && !fps && !timer && !deaths) return;', '    if (!open && !fps && !timer && !deaths && !rupees) return;')):
        if t.count(old) != 1:
            raise SystemExit(f'engine_v21: vk_menu.cpp has {t.count(old)} of {old[:80]!r} (the engine changed: update apply_counters)')
        t = t.replace(old, new)
    old = '    if (timer || deaths) draw_corner(c, open, timer, deaths);\n'
    if t.count(old) != 2:
        raise SystemExit(f'engine_v21: vk_menu.cpp has {t.count(old)} of the corner\'s draw, not 2 (update apply_counters)')
    t = t.replace(old, '    if (rupees && !open) draw_rupees(c);   // (Ocarina Reborn: Classic counters, the wallet)\n' + old)
    f.write_text(t, encoding='utf-8', newline='')
    print('counters: the Classic counters row, the rupees in the bottom left corner')
