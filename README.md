# Ocarina Reborn

This repository contains the **Ocarina Reborn launcher, patched engine and build scripts**, and hosts installer releases for RecompStore. The website is [ocarina-pc-native-build.github.io](https://ocarina-pc-native-build.github.io/).

A native Windows x64 version of **The Legend of Zelda: Ocarina of Time (Switch 2)**, built on your PC from your own `.nup` game file.

**Current release: v1.1.8 · November 28, 2026**

[Download the latest release](https://github.com/ocarina-pc-native-build/ocarina-pc-native-build.github.io/releases/latest) · [Website](https://ocarina-pc-native-build.github.io/) · [Discord](https://discord.gg/vDPAcc6JnY)

## Source code

The actual **v1.1.8 source** is here: [engine and renderer](engine/), [game-build pipeline](engine/nx2/), [Ocarina Reborn launcher](tools/alpha/launcher/), [installer/build scripts](scripts/), [custom hooks and graphics](tools/alpha/hud/), [tests](tools/alpha/tests/) and [build instructions](BUILDING.md). The original [engine builder source](engine/builder/) is retained alongside the Ocarina Reborn launcher.

`engine/` contains the already-patched sources used by the released installer, including custom tunic colors and the classic counters fix. Classic-voice preparation imports a user-selected ZIP; recordings are not bundled. `SOURCE-MANIFEST.json` records the engine file hashes and the matching installer SHA-256. GitHub's v1.1.8 source archives contain this project source; the website lives in its separate repository.

## Get started

1. Download `Ocarina-Reborn-Alpha-Setup.exe` from the latest release and install it.
2. Open Ocarina Reborn and read the development-build notice.
3. Select your own supported `.nup` game file in the launcher and build the game.
4. Connect and turn on your controller before starting the game, then launch it from the launcher.

You need Windows x64, a Vulkan-capable graphics card and your own supported game file. The installer does not include the game, ROMs or Nintendo keys. This is an early development release; compatibility, performance and stability vary by hardware and game area.

## Included features

- **Native rendering:** Vulkan graphics, resolution and display settings, widescreen, ultrawide and 9:16 portrait support.
- **Controller support:** Xbox, PlayStation and Switch controllers, with matching button prompts.
- **Graphics options:** AMD FSR 3.1, FSR 4 on supported AMD hardware, and optional NVIDIA DLSS/DLAA through the launcher's separate setup.
- **Launcher tools:** local game building, update checks, save management and settings.
- **Performance tools:** quality, balanced and performance presets, FPS display and diagnostics.
- **Gameplay options:** difficulty and enemy-damage adjustments, cheat tools and control settings.

NVIDIA's DLSS files are downloaded separately through the launcher after accepting NVIDIA's license.

## What's new in v1.1.8

**Ocarina Reborn v1.1.8 — Fixes & Sharper Textures**

**🌙 First adult night**
- A save stuck at 20:00 in the first adult night now runs its clock again in Hyrule Field too, not only outside it.
- The fix is now kept in your save, so the night no longer comes back after loading.
- In the Market, the Temple of Time and the Chamber of Sages the game keeps its own night, as intended.

**🎨 Graphics**
- Sharper textures with **FSR 3.1, FSR 3.1.6 and FSR 4**: the upscaler now gets texture detail for your output resolution instead of the lower render resolution.
- Fixed large dark rectangles on the floor in Ganon's Tower (for example the room of the two Iron Knuckles and its corridor).

**🎮 Controls**
- A stick pushed past 92% now counts as a full push. Some controllers read slightly short of full tilt after a while, which could stop Link from rolling forward.

**ℹ️ Updating**
- Install over your existing version, then let the launcher update the game. The game code is rebuilt once, so it takes a few minutes longer than usual.
- Shader caches stay: no full shader preparation is needed for this update. Saves and settings stay.

**📊 Help us improve**
- If you notice stutters or crashes, press **Ctrl+F8** when it happens, close the game and create a **Debug Package** in the launcher.
- Post it in **#post-your-logs-here** with the area and what happened.

Thanks for testing! 💙

[Full release notes and SHA-256](https://github.com/ocarina-pc-native-build/ocarina-pc-native-build.github.io/releases/tag/v1.1.4) · [All releases](https://github.com/ocarina-pc-native-build/ocarina-pc-native-build.github.io/releases)

## Feedback and troubleshooting

For help or bug reports, join the [Discord](https://discord.gg/vDPAcc6JnY). Include your installed version, CPU/GPU, the steps that reproduce the issue and a fresh debug package created by the launcher. For controller-icon issues, also mention the controller model and whether you rebuilt the game after updating.

## Licenses

The engine is distributed under [GPL-3.0-or-later](engine/LICENSE). Existing copyright and third-party license notices remain with the code. See [license notices and corresponding source](CREDITS.md) for component terms and release sources.

This repository hosts the project source, build instructions and installer releases. Its Pages entry redirects to the main project website.

Ocarina Reborn is an unofficial community project and is not affiliated with Nintendo.

## Support

[Buy Me a Coffee](https://buymeacoffee.com/hotdevilsauce) — optional support for development tools, testing and ongoing work. Support does not purchase a game, early access or a guaranteed feature.

For release maintenance, see the [main repository publishing notes](https://github.com/ocarina-pc-native-build/ocarina-pc-native-build.github.io/blob/main/PUBLISHING.md).