"""Checked engine patches for loading buffers and failure diagnostics."""
from pathlib import Path
import shutil

HERE = Path(__file__).parent


def replace_once(text, old, new):
    if new in text:
        return text
    if text.count(old) != 1:
        raise RuntimeError('Stability patch anchor changed: ' + old[:100])
    return text.replace(old, new, 1)


def apply(root):
    root = Path(root)
    memory = root / 'gpu/vk/vk_memory.cpp'
    text = memory.read_text(encoding='utf-8')
    legacy = '#include "ocr_capture_pool.inc"'
    marker = '// OCR_CAPTURE_POOL_BEGIN\n'
    end_marker = '// OCR_CAPTURE_POOL_END\n'
    pool = marker + (HERE / 'hud/ocr_capture_pool.inc').read_text(encoding='utf-8') + '\n' + end_marker
    if legacy in text:
        text = text.replace(legacy + '\n', pool, 1)
    elif marker in text:
        start = text.index(marker)
        end = text.index(end_marker, start) + len(end_marker)
        text = text[:start] + pool + text[end:]
    else:
        start = text.index('std::atomic<int> cap_prewarm_busy{0};')
        end = text.index('std::vector<std::pair<uint64_t, uint64_t>> cap_ranges;', start)
        if 'bool cap_buf_get(' not in text[start:end]:
            raise RuntimeError('Capture pool boundary changed')
        text = text[:start] + pool + text[end:]
    text = replace_once(text,
        '        return vram_usage(&used, &allowed) && allowed <= (6ull << 30) + (512ull << 20) ? 32ull << 20 : ~0ull;',
        '        MEMORYSTATUSEX ms{}; ms.dwLength = sizeof(ms);\n'
        '        const uint64_t ram = GlobalMemoryStatusEx(&ms) ? ms.ullTotalPhys : 0;\n'
        '        const uint64_t ram_mb = !ram || ram <= (9ull << 30) ? 64 : ram <= (17ull << 30) ? 128 : ram <= (33ull << 30) ? 256 : 512;\n'
        '        return vram_usage(&used, &allowed) && allowed <= (6ull << 30) + (512ull << 20) ? 32ull << 20 : ram_mb << 20;')
    memory.write_text(text, encoding='utf-8', newline='\n')

    texture = root / 'gpu/vk/vk_texture.cpp'
    text = texture.read_text(encoding='utf-8')
    text = replace_once(text, '        budget = (uint64_t)ocr_gb << 30;\n',
        '        // The manual row must preserve the same shared-memory cap as the engine presets.\n'
        '        budget = preset_texture_budget((uint64_t)ocr_gb << 10, true, false,\n'
        '                                        dev.props.deviceType == VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU, own);\n')
    text = replace_once(text,
        '        if (!told) told = true, logf("[OcarinaReborn/GFX] texture memory %d GB (held under 3/4 of what the driver allows)", ocr_gb);',
        '        if (!told) told = true, logf("[OcarinaReborn/GFX] texture memory requested %d GB, hardware cap %llu MB (driver and pressure limits also apply)",\n'
        '                                    ocr_gb, (unsigned long long)(budget >> 20));')
    texture.write_text(text, encoding='utf-8', newline='\n')

    make = root / 'nx2/make_game.py'
    text = make.read_text(encoding='utf-8')
    text = replace_once(text,
        '    elif code == 3:\n        not_prepared("no usable Vulkan here")',
        '    elif code == 3:\n        not_prepared("shader preparation stopped with exit status 3; see the preceding error output")')
    text = text.replace("A PC whose Vulkan can't (exit 3)", 'A run ending with exit 3 (not a Vulkan diagnosis by itself)')
    make.write_text(text, encoding='utf-8', newline='\n')
    tests = root / 'tests/test_prepare_at_build.py'
    if tests.exists():
        text = tests.read_text(encoding='utf-8').replace('self.assertIn("(no usable Vulkan here)", lines[-1])',
            'self.assertIn("shader preparation stopped with exit status 3", lines[-1])')
        tests.write_text(text, encoding='utf-8', newline='\n')
    glue = root / 'host/mkw_glue.c'
    text = glue.read_text(encoding='utf-8')
    text = replace_once(text, '#include <windows.h>\n', '#include <windows.h>\n#include "ocr_crash.h"\n')
    text = replace_once(text, 'static LONG WINAPI report_crash(EXCEPTION_POINTERS *info) {\n',
        'static LONG WINAPI report_crash(EXCEPTION_POINTERS *info) {\n'
        '    ocr_crash_report("unhandled exception", info->ExceptionRecord->ExceptionCode, info->ContextRecord);\n')
    text = replace_once(text, 'void hos_commit_init(void) {\n',
        'void hos_commit_init(void) {\n    ocr_crash_init();\n')
    glue.write_text(text, encoding='utf-8', newline='\n')
    shutil.copy2(HERE / 'hud/ocr_crash.h', root / 'host/ocr_crash.h')
    logging = root / 'host/hos_thread.c'
    text = logging.read_text(encoding='utf-8')
    text = replace_once(text,
        '    AcquireSRWLockExclusive(&log_write_lock);\n    AcquireSRWLockExclusive(&log_lock);\n    const int n = log_take_locked(batch);',
        '    /* Ocarina Reborn: match log_main lock order, including fatal/exit flushes. */\n'
        '    AcquireSRWLockExclusive(&log_lock);\n    AcquireSRWLockExclusive(&log_write_lock);\n    const int n = log_take_locked(batch);')
    logging.write_text(text, encoding='utf-8', newline='\n')
    print('stability: bounded capture refill, emergency crash report and accurate shader preparation failure')
