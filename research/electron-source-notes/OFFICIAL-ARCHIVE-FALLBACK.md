# Official Chromium 138.0.7204.100 archive fallback

Both archives exist in Google's official `chromium-browser-official` storage bucket. The full archive HEAD request returned HTTP 200. The bucket listing independently confirms exact filenames, object generations and sizes. Official `.hashes` files provide SHA-256 and other digests.

| Archive | Compressed bytes | SHA-256 |
| --- | ---: | --- |
| chromium-138.0.7204.100.tar.xz | 7,269,991,840 | 368d1a1d73c8703b9f9252340680468e3e3073b33b5127ac9e5fd8e9431b18b8 |
| chromium-138.0.7204.100-lite.tar.xz | 1,555,634,580 | d90cc0bd3075f2a9646e0e254aa9cf1865ebf8bf7adf484126f34bb401212f02 |

The full archive is 6.77 GiB; the lite archive is 1.45 GiB. There is also a separate 922,983,008-byte test-data archive. Exact URLs and immutable object generations are in `official-chromium138-archives.json`.

## Source coverage and limitations

The official publishing recipe first checks out the Chromium release tag and runs `gclient sync -D --no-history`, then exports that completed source checkout. This is a distribution source archive with checked-out dependencies, not merely an archive of Chromium's top-level Git repository. It is a credible fallback for Linux source dependencies such as V8, Skia, FFmpeg and other DEPS-managed source repositories.

This does not mean it contains every optional dependency for every operating system. Checkout conditions still apply. Electron's own additional dependencies, including `third_party/electron_node` at Node v22.17.0 and NAN, are outside generic Chromium and must still be fetched separately.

The current official lite recipe removes Android/iOS/Chromecast content and purges build tools or large build-only content such as LLVM sources, LLVM prebuilts, Rust sources/toolchain, bundled Linux Node, Debian x64/x86 sysroots, reclient, some test suites and performance benchmarks. The regular full export also strips nonessential tests and resources. GN/GNI/GRD/GRDP/isolate/pydeps files are intentionally preserved where required by graph generation. Lite is the natural fallback for this build because external UOS-compatible compilers, Rust and a UOS sysroot are being supplied separately.

**All `.git` directories are excluded**, as the official exporter explicitly documents. Thus an archive is not interchangeable with a gclient-managed Git checkout: Electron's patch hook needs Git state, or the patch stacks must be applied in manifest order directly. Re-running a normal gclient Git sync over an unpacked archive without a separate plan can cause expensive replacement downloads. The exported archive also excludes CIPD bootstrap internals and build output.

Evidence retained locally:

* `chromium138-full.hashes` and `chromium138-lite.hashes`: official digest files.
* `official-publish_tarball.py`: official recipe, including tag checkout, gclient sync and lite exclusion lists.
* `official-export_tarball.py`: official export script, including explicit `.git` exclusion and preservation rules.

Evidence URLs:

* <https://storage.googleapis.com/chromium-browser-official/?prefix=chromium-138.0.7204.100>
* <https://chromium.googlesource.com/chromium/tools/build/+/refs/heads/main/recipes/recipes/publish_tarball.py>
* <https://chromium.googlesource.com/chromium/tools/build/+/refs/heads/main/recipes/recipe_modules/chromium/resources/export_tarball.py>

No large source archive was downloaded for this investigation. Coverage conclusions use the official current packaging code; the historical 2025 recipe revision and every member of the specific archive have not been independently inspected. The parent is currently making progress with the official Chromium GitHub mirror, so this remains a documented fallback.
