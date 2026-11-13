**Ocarina Reborn v1.0.4 — Memory protection and graphics fixes**

**🛠️ Memory protection**

- The former RAM guard **Off** option is now **Emergency (512 MB reserve)**, keeping minimum protection active when memory runs short.
- **Auto texture memory** keeps its RAM-based limit in every RAM guard mode. Previously, switching the guard off also disabled this limit.
- The texture cache waits after the last memory-pressure event before growing again, reducing premature refill cycles.
- Launcher diagnostics now detect Windows memory exhaustion and page-file growth even when average FPS looks healthy. Reborn Auto can recommend **RAM guard → Strong** for these failures.

**🎨 Shadows and water**

- Integrated an upstream Hookshot renderer patch for incorrect shadow-map selection in clustered lighting, targeting block/checkerboard artifacts on water and glossy floors. Credit: YakuzaFanA, Hookshot PR #3047.
- This does not claim to fix every cutscene artifact; please retest affected locations and share fresh logs.

**⚡ Performance settings**

- The **Performance** preset now lowers view distance, grass and shadow distance and sets the frame-rate cap to 60 FPS instead of retaining demanding previous values.
- CPU-limited sessions get suggestions for scene detail and a 60 FPS cap, instead of an unnecessary resolution reduction. Loading and shader-compilation pauses are excluded from this recommendation.
- Launcher scene-setting defaults now match the engine, and session logs include those settings.

**ℹ️ Updating and testing**

- Existing 1.0.3 installations will be offered this update. Install it over your current installation; **no game-data reimport or clean reinstall is needed**. Saves and settings are kept.
- The launcher rebuilds the updated game components. The renderer change also requires a **one-time shader-cache rebuild**, so the first start can take longer.
- If you experienced long freezes, set **RAM guard → Strong** in the launcher and retest.
- Validation: **75 automated tests passed**, and the full renderer compiled successfully. Long-session stability and visual results still need in-game confirmation. Please send a fresh **Debug Package in #logs**, with the location and what happened.

Thank you for testing! 💙

https://ocarina-pc-native-build.github.io/

SHA-256: `54f8e5e4b246f854ae656f3c840fc178175e299e6b016c50d020ccd7bc8b8aea`
