# 本地与 CI 测试

## 首次准备（macOS）

建议使用 Python 3.12 或 3.13；CI 使用 Python 3.13。终端进入项目目录后执行：

```bash
brew install exiftool ffmpeg
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
```

如果已经安装 ExifTool、FFmpeg/ffprobe 并能在 PATH 中找到，可跳过 Homebrew 安装。测试不需要 Gooey/wxPython，也不连接照片云服务。

## 一条命令运行

```bash
.venv/bin/python tests/run_tests.py
```

退出码 `0` 表示无意外失败，`1` 表示用例失败，`2` 表示缺少依赖/入口参数有误。依赖缺失会阻断，而不是把集成测试全跳过。

当前基线有一个明确登记的 `expected failure`：多组 XMP 的评分丢失（[XMP-1](KNOWN_ISSUES.md)）。这是原有功能缺陷，不代表该功能通过。测试修复后会变成 `unexpected success` 并阻断，提醒同时移除标记和更新问题文档。

## 测什么

- JPG/HEIC 分别与 MOV/MP4 合成，使用真实 CLI、真实 ExifTool。
- 读取输出的 Motion Photo XMP，验证视频长度和起点。
- 从输出提取视频，验证原视频字节、ffprobe 媒体信息和 FFmpeg 实际解码。
- 图像仍可解码且像素与输入一致。
- 拍摄时间、GPS、相机信息、配对标识、第一组 XMP 描述和文件修改时间保留。
- 原文件内容与修改时间未改变，临时文件被清理。
- 中文/空格路径、递归目录、普通照片/孤立视频/文本复制。
- EXIF 配对能选中不同文件名但标识一致的视频，不误选同名的错误视频。
- 增量转换不重写已生成文件，已有动态照片不重复合成。
- EXIF 模式的空目录、仅图片、仅视频，以及冲突参数报错。
- 已有关键帧解析函数和视频签名判定。

样本由 `tests/generate_samples.py` 每次在临时目录生成：96×64 图片、0.5 秒 H.264 视频、固定的虚构标识/时间/GPS。无私人照片，无测试样本下载，测试后自动清理。图片中最小 Apple MakerNote 结构依据 ExifTool 的 Apple/MakerNotes 标签解析实现；生成后用 ExifTool 验证标识。

这些合成文件不含真实相机的 HDR、复杂 MakerNotes 或 Apple timed still-image 轨道，因此不能代替真机、谷歌相册或 Apple「照片」兼容性验收。关键帧函数测试也不等于真实实况关键帧端到端测试。

## 手工试用样本

```bash
.venv/bin/python tests/generate_samples.py /tmp/motionphoto2-demo
```

目标必须是不存在或空的目录，否则会拒绝，避免覆盖文件。生成目录中同时含不同图片/视频格式，手工试用时将所需的一对复制到另一个目录，不要把整组样本当真实相册。

## 检查打包成品

```bash
.venv/bin/python tests/run_tests.py --app "dist/动态照片转换.app/Contents/MacOS/MotionPhoto2zh"
codesign --verify --deep --strict --verbose=2 "dist/动态照片转换.app"
```

用例会先复制整个 App 到临时目录，再运行其 `--cli`，保留原 App 的内容和签名。成品测试同样需要测试环境中的 ExifTool、FFmpeg、ffprobe 和 Python 测试依赖。

PR 运行 `.github/workflows/test.yml`；两条现有打包流程均以它成功为前提。中文版还在压缩和发布前执行成品回归测试，任何意外失败均阻止发布。
