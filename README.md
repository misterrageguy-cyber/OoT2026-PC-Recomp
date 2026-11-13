# Ocarina Reborn

This repository contains the **Ocarina Reborn launcher, patched engine and build scripts**, and hosts installer releases for RecompStore. The website is [ocarina-pc-native-build.github.io](https://ocarina-pc-native-build.github.io/).

**Built on [Hookshot](https://github.com/NotRexed/Hookshot) by NotRexed and its contributors.** Hookshot provides the recompilation engine, Vulkan renderer and game-build pipeline. Ocarina Reborn adds its own launcher, installer and project-specific changes. [Source & credits](CREDITS.md) · [Hookshot license](LICENSE-HOOKSHOT)

A native Windows x64 version of **The Legend of Zelda: Ocarina of Time (Switch 2)**, built on your PC from your own `.nup` game file.

**Current release: v1.0.3 · November 13, 2026**

[Download the latest release](https://github.com/ocarina-pc-native-build/ocarina-pc-native-build.github.io/releases/latest) · [Website](https://ocarina-pc-native-build.github.io/) · [Discord](https://discord.gg/vDPAcc6JnY)

## Source code

The actual **v1.0.3 source** is here: [engine and renderer](engine/), [Hookshot game-build pipeline](engine/nx2/), [Ocarina Reborn launcher](tools/alpha/launcher/), [installer/build scripts](scripts/), [custom hooks and graphics](tools/alpha/hud/), [tests](tools/alpha/tests/) and [build instructions](BUILDING.md). The upstream [Hookshot Builder source](engine/builder/) is also retained; our distributed launcher is the Ocarina Reborn launcher linked above.

`engine/` contains the already-patched sources used by the released installer, including the classic counters fix. The launcher includes automatic classic-voice preparation. `SOURCE-MANIFEST.json` records the engine file hashes and the matching installer SHA-256. GitHub's v1.0.3 source archives contain this project source; the website lives in its separate repository.

## Get started

1. Download `Ocarina-Reborn-Alpha-Setup.exe` from the latest release and install it.
2. Open Ocarina Reborn and read the development-build notice.
3. Select your own supported `.nup` game file in the launcher and build the game.
4. Connect and turn on your controller before starting the game, then launch it from the launcher.

You need Windows x64, a Vulkan-capable graphics card and your own supported game file. The installer does not include the game, ROMs or Nintendo keys. This is an early development release; compatibility, performance and stability vary by hardware and game area.

## Included features

- **Native rendering:** Vulkan graphics, resolution and display settings, widescreen and ultrawide support.
- **Controller support:** Xbox, PlayStation and Switch controllers, with matching button prompts.
- **Graphics options:** AMD FSR 3.1, FSR 4 on supported AMD hardware, and optional NVIDIA DLSS/DLAA through the launcher's separate setup.
- **Launcher tools:** local game building, update checks, save management and settings.
- **Performance tools:** quality, balanced and performance presets, FPS display and diagnostics.
- **Gameplay options:** difficulty and enemy-damage adjustments, cheat tools and control settings.

NVIDIA's DLSS files are downloaded separately through the launcher after accepting NVIDIA's license.

## What's new in v1.0.3

- **Included classic Link voices:** in Settings > Audio, choose Default or Classic (N64) independently for Young and Adult Link, then save and restart. Preparation is automatic; no separate voice download or import is needed. Dedicated cutscene voices remain unchanged.
- **Classic counters (N64):** a bottom-left rupee counter after loading a save, with pickup counters above Link hidden.
- **Graphics:** FXAA, view distance, grass density and shadow distance.
- **Engine v2.2.0-rc.1:** expanded FPS/frame-time displays, camera and control options, V-Sync Auto/On/Off, FSR 4 with native HDR and multiple engine fixes.
- **Stability:** stronger physical-RAM/VRAM protection, an automatic texture-memory limit of 40% of RAM and Compute mesh shaders on AMD RX 6000 cards.
- **Fixes:** fairy revivals no longer increase the death counter; localized startup text, corrected presets and accessible settings categories.

**Updating from 1.0.2 rebuilds the game once for the new engine**, with updated shaders prepared on first launch. Saves and settings stay. Selecting a classic voice only prepares its audio files and does not rebuild the engine or shaders.

[Full release notes and SHA-256](https://github.com/ocarina-pc-native-build/ocarina-pc-native-build.github.io/releases/tag/v1.0.3) · [All releases](https://github.com/ocarina-pc-native-build/ocarina-pc-native-build.github.io/releases)

## Feedback and troubleshooting

For help or bug reports, join the [Discord](https://discord.gg/vDPAcc6JnY). Include your installed version, CPU/GPU, the steps that reproduce the issue and a fresh debug package created by the launcher. For controller-icon issues, also mention the controller model and whether you rebuilt the game after updating.

## Project and credits

The released engine is based on [Hookshot v2.2.0-rc.1](https://github.com/NotRexed/Hookshot/tree/v2.2.0-rc.1), by **NotRexed and the Hookshot contributors**, under **GPL-3.0-or-later**. The original copyright, license and third-party notices are retained. Our changes are published alongside the engine. Ocarina Reborn is independently maintained and is not an official Hookshot release.

See [Source & credits](CREDITS.md) for the component links, upstream acknowledgements and license scope. Thanks to the Hookshot team and the projects it builds on for making this work possible.

This repository hosts the project source, build instructions and installer releases. Its Pages entry redirects to the main project website.

Ocarina Reborn is an unofficial community project and is not affiliated with Nintendo.

## Support

[Buy Me a Coffee](https://buymeacoffee.com/hotdevilsauce) — optional support for development tools, testing and ongoing work. Support does not purchase a game, early access or a guaranteed feature.

For release maintenance, see the [main repository publishing notes](https://github.com/ocarina-pc-native-build/ocarina-pc-native-build.github.io/blob/main/PUBLISHING.md).
