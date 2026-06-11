# 小红书内容分享项目记忆

## 使用约定

- 本文件是仓库根目录级项目记忆入口，用于记录当前主项目方向、关键进度和后续协作约定。
- 当前主要开发目录是 `实施/xhs-agent`。
- 详细逐轮进度记录在 `实施/xhs-agent/memory/current_progress.md`。
- 全局路线图记录在 `实施/xhs-agent/memory/project_status_and_roadmap.md`。

## 当前项目目标

当前主项目是“小红书内容生成 Agent”，目标是完成从选题洞察、评论采集、内容生成、人工审核、草稿保存、运营记忆、表现录入到复盘沉淀的闭环。

## 当前阶段

- MVP 主链路已经跑通。
- M17a 已完成最小生产护栏：API token、日志落盘、敏感字段脱敏、运行配置检查和 token 烟测。
- M17b 已完成启动模板：本地 API、SQLite API、SQLite worker 的 PowerShell 模板，并明确优先使用 `D:\Anaconda\envs\ContentShare\python.exe`。
- M19a 已完成创作者平台连接基础适配：默认 mock、真实模式 Cookie 预检、私密图文发布入口、作品列表同步入口和命令行自测。
- 规则泛化和硬编码问题已记录，但暂不阻塞主要功能开发。

## 当前优先级

1. 继续推进主要工程和产品功能。
2. 下一步优先进入 M19b：把创作者平台私密发布接入现有审核/运行结果链路，并把发布结果回填到 run 与运营记忆。
3. 内容审核、评论洞察、模板 fallback、跨领域记忆过滤等泛化问题后续单独治理。

## 协作注意事项

- 每次执行命令前，需要说明执行目的、预期结果和异常处理方式。
- Python 命令优先使用 `D:\Anaconda\envs\ContentShare\python.exe`。
- `pdf识别` 目录与当前小红书项目无关，可以从当前仓库移除。
