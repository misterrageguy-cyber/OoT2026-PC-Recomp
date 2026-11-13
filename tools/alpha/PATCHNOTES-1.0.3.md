**Ocarina Reborn v1.0.3 — Classic HUD, graphics and stability**

**🎮 Classic HUD and Link voices**

- **Classic counters (N64):** the rupee counter appears in the bottom-left corner after loading a save. Pickup counters above Link are hidden, including rupees, arrows and bombs. Enable it in Settings → Gameplay or the F1 menu.
- **Classic voices are now included:** in Settings → Audio, choose **Default** or **Classic (N64)** separately for Young Link and Adult Link. No separate download or ZIP import is needed. The launcher prepares the voice automatically on first selection; click **Save** and restart the game.
- Classic voices cover supported gameplay actions such as attacks, damage, jumping and climbing. Dedicated cutscene voice entries remain unchanged.

**🎨 Graphics and engine update**

- **FXAA** edge smoothing, plus adjustable **view distance, grass density and shadow distance**.
- Engine updated to **v2.2.0-rc.1**: V-Sync Auto / On / Off, expanded FPS and frame-time displays, field of view, camera speed and intro skipping.
- Custom ocarina-note keys and a second gamepad mapping. The F1 menu is organized into sections and supports 13 languages.
- FSR 4 with native HDR, an uncapped frame-rate option, and engine fixes for sound and water above 60 FPS, gyro after Alt+Tab and changing audio devices.

**🛠️ Stability and fixes**

- **RAM guard:** also reacts to low physical RAM and nearly full video memory, helping reduce long freezes under memory pressure.
- **Texture memory Auto:** limited to 40% of system RAM to reduce memory pressure, especially on 16 GB PCs.
- **AMD RX 6000:** automatic Compute mesh shaders to address GPU crashes.
- **Death counter:** a fairy revival no longer counts as a death.
- **Startup screen:** follows the game language and fixes broken accented characters.
- **Launcher settings:** preset buttons stay in Quality and no longer cover settings. All categories remain reachable in smaller windows.
- **Preset fixes:** corrected saved values, a Performance FPS target, compact texture-memory recommendations for 8 GB cards, and warnings about Parsec or Virtual Desktop.
- Custom options no longer invalidate the entire shader cache. The engine upgrade itself still requires a one-time shader rebuild.

**ℹ️ Updating**

- Updating from **1.0.2** rebuilds the game once for the new engine. The first launch also prepares the updated shaders. Your saves and settings are kept.
- Selecting a classic voice does **not** rebuild the engine or shaders. Its local audio preparation is cached for later use.
- Please share fresh **Debug Packages in #logs**, especially from lower-end PCs. For voice issues, include which Link, the action and the location; a short recording helps.

Thanks for testing and helping improve Ocarina Reborn! 💙

https://ocarina-pc-native-build.github.io/

SHA-256: `0916c7330f9ddc54b6fc4af6ead61b3d73df5b0b2a8a869c2accb877ef51980d`
