import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import advisor
import game_settings
import performance


def sample(*, frames=200, seconds=5, cpu=8, gpu=23, used=2, budget=4, known=True,
           menu=0, complete=1, fg=0, draws=1500, worst=40, wait=0, p95=28, p99=35, h50=0, h100=0):
    return (f'[perf] fps {frames / seconds:.1f} | frame {seconds * 1000 / frames:.1f} ms avg, {worst:.1f} ms worst | '
            f'CPU (renderer) {cpu:.1f} ms | GPU {gpu:.1f} ms | VRAM {"" if known else "? "}{used:.2f} / {budget:.2f} GB | '
            f'textures 100 (1000 MB) | draws {draws} (0.0 skipped, 0.0 not ready) | dispatches 10 | uploads 0.00 MB | '
            f'new pipelines 0, waits 0.00 ({wait:.1f} ms) | programs translated 0, failed 0 (all: 0) | '
            f'stats2 seconds {seconds:.3f} frames {frames} p95 {p95:.2f} p99 {p99:.2f} over50 {h50} over100 {h100} '
            f'menu {menu} complete {complete} fg {fg}')


class Measurements(unittest.TestCase):
    def test_weighted_fps_and_hitch_counts(self):
        s = performance.summarize([sample(), sample(frames=100, seconds=10, worst=160, h50=4, h100=2)])
        self.assertEqual(s['fps'], 300 / 15)
        self.assertEqual((s['over50'], s['over100']), (4, 2))
        self.assertEqual(s['worst_ms'], 160)

    def test_menus_low_draws_and_overflow_do_not_qualify(self):
        self.assertIsNone(performance.summarize([sample(menu=1), sample(draws=4), sample(complete=0)]))

    def test_legacy_log_is_not_new_measurement(self):
        self.assertIsNone(performance.summarize([sample().split(' | stats2')[0]]))

    def test_corrupt_numeric_log_is_ignored(self):
        self.assertIsNone(performance.summarize([sample().replace('p95 28.00', 'p95 28..0')]))

    def test_missing_cpu_counter_does_not_guess_gpu_bottleneck(self):
        s = performance.summarize([sample(cpu=0)] * 6)
        settings = {'resolution': 1}
        self.assertFalse(performance.suggest(s, settings, performance.signature(settings))[0])

    def test_excluded_new_samples_do_not_fall_back_to_old_diagnostics(self):
        diag = advisor.diagnose([sample(menu=1)] * 6)
        self.assertIn('keine auswertbaren', diag[0][1])

    def test_corrupt_counts_and_percentiles_rejected(self):
        self.assertIsNone(performance.summarize([sample(h50=1, h100=2), sample(p95=40, p99=20)]))

    def test_unknown_vram_does_not_trigger_pressure(self):
        s = performance.summarize([sample(used=6, budget=4, known=False)] * 6)
        self.assertEqual(s['vram_pressure_seconds'], 0)

    def test_framegen_is_counted_as_game_frames_and_disabled_first(self):
        s = performance.summarize([sample(fg=2)] * 6)
        settings = {'resolution': 1, 'frame_generation': 2}
        changes, _ = performance.suggest(s, settings, performance.signature(settings))
        self.assertEqual(s['fps'], 40)
        self.assertEqual(changes, {'frame_generation': 0})

    def test_minimum_duration_and_stale_settings(self):
        settings = {'resolution': 1}
        old = performance.signature(settings)
        for summary, current in ((performance.summarize([sample()] * 5), settings),
                                 (performance.summarize([sample()] * 6), {'resolution': 4})):
            self.assertFalse(performance.suggest(summary, current, old)[0])

    def test_gpu_bound_reduces_one_step_but_cpu_bound_does_not(self):
        settings = {'resolution': 1}
        sig = performance.signature(settings)
        gpu = performance.summarize([sample()] * 6)
        cpu = performance.summarize([sample(cpu=25, gpu=6)] * 6)
        self.assertEqual(performance.suggest(gpu, settings, sig)[0], {'resolution': 2})
        self.assertFalse(performance.suggest(cpu, settings, sig)[0])

    def test_loading_and_compile_stalls_do_not_reduce_resolution(self):
        settings = {'resolution': 1}
        for line in (sample(worst=1000), sample(wait=10)):
            s = performance.summarize([line] * 6)
            self.assertFalse(performance.suggest(s, settings, performance.signature(settings))[0])

    def test_dynamic_and_native_aa_left_alone(self):
        s = performance.summarize([sample()] * 6)
        for settings in ({'resolution': 0}, {'resolution': 1, 'dlss': 2}, {'resolution': 1, 'dlss': 5}):
            self.assertFalse(performance.suggest(s, settings, performance.signature(settings))[0])

    def test_memory_pressure_and_custom_preset(self):
        s = performance.summarize([sample(gpu=6, used=3.8)] * 6)
        settings = {'texture_memory': 2, 'quality_preset': 3, 'texture_saving': 0}
        changes, _ = performance.suggest(s, settings, performance.signature(settings))
        self.assertEqual(changes, {'texture_memory': 1, 'quality_preset': 0})
        self.assertNotIn('texture_saving', changes)

    def test_percentile_description_states_window_scope(self):
        description = performance.describe(performance.summarize([sample()]), False)
        self.assertIn('Worst 5-second window', description[1][1])


class Profiles(unittest.TestCase):
    def test_low_end_uses_cpu_ram_and_no_framegen(self):
        facts = dict(gpus=[('NVIDIA GeForce RTX 3060', 12)], cpu_cores=4, cpu_threads=8, ram_gb=16)
        key, profile, *_ = advisor.recommend(facts)
        self.assertEqual(key, 'performance')
        self.assertEqual(profile['frame_generation'], 0)
        self.assertEqual(profile['output_res'], '1920x1080')
        self.assertEqual(profile['shader_threads'], 1)
        self.assertNotIn('texture_saving', profile)

    def test_vram_alone_does_not_choose_quality(self):
        key, *_ = advisor.recommend(dict(gpus=[('NVIDIA GeForce RTX 3060', 12)], cpu_cores=8, ram_gb=32))
        self.assertEqual(key, 'balanced')

    def test_integrated_memory_and_resolution(self):
        facts = dict(gpus=[('AMD Radeon(TM) Graphics', 0.5)], cpu_threads=8, ram_gb=16)
        p = advisor.build_preset('performance', facts)
        self.assertEqual((p['output_res'], p['dlss'], p['frame_generation']), ('1280x720', 0, 0))

    def test_performance_does_not_enable_fsr4_by_vendor(self):
        p = advisor.build_preset('performance', dict(gpus=[('AMD Radeon RX 7900 XTX', 24)]))
        self.assertEqual(p['dlss'], 3)

    def test_low_memory_and_unknown_hardware(self):
        key, *_ = advisor.recommend(dict(gpus=[('AMD Radeon RX 7900 XTX', 24)], ram_gb=8, cpu_cores=8))
        self.assertEqual(key, 'performance')
        self.assertEqual(advisor.recommend(dict(gpus=[]))[0], 'performance')

    def test_experimental_option_roundtrip_and_reset(self):
        with tempfile.TemporaryDirectory() as d:
            game_settings.write(d, {'texture_saving': 2, 'volume': 75, 'output_res': '1280x720'})
            self.assertEqual(game_settings.read(d)['texture_saving'], '2')
            game_settings.reset(d)
            self.assertEqual(game_settings.read(d), {'volume': '75'})
        self.assertEqual(game_settings.DEFAULTS['texture_saving'], 0)

    def test_output_signature_accepts_legacy_and_size(self):
        self.assertEqual(performance.signature({'output_res': 3}), performance.signature({'output_res': '1920x1080'}))


def run_summary(seconds=120, fps=60.0, over50=2, over100=0, p99=40.0):
    return dict(schema=2, seconds=seconds, fps=fps, over50=over50, over100=over100, p99_worst_window=p99)


class RebornAuto(unittest.TestCase):
    def test_short_runs_give_no_verdict(self):
        verdict, lines = performance.compare(run_summary(seconds=30), run_summary(), de=False)
        self.assertIsNone(verdict)
        self.assertIn('60', lines[0])

    def test_missing_run_gives_no_verdict(self):
        self.assertIsNone(performance.compare(None, run_summary())[0])

    def test_fewer_hitches_and_more_fps_is_better(self):
        verdict, _ = performance.compare(run_summary(fps=45, over50=20, over100=6, p99=120),
                                         run_summary(fps=55, over50=4, over100=0, p99=60))
        self.assertEqual(verdict, 'better')

    def test_slower_with_more_hitches_is_worse(self):
        verdict, _ = performance.compare(run_summary(fps=58, over50=2), run_summary(fps=50, over50=12, p99=90))
        self.assertEqual(verdict, 'worse')

    def test_noise_is_the_same(self):
        verdict, _ = performance.compare(run_summary(fps=59.5, over50=3), run_summary(fps=60.0, over50=2))
        self.assertEqual(verdict, 'same')

    def test_hitches_compared_per_minute(self):
        # twice as long, twice the hitches: the same rate
        verdict, _ = performance.compare(run_summary(seconds=60, over50=10), run_summary(seconds=120, over50=20))
        self.assertEqual(verdict, 'same')


if __name__ == '__main__':
    unittest.main()
