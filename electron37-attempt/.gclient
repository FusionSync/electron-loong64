solutions = [
  {
    'name': 'src/electron',
    'url': 'https://github.com/electron/electron.git@102f740ec2fc8f34601c84b79ea1bf06042e8d00',
    'deps_file': 'DEPS',
    'managed': False,
    'custom_deps': {},
    # continue-build.sh applies patches with per-repository recovery records.
    'custom_hooks': [{'name': 'patch_chromium'}],
    'custom_vars': {
      'chromium_version': '5f45b4744e3d5ba82c2ca6d942f1e7a516110752',
      'checkout_configuration': 'small',
      'checkout_js_coverage_modules': False,
      'checkout_pgo_profiles': False,
      'checkout_clang_tidy': False,
      'checkout_telemetry_dependencies': False,
      'checkout_instrumented_libraries': False,
      'install_sysroot': False,
      'use_mtime_cache': False,
    },
  },
]
target_os = ['linux']

