# 项目优化：如何开始

本文档给出「整体项目优化」的**起步顺序**和**可执行清单**，便于按优先级推进、避免摊大饼。

---

## 一、先做「立刻能做的」（本周可完成）

这些改动风险小、收益明确，适合作为第一周的小目标。

| 序号 | 事项 | 说明 | 状态 |
|------|------|------|------|
| 1 | 修复 `custum` → `custom` | `src/common/core.py` 中错误拼写，统一错误提示。 | 见下方已修复 |
| 2 | 修复 `make test` 路径 | Makefile 中 `tests/` 改为 `test/`，与项目目录一致。 | 见下方已修复 |
| 3 | 确认本地能跑通测试 | 执行 `make test` 或 `PYTHONPATH=. python3 -m pytest test/ -v`，确保现有用例通过。 | 待你本地验证 |
| 4 | 在 README 中补充开发命令 | 增加 `pip install -e .`、`make init`、`make test` 的简短说明。 | 可选 |

完成上述 1～3 后，你就有了「改完能验」的基础。

---

## 二、再做「短期可规划」（2～4 周）

按「稳定 → 测试 → 文档」顺序，每项都可以拆成 1～2 个 PR。

### 2.1 稳定与可维护性

- **stdio 的 err_stream**：落实 `diag_cmd.py` / `stdio.py` 中的 TODO，将错误输出切到 `sys.stderr`（可做成可选，避免破坏现有行为）。
- **异常与日志**：在 1～2 个高频路径（如 config 加载、SSH 连接）统一错误信息格式（例如「原因 + 建议 + 文档链接」）。

### 2.2 测试

- **统一入口**：CI 和本地都使用同一套命令（如 `pytest test/`），在 README/CONTRIBUTING 中写清楚。
- **补 1～2 个 Handler 单测**：优先选「不依赖真实 OB/SSH」的模块，例如：
  - `CheckHandler` 的配置解析、任务列表加载；
  - 某个 gather 子命令的参数解析与 context 构建（用 mock）。
- **目标**：`make test` 一次能跑完全部用例，且至少 1 个新用例覆盖 handler 层。

### 2.3 文档与贡献体验

- **开发环境**：在 README 或 `docs/` 中写清：Python 版本、`pip install -e .`、虚拟环境建议、`make init` / `make test`。
- **贡献流程**：如何加 check 任务、display 场景、gather 任务（yaml/python 各一例），便于新人按文档贡献。

---

## 三、中期按「三个月规划」推进

详见 [ROADMAP_3MONTHS.md](ROADMAP_3MONTHS.md)，这里只做对应关系：

- **2 月**：对应上文「短期可规划」的收尾 + 更多测试与文档。
- **3 月**：场景扩展（check/display/rca）+ OB 版本/环境兼容。
- **4 月**：报告与交互体验 + AI/工具链可用性。

优化时优先完成「立刻能做的」和「短期可规划」，再按月度拆 issue，避免一开始就铺太多需求。

---

## 四、建议的起步动作（今天就可以做）

1. **拉最新代码，跑一遍**  
   `make init`（或 `pip install -e .`）→ `make test`，确认当前状态。

2. **选一个「立刻能做的」项**  
   若尚未修复：先做 `custum` 修正和 `make test` 路径修正（见下），提交一个小 PR。

3. **列一张你自己的「优化 backlog」**  
   把 [ROADMAP_3MONTHS.md](ROADMAP_3MONTHS.md) 里你关心的项复制到 issue 或本地列表，标上「本周 / 本月 / 后续」。

4. **每次只推进 1～2 个主题**  
   例如：本周只做「拼写 + test 路径 + 文档里补充 make test」；下周再做「一个 CheckHandler 单测」。这样容易收口、也方便 review。

---

## 五、已在本仓库内完成的快速修复

- **`src/common/core.py`**：所有 `No such custum config` 已改为 `No such custom config`。
- **Makefile**：`test` 目标中的 `tests/` 已改为 `test/`，与现有 `test/` 目录一致。

你可以从「跑一遍 `make test`、再挑一个短期项」开始，后续按本文档和三个月规划迭代即可。
