## Ocarina Reborn v1.0.6

### Updates and project media
- Launcher updates are available again through the existing Update button.
- New original launcher graphics; bundled voice recordings, launcher music and the fairy animation have been removed.
- Classic voices now require a voice ZIP supplied by the user. Existing saves and settings are preserved.

### Audio and stability
- Fixed audio voice stop/reset handling and inconsistent playback-status updates. This addresses reproduced audio defects; the reported boss/ocarina music case still needs tester confirmation.
- Bounded temporary capture-buffer allocation to reduce memory pressure during loading.
- Integrated GPUs now get an enforced texture-memory limit; improved AMD integrated-GPU detection.
- Better crash reports, memory/GPU diagnostics and identification of the current session's log.
- Shader preparation failures no longer automatically claim that Vulkan is unsupported.

### Controls and optional imports
- Experimental read-only amiibo support for your own raw NTAG215 .bin files, selectable in the launcher and F1 menu. No tag files or keys are included; encrypted owner data and writing to tags are not supported.
- Removed the Discord link from the F1 menu.

### Updating
Restart the launcher and choose Update, then install over your existing installation. Let the launcher update the game components afterwards; this may take a while. No uninstall or game-file reimport is needed for an existing working installation. Saves and settings stay.
