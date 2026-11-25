"""Measured-session summaries and conservative, reviewable setting suggestions.

Only versioned game-frame samples from the current renderer qualify for tuning.
Percentiles are per five-second window, never presented as whole-session percentiles.
"""
import math
import re

from pt_br import tr

BASE = re.compile(r'\[perf\] fps ([\d.]+) \| frame ([\d.]+) ms avg, ([\d.]+) ms worst \| CPU \(renderer\) ([\d.]+) ms \| GPU '
                  r'([\d.]+) ms \| VRAM (\??)\s*([\d.]+) / ([\d.]+) GB')
DETAIL = re.compile(r'stats2 seconds ([\d.]+) frames (\d+) p95 ([\d.]+) p99 ([\d.]+) over50 (\d+) over100 (\d+) '
                    r'menu ([01]) complete ([01]) fg (\d+)')
DRAW = re.compile(r'\| draws ([\d.]+)')
PIPELINE = re.compile(r'new pipelines (\d+), waits [\d.]+ \(([\d.]+) ms\)')
CACHE_PIPELINE = re.compile(r'vk: pipeline cache .+ \((\d+) KB\)')
CACHE_PROGRAM = re.compile(r'vk: program cache .+: (\d+) program keys kept, (\d+) KB')
CACHE_IN_USE = re.compile(r'vk: program cache .+: another Ocarina Reborn is using it: this one runs without it')
DEFAULTS = dict(output_res='2048x1152', resolution=0, dlss=0, frame_generation=0, frame_rate_cap=0,
                texture_memory=0, texture_saving=0, texture_detail=1, texture_filtering=0,
                shader_threads=0, shader_cache=1, pipeline_precompile=1, soft_shadows=1,
                anisotropic_filtering=4, quality_preset=0, handheld_profile=0, frame_pacing=1,
                view_distance=1, grass=2, shadow_distance=1)
OUTPUTS = {'0': '2048x1152', '1': '2560x1440', '2': '3840x2160', '3': '1920x1080', '4': '5120x1440'}


def signature(settings):
    values = {k: str(settings.get(k, v)) for k, v in DEFAULTS.items()}
    values['output_res'] = OUTPUTS.get(values['output_res'], values['output_res'])
    return values


def hardware_signature(facts):
    facts = facts or {}
    return {'gpus': sorted(n for n, _ in facts.get('gpus', [])),
            'threads': facts.get('cpu_threads'), 'ram_gb': facts.get('ram_gb')}


# VK_ERROR_OUT_OF_HOST_MEMORY (-1) and a confirmed Windows commit retry are specific
# evidence; failed shader translation and VK_ERROR_UNKNOWN (-13) are not.
HOST_MEMORY_ERROR = re.compile(r"vk: (?:batched |segment )?submit \d+ failed \(-1\)|VK_ERROR_OUT_OF_HOST_MEMORY|mem: commit .*Windows grew the page file")
GPU_SUBMIT_ERROR = re.compile(r'vk: (?:batched |segment )?submit \d+ failed \((-2|-4)\)')

# A rejected adapter alone is not a failed session: another adapter/backend may work.
RENDERER_STARTUP_LOG = ('vk: device ', 'vk: no Vulkan 1.3 GPU', 'vk: the Vulkan loader is ',
                        'vk: pick_device failed', 'display: no WebGPU device: the window stays black')


def renderer_startup_failure(lines):
    """Require the display's explicit terminal failure, not just a missing/old adapter."""
    reason, failure, evidence = None, None, []
    for line in lines:
        if 'vk: no Vulkan 1.3 GPU' in line or ('vk: the Vulkan loader is ' in line and '1.3 is needed' in line):
            reason = 'vulkan_1_3_unavailable'
        if any(marker in line for marker in RENDERER_STARTUP_LOG):
            evidence.append(line[:512])
            evidence = evidence[-8:]
        if 'display: no WebGPU device: the window stays black' in line:
            failure = dict(reason=reason or 'no_graphics_device', evidence=list(evidence))
        # Guest "frames presented" and audio progress do not prove GPU rendering.
        draw = DRAW.search(line)
        if BASE.search(line) and draw:
            try:
                rendered = float(draw[1])
            except ValueError:
                continue
            if math.isfinite(rendered) and rendered > 0:
                reason, failure, evidence = None, None, []
    return failure


def renderer_failure_advice(failure, de=True):
    if not failure:
        return []
    t = lambda d, e: d if de else tr(e)
    if failure['reason'] == 'vulkan_1_3_unavailable':
        message = t(
            'Dem Spiel stand kein Vulkan-1.3-Grafikgerät zur Verfügung. Deshalb kann das Bild schwarz bleiben, '
            'obwohl Ton und Eingaben funktionieren. Prüfe Treiber und Unterstützung beim GPU- oder Laptop-Hersteller. '
            'Niedrigere Grafikeinstellungen oder ein neuer Shader-Cache ersetzen die fehlende Vulkan-Unterstützung nicht.',
            'No Vulkan 1.3 graphics device was available to the game. This can leave a black screen while audio and '
            'inputs still work. Check driver support with your GPU or laptop manufacturer. '
            'Lower graphics settings or rebuilding shaders cannot add the missing Vulkan support.')
    else:
        message = t(
            'Die Grafik konnte nicht gestartet werden; das Bild bleibt schwarz, obwohl Ton weiterlaufen kann. '
            'Schließe das Spiel und sende ein Debug-Paket, damit wir den Grafikstart prüfen können.',
            'Graphics initialization failed; the screen stays black even though audio may continue. '
            'Close the game and send a Debug Package so we can check the graphics startup failure.')
    return [('warn', message)]


def gpu_failures(lines):
    """Explicit Vulkan results or watchdog failures, independent of FPS and exit code."""
    result = dict(device_memory_errors=0, device_lost_errors=0, gpu_hangs=0)
    fatal_hang = False
    for line in lines:
        match = GPU_SUBMIT_ERROR.search(line)
        if (match and match[1] == '-2') or 'VK_ERROR_OUT_OF_DEVICE_MEMORY' in line:
            result['device_memory_errors'] += 1
        if (match and match[1] == '-4') or 'VK_ERROR_DEVICE_LOST' in line:
            result['device_lost_errors'] += 1
        if re.search(r'vk: GPU hang: the timeline at \d+, \d+ sent', line):
            result['gpu_hangs'] += 1
        # The fatal message is printed through both the host log and stderr. Count
        # it only as fallback evidence when the preceding watchdog marker is gone.
        fatal_hang |= bool(re.search(r'vk: FATAL: the GPU hung: no submission finished in \d+ s', line))
    if fatal_hang and not result['gpu_hangs']:
        result['gpu_hangs'] = 1
    return result


def gpu_failure_advice(summary, de=True):
    t = lambda d, e: d if de else tr(e)
    advice = []
    if summary.get('gpu_hangs', 0):
        advice.append(('warn', t(
            'Der GPU-Watchdog hat das Spiel beendet, nachdem eingereichte Grafikbefehle nicht mehr fertig wurden. '
            'Ein solcher Hänger kann auch ohne Device-Lost-Meldung auftreten. Bitte dieselbe Stelle ohne Frame Generation testen '
            'und ein neues Debug-Paket senden. Der Log allein belegt weder die Ursache noch einen Hardwaredefekt.',
            'The GPU watchdog stopped the game because submitted graphics work stopped completing. '
            'This can happen without a driver-reported device loss. Please test the same area with frame generation off '
            'and send a fresh Debug Package. This log alone does not identify the cause or prove a hardware fault.')))
    if summary.get('device_memory_errors', 0):
        advice.append(('warn', t(
            'Der Renderer meldete erschöpften GPU-Speicher (VK_ERROR_OUT_OF_DEVICE_MEMORY). '
            'Texturspeicher auf 2 GB stellen und andere GPU-intensive Programme schließen. '
            'Integrierte Grafik teilt sich den Arbeitsspeicher mit dem Spiel.',
            'The renderer ran out of GPU memory (VK_ERROR_OUT_OF_DEVICE_MEMORY). '
            'Set Texture memory to 2 GB and close other GPU-intensive programs. '
            'Integrated graphics shares system RAM with the game.')))
    if summary.get('device_lost_errors', 0):
        advice.append(('warn', t(
            'Die GPU-Verbindung ging verloren (VK_ERROR_DEVICE_LOST). Das Spiel neu starten und das Debug-Paket senden. '
            'Dieser Fehler allein beweist keinen Speicher- oder Treiberdefekt.',
            'The GPU device was lost (VK_ERROR_DEVICE_LOST). Restart the game and send the Debug Package. '
            'This error alone does not establish a memory or driver fault.')))
    return advice


def memory_pressure(lines):
    """Observed pressure is separate from allocation failure, and never called OOM."""
    samples = []
    for line in lines:
        m = re.search(r'\[OcarinaReborn/MEM\] system: commit free (\d+) MB, RAM free (\d+) MB, reserve (\d+) MB', line)
        if m:
            samples.append(tuple(map(int, m.groups())))
    return dict(memory_pressure_events=sum(c < 1024 or r < 1024 for c, r, _ in samples),
                ram_free_min_mb=min((r for _, r, _ in samples), default=None),
                commit_free_min_mb=min((c for c, _, _ in samples), default=None))


def memory_pressure_advice(de=True):
    return ('warn',
        'Wenig freier RAM oder Windows-Speicher im Spiel gemessen. Nachladen und Speicher auf Weniger Speicher stellen, '
        'RAM-Schutz auf Stark lassen und unnötige Hintergrundprogramme schließen. Ein Shader-Neubau hilft hier nicht.'
        if de else
        tr('Low available RAM or Windows commit headroom was measured during play. Set Streaming and memory to '
        'Lower memory, keep RAM guard on Strong, and close unnecessary background apps. Rebuilding shaders will not fix this.'))


def memory_events(lines):
    return sum(bool(HOST_MEMORY_ERROR.search(line)) for line in lines)


def memory_advice(de=True):
    return ('warn',
            'Windows-Speicher war erschöpft; der Renderer meldete Speicherfehler oder Windows musste die Auslagerungsdatei vergrößern. '
            'RAM-Schutz auf Stark stellen, Hintergrundprogramme schließen und die Windows-Auslagerungsdatei systemverwaltet lassen.'
            if de else
            tr('Windows memory was exhausted: the renderer reported host-memory errors or Windows had to grow the page file. '
            'Set RAM guard to Strong, close background programs and keep the Windows page file system-managed.'))


def cache_status(lines):
    """Presence reported at startup, not a promise that every driver pipeline is reusable."""
    result = dict(pipeline_cache_kb=0, program_cache_keys=0, program_cache_kb=0, program_cache_in_use=False)
    for line in lines:
        if CACHE_IN_USE.search(line):
            result['program_cache_in_use'] = True
        pipeline, program = CACHE_PIPELINE.search(line), CACHE_PROGRAM.search(line)
        if pipeline:
            result['pipeline_cache_kb'] = max(result['pipeline_cache_kb'], int(pipeline[1]))
        if program:
            result['program_cache_keys'] = max(result['program_cache_keys'], int(program[1]))
            result['program_cache_kb'] = max(result['program_cache_kb'], int(program[2]))
    return result


def cache_conflict_advice(status, de=True):
    if not status.get('program_cache_in_use'):
        return []
    return [('warn',
        'Der Shader-Programmcache war durch einen anderen Spiel- oder Vorbereitungsprozess belegt. '
        'Dieser Lauf konnte ihn nicht nutzen und musste Shader neu berechnen. '
        'Schließe weitere Spielinstanzen oder warte auf die Shader-Vorbereitung, dann starte einmal neu. '
        'Den Cache nicht löschen.' if de else
        tr('Another game or preparation process held the shader program cache. '
        'This run could not use it and had to compile shaders again. '
        'Close other game instances or let shader preparation finish, then restart once. Do not delete the cache.'))]


def summarize(lines):
    lines = list(lines)
    host_memory_events = memory_events(lines)
    rows = []
    excluded = 0
    for line in lines:
        b, detail, draw = BASE.search(line), DETAIL.search(line), DRAW.search(line)
        if not (b and detail and draw):
            continue
        try:
            fps, avg, worst, cpu, gpu = map(float, b.groups()[:5])
            used, budget = map(float, b.groups()[6:])
            seconds, count, p95, p99, h50, h100, menu, complete, fg = map(float, detail.groups())
            draw_count = float(draw[1])
            pipeline = PIPELINE.search(line)
            pipeline_ms = float(pipeline[2]) if pipeline else 0
        except ValueError:
            continue
        numbers = (fps, avg, worst, cpu, gpu, used, budget, seconds, count, p95, p99, h50, h100)
        if not all(math.isfinite(v) and v >= 0 for v in numbers):
            continue
        if (not complete or menu or draw_count < 100 or seconds <= 0 or count < 2 or
                p95 <= 0 or p99 < p95 or h100 > h50 or h50 > count):
            excluded += 1
            continue
        rows.append(dict(seconds=seconds, frames=count, fps=count / seconds, worst=worst, cpu=cpu, gpu=gpu,
                         used=used, budget=budget, known=not b[6], p95=p95, p99=p99, h50=h50, h100=h100,
                         fg=fg, pipeline_ms=pipeline_ms))
    if not rows:
        return None
    seconds = sum(r['seconds'] for r in rows)
    frames = sum(r['frames'] for r in rows)
    known = [r for r in rows if r['known'] and r['budget'] > 0]
    # Windows dominated by a load or shader creation are reported, but not used to lower resolution.
    steady = [r for r in rows if r['worst'] < 250 and r['pipeline_ms'] < 2]
    steady_seconds = sum(r['seconds'] for r in steady)
    gpu_slow = sum(r['seconds'] for r in steady if r['fps'] < 55 and r['cpu'] > .1 and
                   r['gpu'] > 18.0 and r['gpu'] > 1.25 * r['cpu'])
    # The renderer's CPU counter does not include all game logic. Require both valid counters and a clear gap;
    # loading/compilation pauses above are excluded, and no CPU model is used as a proxy for measured pressure.
    cpu_slow = sum(r['seconds'] for r in steady if r['fps'] < 55 and r['cpu'] >= 12 and
                   r['gpu'] > .1 and r['cpu'] > 1.2 * r['gpu'])
    return dict(schema=2, **gpu_failures(lines), **cache_status(lines), **memory_pressure(lines), host_memory_events=host_memory_events, seconds=seconds, frames=int(frames), fps=frames / seconds,
                p95_worst_window=max(r['p95'] for r in rows), p99_worst_window=max(r['p99'] for r in rows),
                worst_ms=max(r['worst'] for r in rows), over50=int(sum(r['h50'] for r in rows)),
                over100=int(sum(r['h100'] for r in rows)),
                cpu_ms=sum(r['cpu'] * r['frames'] for r in rows) / frames,
                gpu_ms=sum(r['gpu'] * r['frames'] for r in rows) / frames,
                vram_peak_gb=max((r['used'] for r in known), default=0),
                vram_pressure_seconds=sum(r['seconds'] for r in known if r['used'] / r['budget'] > .90),
                steady_seconds=steady_seconds, gpu_slow_seconds=gpu_slow, cpu_slow_seconds=cpu_slow,
                frame_generation=any(r['fg'] for r in rows), windows=len(rows), excluded_windows=excluded)


def cpu_pressure(summary):
    """Several slow samples, not a single hitch or a tiny fraction of a long session."""
    steady = summary.get('steady_seconds', 0)
    return steady >= 30 and summary.get('cpu_slow_seconds', 0) >= max(15, .15 * steady)


def describe(summary, de=True):
    if not summary:
        return []
    t = lambda d, e: d if de else tr(e)
    s = summary
    lines = [
        ('ok' if s['fps'] >= 55 and not s['over100'] else 'warn', t(
            f"{s['fps']:.1f} echte Spiel-FPS über {s['seconds']:.0f} s ausgewertete Renderzeit (Zwischenbilder nicht mitgezählt).",
            f"{s['fps']:.1f} actual game fps over {s['seconds']:.0f} s of analyzed rendering (generated frames excluded).")),
        ('tip', t(f"Schlechtester 5-s-Abschnitt: P95 {s['p95_worst_window']:.1f} ms, P99 {s['p99_worst_window']:.1f} ms. "
                  f"{s['over50']} Bilder über 50 ms, davon {s['over100']} über 100 ms.",
                  f"Worst 5-second window: P95 {s['p95_worst_window']:.1f} ms, P99 {s['p99_worst_window']:.1f} ms. "
                  f"{s['over50']} frames over 50 ms, including {s['over100']} over 100 ms.")),
        ('tip', t(f"Renderer-CPU {s['cpu_ms']:.1f} ms/Bild, GPU {s['gpu_ms']:.1f} ms/Bild; "
                  f"höchster gemeldeter VRAM-Verbrauch {s['vram_peak_gb']:.2f} GB. CPU-Wert ohne übrige Spiellogik.",
                  f"Renderer CPU {s['cpu_ms']:.1f} ms/frame, GPU {s['gpu_ms']:.1f} ms/frame; "
                  f"peak reported VRAM use {s['vram_peak_gb']:.2f} GB. CPU time excludes other game logic.")),
        ('tip', t('Abschnitte mit offenem F1-Menü und sehr wenigen Zeichenbefehlen werden ausgelassen. Ladephasen können enthalten sein.',
                  'Windows with the F1 menu open or very few draw calls are excluded. Loading may still be included.')),
    ]
    if s.get('host_memory_events', 0):
        lines.insert(0, memory_advice(de))
    elif s.get('memory_pressure_events', 0):
        lines.insert(0, memory_pressure_advice(de))
    lines[0:0] = gpu_failure_advice(s, de)
    lines[0:0] = cache_conflict_advice(s, de)
    if cpu_pressure(s):
        lines.insert(-1, ('warn', t(
            f"In {s['cpu_slow_seconds']:.0f} s unter 55 FPS brauchte der Renderer auf der CPU deutlich länger als die GPU. "
            'Sichtweite und Gras reduzieren; ein 60-FPS-Limit testen.',
            f"During {s['cpu_slow_seconds']:.0f} s below 55 fps, renderer CPU time was clearly higher than GPU time. "
            'Reduce view distance and grass; test a 60 fps limit.')))
    if s.get('vram_pressure_seconds', 0) >= 15:
        lines.insert(-1, ('warn', t(
            f"Grafikspeicher über 90 % des gemeldeten Budgets für {s['vram_pressure_seconds']:.0f} s. "
            'Das kann Ruckler verursachen. Einen kleineren Texturcache testen (auch bei Auto) und GPU-intensive Hintergrundprogramme schließen.',
            f"Video memory exceeded 90% of the reported budget for {s['vram_pressure_seconds']:.0f} s. "
            'This can cause stutter. Test a smaller texture cache (including when set to Auto) and close GPU-intensive background programs.')))
    if s.get('frame_generation') and s['fps'] < 55:
        lines.insert(-1, ('tip', t(
            'Frame Generation war bei niedrigen echten Spiel-FPS aktiv. Hohe Faktoren können die echte Bildrate zusätzlich begrenzen. '
            'Zum Vergleich Frame Generation ausschalten; mehr Zwischenbilder beheben die niedrige Basisbildrate nicht.',
            'Frame generation was active with low actual game fps. High multipliers can further limit the base frame rate. '
            'Turn frame generation off for comparison; more generated frames do not fix a low base frame rate.')))
    if s.get('pipeline_cache_kb', 0) or s.get('program_cache_keys', 0):
        lines.insert(-1, ('tip', t(
            'Das Log meldet vorhandene Shader-/Pipeline-Caches. Nicht zum Beheben von FPS-Einbrüchen löschen: '
            'neue Pipelines und Nachladen können trotzdem Ruckler verursachen.',
            'The log reports existing shader/pipeline caches. Do not clear them to fix low fps: '
            'new pipelines and asset loading can still cause stutter.')))
    return lines


AUTO_MIN_SECONDS = 60   # (Reborn Auto: a run shorter than this says too little to compare)


def compare(before, after, de=True):
    """Reborn Auto's verdict on two runs of the same scenes: 'better', 'same', 'worse' or None (too little measured), and
    the lines that say why. Per minute for the long-frame counts (two runs are never the same length); a few percent of
    fps or a frame or two either way is noise, not a result."""
    t = lambda d, e: d if de else tr(e)
    if not before or not after or min(before.get('seconds', 0), after.get('seconds', 0)) < AUTO_MIN_SECONDS:
        return None, [t(f'Für einen Vergleich braucht jede Runde mindestens {AUTO_MIN_SECONDS} s auswertbare Spielzeit.',
                        f'A comparison needs at least {AUTO_MIN_SECONDS} s of usable play in each run.')]
    per_min = lambda s, k: s[k] * 60 / s['seconds']
    fps = (after['fps'] - before['fps']) / max(before['fps'], 1) * 100
    s50 = per_min(after, 'over50') - per_min(before, 'over50')
    s100 = per_min(after, 'over100') - per_min(before, 'over100')
    p99 = after['p99_worst_window'] - before['p99_worst_window']
    lines = [
        t(f"FPS: {before['fps']:.1f} → {after['fps']:.1f} ({fps:+.0f} %)", f"FPS: {before['fps']:.1f} → {after['fps']:.1f} ({fps:+.0f}%)"),
        t(f"Bilder über 50 ms pro Minute: {per_min(before, 'over50'):.1f} → {per_min(after, 'over50'):.1f}",
          f"Frames over 50 ms per minute: {per_min(before, 'over50'):.1f} → {per_min(after, 'over50'):.1f}"),
        t(f"Bilder über 100 ms pro Minute: {per_min(before, 'over100'):.1f} → {per_min(after, 'over100'):.1f}",
          f"Frames over 100 ms per minute: {per_min(before, 'over100'):.1f} → {per_min(after, 'over100'):.1f}"),
        t(f"Schlechtester Abschnitt P99: {before['p99_worst_window']:.0f} → {after['p99_worst_window']:.0f} ms",
          f"Worst window P99: {before['p99_worst_window']:.0f} → {after['p99_worst_window']:.0f} ms"),
    ]
    gains = (fps >= 3) + (s50 <= -1) + (s100 <= -0.5) + (p99 <= -10)
    losses = (fps <= -3) + (s50 >= 1) + (s100 >= 0.5) + (p99 >= 10)
    verdict = 'better' if gains > losses else 'worse' if losses > gains else 'same'
    return verdict, lines


def suggest(summary, current, measured_settings, de=True):
    """Never modify a file. Return a small proposed delta and its explanations."""
    t = lambda d, e: d if de else tr(e)
    if not summary or summary.get('schema') != 2 or summary.get('seconds', 0) < 30:
        return {}, [t('Für Vorschläge fehlen mindestens 30 s auswertbare Spielzeit.',
                      'Suggestions need at least 30 seconds of usable play measurements.')]
    if signature(current) != measured_settings:
        return {}, [t('Einstellungen seit der Messung geändert: erst eine neue Runde messen.',
                      'Settings changed since measurement: play another session first.')]
    values = signature(current)
    if summary.get('program_cache_in_use'):
        return {}, [text for _, text in cache_conflict_advice(summary, de)]
    changes, reasons = {}, []
    if summary['frame_generation']:
        changes['frame_generation'] = 0
        reasons.append(t('Für einen Vergleich zunächst ohne Zwischenbilder messen.',
                         'Measure without generated frames first to establish a comparison.'))
        return changes, reasons
    if summary['steady_seconds'] >= 30 and summary['gpu_slow_seconds'] >= summary['steady_seconds'] / 2:
        # One step at a time. Leave dynamic resolution and unrecognized/custom values alone.
        lower = {'1': 2, '2': 3, '3': 5, '5': 4}
        if values['resolution'] in lower and values['dlss'] not in ('2', '5'):
            changes['resolution'] = lower[values['resolution']]
            reasons.append(t('Die GPU war in vielen ruhigen Abschnitten langsam: Render-Auflösung eine Stufe senken.',
                             'GPU time was high in many steady windows: reduce render resolution by one step.'))
    elif cpu_pressure(summary):
        # Lower scene work, not image resolution, when CPU rendering is the measured limit.
        for key, lower in (('view_distance', {'4': 3, '3': 2, '2': 1, '1': 0}),
                           ('grass', {'4': 3, '3': 2, '2': 1, '1': 0})):
            if values[key] in lower:
                changes[key] = lower[values[key]]
        if any(k in changes for k in ('view_distance', 'grass')):
            reasons.append(t('Hohe Renderer-CPU-Zeit bei FPS-Einbrüchen: Sichtweite und Gras jeweils eine Stufe kleiner testen.',
                             'High renderer CPU time during FPS drops: test one lower step for view distance and grass.'))
        if values['frame_rate_cap'] in ('1', '2', '3', '4', '5', '6'):
            changes['frame_rate_cap'] = 0
            reasons.append(t('Das bisherige FPS-Limit liegt über 60: zum Vergleich auf 60 begrenzen.',
                             'The current frame-rate limit is above 60: cap it at 60 for the comparison.'))
    if summary.get('device_memory_errors', 0) or summary['vram_pressure_seconds'] >= 15:
        # Auto also needs an actionable suggestion when the measured budget stays full.
        # This is an upper limit; the renderer still enforces its lower hardware budget.
        lower_budget = {'0': 1, '2': 1, '3': 2, '4': 3, '5': 4, '6': 5}
        if values['texture_memory'] in lower_budget:
            changes['texture_memory'] = lower_budget[values['texture_memory']]
            reasons.append(t('GPU-Speicherfehler oder anhaltend knappes Speicherbudget: kleineren Texturcache testen.',
                             'GPU memory errors or sustained memory pressure: test a smaller texture cache.'))
    if changes and values['quality_preset'] != '0':
        changes['quality_preset'] = 0
    if not changes:
        reasons.append(t('Keine eindeutige automatische Anpassung. Bei Rucklern die gleichen Szenen erneut vergleichen.',
                         'No clear automatic adjustment. Compare the same scenes again when investigating stutter.'))
    return changes, reasons
