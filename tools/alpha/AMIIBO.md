# amiibo files (experimental, read-only)

Select your own raw NTAG215 `.bin` in **Launcher → Settings → amiibo** or
**F1 → Gameplay → Load amiibo (.bin)**. Supported dump sizes are 532, 540 and
572 bytes (the last includes a reader signature). Enable the game's amiibo
feature under **System → Options → amiibo**. Select the amiibo icon in **Items**,
close the menu and press your **Use Item** button in a suitable open area.
No restart is needed to change the selected file.
If replacing a figure during a scan, cancel that scan and start another.

**Remove amiibo** removes the reader's private selection. The original file is
never edited. No figures, tag dumps, keys or downloads are included. Normal
game restrictions, supported figures and reward limits still apply; the reader
keeps the tag's original identity and does not randomize it.

The reader supports tag/model identification for the game's reward path.
Encrypted owner/application data, registering or repairing a figure, and saving
game data to a tag are not supported. These operations return failure, rather
than claiming to have written anything. The importer checks structure and UID
check bytes; it does not authenticate cryptographic signatures. Internal or
decrypted amiitool layouts are rejected.

## Implementation

- `launcher/amiibo.py`: bounded validation, private copy and atomic selection.
- `hud/ocr_amiibo_file.h`: identical native validation and game-folder lookup.
- `hud/ocr_amiibo.c`: one virtual NFP reader, lifecycle, SDK output structures,
  polling/event notification, stable mounted-tag identity and read-only errors.
- `hud/ocr_amiibo_menu.h`: asynchronous Windows file picker; the renderer keeps
  running while the dialog is open. Cancel or an invalid file keeps the previous
  selection.
- `engine_amiibo.py`: checked staging patches. The new HLE names enter the
  engine's existing translation key, so installed games rebuild their code once.
  Renderer ABI and shader translation inputs are unchanged.

The selected private file is `ocarina_reborn_amiibo.bin` in the game folder.
It also works when launching the game executable directly. No serial numbers or
source paths are logged, and the debug-package collector does not include it.

The native ABI/state definitions were checked against
[libnx nfc.h](https://github.com/switchbrew/libnx/blob/master/nx/include/switch/services/nfc.h).
Raw tag order versus internal order was checked against
[amiitool's format conversion](https://github.com/socram8888/amiitool/blob/master/amiibo.c).
The implementation contains no code copied from a game executable.

## Validation

`tests/test_amiibo.py` uses invented bytes, not real figure dumps. It checks
accepted sizes, malformed/truncated files, Unicode paths, cancellation-safe
replacement, original-file preservation, native discovery/mount/read/remove
transitions, guest buffer bounds, events, exact model byte order, and rejected
write operations. The native fixture compiles the production C reader with only
guest memory and OS event calls substituted. It needs a Windows C compiler.

Local validation on 2026-11-13: 88 project tests passed and the complete native
game and Vulkan renderer built with no compile failures. In a separate game
folder with copied saves, the user's Young Link and Young Zelda files both
completed a scan and spawned their respective masks. The Princess Mask was
picked up and confirmed by the game's item message. Repeated scans, switching
figures without restarting and removing a selected file were also exercised.
The original files and original saves were not changed. Other figures and
their game-specific reward restrictions still need wider testing.

For isolated automated runs, use the documented control bridge with
`HOS_HEADLESS=1` and **without** `HOS_INPUT_SCRIPT_BACKGROUND=1`: bridge input
already works in the background, while that script flag also admits physical
keyboard/controller input. Otherwise typing in another app can interfere with
the scan or move Link during a test.
