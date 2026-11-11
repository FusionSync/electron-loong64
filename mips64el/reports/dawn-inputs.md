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

随后检查了 release 的 Dawn native / OpenGL 依赖：`khronos_platform` 需要
EGL-Registry 的 `api/KHR/khrplatform.h`，生成的 native 编译规则也包含该库的
`api` 路径，因此在构建走到这些源文件前，主动恢复了完整 `api` 子树的 10 个文件。
来源为 Khronos 官方 EGL-Registry 固定 commit
`7dea2ed79187cd13f76183c4b9100159b9e3e071`。文件从官方 API/raw 获取，逐个
核对该 commit 的 Git blob 后写入，来源 URL、大小和 SHA256 记录在
[egl-registry-inputs.json](egl-registry-inputs.json)。

`api/egl.xml` 通过 XML 解析，`EGL/egl.h`、`EGL/eglext.h` 和
`KHR/khrplatform.h` 通过实际 Buster 交叉编译器的头文件编译检查；
`EGLAttrib` 和 `khronos_uintptr_t` 的 N64 尺寸均为 8 字节。

外部 `webgpu-headers/src` 在 Dawn DEPS 中明确用于测试。当前 release 从
Dawn JSON 生成 `webgpu-headers/webgpu.h`，生成的 release 构建规则未引用
外部测试头文件目录，因此本次无需额外获取该测试依赖。干净的公开递归同步流程
仍按上游 DEPS 下载它。
