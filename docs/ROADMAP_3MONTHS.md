# obdiag 三个月规划（2026年2月–4月）

本文档基于当前项目结构、4.0.0 能力与历史 Roadmap，为 obdiag 设计接下来三个月的迭代规划。**在 Cursor 等 AI 辅助开发下，规划中增加了更多功能项**，便于在保证质量的前提下提升交付量。

---

## 一、项目现状概览

### 1.1 核心能力

| 模块 | 说明 | 当前形态 |
|------|------|----------|
| **gather** | 一键采集（日志、AWR、sysstat、obstack、perf、scenes、tabledump、parameters/variables、dbms_xplan、core、ash_report 等） | Handler + 插件 yaml/python |
| **check** | 一键巡检（observer/obproxy 包、Python 脚本任务） | 包 yaml + tasks 目录下 .py |
| **analyze** | 分析（log、sql、sql_review、parameter、variable、memory、index_space、queue、flt_trace） | Handler 内置 |
| **display** | 场景化展示（compaction、leader、memory、slowsql、topsql 等约 29 个 observer 场景） | yaml 场景 |
| **rca** | 根因分析（clog、事务、内存、锁、OMS 等约 25+ 场景） | plugins/rca/*.py |
| **tool** | 工具集（ai_assistant BETA、io_performance、config_check、crypto_config） | Handler + 可选依赖 |

### 1.2 技术栈与工程

- **依赖管理**：已迁移至 `pyproject.toml`，支持 `pip install .` / `pip install .[build]` / `.[macos]`。
- **测试**：覆盖 `test/analyzer`（SQL 规则、log tree）、`test/common`（command、config、scene、ssh_client 等）；**未覆盖** gather/check/display/rca/tools 的 Handler 与集成流程。
- **CI**：build_package（RPM/DEB/macOS）、test_sql_rule、test_command_scene_configHelper、test_ssh_client、format_check、codeql、translate。
- **已知技术债**：stdio 的 `err_stream` 待切到 stderr（TODO）；core 中 “custum” 已修复；部分异常与日志可统一与增强。

---

## 二、规划原则

- **稳定性优先**：修已知问题、补测试、少破坏性变更。
- **体验与可观测**：报告可读性、错误提示、日志与 Trace ID。
- **场景延续**：延续历史 Roadmap 的 check/display/rca 场景扩展与 OceanBase 新版本适配。
- **AI 与工具渐进**：AI 助手从 BETA 向 GA 演进，工具链可扩展。
- **AI 辅助开发**：在 Cursor 等工具辅助下，适当增加单月功能密度，并保持每项可验收、可拆 PR。

---

## 三、三个月目标总览

| 月份 | 主题 | 关键目标 |
|------|------|----------|
| **2 月** | 稳定与质量 | 技术债、测试与 CI、**AI 基础（配置/单测/文档）**、文档与贡献、代码规范 |
| **3 月** | 场景与兼容 | Check/Display/RCA 场景扩展、**AI 能力（意图识别/与 check-gather 联动）**、OB 兼容、analyze 增强 |
| **4 月** | 体验与 AI/工具 | **AI 专项（多后端、MCP、BETA→GA）**、报告与交互、工具链、可观测与 4.1.0 发布 |

**AI 投入说明**：三个月内将 AI 作为重点方向之一，2 月打基础（配置、测试、文档），3 月做能力（与诊断流程联动），4 月做成熟度（多后端、MCP、发布就绪）。

---

## 四、月度详细规划（扩展版）

### 4.1 二月：稳定与质量

**目标**：夯实基础，减少线上问题，提升贡献与使用体验；在 AI 辅助下完成更多技术债与测试。

| 类别 | 事项 | 说明 |
|------|------|------|
| **技术债** | 修复 stdio 的 err_stream | 落实 TODO：默认/可选使用 `sys.stderr`，兼容现有行为。 |
| | 异常与日志统一 | 在 config 加载、SSH 连接、OB 连接等路径统一错误信息格式（原因 + 建议 + 文档链接）。 |
| | 重复代码收敛 | 对 core.py 中多处相似的 “No such custom config” 分支做抽取，减少重复。 |
| **测试** | check 相关单测 | `CheckHandler` 配置解析、任务加载、报告生成；至少 2 个 check 任务的 mock 执行。 |
| | gather 关键路径测试 | gather_log、gather_sysstat 等 1–2 个 handler 的 mock 单测（不依赖真实 OB/SSH）。 |
| | display 场景加载测试 | display 场景列表加载、yaml 解析的单元测试。 |
| | rca 场景加载测试 | rca 插件加载、场景列表的单元测试。 |
| **CI** | 统一测试入口 | 使用 `make test` / `pytest test/` 在 CI 中统一跑测试；修复 test 目录路径（已修复）。 |
| | 新增测试 workflow | 可选：单独 workflow 跑 `make test`，或与现有 test_* 合并为 matrix。 |
| | 测试覆盖率 | 可选：引入 coverage 并输出摘要（不强制设阈值）。 |
| **文档** | 开发环境说明 | README 中补充 `pip install -e .`、`pip install .[build]`、`make init`、`make test`、虚拟环境建议。 |
| | 贡献指南 | CONTRIBUTING 或 docs：check 插件（yaml + python）、display/gather 场景的添加方式与示例。 |
| | 架构/模块说明 | docs 中新增简短架构说明：diag_cmd → core → handler → plugin 的调用关系。 |
| **代码规范** | 类型注解 | 对 src/common（config、context、result_type）和 1–2 个 handler 入口补充 type hints，便于 IDE 与静态检查。 |
| | 文档字符串 | 对核心类（ObdiagHome、CheckHandler、GatherComponentLogHandler 等）补充 docstring。 |
| **体验** | 错误信息可读性 | 对 config 缺失、SSH 失败、OB 版本不兼容等常见错误给出明确提示与文档链接。 |
| **AI 基础** | ai_assistant 配置与文档 | 梳理 conf/ai.yml 与环境变量；文档中明确 BETA 范围、推荐用法、OpenAI/OBI 配置示例与降级策略。 |
| | AI 模块单测 | 对 openai_client、obi_client、ai_assistant_handler 的配置解析与请求构造做 mock 单测（不调用真实 API）。 |
| | 错误处理与降级 | 对 API 超时、限流、鉴权失败等做统一错误处理与用户可读提示；无可用后端时给出明确说明。 |
| | MCP 现状梳理 | 梳理 mcp_client/mcp_server 与 obdiag-mcp 的现状；在 docs 中记录已暴露能力与后续扩展点。 |

**交付物**：  
- 至少 2 项技术债修复合入（含 err_stream 或异常统一）。  
- 至少 3 类测试补充：check、gather、display/rca 中至少各 1 个方向。  
- **AI**：ai_assistant 配置/文档更新、至少 1 个 AI 相关单测、错误处理与降级逻辑落地。  
- README/CONTRIBUTING 及可选架构说明更新。  
- 至少 1 个模块的类型注解或 docstring 增强。

---

### 4.2 三月：场景与兼容

**目标**：扩展巡检与展示场景，提升对多版本 OceanBase 及部署环境的兼容性；在 AI 辅助下增加场景数量与 analyze/gather 增强。

| 类别 | 事项 | 说明 |
|------|------|------|
| **Check** | 场景扩展 | 新增或增强 3–5 个 observer/obproxy 检查场景（集群、磁盘、网络、参数等）。 |
| | 包与任务组织 | 梳理 observer_check_package 与任务目录；支持按标签/场景过滤（如 `--case k8s_basic`）。 |
| | 检查结果结构化 | 可选：check 结果支持 JSON 导出，便于外部系统集成。 |
| **Display** | 场景扩展 | 新增 2–3 个 display 场景（如与 4.x 新特性、资源使用、复制延迟相关的视图）。 |
| | 输出格式 | 支持 table/json 等输出格式选项（与现有 display 逻辑兼容）。 |
| **RCA** | 场景扩展 | 新增或完善 2–3 个 rca 场景（日志、性能、事务、锁等高频问题）。 |
| | 场景文档 | 每个 rca 场景在代码或 docs 中补充简要说明与适用条件。 |
| **Analyze** | 能力增强 | 对 analyze_sql_review、analyze_memory 等补充 1–2 项规则或输出优化。 |
| **Gather** | 能力增强 | 对 gather_log 的 redact、gather_scenes 的 scene 列表做文档或小优化；可选：gather 进度输出更细化。 |
| **兼容** | OB 版本 | 对 4.2.x / 4.3.x 在 check/display/gather 中的 SQL 或系统表做兼容性验证与修正。 |
| | 环境 | K8s/Docker 下 gather/check 的路径与权限核对；补充部署文档。 |
| **依赖** | 依赖与安全 | 审查 pyproject.toml 依赖版本，升级已知 CVE 的库。 |
| **AI 能力** | 意图识别与指令映射 | 对用户自然语言做意图分类（如「采集日志」「跑巡检」「看内存」），映射到 obdiag gather/check/display 等子命令与参数。 |
| | 与 check/gather 联动 | 在 ai_assistant 中支持「执行一次 check」「执行 gather log」等指令，调用现有 handler 并汇总结果给用户（可先做 1–2 条指令闭环）。 |
| | 与 display/rca 联动 | 支持「展示 compaction」「跑一次 rca 事务超时」等指令，返回 display/rca 结果摘要或建议。 |
| | 上下文与历史 | 对话内保留当前集群/配置上下文；可选：简短对话历史（轮数可配置）以支持多轮追问。 |
| | Prompt 与系统角色 | 优化 system prompt，明确 obdiag 能力边界与推荐话术；可选：增加「诊断建议」模板（如先 check 再 gather 再 analyze）。 |

**交付物**：  
- 3–5 个 check 相关能力（新场景或包/标签整理）合入。  
- 2–3 个 display、2–3 个 rca 相关增强。  
- 至少 1 项 analyze 或 gather 增强。  
- **AI**：意图识别或指令映射落地、至少 1 条「AI 触发 check/gather/display」闭环；Prompt/上下文至少 1 项优化。  
- 版本/环境兼容性说明或文档更新。

---

### 4.3 四月：体验与 AI/工具

**目标**：提升报告与交互体验，将 AI 助手与工具链从 BETA 推向更可用状态；在 AI 辅助下完成更多体验与可观测项。

| 类别 | 事项 | 说明 |
|------|------|------|
| **报告** | check 报告 | 表格/HTML 报告可读性（列宽、排序、关键项高亮、失败项置顶）。 |
| | display 输出 | 长表或大结果的分页/截断策略与格式统一。 |
| | 报告导出 | 支持 check 报告导出为 HTML/JSON，便于归档与分享。 |
| **交互** | 进度与取消 | 长时间 gather/check 的进度提示与友好取消（Ctrl+C 后的清理与提示）。 |
| | 静默与输出 | 完善 `--silent` 与输出格式（md/json）的一致性。 |
| **AI 专项** | 多后端与配置 | 支持 OpenAI 兼容 base_url、model 选择；OBI 与 OpenAI 可配置切换；文档中说明各后端适用场景。 |
| | 对话与上下文 | 多轮对话历史（轮数可配置）、当前集群/配置上下文保持；长回复分页或流式输出（可选）。 |
| | BETA→GA 准备 | 错误处理与降级完善、配置校验、日志与 trace 关联；发布说明中明确 AI 功能范围与限制；视情况摘掉 BETA 标识或保留「推荐场景」说明。 |
| | MCP 扩展 | 完善 obdiag-mcp 文档与示例；暴露 2–3 个 MCP 工具（如 run_check、gather_list、display_scene 等），便于 IDE/Agent 调用 obdiag。 |
| | AI 与报告 | 可选：对 check 报告做简短 AI 摘要或建议（如「建议优先处理以下项」）；与现有报告导出兼容。 |
| **工具** | io_performance | 根据反馈修 bug、补文档与示例；可选单测。 |
| | config_check | 校验规则与输出优化；文档与示例。 |
| | crypto_config | 文档与使用场景说明。 |
| **可观测** | 日志与 Trace | 关键路径（gather/check/rca）的 trace_id 与日志关联；可选：结构化日志字段。 |
| | 耗时统计 | 对 gather/check 各阶段输出耗时摘要，便于定位慢点。 |
| **发布** | 4.1.0 | 发布说明：汇总 2–4 月改动、升级与兼容说明、已知限制；更新 README Roadmap 表格。 |

**交付物**：  
- check/display 至少 2 处报告或交互体验改进。  
- **AI**：多后端/配置或 BETA→GA 准备落地、MCP 至少 2 个工具暴露并文档化、对话/上下文至少 1 项优化。  
- 工具链（io_performance/config_check/crypto_config）至少 1 处文档或功能改进。  
- 4.1.0 发布说明与版本发布（含 AI 功能说明）。

---

## 五、AI 投入汇总（三个月）

| 月份 | 重点 | 关键产出 |
|------|------|----------|
| **2 月** | AI 基础 | 配置/文档、AI 模块单测、错误处理与降级、MCP 现状梳理与文档 |
| **3 月** | AI 能力 | 意图识别/指令映射、与 check/gather/display/rca 联动（至少 1 条闭环）、Prompt 与上下文优化 |
| **4 月** | AI 专项 | 多后端与配置、对话与上下文、BETA→GA 准备、MCP 2–3 个工具暴露、可选 AI 报告摘要 |

**AI 依赖与风险**：依赖外部 API（OpenAI/OBI）与网络；需在文档中说明环境要求、鉴权方式与降级策略；3 月联动需注意调用 obdiag 子流程时的环境与权限一致性。

---

## 六、依赖与风险

- **人力**：在 Cursor 等 AI 辅助下，可争取完成上述大部分项；若人力有限，可优先 2 月技术债与 AI 基础、3 月场景与 AI 联动、4 月体验与 AI 专项及发布，其余标为 backlog。  
- **OceanBase 版本**：新 SQL/视图可能影响 check/display/gather，建议 3 月做一次 4.2/4.3 回归。  
- **AI 依赖**：AI 助手依赖外部 API 与网络，需在文档中说明环境要求、鉴权与降级策略；AI 触发子命令时需保证与直接执行 obdiag 的行为一致（配置、权限、错误处理）。

---

## 七、成功指标（扩展版）

| 指标 | 目标（三个月内） |
|------|------------------|
| 技术债 | 至少 3 项修复（err_stream、异常统一、重复代码收敛等） |
| 测试 | 新增不少于 6 个与 handler 或核心流程相关的测试用例（含 **至少 1 个 AI 模块单测**） |
| 场景 | 新增或明显增强不少于 6 个 check 场景、2 个 display、2 个 rca |
| 体验 | 至少 2 项报告或交互体验改进、1 项可观测（trace/耗时）改进 |
| **AI** | **2 月**：配置/文档 + 错误处理与降级 + 1 个 AI 单测；**3 月**：至少 1 条「AI 触发 check/gather/display」闭环 + Prompt/上下文优化；**4 月**：多后端或 BETA→GA 准备 + MCP 至少 2 个工具暴露 + 对话/上下文 1 项优化 |
| 工具链 | 工具链（io_performance/config_check/crypto_config）至少 1 处文档或功能改进 |
| 文档 | 开发/贡献/架构说明至少 1 份新增或显著更新；**AI 使用与配置文档**更新 |
| 发布 | 4.1.0 发布并附带发布说明（含 AI 功能说明） |

---

## 八、与历史 Roadmap 的衔接

- 延续 README 中 3.6–4.0 的脉络：MCP、AI 助手、io_performance、config_check、display compaction、RCA 扩展等，在本规划中通过「稳定与质量 → 场景与兼容 → 体验与 AI」三阶段落实和收尾。
- **在 Cursor 辅助下**：规划中增加了更多可拆 PR 的功能点，便于按周/按模块推进；每项仍保持可验收、可文档化。

---

*文档版本：v3；基于 2026 年 2 月项目状态编写；在 Cursor 等 AI 辅助开发前提下扩展了功能密度与成功指标；**本月度规划中显著增加 AI 部分投入**（2 月基础、3 月能力联动、4 月专项与发布就绪）。*
