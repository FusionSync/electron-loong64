# PartitionAlloc 的 MIPS64EL 页大小验证

2026-11-10，Electron 37.2.2 的独立 MIPS64EL 源码树验证通过。

Linux MIPS64EL 现在复用 PartitionAlloc 已有的 POSIX 运行时页大小缓存，
通过 `getpagesize()` 获取系统页大小。`PartitionPageShift()` 使用系统页移位加 2，
最大 slot 数量预算按 64 KiB 系统页计算，可覆盖 4、16、64 KiB 页。
没有为通用 MIPS64R2 构建伪造 `_MIPS_ARCH_LOONGSON`。

探针直接包含实际源码的 `partition_page_constants.h`，使用实际 GN 输出的
`partition_alloc/buildflags.h`、Clang 20.1.8 和源码内 libc++ 头文件，以
MIPS64R2 / N64 / hard-float / `-O2` 编译。探针提供缓存变量的存储；生产代码的
同一变量已在 `partition_address_space.cc` 中由相同宏控制定义，无需修改该文件。

程序通过 QEMU 8.2.2 的 `Loongson-3A4000` CPU 模型和完整 Debian Buster
MIPS64EL 运行库执行。前三项用链接器 `--wrap=getpagesize` 模拟页大小，
最后一项直接调用 QEMU 环境中的 `getpagesize()`。

| 验证场景 | 系统页大小 | 系统页移位 | PartitionPage 大小 | PartitionPage 移位 |
| --- | ---: | ---: | ---: | ---: |
| 模拟 4 KiB | 4096 | 12 | 16384 | 14 |
| 模拟 16 KiB | 16384 | 14 | 65536 | 16 |
| 模拟 64 KiB | 65536 | 16 | 262144 | 18 |
| QEMU 实际值 | 4096 | 12 | 16384 | 14 |

同时检查了 `SystemPageSize()`、每个 PartitionPage 含四个系统页、最大 slot
预算和缓存值。全部进程返回 0。该验证覆盖真实头文件中的计算逻辑；完整 allocator
运行和物理 3A4000 的 16 KiB 内核仍需要后续实机测试。

在可访问源码、GN 输出、完整运行库和 QEMU 的交叉编译容器内运行：

```bash
python3 tests/pa-page-sizes/run.py \
  --source-root /work/src \
  --out-dir /work/out/mips64el-clang20 \
  --runtime-root /runtime/mips64el-buster \
  --qemu /usr/bin/qemu-mips64el-static
```

`--sysroot` 默认 `/opt/mips-sysroot`，用于编译链接；`--runtime-root` 必须指向
完整目标运行库。Chromium 的裁剪 sysroot 仅供链接，不能用于运行程序。
可用 `--llvm-root` 指定工具链路径。生成的程序自动写入、清理临时目录，仓库不包含
测试二进制，也不修改主构建输出。
