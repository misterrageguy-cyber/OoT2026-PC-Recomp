Ocarina Reborn 1.0.2

This project is still in active development.
Compatibility, performance and stability vary by hardware and game area.

1. Install Ocarina Reborn (double-click Ocarina-Reborn-Alpha-Setup.exe).
2. Launch it.
3. Select your own Ocarina of Time 1.1.1 game file (.nup).
4. Wait for the preparation (the first time only; it needs about 45 GB of free space).
5. Play. Try different areas.
6. If something breaks, click "Create Debug Package" and send me the ZIP.
   Tell me what you were doing when it happened.

You need Windows 10 or 11 (64-bit) and an up-to-date AMD or NVIDIA graphics driver.
Your game file stays on your PC: it is never changed and never uploaded.

1.0.2 classic gameplay voices (local test)
-----------------------------------------
Settings > Audio has separate voice choices for Young Link and Adult Link.
Import your OOT_YoungLink.zip / OOT_AdultLink.zip, select Classic (N64), then Save.
Attacks, damage, jumps and other mapped gameplay actions use the imported voices.
Dedicated cutscene voice entries and other characters are left unchanged.
Restart the game after changing a voice. Default restores that age's current voices.

The launcher generates local RomFS mods; original game files and saves stay unchanged.
No voice recordings are included in the installer. If the game's audio banks change
after a game-data update, reimport the ZIPs before enabling their classic voices again.
Test both ages: attacks, jump attacks, taking damage, rolling, jumping and climbing.
Check the timing and volume as well as switching each age back to Default.
Playback in the game still needs listening tests; file conversion tests alone do not
prove that every event sounds correct.

1.0.0 performance tools and experimental texture saving
-----------------------------------------------------
After installing, rebuild the game in the launcher so the renderer changes are compiled.

- Performance presets leave frame generation off. The performance preset uses at most
  1080p output; integrated graphics start at 720p. CPU cores and RAM also inform the recommendation.
- Play the same route for at least 60 seconds, with F1 closed, then exit normally.
  The launcher's Performance button shows actual game FPS, per-window P95/P99 frame times,
  hitch counts and renderer CPU/GPU times. A suggested adjustment is shown before it is applied.
  Measurements and previous settings are saved in the app's Reports folder.
- Settings > Memory > Texture saving (test): Off / 1024 / 512.
  This experimental option reduces stored mip levels only for large, coarse ASTC 2D arrays.
  It is off by default. Try 1024 first, restart, and repeat the same route. Compare terrain,
  lighting and transitions as well as VRAM and stutter. Off + restart restores the original policy.

Frame-time percentiles describe individual five-second windows, not the entire session.
Loading can still appear in the measurements. No low-end performance gain is claimed until
these builds have been compared on the target PCs. Texture saving remains experimental and optional.
