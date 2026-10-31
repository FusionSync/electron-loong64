# Electron on UOS: minimal runtime checks

These scripts are prepared for the final unpacked Electron distribution. They
have not yet been executed on UOS. The separate `audit-dist.py` checks package
contents and ELF compatibility; the earlier LLVM/Rust probes validate the
toolchain. Neither substitutes for this Electron runtime check.

Copy this directory alongside the complete, unpacked distribution, retaining
Electron's executable permissions and companion files. Run on the real UOS
machine as the logged-in desktop user. No system packages, npm modules, SSH
connection, remote execution, or sandbox permission changes are made by these
scripts.

```bash
# Existing UOS desktop session confirmed on 2026-10-29; use its current values.
export DISPLAY=:0
export XAUTHORITY=${XAUTHORITY:-$HOME/.Xauthority}
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
export XDG_SESSION_TYPE=${XDG_SESSION_TYPE:-x11}
bash runtime-validation/run.sh /path/to/electron-dist/electron
```

The desktop environment is inherited, never guessed or overwritten by the
runner. The example is for the existing UOS X11 desktop, not SSH X forwarding.
The same user's `xdpyinfo` and `unshare --user --map-root-user true` probes
passed on 2026-10-29; this does not validate Chromium's complete sandbox.
An optional second argument chooses a **new** results directory; existing
directories are rejected. Defaults are Electron `37.2.2` and Node architecture
`loong64`, matching the current generated `NODE_ARCH`. Override only for an
intentional build change:

```bash
UOS_EXPECTED_ELECTRON_VERSION=37.2.5 \
  bash runtime-validation/run.sh /path/to/electron-dist/electron ./new-results
```

Each stage writes separate stdout/stderr logs and an exit code:

- `version`: runs `electron --version` and verifies the expected version.
- `node`: uses `ELECTRON_RUN_AS_NODE=1`, verifies standalone Node mode and Linux/architecture/Electron
  version, and records Node, Chromium, V8 and other `process.versions` values.
- `renderer`: opens a real BrowserWindow, loads only the local page, verifies
  page JavaScript, `executeJavaScript`, canvas pixels, context isolation and
  the renderer's sandbox report, saves `renderer.png`, then quits normally.

`summary.tsv` and `overall.exit` describe the run. Exit zero requires all three
stages and a normal renderer exit. A missing display is recorded as skipped
and makes the overall result unsuccessful. Startup failures and timeouts
remain failures even when no renderer JSON could be written. The runner uses
GNU `timeout` (30 seconds per CLI check, 90 seconds for the window); no external
Node installation is required. The application stores its disposable profile
inside the new evidence directory, keeping the user's ordinary profile separate.

Sandboxing remains enabled, with explicit `sandbox: true`,
`contextIsolation: true`, and `nodeIntegration: false`. There is no
`--no-sandbox` fallback and no automatic chmod/chown of `chrome-sandbox`.
If UOS rejects sandbox startup, preserve the logs and diagnose its actual
user-namespace/setuid-helper configuration before retrying. The reported
`process.sandboxed` and optional `/proc` fields are observations, not a complete
sandbox security audit.

GPU feature status/basic device information and child-process failures are
recorded as information only. A successful screenshot does not certify hardware
acceleration, WebGL/Vulkan, codecs, native modules, Crashpad uploads, printing,
or all Electron APIs; those require their own targeted checks. Screenshots
capture this application's web contents, not the user's desktop.
