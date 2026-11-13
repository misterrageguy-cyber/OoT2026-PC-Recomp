"""Checked audio stop/reset patch for the pinned Hookshot renderer.

The report is lingering battle music; its exact game scene still needs retesting.
These fixes address reproduced voice cancellation and playback-status defects.
Reference semantics: switchbrew/libnx nx/source/audio/voice.c (audrvVoiceStop,
_audrvVoiceUpdate): stop clears queued buffers and playback position; renderer
status reaches the client together at the update boundary.
"""
from pathlib import Path

MARKER = '/* Ocarina Reborn: coherent voice stop/reset and playback status. */'
CHANGES = (
    ('    int64_t played;\n',
     MARKER + '\n    int64_t played, played_reported;  /* snapshot returned at the last renderer update */\n'),
    ('            if (k->i0 == PLAY_STOPPED && v->state != PLAY_STOPPED) {   /* stopped: every queued buffer is released */',
     '            if (k->i0 == PLAY_STOPPED) {   /* every stop cancels queued buffers, including a primed stopped voice */'),
    ('                v->nwb = 0;\n                v->started_wb = 0;',
     '                v->nwb = 0;\n                v->played = 0;\n                v->pos = 0;\n                v->started_wb = 0;'),
    ('    for (int i = 0; i < MAX_VOICES; i++) voices[i].nrel_seen = voices[i].nrel;   /* (the finished buffers, to the game) */',
     '    for (int i = 0; i < MAX_VOICES; i++) {\n'
     '        voices[i].nrel_seen = voices[i].nrel;\n'
     '        voices[i].played_reported = voices[i].played;\n'
     '    }   /* completed buffers and sample positions describe the same renderer update */'),
    ('    RET(v ? v->played : 0);', '    RET(v ? v->played_reported : 0);'),
    ('    hos_log("audio: renderer opened");',
     '    hos_log("audio: renderer opened");\n'
     '    hos_log("audio: voice stop/reset fix active (queued loops and playback status)");'),
)

# The mixer still needs to apply queued controls if the game stalls for 50 ms.
# That is not a client renderer update: publishing status there can split the
# client's six-speaker query across two snapshots and feed one speaker twice.
TIMEOUT_MARKER = '/* Audio: mixer fallback preserves the client status snapshot. */'
TIMEOUT_CHANGES = (
    ('static void commit(void) {   /* (with the lock held) */\n'
     '    for (int i = 0; i < ncmds; i++) apply(&cmds[i]);\n'
     '    ncmds = 0;\n',
     TIMEOUT_MARKER + '\n'
     'static void apply_pending(void) {   /* (with the lock held; no status publication) */\n'
     '    for (int i = 0; i < ncmds; i++) apply(&cmds[i]);\n'
     '    ncmds = 0;\n'
     '}\n'
     'static void commit(void) {   /* (client RequestUpdateAudioRenderer, with the lock held) */\n'
     '    apply_pending();\n'),
    ('if (ncmds && hos_now_ns() - last_update_ns > 50000000) commit();   /* (no update came: see "parameter updates") */',
     'if (ncmds && hos_now_ns() - last_update_ns > 50000000) apply_pending();   /* controls only: status waits for the client update */'),
    ('    hos_log("audio: voice stop/reset fix active (queued loops and playback status)");',
     '    hos_log("audio: voice stop/reset fix active (queued loops and playback status)");\n'
     '    hos_log("audio: timeout status snapshot fix active (client update boundary)");'),
)


def patch_group(source, marker, changes):
    if marker in source:
        if not all(new in source for _, new in changes):
            raise RuntimeError('Incomplete audio patch: ' + marker)
        return source
    for old, _ in changes:
        if source.count(old) != 1:
            raise RuntimeError('Audio patch anchor changed: ' + repr(old[:90]))
    for old, new in changes:
        source = source.replace(old, new, 1)
    return source


def apply(root):
    path = Path(root) / 'host/nn_audio.c'
    source = path.read_text(encoding='utf-8')
    # Validate both generations in memory before writing; supports the original
    # engine and an existing stop/reset test build without a partial upgrade.
    updated = patch_group(source, MARKER, CHANGES)
    updated = patch_group(updated, TIMEOUT_MARKER, TIMEOUT_CHANGES)
    if updated != source:
        path.write_text(updated, encoding='utf-8', newline='\n')
    print('audio: coherent stop/reset and client status across mixer timeouts')
