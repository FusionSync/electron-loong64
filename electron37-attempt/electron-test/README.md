# Electron 37 Loong64 功能测试

这个目录不需要 npm install，直接使用旁边的 Electron 二进制即可。

```bash
cd /path/to/electron-loong64-gldfixed/electron-test
DISPLAY=:0 ../electron --no-sandbox --disable-gpu .
```

依次检查：

1. 系统信息显示 `loong64`、Electron 和 Node 版本。
2. 点击“开始/暂停 CSS 动画”，彩色条应移动。
3. Canvas 中小球应持续反弹，FPS 应更新。
4. 点击“选择并读取文件”，选择一个文本文件，页面应显示路径、大小和预览。
5. 默认 URL 点击“发送 GET 请求”，应显示 HTTP 状态；如果 B 站网络不可达，改用可访问的 HTTPS 地址。
6. 点击“用系统浏览器打开 B 站”，应调用系统默认浏览器打开 `https://www.bilibili.com/`。

`main.js`、`preload.js` 和 `renderer.js` 分别覆盖主进程、隔离预加载和渲染进程 IPC；页面没有加载第三方脚本。

## 媒体和图形测试

使用 `--media` 打开离线媒体页面：

```bash
DISPLAY=:0 ../electron --no-sandbox --disable-gpu . --media
```

页面运行时生成 3 秒 WebM、WAV 和 Web Audio 音调，并检查 `<video>` 元数据、`<audio>` 解码、WebGL 着色器、Canvas 2D 绘制及像素读取。没有网络依赖，也不需要额外的媒体文件。`--disable-gpu` 会让 WebGL 走软件实现；若要验证 GPU 合成，去掉该参数并观察 `gl-info` 的 renderer。
