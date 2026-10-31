#!/usr/bin/env python3
"""Require GNU ld trace to resolve a symbol from the expected LLVM archive."""
from pathlib import Path
import re
import sys

log_path, archive_name, symbol = sys.argv[1:]
text = Path(log_path).read_text()
archive = Path(__file__).resolve().parent / 'tools/llvm20/lib/clang/20/lib/linux' / archive_name
pattern = re.escape(str(archive)) + r'\([^\n)]+\): definition of ' + re.escape(symbol) + r'(?:\s|$)'
if not re.search(pattern, text):
    raise SystemExit(f'No verified archive provider for {symbol}: expected {archive}; see {log_path}')
print(f'Confirmed {symbol} is supplied by {archive}')
