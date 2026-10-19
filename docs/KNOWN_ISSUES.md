# 阶段 0 发现的原有问题

## XMP-1：只保留第一组 rdf:Description

- 状态：已复现，未修复；阶段 0 按任务书不修改功能代码。
- 位置：`Muxer.py` 的 `merge_xmp()` 用 `find()` 取得第一个 `rdf:Description`，只复制该节点的子元素和属性。
- 影响：如果原图的 XMP 分成多个 `rdf:Description`，后续组的信息会丢失。测试样本的描述文字在第一组、评分 `Rating=4` 在第二组；转换后描述保留、评分缺失。JPG 和 HEIC 均已在本地复现。
- 回归用例：`test_all_xmp_description_blocks_are_preserved`。当前以 `unittest.expectedFailure` 明确标记，并在日志中可见，其他转换用例继续严格校验。
- 修复方向：遍历全部 `rdf:Description`，设计与已有 Motion Photo 字段的冲突处理，避免重复 Container Directory 或覆盖新生成的长度/偏移；补多组、属性形式及重复字段测试。
- 后续归属：阶段 2 的元数据保全。修复时移除 expectedFailure 标记，验证原文件及全部元数据保全。

这不是“所有元数据无损”的承诺。阶段 0 的测试将已经验证的行为与此已知缺陷分开报告。

## SIGN-1：CLI 配置写入 App 包，可能使签名失效

- 状态：原有问题，阶段 0 未修改设置保存逻辑。
- 位置：`utils.save_defaults()` 将 `motionphoto2.json` 写在模块旁；PyInstaller 打包后该位置可能在 App 的 Frameworks 中。
- 证据：本机已安装 App 在本次测试前运行 `codesign --verify --deep --strict`，报告 `Contents/Frameworks/motionphoto2.json` 导致签名无效。
- 本轮测试处理：源码和成品均在临时副本内执行，防止测试写坏待发布 App；CI 在成品测试后复验原 App 签名。
- 后续修复：把 CLI 配置迁到独立用户数据目录，同时保持核心的多平台路径兼容。迁移与签名验收需要单独测试，不能把“测试使用副本”当作此问题已经修复。
