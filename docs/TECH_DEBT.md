# 技术债清单

本文档列出当前已知技术债，按**必须马上解决**与**应尽快解决**分类，便于按优先级处理。技术债理论上是必须马上解决的事，建议优先处理「必须马上解决」项。

---

## 一、必须马上解决

以下项影响正确性、Python 3 兼容性或标准行为，应优先修复。

### 1.1 错误输出流（err_stream）默认应为 stderr

| 位置 | 说明 |
|------|------|
| `src/common/diag_cmd.py` 第 34–35 行 | TODO 注明：obdiag_version ≥ 3.0 时 err_stream 默认改为 sys.stderr；当前 `ROOT_IO = IO(1, error_stream=sys.stdout)` 导致错误与正常输出混在 stdout。 |
| `src/common/stdio.py` 第 433 行 | TODO：默认分支 `error_stream = sys.stdout` 应改为 `sys.stderr`，与 diag_cmd 保持一致。 |

**建议**：将默认错误流改为 `sys.stderr`，保证错误信息与标准输出分离；若有依赖 stdout 的脚本，可在配置或环境变量中提供兼容选项。

---

### 1.2 main.py 中的 Python 2 遗留代码

| 位置 | 说明 |
|------|------|
| `src/main.py` 第 37–45 行 | 使用 `sys.getdefaultencoding()`、`sys.setdefaultencoding()` 及 `from imp import reload`。Python 3 中无 `setdefaultencoding`，且项目要求 Python ≥3.11，`imp` 已在 3.12 移除；该分支在 3.x 上实际不生效或存在兼容风险。 |

**建议**：删除该分支（或仅保留 `import importlib; importlib.reload(sys)` 若确需 reload），避免依赖已废弃模块并明确仅支持 Python 3。

---

### 1.3 裸 except 吞掉异常（影响排障）

以下位置使用裸 `except:` 或 `except Exception:` 后直接 `pass`，既不记录也不再抛，导致失败原因难以排查。**至少应记录日志或按需再抛。**

| 文件 | 行号 | 说明 |
|------|------|------|
| `src/main.py` | 40 | 顶层 `except: pass`，启动阶段异常被吞。**注意：保留不改，为经验 feature** |
| `src/telemetry/telemetry.py` | 175–176 | 裸 except + pass。**已处理：保持静默失败，已添加注释说明** |
| `src/common/command.py` | 38, 47, 219 | 多处 except 后未记录。**已处理：已有日志记录** |
| `src/common/diag_cmd.py` | 341, 380 | except 后 pass。**已处理：已有日志记录** |
| `src/common/config_helper.py` | 401–402 | except + pass。**已处理：已有日志记录** |
| `src/common/tool.py` | 多处 139, 203, 215, 226, 369, 407, 557, 568, 580, 867, 880, 1704, 1762, 1777 | 大量 except 后 pass，工具函数内失败难以定位。 |
| `src/common/stdio.py` | 506–507 | except + pass。 |
| `src/common/ssh_client/local_client.py` | 74 | except + pass。 |
| `src/common/ssh.py` | 241, 521 | except + pass。 |
| `src/common/types.py` | 46, 317 | except + pass。 |
| `src/handler/gather/gather_sysstat.py` | 173, 186, 195, 203, 211, 219, 227, 235, 258 | **已处理**：已改为 except Exception 并补日志 |
| `src/handler/gather/gather_obstack2.py` | 184, 264 | **已处理**：已改为 except Exception 并补日志 |
| `src/handler/gather/gather_core.py` | 431 | **已处理**：已改为 except Exception 并补日志 |
| `src/handler/gather/gather_obadmin.py` | 315 | **已检查**：已有日志记录 |
| `src/handler/gather/gather_perf.py` | 281, 307, 315, 341 | **已处理**：已改为 except Exception 并补日志 |
| `src/handler/analyzer/analyze_sql.py` | 183 | **已检查**：无问题 |
| `src/handler/analyzer/analyze_flt_trace.py` | 320, 353, 360, 560, 571 | **已处理**：已改为 except Exception 并补日志 |
| `src/handler/meta/sql_meta.py` | 33, 39 | **已处理**：已改为 except Exception 并改进日志 |
| `src/handler/meta/check_meta.py` | 33, 39 | **已处理**：已改为 except Exception 并改进日志 |
| `src/handler/meta/html_meta.py` | 33, 39 | **已处理**：已改为 except Exception 并改进日志 |

**建议**：按模块分批改：至少 `self.stdio.warn(...)` 或 `logging.exception(...)` 记录异常；若为关键路径则考虑再抛或返回明确错误结果，避免静默失败。

---

## 二、应尽快解决

以下项不立即导致错误，但会累积维护成本或影响可维护性，建议尽快排期。

### 2.1 代码中的 TODO / 未完成逻辑

| 位置 | 说明 |
|------|------|
| `src/common/core.py` 第 494 行 | `# todo not support silent`：analyze_sql 尚未支持 silent 模式，与其它子命令行为不一致。 |
| `src/handler/display/display_scenes.py` 第 88 行 | `# todo display no code task`：display 中「无 code 任务」的处理未实现或未理清。 |
| `plugins/rca/memory_full.py` 第 134 行 | `# TODO When connection is not available, use logs for troubleshooting`：无连接时的降级策略未实现。 |

---

### 2.2 重复代码（core.py 中“No such custom config”）

| 位置 | 说明 |
|------|------|
| `src/common/core.py` | 约 16 处相同判断与报错：`if not config` 后 `_call_stdio('error', 'No such custom config')` 并返回 `ObdiagResult(INPUT_ERROR_CODE, ...)`。 |
| `src/common/core.py` | **拼写错误**：13 处将 "custom" 误写为 "custum"（第 252, 253, 413, 414, 437, 438, 476, 477, 505, 506, 596, 597, 649, 650, 661, 662, 680, 681, 692, 693, 707, 708, 762, 763 行），3 处正确（第 719, 720, 733, 734, 748, 749 行）。 |

**建议**：
1. 抽成私有方法如 `_require_config(config)`，统一返回错误结果并减少重复。
2. 修复所有拼写错误，统一为 "custom"。

---

### 2.3 占位符与废弃标记

| 位置 | 说明 |
|------|------|
| `src/handler/check/check_task.py` 第 157 行 | `get_task_info` 示例中 `issue_link` 为 `"https://github.com/oceanbase/obdiag/issues/xxx"`，应改为实际 issue 模板或说明。 |
| `src/handler/analyzer/log_parser/log_entry.py` 第 47 行 | `self.log_type = log_type  # deprecated`：若已废弃，应移除或明确迁移路径并文档化。 |

---

### 2.4 异常处理过宽（except Exception 后仅 pass）

以下位置在捕获 `Exception` 后仅 `pass`，未记录也未向上传递，排障困难。建议至少打日志或返回/抛出明确错误。

- `src/handler/tools/io_performance_handler.py` 103 **已处理**：已补日志
- `src/handler/ai/ai_assistant_handler.py` 510–511 **已处理**：已补日志
- `src/handler/ai/mcp_server.py` 416–417（已检查，无except pass问题）
- `src/handler/ai/openai_client.py` 203–204, 223–224, 775–776 **已处理**：已补日志
- `src/handler/ai/mcp_client.py` 多处 116, 137, 178, 377, 401, 412, 431 **已处理**：已补日志
- `src/handler/tools/config_check_handler.py` 123–124 **已处理**：已补日志
- `src/handler/gather/gather_log/base.py` 124–125 **已处理**：已补日志
- `src/handler/gather/gather_component_log.py` 235（已检查，无except pass问题）
- `src/handler/gather/gather_dbms_xplan.py` 407, 210–211（已检查，无except pass问题）
- `src/handler/analyzer/sql/rules/review/*.py` 中多处 `except Exception as e: pass`（arithmetic, select_all, full_scan, large_in_clause, multi_table_join, is_null, update_delete_* 等）（待处理）

**注意**：项目中已定义 `ErrorHandler` 类（`src/common/error_handler.py`），但大部分代码未使用，仍采用裸 except。建议逐步迁移到统一的错误处理框架。

---

### 2.5 配置默认值不一致

| 位置 | 说明 |
|------|------|
| `src/common/config.py` vs `conf/inner_config.yml` | `DEFAULT_INNER_CONFIG` 与 `inner_config.yml` 中的默认值不一致：<br>- `file_number_limit`: 20 (config.py) vs 50 (inner_config.yml)<br>- `file_size_limit`: '2G' (config.py) vs '5G' (inner_config.yml)<br>- `ssh_client.cmd_exec_timeout`: 缺失 (config.py) vs 180 (inner_config.yml) |

**建议**：统一配置默认值来源，建议以 `inner_config.yml` 为准，`DEFAULT_INNER_CONFIG` 仅作为运行时 fallback，或通过代码自动从 YAML 加载。

---

### 2.6 并发实现不一致

| 位置 | 说明 |
|------|------|
| `src/handler/check/check_handler.py` | 使用 `ThreadPoolExecutor`（推荐方式） |
| `src/handler/analyzer/analyze_memory.py` | 使用 `threading.Thread` |
| `src/handler/gather/gather_component_log.py` | 使用 `threading.Thread` |
| `src/handler/tools/config_check_handler.py` | 使用 `threading.Thread` |
| `src/handler/analyzer/analyze_flt_trace.py` | 使用 `ProcessPoolExecutor` |
| `src/common/ssh.py` | 使用 `multiprocessing.Pool`（`ThreadPool`） |

**建议**：统一并发实现方式。对于 I/O 密集型任务（SSH、数据库查询），建议统一使用 `ThreadPoolExecutor`；对于 CPU 密集型任务，使用 `ProcessPoolExecutor`。统一后便于管理线程池大小、超时、错误处理等。

---

### 2.7 配置访问方式不一致

| 位置 | 说明 |
|------|------|
| `src/common/config_accessor.py` | 部分属性使用 `self.inner_config.get(...)`（如 `check_max_workers`），部分使用 `self.inner_config.config.get(...)`（如 `gather_work_path`），访问方式不统一。 |

**建议**：统一配置访问方式。建议在 `ConfigAccessor` 中封装统一的访问方法，避免直接访问 `inner_config` 的内部结构。

---

### 2.8 已废弃代码未移除

| 位置 | 说明 |
|------|------|
| `plugins/rca/transaction_wait_timeout.py` | 标记为 `[Deprecated]`，建议使用 `lock_conflict` 场景，但代码未移除。 |
| `plugins/rca/transaction_not_ending.py` | 标记为 `[Deprecated]`，建议使用 `suspend_transaction` 场景，但代码未移除。 |

**建议**：如果确定不再使用，应移除废弃代码；若需保留兼容性，应在文档中明确说明废弃时间表和迁移路径，并在代码中添加警告日志。

---

### 2.9 类型注解缺失

| 位置 | 说明 |
|------|------|
| `src/common/config.py` | 大量方法缺少类型注解（如 `__init__`, `load_config`, `get_ob_cluster_config` 等）。 |
| `src/common/core.py` | 大量方法缺少类型注解。 |
| `src/common/tool.py` | 大量工具函数缺少类型注解。 |

**建议**：逐步为公共 API 和核心模块补充类型注解，提升代码可读性和 IDE 支持。优先处理 `src/common` 下的核心模块。

---

## 三、处理优先级建议

| 优先级 | 项 | 预估工作量 |
|--------|----|------------|
| P0 | 1.1 err_stream 改为 stderr | 小 |
| P0 | 1.2 main.py 移除 Python 2 遗留 | 小 |
| P0 | 2.2 core.py 修复拼写错误（custum → custom） | 小 |
| P1 | 1.3 裸 except：至少从 main、telemetry、command、diag_cmd、config_helper 开始补日志或再抛 | 中 |
| P1 | 2.5 配置默认值统一（DEFAULT_INNER_CONFIG vs inner_config.yml） | 小 |
| P2 | 2.1 三个 TODO 的落实或文档化 | 小 |
| P2 | 2.2 core.py 抽取 _require_config 并修复拼写 | 小 |
| P2 | 2.3 占位符与 deprecated 清理 | 小 |
| P2 | 2.6 并发实现统一（ThreadPoolExecutor vs threading.Thread） | 中 |
| P2 | 2.7 配置访问方式统一 | 小 |
| P2 | 2.8 已废弃代码处理（移除或明确迁移路径） | 小 |
| P3 | 1.3 其余 gather/analyzer/meta 等 except 补日志 | 中（大部分完成：gather、meta、analyzer 模块已处理） |
| P3 | 2.4 AI/工具等 Exception 后 pass 的补日志或返回错误 | 中（部分完成：AI 模块主要文件已处理） |
| P3 | 2.9 类型注解补充（优先 common 模块） | 大 |

---

## 四、与 ROADMAP 的对应

- **2 月「技术债」**：建议在本月完成 P0（1.1、1.2、2.2 拼写错误）及 P1 中列出的核心模块裸 except 整改和配置统一；2.2（core 抽取）可一并放入 2 月。
- 其余 P2/P3 可排入后续迭代，并在完成后在本文档中勾选或移入「已解决」小节。

---

## 五、新增发现的技术债（2026年2月补充）

本次分析新增发现以下技术债：

1. **拼写错误**：`core.py` 中 13 处 "custum" 应为 "custom"（P0）
2. **配置不一致**：`DEFAULT_INNER_CONFIG` 与 `inner_config.yml` 默认值不一致（P1）
3. **并发实现不统一**：混用 ThreadPoolExecutor、threading.Thread、ProcessPoolExecutor（P2）
4. **配置访问不统一**：`config_accessor.py` 中访问方式不一致（P2）
5. **废弃代码未处理**：transaction_wait_timeout 和 transaction_not_ending 标记废弃但未移除（P2）
6. **类型注解缺失**：大量核心模块缺少类型注解（P3）
7. **ErrorHandler 未充分使用**：已定义统一错误处理框架但大部分代码未使用（P3）

---

*文档版本：v2；基于 2026 年 2 月对 src 与 plugins 的深入扫描结果，新增 7 项技术债。*
