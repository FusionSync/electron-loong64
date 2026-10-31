#!/bin/sh
set -eu
OUT=/work/electron37-attempt/src/out/UOS37
cd "$OUT"
cp --reflink=auto electron-gldfixed electron
chmod +x electron
python3 ../../electron/build/zip.py dist-gldfixed.zip gen.runtime/electron/electron_dist_zip/electron_dist_zip.runtime_deps loong64 linux false false
