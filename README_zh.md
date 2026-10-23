# 动态照片转换（MotionPhoto2 macOS 中文版）

把 iPhone **实况照片**（HEIC/JPG 照片 + MOV 视频）批量合成为 **谷歌相册 / 三星相册** 能识别的**动态照片**（Motion Photo）。

本仓库 fork 自 [PetrVys/MotionPhoto2](https://github.com/PetrVys/MotionPhoto2)（MIT 许可），转换核心未改动，只新增了 macOS 中文图形界面：

- 全中文界面，自动适配 macOS **深色 / 浅色模式**
- 双击打开即可，**不再弹出终端窗口**
- 可以把照片文件夹**拖到 Dock 图标**上
- **内置 ExifTool**，不用另外安装（装了 Homebrew 版会优先使用）
- 记住上次的文件夹和选项

## 许可证

本仓库的衍生版本整体及 Jaron-admin 有权授权的原创修改采用 **GNU GPL 仅第 3 版**（`GPL-3.0-only`），见 [LICENSE](LICENSE) 与 [许可范围及分发说明](LICENSING.md)。

上游 MotionPhoto2 代码保留原 MIT 许可；[LICENSES/MIT.txt](LICENSES/MIT.txt) 完整保留 Petr Vyskocil 的版权与授权原文。本声明不修改上游项目的许可，也不撤销旧版本已经授予的权利；ExifTool 等第三方组件继续适用各自许可。

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
