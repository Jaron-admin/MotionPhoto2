# 阶段 1：动态照片转实况照片方案

状态：已适配现成 Python 轨道模块，反向转换与界面已实现；合成验证通过，真实 Pixel 导入播放待验收。

来源：[Notion 任务书](https://app.notion.com/p/Codex-8297e162aced4ee7952817135594b112?source=copy_link)。
基础：阶段 0 的提交 `2d64413`，对应 [PR #1](https://github.com/Jaron-admin/MotionPhoto2/pull/1)，回归测试已通过。阶段 1 使用独立分支 `codex/stage-1-reverse-live-photo`；本方案不代表 PR #1 已合并。

## 用户要得到什么

在现有中文 App 选择“动态 → 实况”，把 Google/Pixel 动态照片转换成同名的 JPG/HEIC 与 MOV 文件。将这一对文件一起导入 Mac「照片」，应成为一个可播放的实况照片。默认保留原图格式、尺寸、方向、拍摄时间、GPS 和设备信息，原文件不变。

阶段验收必须包含真实 Pixel 原文件和 Apple「照片」播放结果。自动化测试与合成文件只能证明它们覆盖的行为，不能替代这个验收。

## 调研结论

- Google 当前格式用 XMP 容器目录描述图片和附加视频；HEIC 的附加视频位于 `mpvd`。不能仅凭文件名或一个 MotionPhoto 标志断定视频存在。旧 MicroVideo 格式需要单独识别，不能在新版目录无效时随意回退到旧偏移。[Google 格式说明](https://developer.android.com/media/platform/motion-photo-format)
- Apple 通过图片 Apple MakerNote 中的标识与 MOV 的 ContentIdentifier 关联资源，还使用定时元数据轨道记录静态画面对应的时刻。同名文件本身不构成实况照片。[Apple WWDC 说明](https://developer.apple.com/videos/play/wwdc2016/501/)
- QuickTime 定时元数据采用 `mebx` 样本描述。[Apple 容器说明](https://developer.apple.com/documentation/quicktime-file-format/timed_metadata_sample_descriptions)
- 本机 ExifTool 13.59 的 `QuickTime.pm` 将 StillImageTime 标记为 `Writable => 0`：不能靠调用 ExifTool 写普通标签来代替这条轨道。仍可用它读取结果，独立检查轨道内容。

## 方案选择

| 方案 | 收益 | 代价或限制 | 决定 |
| --- | --- | --- | --- |
| 优先评估已有 Python QuickTime 写入模块，沿用 ExifTool 管理图片元数据 | 核心不依赖 macOS API；减少重复实现；保留编码媒体数据 | 现成模块需适配与独立验证，不能直接作为已通过 Apple 验收的依赖 | 推荐先做复用验证，不直接从零重写 |
| Python 检测提取，Swift/AVFoundation 生成实况 MOV | 使用 Apple 的媒体写入 API | 产品转换路径依赖 macOS，与任务书核心可移植的约束冲突 | 不作为默认方案；第一方案不可行时另行讨论 |
| 仅提取图片与视频，或只写同一个 UUID | 实现较少 | 缺少实况时间轨道及 Apple 验证，达不到验收目标 | 排除 |

推荐方案目前是设计判断，不是兼容性结论。第一项实现工作就是生成最小输出，并通过独立媒体读取器和 Apple 框架验证；失败时先诊断，不先扩展界面或把拆分功能标成实况转换成功。

## GitHub 现成项目核查（2026-10-19）

用户要求先查现成项目；结果是存在直接转换工具和可供复用的底层实现，不应再以“没有现成方案”为开发前提。以下核查以源码为主；作者的兼容性声明与本地实测分开记录。

| 项目及检查版本 | 已有能力 | 对本项目的适用性 |
| --- | --- | --- |
| [AssassinJY/live_motion_photos_convert](https://github.com/AssassinJY/live_motion_photos_convert/tree/28d74fdf3ab92ced30590611be7ec9798082b931)，MIT | 双向转换；macOS 路径用 Swift/AVFoundation 写入实况时间轨道。README 声明在 macOS「照片」验证过 | 最接近完整功能参考；工具依赖较多，图片转成 HEIC，非 macOS 回退路径不能等同完整轨道能力。需保留本项目原画质和核心可移植约束 |
| [reviventura/LivePhotoTools](https://github.com/reviventura/LivePhotoTools/tree/fbe7be3e165bde2c6448c7ab66fe5f53ab0e591f)，MIT | 已有 Apple Silicon / macOS 15+ App，含 Motion2Live；提供 v1.0 下载，JPG 图片字节不重编码 | 可试用的现成应用；Motion2Live 子目录 README 明确不生成 still-image-time 轨道，且已有核验是格式对比、不是导入测试，不能直接替代本项目验收 |
| [yangzhen-23/video-to-live-photo](https://github.com/yangzhen-23/video-to-live-photo/tree/83b55e6e66b6cbb39e7d7acddbbb52eef1585adc)，Apache-2.0 | Python `apple.py` / `iso_bmff.py` 已实现 UUID、mebx 时间轨道和采样偏移调整，有对应单元测试 | 与现有 Python 核心最接近，优先评估视频写入模块。上游目标是视频生成实况，尚需补动态照片检测和 HEIC；图片写入会重编码并改写 Make/Model，不能原样使用 |
| [Albresky/MotionPhoto2AppleLivePhoto](https://github.com/Albresky/MotionPhoto2AppleLivePhoto/tree/3b198540ce9dde9b60b728fb4d9bf18e8aaa0367) | Python 直接处理 Google/小米动态照片，带 Web UI，输出 HEIC + MOV | 主转换链重新编码图片，视频链只做 remux 与 ContentIdentifier 注入，未找到新增 still-image-time 的步骤；未找到项目本身的明确许可，不纳入代码复用候选 |

也检查了 `nicing/make-live-photo`、`Bai-Mirror/pyheic_struct`、`Huakira/MotionTrans`、`google/libmotionphoto` 等。它们分别更偏向 Apple 原生生成、三星 HEIC 处理、平台专用转换或 Google 格式解析，不能直接替换现有产品所需的完整流程。

### 临时小样本结果

只在 `/tmp/motionphoto-reuse-check` 运行外部 Python 模块，未复制到产品目录、未导入用户照片图库。样本是新生成的 96×64 静态图与 3 秒 H.264 视频。

- 上游 Python 输出的图片和视频，ExifTool 读出的 ContentIdentifier 一致。
- ffprobe 识别到 `mebx` 轨道，起始时间为请求的 1.5 秒；FFmpeg 完整解码视频成功。
- ExifTool 读到 StillImageTime = -1；SampleTime 显示 0，而 ffprobe 显示编辑列表后的时间为 1.5 秒，验证不能只检查一个工具的单一字段。
- 图片 Make/Model 被上游改为 Apple / Video to Live Photo，与本项目保留实际设备信息的要求不符。
- 本机 macOS 27.0 的 `PHLivePhoto.request` 检查未返回有效 Live Photo 对象；移出沙箱复查后仍未成功。该试验没有已知有效资源作为阳性对照，不能据此断言是上游代码缺陷，也不能宣称已被 Apple 接受。更换 MakerNote 存放位置的单一试验未解决它。

结论：已有代码能减少重复实现，尚无本次检查已证明满足所有要求的即插即用替代。优先评估 Apache-2.0 视频模块，保留作者署名及许可；先补独立 Apple 验证与容器边界测试，再决定适配范围。不要原样引入其图片重编码逻辑；不要把有许可证的参考代码统一改标成原项目 MIT。

## 支持范围与产品行为

1. 输入覆盖 JPG/HEIC：当前 Google Motion Photo 1.0，以及单独识别的旧 MicroVideo。首轮视频目标为非碎片化、非加密的 H.264/HEVC，允许无音频或 AAC-LC 单/双声道音频。AVIF、其他品牌私有格式、多视角视频与自动转码留待后续。
2. 图片保持原格式，不重新编码。视频音画数据保持原编码，写入真正的 MOV 容器与实况轨道。不能只改扩展名；不兼容的视频必须明确报错，不偷偷降质、删音轨或改颜色。
3. HDR、增益图、深度/辅助轨道在第一轮不宣称已支持。遇到已识别但尚未验证的此类内容，明确跳过并说明原因，不能静默转成 SDR。支持范围后续由真实样本验证扩展。
4. 原文件只读；默认输出到同级“原文件夹名_实况照片”。两份输出使用同一文件名主体和新生成的 UUID。发生重名时整对跳过；拒绝输出到输入目录或其子目录，避免覆盖和递归重入。
5. 沿用现有目录选择与子目录选项。普通照片跳过并给出中文原因；“按内部信息配对”“复制普通照片”“增量转换”等正向选项在反向模式禁用，避免含义混淆。反向的重名保护始终有效。
6. 界面增加方向切换，默认仍为“实况 → 动态”；方向改变时同步说明和默认输出目录，但保留用户明确选择的自定义目录。CLI 新增 `--direction live-to-motion|motion-to-live`，旧调用保持原行为。
7. 一个文件失败后继续处理其余文件，日志区分已转换、非动态照片、暂不支持、重名和损坏。出现处理错误时进程非零退出；当前阶段不新增 CSV 报告、缩略图或新平台产品。

## 模块与数据流

建议新增一个独立 Python 包，职责分开，现有正向 Muxer 保持独立：

- `reverse/detect.py`：读取 XMP 与文件结构，返回格式类型、图片/视频有效范围和关键帧时间依据。按命名空间 URI 解析 XMP，禁止外部实体；校验长度、边界、重复目录项、残留标志和缺失视频。
- `reverse/quicktime.py`：有限范围的 ISO BMFF/QuickTime 读取和写入，处理轨道、时间基准与采样偏移。拒绝未支持的碎片、外部媒体引用、加密和不完整容器，不能把所有输入都当作简单 MP4。
- `reverse/photo.py`：从副本去除动态视频包装和失效的 Motion Photo 专用字段，写入 Apple 图片配对标识，校验标准 EXIF 与其他 XMP 组。保持实际 Make/Model，不把安卓照片伪装成 Apple 拍摄。
- `reverse/convert.py`：协调一次转换、分块复制数据、取消清理、校验和输出落盘，返回结构化结果；不导入 GUI、Photos 或 AVFoundation。
- `motionphoto2.py`：根据方向分派调用；`mac_gui.py` 仍只组织参数、显示结果和停止任务，不承载格式转换逻辑。

每个文件依次经过：检测 → 校验 → 临时提取 → 分别写入配对标识和视频轨道 → 独立校验 → 落盘。任何一步失败，都不得留下被报告为成功的半对资源。

## 容器和元数据规则

- 视频关键帧使用有效的源时间戳，并映射到实际展示时间轴；缺省或未指定时选取视频中间附近的展示帧并记录采用的规则。明确越界的时间戳判为损坏，不静默夹到边界。
- 必须处理音视频时间基准、B 帧显示时间、编辑列表和旋转；实况元数据样本的呈现时刻应与选定帧对应，不能用轨道总时长代替它。
- 写入 `com.apple.quicktime.content.identifier` 与 `com.apple.quicktime.still-image-time` 定时轨道；UUID 必须与图片的 Apple 标识一致。具体轨道值与布局以 Apple 可读性验证结果确定，不能仅凭 ExifTool 显示某个标签判为成功。
- 重组 MOV 时重新计算受影响的 `stco`/`co64` 和容器长度，保留音视频样本及时间信息；检查整数溢出、长度越界与截断。只支持经过测试的容器结构。
- 图片与视频保留原有拍摄时间及存在的时区信息；不凭空补时区。两份输出的文件修改时间采用源动态照片时间。
- Android 厂商 MakerNote 与 Apple MakerNote 不能假定可无损合并。标准拍摄时间、GPS、设备信息是硬性校验项；若必须替换厂商私有 MakerNote，在结果日志明确说明，原始信息仍保留在未改动的源文件。本阶段不承诺所有厂商私有字段无损。
- 每次先在输出目录内的临时目录完成整对结果。最终落盘采用“不覆盖已有文件”的操作；第二个文件提交失败时回滚本次创建的第一个文件，不删除已有文件。断电或强制终止遗留不能伪装成已完成，重试须报告不完整输出。

## 验证与交付顺序

1. **最小实况输出**：先测试受限容器写入器与图片标识。用生成样本验证 UUID、定时轨道、选定时刻和音视频字节；用 FFmpeg 解码、ExifTool 读取，再用仅用于测试的 Apple 框架检查资源能否组成 Live Photo。Apple 测试工具不进入产品转换核心。
2. **检测与安全提取**：覆盖新版/旧版、JPG/HEIC、中文路径、错误偏移、无视频、重复项、截断和不支持的编码。增加独立构造的格式样本，不能只测试本项目 Muxer 生成的文件；本项目正反互转不等于已支持所有三星格式。
3. **转换入口与界面**：增加单文件、目录和递归调用；验证停止、同名保护、原文件哈希及修改时间、缺失依赖的清晰提示。阶段 0 的 14 项测试持续运行，不能用修改预期掩盖回归。
4. **打包与 CI**：检查 PyInstaller 包含新模块，在临时 App 副本上执行新旧转换测试。为 PR 增加只验证、生成构建产物的路径；发布步骤仅在明确发布入口运行，避免测试分支自动发布 Release。
5. **真实验收**：使用用户提供的 Pixel 原始动态照片，在独立测试资料库导入输出的一对文件，确认显示“实况”、可播放、方向正确，检查时间与 GPS。测试记录包括系统版本、源样本散列、转换版本和观察结果；私有样本不提交仓库。

FFmpeg/ffprobe 在推荐方案中继续仅用于测试。尚未证明纯 Python 容器写入可满足 Apple 兼容性；若最小验证不通过，将记录原因和替代方案，不未经讨论改变核心可移植约束。

## 当前实现与证据

- `reverse/metadata.py`、`reverse/iso_bmff.py` 复用已核查的 Apache-2.0 源码，保留署名和完整许可；图片重编码代码未引入。
- 小样本失败已定位到图片 EXIF 的写入布局；ExifTool 直接写入 MakerNotes 后，Google/Synthetic 厂商信息无需伪装成 Apple，纯 Python 视频可以通过 Apple 最终完整回调。原生 Swift 输出只作为临时阳性对照，未进入产品核心。
- MOV 重组保留原媒体偏移：旧 moov 替换成等长 free，末尾加入时间采样和新索引，再由 ExifTool 合并 ContentIdentifier。这样不移动媒体采样，代价是保留一段旧索引大小的空白。
- 已接入独立检测、同名保护、取消/失败回滚、CLI 和中文方向开关。UI 将反向标为试用。
- 当前明确拒绝额外元数据/辅助轨道、复杂多段编辑列表、HDR、增益图、加密与外部引用；这会使部分真实 Pixel 文件暂不支持，需真实样本验证后扩展。
- 仓库没有真实 Pixel 原文件；合成 Apple 识别测试不等于 Photos 资料库导入播放验收。未发布正式 App，也未进入下一阶段。

## 独立审查与实施取舍

独立审查发现并修复两个问题：`mp4a` 可能承载 MP3，因此增加 ES/AAC-LC 配置验证；大量小容器段可能放大内存分配，因此增加段数量和 HEIC 类型头上限。两项都有先失败再通过的回归测试。修复后本地 39 项测试：38 通过，1 项既有 XMP-1 预期失败；合成 JPG/HEIC 再次通过 Apple 完整回调。审查无遗留 Minor。

- 沿用干净的阶段 1 分支工作目录，未另建 worktree；符合宿主优先复用要求，如后续出现共享工作冲突需搬移改动。
- 保留原媒体偏移和一段旧索引大小的空白，以降低重新定位采样风险；代价是少量文件体积。
- 试用阶段拒绝复杂编辑列表与额外轨道，可能暂时拒绝部分真实 Pixel 文件。
- 真实 Pixel 兼容性、Photos 资料库导入与播放暂不能下结论；代价是正式验收与发布仍需真实原文件。
- MP3 明确拒绝，因为不在已验证的 AAC-LC 范围内；并不据此断言它一定无法被 Apple 播放，代价是部分可能可用的输入被拒绝。
- 保留常规符号链接与重名保护，未承诺对抗同权限进程主动替换目录；代价是没有对抗性文件系统竞态保证。
- 保留“不覆盖”的硬链接落盘；FAT/exFAT 输出失败时先用本机支持的目录再复制配对，代价是部分外置磁盘多一个复制步骤。

远程构建与实际使用入口记录在 [阶段 1 草稿 PR #2](https://github.com/Jaron-admin/MotionPhoto2/pull/2)。不合并阶段 0/1、不自动发布；真实样本验收完成前保持草稿。
