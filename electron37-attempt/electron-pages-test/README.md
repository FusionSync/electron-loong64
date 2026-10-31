# Electron 37 Loong64 多页面测试

这个目录会直接在 Electron 内打开三个真实网站窗口：

- 小红书：`https://www.xiaohongshu.com/`
- 哔哩哔哩：`https://www.bilibili.com/`
- 百度：`https://www.baidu.com/`

运行：

```bash
cd /path/to/electron-loong64-gldfixed/electron-pages-test
DISPLAY=:0 ../electron --no-sandbox --disable-gpu --no-zygote .
```

程序启动时强制使用软件渲染，关闭 WebGL、硬件视频解码和 GPU 合成，并使用 `--no-zygote --no-sandbox` 绕过当前 Loong64 Linux 的渲染器 zygote 崩溃路径。窗口默认等页面完成导航后再显示，避免把加载阶段的白色背景误认为白屏。终端会打印每个页面的
DOM 状态，并在 `/tmp/electron-page-0.png`、`/tmp/electron-page-1.png`、`/tmp/electron-page-2.png`
保存截图。若页面加载完成但没有可见内容，窗口内会显示诊断提示和“重新加载”按钮。

如需把三个窗口平铺在屏幕上，使用：

```bash
ELECTRON_TEST_TILE=1 DISPLAY=:0 ../electron --no-sandbox --disable-gpu --no-zygote .
```

只测试小红书时可以暂时编辑 `main.js` 的 `pages` 列表，或使用日志和截图判断实际加载结果；
页面窗口没有工具栏，窗口标题会由网站的 `document.title` 接管。

也可以只打开一个网站，避免其他网站的网络错误干扰观察：

```bash
ELECTRON_TEST_PAGE=xhs DISPLAY=:0 ../electron --no-sandbox --disable-gpu .
```

可选值为 `xhs`、`bilibili` 和 `baidu`。

如果需要通过 HTTP 代理访问：

```bash
ELECTRON_TEST_PROXY="$UOS_BUILD_PROXY" DISPLAY=:0 \
  ../electron --no-sandbox --disable-gpu .
```

代理连接失败会显示可读的错误页（包含 Chromium 错误码），直连测试建议先不要设置
`ELECTRON_TEST_PROXY`。可用 `ELECTRON_TEST_DIAGNOSTICS_DIR=/tmp/electron-pages`
改变截图目录。

终端会打印每个窗口的开始加载、加载完成、加载失败和渲染进程退出信息。关闭所有页面窗口即可退出测试。

网站登录、视频播放、图片加载和跳转行为都在 Electron 的 Chromium 窗口中进行。小红书或其他站点如果因网络、风控、登录状态或地区策略显示异常，不等同于 Electron 渲染器崩溃；请同时观察终端日志中的 `renderer gone` 和页面是否能加载。
