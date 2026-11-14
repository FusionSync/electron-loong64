# 3A4000 桌面手工验证

这是后续在 **MIPS64EL / 3A4000 实机桌面**运行的测试应用。目前只检查了 JavaScript 语法，尚未用本次 MIPS Electron 执行；不能据此声明 GUI、GPU、sandbox 或网页兼容性通过。

将整个 `manual-desktop/` 目录复制到目标机器。解压完整 Electron 运行包，在真实桌面的普通用户终端中启动：

```sh
cd /path/to/unpacked-electron
./electron /path/to/manual-desktop/main.js
```

不需要 npm 安装。请保留窗口旁的终端，以便看到 Chromium 原生日志和进程退出信息；不要通过 SSH 随意替换 `DISPLAY`，应使用当前登录桌面的显示会话。

## 逐项观察

1. **动画与 Canvas**：圆点往返、Canvas 彩球持续移动；暂停/继续按钮有效。点击“Canvas 导出 PNG”应生成 data URL，说明 2D 绘制和像素导出链路可用。帧率只供观察，不设性能通过阈值。
2. **文件**：打开小文本、中文文件名和一张 PNG/JPEG；核对文字与图片。取消选择应返回“已取消”，超过 2 MiB 的文件应明确拒绝。仅本地面板可以调用打开文件功能；文字预览不会作为 HTML 执行。
3. **网络**：请求一个可访问的 HTTPS 地址，检查 HTTP 状态与响应预览。该项走 Electron `net.fetch`；15 秒超时、响应最多读取前 64 KiB。HTTP 403/412 等需结合网站访问策略判断。
4. **网页**：点击“两个都打开”，B 站和小红书分别使用独立 `BrowserWindow`，无 iframe。分别观察实际内容、滚动和交互；若手动播放视频，请另行记录画面、声音和所用页面。
5. **GPU 与日志**：记录版本、CPU、GLIBC、GPU 功能状态；关闭网页窗口后确认主面板仍能操作。
6. **视频、音频与 WebGL**：点击“播放测试音”，确认 AudioContext 进入 running 且物理机能听到约 1 秒的 440 Hz 音；也可选择本地 WAV/MP3/Ogg 等文件，观察元数据、播放和解码错误。点击“播放 Canvas 视频”，确认画面持续变化、播放/暂停/currentTime 工作；选择本地 MP4/WebM/Ogg 文件可进一步验证实际视频解码。WebGL 区域会编译顶点/片元着色器并显示旋转三角形，状态中记录 WebGL 版本、渲染器和帧数；“重新运行 WebGL”可重复测试。Canvas captureStream 验证合成与播放链路，不能代替 H.264/VP9 等编码器验证。

远程网页使用 `contextIsolation=true`、`nodeIntegration=false`、`sandbox=true`，没有本地 preload 或文件 IPC。相机、麦克风、通知等权限请求会拒绝并记日志，不属于此测试的授权范围。

## 白屏诊断

面板底部显示 JSONL 日志路径，通常在 `~/.config/electron-mips64el-manual-desktop/logs/`。每条记录包含窗口 ID，便于区分 B 站和小红书。当前日志与一个轮转文件各限制在约 8 MiB；面板保留最近 160 条。程序不主动记录 Cookie 或所选文件正文；结构化 URL 字段去除查询参数，但页面标题、console 和错误正文仍可能包含网站内容或原始 URL。

- `http-response` / `navigation`：主页面的 HTTP 状态。
- `load-finished` / `dom-ready`：加载阶段；**标题变化或 HTTP 200 不等于页面已经正确绘制**。
- `load-failed` / `http-error`：网络错误；`code=-3` 常见于被替换或取消的导航，需结合前后记录判断。
- `render-process-gone`：renderer 的退出原因与退出码。
- `child-process-gone`：GPU、zygote、utility 等进程的退出原因与退出码。
- `console` / `preload-error`：页面警告、错误或本地 preload 错误。

在白屏的网页窗口选择“查看 → 开发者工具”，检查 Console 与 Network。可另开终端启动并保存 Chromium 原生日志：

```sh
./electron --enable-logging=stderr --v=1 /path/to/manual-desktop/main.js 2>&1 | tee desktop-terminal.log
```

**软件绘制对照**需要重新启动应用，保持其他参数一致：

```sh
./electron /path/to/manual-desktop/main.js --software-rendering
```

该选项在 ready 前调用 `app.disableHardwareAcceleration()`，不改变 sandbox。请分别记录默认模式和软件模式的结果；软件模式成功不能作为硬件 GPU 已通过的证据。

如目标网络需要已配置的代理，可显式指定 Chromium 代理，将 `PROXY_HOST` 替换为目标机器可访问的代理地址：

```sh
./electron --proxy-server=http://PROXY_HOST:7890 /path/to/manual-desktop/main.js
```

只有当日志明确指向 sandbox 初始化故障时，才可用 `--no-sandbox` 做一次定位对照。**该选项关闭 Chromium 进程隔离，不属于默认配置，也不能计为 sandbox 验证通过。** 应使用普通用户、检查内核与桌面环境，再修复正常隔离配置；测试程序不会自动添加该参数。

请保留启动命令、两种绘制模式的观察、JSONL 和终端日志。工具不自动生成“全部通过”结论，网页登录/验证码、网站策略、GPU、媒体播放和真实硬件表现都需要人工确认。

## 仅检查语法

```sh
node --check main.js
node --check preload.js
node --check renderer.js
```

宿主 Node 的语法检查不会启动 Electron，也不会验证目标架构的 GUI。
