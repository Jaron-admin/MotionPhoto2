# 现有项目说明

本轮基于 `39fcb1f`，范围为阶段 0：补测试、CI 和文档，保留现有功能及版权。

## 目录

| 文件 | 用途 |
| --- | --- |
| `mac_gui.py` | Tk 中文界面、中文日志、进度、设置；通过子进程 `--cli` 调用核心 |
| `motionphoto2.py` | 命令行参数、目录扫描、文件名/ContentIdentifier 配对、递归、增量及普通文件复制 |
| `Muxer.py` | 读取元数据、合并 XMP、合成图片与视频、保留文件时间 |
| `SamsungTags.py` | 生成三星 SEF 尾部；HEIC 另使用 `mpvd` / `sefd` 容器 |
| `constants.py` | XMP 模板、命名空间、格式标记 |
| `utils.py` | 检测/提取动态视频、关键帧时间、文件比较、CLI 设置 |
| `build-mac-app.spec` | PyInstaller 中文 App 配置，内置 ExifTool，排除 Gooey/wxPython |
| `assets/make_icon.py` | 生成 PNG/ICNS 图标 |
| `.github/workflows/build-mac-zh.yml` | 测试 → 打包 → ad-hoc 签名 → 成品测试 → ZIP → Release |
| `.github/workflows/build.yml` | 上游已有的 macOS/Linux/Windows 打包；本轮只加公共测试前置条件 |
| `legacy_ps1/` | 旧 PowerShell 实现，当前中文 App 不调用 |
| `tests/` | 本轮新增：合成样本、真实转换回归测试、单命令入口 |

## 转换流程

1. 界面收集输入、输出目录及选项，启动 `mac_gui.py --cli`（打包后调用自身可执行文件）。
2. `motionphoto2.py` 扫描图片与视频，按文件名或图片 MakerNotes / 视频 QuickTime 中的 ContentIdentifier 配对。
3. `Muxer` 调用 ExifTool 读取元数据和可选关键帧时间，复制图片并加入 Google Motion Photo XMP。
4. `SamsungTags` 追加原视频字节和格式尾部；不重新编码视频。HEIC 与 JPEG 的视频存储结构不同。
5. 写出结果、复制原图文件时间、清理临时文件；目录模式按选项复制未合成文件。
6. 界面解析子进程日志更新中文进度与统计。

界面和核心已基本分开。`Muxer.py` 等核心文件不导入 Tk 或 macOS API；本阶段不做架构重写。

## 依赖

- **ExifTool**：独立命令行程序（中文版内置 Perl 版本），读写 EXIF/XMP/QuickTime 元数据。
- **PyExifTool**：Python 调用 ExifTool 的封装，并不是 ExifTool 本体。
- **lxml、six**：现有核心依赖。
- **Tkinter**：中文界面，随适用的 Python 发行版提供。
- **Gooey/wxPython**：上游旧界面使用，中文 App 及本轮无界面测试不需要。
- **PyInstaller、Pillow**：打包与图标生成。
- **FFmpeg/ffprobe**：测试时生成并解码小视频；当前正向合成不调用 FFmpeg 转码。
- **pillow-heif**：仅测试使用，生成/读取 HEIC 合成样本；不添加到 App 功能依赖中。

CLI 将配置写到脚本旁的 `motionphoto2.json`，中文界面配置在用户 Application Support 下。测试在临时源码副本或临时 App 副本中运行，避免污染真实设置或破坏待发布 App 的签名。

## 打包与发布

中文版工作流在相关文件推送到 `main`/`master`，或手动运行时启动：

1. 复用 `test.yml` 运行完整源码测试，失败则不会开始打包。
2. macOS runner 安装 Python 3.13、打包依赖，下载并内置 ExifTool。
3. 检查 CLI、尝试界面启动、生成图标，用 PyInstaller 打包。
4. 对整个 `.app` 做 ad-hoc 签名并验证。
5. 对 App 临时副本执行完整转换测试，再验证原 App 的签名。
6. 压缩并上传 artifact，按既有 `zh-v1.0.${github.run_number}` 规则发布 Release。

既有 GUI 启动检查使用 `continue-on-error`，因此绿色转换测试不等同于界面人工验收。阶段 0 不改变这一原有策略。

本轮工作先放入开发分支/PR，PR 触发 `转换回归测试`，不发布版本。确认 PR 的检查通过后合并，主分支自动执行打包发布。也可在 GitHub Actions 中选择「构建 macOS 中文版」→ Run workflow，选择已确认的分支；此操作会公开发布 Release。

发布后下载 ZIP，核对 App 可打开、界面正常、小样本转换成功，再继续下一阶段。当前 App 内部版本仍为 `1.0.0`，和既有 Release 标签不完全一致，版本统一列入阶段 4。
