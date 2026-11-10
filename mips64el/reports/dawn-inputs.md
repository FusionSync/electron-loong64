# Dawn 生成输入恢复记录

2026-11-10，Electron 37.2.2 的 MIPS64EL / Buster 构建发现两个缺失输入。
原因是复用的独立源码工作目录未完整填入嵌套依赖，也未生成该版本文件。
它们均由上游 DEPS 和 hooks 定义，无需修改 Dawn 代码或 GN 配置。

| 输入 | 上游定义 | 恢复结果 |
| --- | --- | --- |
| `gpu/webgpu/DAWN_VERSION` | Chromium DEPS 的 `lastchange_dawn` hook | 与固定的 Dawn revision `86772f20cca54b46f62b65ece1ef61224aef09db` 一致 |
| `third_party/dawn/third_party/khronos/OpenGL-Registry/xml/gl.xml` | Dawn DEPS 的 OpenGL-Registry 依赖 | 固定 revision `5bae8738b23d06968e7c3a41308568120943ae77` |

版本文件使用原始 hook 在源码 workspace 执行生成：

```bash
python3 src/build/util/lastchange.py \
  -s src/third_party/dawn \
  --revision src/gpu/webgpu/DAWN_VERSION
```

OpenGL-Registry 从 Khronos 官方仓库
<https://github.com/KhronosGroup/OpenGL-Registry> 获取，与 DEPS 中的
Chromium 镜像保持相同 commit。本次独立 Git checkout 仅展开 `xml/gl.xml`，
没有复制其他架构的源码树。Git 工作目录干净，HEAD 为上述固定 revision。

该文件大小为 2,750,041 字节，XML 根节点为 `registry`。
Git blob 为 `9a1b2e343d3acc5c25abce87df06f9a7cb8568e8`，与官方 GitHub
该 commit 的 Contents API 返回值一致。SHA256：

```text
a0d22b883dfe2698002475c658bdc2ec4ba5c01d0a9aac38b707d7aaf9812b34
```

恢复后，原始 `dawn_version_generator.py` 和 `opengl_loader_generator.py`
命令分别输出到临时目录，均返回 0；主构建输出未被这些检查修改。
这验证了缺失输入已恢复，不代表 Dawn 或完整 Electron 已构建完成。

公开的干净构建流程使用递归 `gclient sync` 和 `gclient runhooks` 获取这些输入，
并在 hooks 后检查关键文件，避免在后续编译时才发现同步不完整。
