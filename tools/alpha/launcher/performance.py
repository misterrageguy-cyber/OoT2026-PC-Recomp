"""Measured-session summaries and conservative, reviewable setting suggestions.

Only versioned game-frame samples from the current renderer qualify for tuning.
Percentiles are per five-second window, never presented as whole-session percentiles.
"""
import math
import re

BASE = re.compile(r'\[perf\] fps ([\d.]+) \| frame ([\d.]+) ms avg, ([\d.]+) ms worst \| CPU \(renderer\) ([\d.]+) ms \| GPU '
                  r'([\d.]+) ms \| VRAM (\??)\s*([\d.]+) / ([\d.]+) GB')
DETAIL = re.compile(r'stats2 seconds ([\d.]+) frames (\d+) p95 ([\d.]+) p99 ([\d.]+) over50 (\d+) over100 (\d+) '
                    r'menu ([01]) complete ([01]) fg (\d+)')
DRAW = re.compile(r'\| draws ([\d.]+)')
PIPELINE = re.compile(r'new pipelines (\d+), waits [\d.]+ \(([\d.]+) ms\)')
DEFAULTS = dict(output_res='2048x1152', resolution=0, dlss=0, frame_generation=0, frame_rate_cap=0,
                texture_memory=0, texture_saving=0, texture_detail=1, texture_filtering=0,
                shader_threads=0, shader_cache=1, pipeline_precompile=1, soft_shadows=1,
                anisotropic_filtering=4, quality_preset=0, handheld_profile=0, frame_pacing=1)
OUTPUTS = {'0': '2048x1152', '1': '2560x1440', '2': '3840x2160', '3': '1920x1080', '4': '5120x1440'}


def signature(settings):
    values = {k: str(settings.get(k, v)) for k, v in DEFAULTS.items()}
    values['output_res'] = OUTPUTS.get(values['output_res'], values['output_res'])
    return values


def hardware_signature(facts):
    facts = facts or {}
    return {'gpus': sorted(n for n, _ in facts.get('gpus', [])),
            'threads': facts.get('cpu_threads'), 'ram_gb': facts.get('ram_gb')}


def summarize(lines):
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
    return dict(schema=2, seconds=seconds, frames=int(frames), fps=frames / seconds,
                p95_worst_window=max(r['p95'] for r in rows), p99_worst_window=max(r['p99'] for r in rows),
                worst_ms=max(r['worst'] for r in rows), over50=int(sum(r['h50'] for r in rows)),
                over100=int(sum(r['h100'] for r in rows)),
                cpu_ms=sum(r['cpu'] * r['frames'] for r in rows) / frames,
                gpu_ms=sum(r['gpu'] * r['frames'] for r in rows) / frames,
                vram_peak_gb=max((r['used'] for r in known), default=0),
                vram_pressure_seconds=sum(r['seconds'] for r in known if r['used'] / r['budget'] > .90),
                steady_seconds=steady_seconds, gpu_slow_seconds=gpu_slow,
                frame_generation=any(r['fg'] for r in rows), windows=len(rows), excluded_windows=excluded)


def describe(summary, de=True):
    if not summary:
        return []
    t = lambda d, e: d if de else e
    s = summary
    return [
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


AUTO_MIN_SECONDS = 60   # (Reborn Auto: a run shorter than this says too little to compare)


def compare(before, after, de=True):
    """Reborn Auto's verdict on two runs of the same scenes: 'better', 'same', 'worse' or None (too little measured), and
    the lines that say why. Per minute for the long-frame counts (two runs are never the same length); a few percent of
    fps or a frame or two either way is noise, not a result."""
    t = lambda d, e: d if de else e
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
    t = lambda d, e: d if de else e
    if not summary or summary.get('schema') != 2 or summary.get('seconds', 0) < 30:
        return {}, [t('Für Vorschläge fehlen mindestens 30 s auswertbare Spielzeit.',
                      'Suggestions need at least 30 seconds of usable play measurements.')]
    if signature(current) != measured_settings:
        return {}, [t('Einstellungen seit der Messung geändert: erst eine neue Runde messen.',
                      'Settings changed since measurement: play another session first.')]
    values = signature(current)
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
    if summary['vram_pressure_seconds'] >= 15:
        lower_budget = {'2': 1, '3': 2, '4': 3, '5': 4, '6': 5}
        if values['texture_memory'] in lower_budget:
            changes['texture_memory'] = lower_budget[values['texture_memory']]
            reasons.append(t('Das gemeldete Speicherbudget war länger fast voll: Texturcache eine Stufe kleiner testen.',
                             'Reported memory budget was nearly full for a sustained period: test one smaller texture-cache step.'))
    if changes and values['quality_preset'] != '0':
        changes['quality_preset'] = 0
    if not changes:
        reasons.append(t('Keine eindeutige automatische Anpassung. Bei Rucklern die gleichen Szenen erneut vergleichen.',
                         'No clear automatic adjustment. Compare the same scenes again when investigating stutter.'))
    return changes, reasons
