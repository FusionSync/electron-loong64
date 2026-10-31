# Electron 37.2.2 Loong64 UOS release bundle

这是 Electron 37.2.2 LoongArch64 修正版的统一下载包，目标系统是 UOS Loong64。

## 内容

`artifacts/electron-v37.2.2-linux-loong64.zip` 是主运行包。它已经包含 Chromium 内核相关文件，包括：

- Electron/Chromium 主程序
- `libffmpeg.so`
- `libEGL.so`、`libGLESv2.so`、`libvulkan.so.1`
- `resources.pak`、`chrome_100_percent.pak`、`chrome_200_percent.pak`
- `chrome-sandbox`、`chrome_crashpad_handler`
- V8 snapshot、ICU 数据、语言包和默认资源

单独的 `ffmpeg-v37.2.2-linux-loong64.zip` 用于替换或单独检查 ffmpeg；正常运行 Electron 时，主 Electron ZIP 内已有一份 `libffmpeg.so`。

`mksnapshot-v37.2.2-linux-loong64.zip` 是构建阶段工具包，不是运行 Electron 必需文件。`chromedriver` 是 Loong64 WebDriver，`libcxx*` 和 Node headers 用于开发或重新编译。

`tests/electron-pages-test` 是真实网页测试，包含小红书、哔哩哔哩和百度页面；`tests/electron-test` 是本地动画、Canvas、文件选择、IPC 和网络 API 测试。

## 运行真实网页测试

先解压 Electron 主包（这是 ZIP 文件）：

```bash
mkdir -p runtime
unzip artifacts/electron-v37.2.2-linux-loong64.zip -d runtime
```

在物理桌面 `DISPLAY=:0` 上运行：

```bash
cd tests/electron-pages-test
unset ELECTRON_TEST_PROXY HTTP_PROXY HTTPS_PROXY ALL_PROXY
ELECTRON_TEST_TILE=1 DISPLAY=:0 ../../runtime/electron .
```

只测试小红书：

```bash
ELECTRON_TEST_PAGE=xhs DISPLAY=:0 ../../runtime/electron .
```

测试程序已经针对当前 UOS Loong64 的 Chromium zygote/GPU 崩溃路径内置了软件渲染、`--no-zygote` 和 `--no-sandbox` 设置。B 站如果显示 `ERR_CONNECTION_RESET`，通常是网络访问问题，不代表 Electron 渲染器崩溃。

## 校验

`artifacts/SHASUMS256.txt` 是原始 Electron release assets 的校验文件；顶层 `SHA256SUMS.txt` 包含统一包内资产和测试文件的校验值。

该包只包含正式运行/分发产物和手工测试目录，没有包含几十 GB 的 Chromium 源码、LLVM、sysroot 或中间编译目录。
