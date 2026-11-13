# Distribution review

Public installer downloads are paused. Previous packages contained bundled voice recordings and project media whose distribution rights were not established. Those packages have been withdrawn. Existing local installations are unaffected by this pause.

The current source removes the bundled recordings, launcher music and previous artwork. The launcher imports only user-selected voice ZIPs. It does not download recordings or game files. New project graphics are generated from original geometric shapes and the project name by `tools/alpha/make_project_art.py`; hashes and origin are recorded in `tools/alpha/MEDIA-PROVENANCE.json`.

Hookshot and other upstream copyright notices, GPL source and third-party licenses remain intact. Removing media does not change those licenses. Historical source references are being cleaned of the same withdrawn media; old installer checksums are historical records, not available downloads or endorsements of redistribution.

Before publishing source or an installer, run:

```text
python tools/alpha/distribution_guard.py <source-or-stage-directory>
```

The staging script runs this check automatically. Never distribute ROMs, game containers, encryption keys, translated game code, built game executables, imported mods or recordings without appropriate distribution rights. Local game preparation and debug packages belong outside the public source tree.

The automated check is a technical safeguard, not a legal opinion or a guarantee against platform action. Only reviewed artifacts should be released. Do not restore withdrawn assets from local backups, old tags or previous installers. Assess new media separately and record its provenance.
