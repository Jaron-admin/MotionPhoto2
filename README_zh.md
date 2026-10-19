# 动态照片转换（MotionPhoto2 macOS 中文版）

把 iPhone **实况照片**（HEIC/JPG 照片 + MOV 视频）批量合成为 **谷歌相册 / 三星相册** 能识别的**动态照片**（Motion Photo）。

本仓库 fork 自 [PetrVys/MotionPhoto2](https://github.com/PetrVys/MotionPhoto2)（MIT 许可），转换核心未改动，只新增了 macOS 中文图形界面：

- 全中文界面，自动适配 macOS **深色 / 浅色模式**
- 双击打开即可，**不再弹出终端窗口**
- 可以把照片文件夹**拖到 Dock 图标**上
- **内置 ExifTool**，不用另外安装（装了 Homebrew 版会优先使用）
- 记住上次的文件夹和选项

## 下载安装

1. 到 [Releases](../../releases/latest) 下载 `MotionPhoto2-zh-macOS.zip`
2. 解压，把「动态照片转换.app」拖进「应用程序」
3. 第一次打开如果提示无法验证开发者：**系统设置 → 隐私与安全性 → 往下拉 → 仍要打开**

目前只提供 Apple 芯片（M 系列）版本。

## 使用

1. 用「图像捕捉」把 iPhone 照片导入一个文件夹（iPhone 设置 → 照片 → 传输到 Mac 或 PC → **保留原片**）
2. 打开「动态照片转换」，选择这个文件夹（或直接拖到 Dock 图标上）
3. 点「开始转换」，完成后点「在访达中打开结果」

推荐保持默认勾选：**按照片内部信息配对** + **同时复制普通照片和视频**。这样输出文件夹就是完整的一批，可以整个传到安卓手机上让谷歌相册备份。

原文件不会被修改。

## 自己构建

```bash
pip install lxml PyExifTool six pyinstaller
python mac_gui.py                         # 直接运行界面
pyinstaller --noconfirm build-mac-app.spec  # 打包成 .app
```

推送到 main 分支后，GitHub Actions（`.github/workflows/build-mac-zh.yml`）会自动构建并发布到 Releases。

## 开发与测试

完成测试环境准备后，一条命令运行现有转换的回归测试：

```bash
.venv/bin/python tests/run_tests.py
```

详见 [测试与样本生成](docs/TESTING.md)、[项目结构与发布流程](docs/PROJECT_GUIDE.md)、[分阶段开发路线](docs/ROADMAP.md) 和 [已知问题](docs/KNOWN_ISSUES.md)。打包与发布前必须通过测试；原作者版权与 MIT 许可保持不变。

### 动态照片 → 实况照片（阶段 1 试用）

新版源码可在窗口切换「动态 → 实况」，选择 Google Motion Photo 文件夹，生成同名 JPG/HEIC 与 MOV 配对。默认输出到同级「原文件夹名_实况照片」；将两份文件一起导入 Apple「照片」。原文件保持不变，同名输出整对跳过。

```bash
python mac_gui.py --cli --direction motion-to-live --input-directory "动态照片文件夹"
# 单文件（输出目录可省略）：
python mac_gui.py --cli --direction motion-to-live --input-image "动态照片.JPG" --output-directory "实况输出文件夹"
```

当前范围：新版 Google JPG/HEIC、旧 MicroVideo JPG；非碎片化 H.264/HEVC，最多一个 AAC-LC 单/双声道音轨。图片和音视频不重新编码。暂不处理 HDR/增益图、深度/辅助资源、额外元数据轨道、加密或外部引用；遇到这些输入会明确说明并跳过。标准拍摄时间、GPS 和厂商信息保留；厂商私有 MakerNote 若被替换会在日志说明，源文件仍保留完整原始信息。

已做合成资源与 Apple 框架检查，真实 Pixel 原文件的「照片」导入和播放尚待验收，不宣称所有安卓设备通用。测试方法和构建产物见 [测试文档](docs/TESTING.md)。反向轨道代码复用了 Apache-2.0 项目，详见 [第三方声明](THIRD_PARTY_NOTICES.md)。
