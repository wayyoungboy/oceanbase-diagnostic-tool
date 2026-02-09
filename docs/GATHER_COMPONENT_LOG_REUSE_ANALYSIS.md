# GatherComponentLogHandler 复用分析报告

## 概述

`GatherComponentLogHandler` 是一个统一的组件日志采集处理器，支持 observer、obproxy、oms 三种组件的日志采集。本文档分析了代码库中可以复用该 Handler 的场景，以减少重复代码和建设成本。

---

## 一、GatherComponentLogHandler 功能特性

### 1.0 使用方式说明

**重要**：根据使用场景选择合适的方式：

1. **RCA 场景**（`plugins/rca/*.py`）：
   - **应使用 `gather_log` 插件（中间件）**，而不是直接调用 `GatherComponentLogHandler`
   - `gather_log` 插件在 `RcaScene.init()` 中通过 `context.get_variable("gather_log")` 获取
   - 该插件封装了 `GatherComponentLogHandler`，提供了更友好的 API
   - 参考：`src/handler/rca/plugins/gather.py`

2. **非 RCA 场景**（如 `src/handler/analyzer/*.py`、`plugins/gather/tasks/*.py`）：
   - 可直接使用 `GatherComponentLogHandler`
   - 需要手动创建和初始化 handler

### 1.1 核心能力

- **多组件支持**：observer、obproxy、oms
- **灵活的过滤选项**：
  - `from` / `to`：时间范围过滤
  - `since`：相对时间过滤（如 "30m"）
  - `scope`：日志范围过滤（如 "all", "observer", "election" 等）
  - `grep`：关键词过滤（支持多个关键词）
  - `recent_count`：仅采集最近 N 个日志文件
- **并发执行**：支持多节点并行采集
- **日志脱敏**：支持 redact 功能
- **结果汇总**：自动生成采集结果摘要

### 1.2 使用方式

#### 方式一：RCA 场景使用 `gather_log` 插件（推荐）

**⚠️ 重要性能原则**：日志采集原则上不要重复调用，因为相对比较消耗资源。如果存在多次调用（基于不同 grep 关键词的），应该先一次性采集日志，然后在本地分析。

**❌ 错误示例**（多次调用，浪费资源）：
```python
# 错误：多次调用 gather_log.execute()
self.gather_log.grep("error")
logs_error = self.gather_log.execute(save_path="/path/to/error_logs")

self.gather_log.reset()  # 需要重置
self.gather_log.grep("warning")
logs_warning = self.gather_log.execute(save_path="/path/to/warning_logs")

self.gather_log.reset()  # 需要重置
self.gather_log.grep("critical")
logs_critical = self.gather_log.execute(save_path="/path/to/critical_logs")
```

**✅ 正确示例**（一次性采集，本地分析）：
```python
# 在 RCA 场景中，gather_log 插件已在 RcaScene.init() 中初始化
# self.gather_log = context.get_variable("gather_log")

# 设置参数
self.gather_log.set_parameters("target", "observer")  # 或 "obproxy", "oms"
self.gather_log.set_parameters("scope", "all")  # 日志范围
self.gather_log.set_parameters("since", "30m")  # 时间范围

# 如果需要多个关键词，可以一次性设置（grep 会使用 AND 逻辑）
# 或者不设置 grep，采集完整日志后在本地分析
# self.gather_log.grep("error")  # 可选：如果确定只需要这些关键词

# 设置过滤节点（可选）
self.gather_log.set_parameters("filter_nodes_list", [specific_node])

# 一次性执行采集
result_log_files = self.gather_log.execute(save_path="/path/to/store")

# 在本地对采集的日志进行分析
for log_file in result_log_files:
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        # 本地分析多个关键词
        if "error" in content:
            # 处理 error 相关日志
            pass
        if "warning" in content:
            # 处理 warning 相关日志
            pass
        if "critical" in content:
            # 处理 critical 相关日志
            pass
```

**✅ 如果确实需要多个关键词过滤，使用 AND 逻辑**：
```python
# 设置多个关键词（AND 逻辑：同时包含这些关键词）
self.gather_log.grep("major_merge_progress_checker")
self.gather_log.grep(f"T{tenant_id}")

# 一次性执行
result_log_files = self.gather_log.execute(save_path="/path/to/store")
```

**✅ 参考示例**（`plugins/rca/major_hold.py` 的 `_handle_weak_read_not_ready` 方法）：
```python
# 一次性设置多个关键词（AND 逻辑）
if weak_read_scn:
    self.gather_log.grep(str(int(weak_read_scn) + 1))
self.gather_log.grep("generate_weak_read_timestamp_")
self.gather_log.grep("log disk space is almost full")

# 一次性执行采集
self.gather_log.execute(save_path=work_path)
```

#### 方式二：非 RCA 场景直接使用 `GatherComponentLogHandler`

```python
handler = GatherComponentLogHandler()
handler.init(
    context=self.context,
    target="observer",  # 或 "obproxy", "oms"
    nodes=nodes_list,  # 节点列表
    from_option="2024-01-01 00:00:00",
    to_option="2024-01-01 23:59:59",
    since="30m",  # 或 from/to
    scope="all",  # 日志范围
    grep=["error", "warning"],  # 关键词列表
    store_dir="/path/to/store",
    temp_dir="/tmp",
    redact=True,  # 是否脱敏
    is_scene=True,  # 是否在场景中使用
    oms_component_id=None,  # OMS 组件 ID（用于 CDC 日志）
    recent_count=0,  # 仅采集最近 N 个文件
)
result = handler.handle()
```

---

## 二、已使用 GatherComponentLogHandler 的场景

以下场景已经正确使用了 `GatherComponentLogHandler`，无需改动：

### 2.1 RCA 插件

| 文件 | 说明 |
|------|------|
| `src/handler/rca/plugins/gather.py` | RCA 场景的通用日志采集插件，封装了 GatherComponentLogHandler |

### 2.2 Gather Scenes

| 文件 | 说明 |
|------|------|
| `plugins/gather/tasks/observer/perf_sql.py` | SQL 性能问题场景，使用 trace_id 过滤采集日志 |
| `plugins/gather/tasks/observer/sql_err.py` | SQL 错误场景，使用 trace_id 过滤采集日志 |
| `plugins/gather/tasks/observer/px_collect_log.py` | PX 收集日志场景，使用 trace_id 和时间范围过滤 |
| `plugins/gather/tasks/observer/cpu_high.py` | CPU 高场景，采集所有 observer 日志 |

### 2.3 Gather Steps

| 文件 | 说明 |
|------|------|
| `src/handler/gather/step/base.py` | Gather 场景的 step 类型为 "log" 时，使用 GatherComponentLogHandler |

### 2.4 通过 gather_log 插件间接使用

以下 RCA 场景通过 `gather_log` 插件（内部使用 GatherComponentLogHandler）进行日志采集：

| 文件 | 说明 |
|------|------|
| `plugins/rca/memory_full.py` | 内存爆场景，采集 observer 日志 |
| `plugins/rca/weak_read_troubleshooting.py` | 弱读问题排查，采集所有日志后本地分析 |
| `plugins/rca/gc_troubleshooting.py` | GC 问题排查，使用 grep 过滤 GC 相关日志 |
| `plugins/rca/transaction_not_ending.py` | 事务不结束场景，使用 tx_id 过滤采集日志 |
| `plugins/rca/oms_obcdc.py` | OMS OBCDC 场景，采集 OMS CDC 日志 |

**注意**：这些场景已经通过 `gather_log` 插件间接使用了 `GatherComponentLogHandler`，实现方式合理，无需改动。

---

## 三、可以复用但当前使用直接 SSH 命令的场景

以下场景当前使用直接的 SSH 命令进行日志采集，可以改为使用 `GatherComponentLogHandler` 以减少重复代码：

### 3.1 高优先级（建议优先改造）

#### 3.1.1 `plugins/rca/major_hold.py` - `_collect_observer_logs` 方法

**当前实现**：
```python
def _collect_observer_logs(self, tenant_id, tenant_record):
    # 使用直接 SSH grep 命令
    ssh_client.exec_cmd('grep "major_merge_progress_checker" {0}/log/rootservice.log* | grep "T{1}" -m 500 > {2}'.format(
        node.get("home_path"), tenant_id, log_name))
    ssh_client.download(log_name, local_log)
```

**建议改造**：
```python
def _collect_observer_logs(self, tenant_id, tenant_record):
    """Collect relevant observer logs for the tenant"""
    # 使用 gather_log 插件（中间件），而不是直接调用 GatherComponentLogHandler
    # gather_log 插件已经在 RcaScene.init() 中通过 context.get_variable("gather_log") 初始化
    if self.gather_log is None:
        tenant_record.add_record("gather_log plugin is not available")
        return
    
    # 设置过滤节点（仅采集特定节点的日志）
    node, ssh_client = self._find_observer_node(svr_ip, svr_port)
    if node:
        self.gather_log.set_parameters("filter_nodes_list", [node])
    
    # 设置日志范围和时间过滤
    self.gather_log.set_parameters("scope", "rootservice")  # 仅采集 rootservice 日志
    self.gather_log.set_parameters("target", "observer")
    
    # 设置 grep 关键词
    self.gather_log.grep("major_merge_progress_checker")
    self.gather_log.grep(f"T{tenant_id}")
    
    # 执行日志采集
    log_save_path = os.path.join(self.local_path, f"major_merge_progress_checker_{tenant_id}")
    self.gather_log.execute(save_path=log_save_path)
    
    tenant_record.add_record("Collected major_merge_progress_checker logs")
```

**说明**：
- RCA 场景中已经提供了 `gather_log` 插件作为中间件（在 `RcaScene.init()` 中通过 `context.get_variable("gather_log")` 获取）
- `gather_log` 插件内部封装了 `GatherComponentLogHandler`，提供了更友好的 API
- 应该使用 `gather_log` 插件而不是直接调用 `GatherComponentLogHandler`
- 参考 `_handle_weak_read_not_ready` 方法中已有的使用示例（第585-588行）

**优势**：
- 统一日志采集逻辑，减少重复代码
- 支持日志脱敏、并发采集等高级功能
- 自动处理日志文件压缩、时间过滤等
- 使用统一的中间件接口，保持代码风格一致

**改造难度**：低

---

#### 3.1.2 性能优化示例：`plugins/rca/transaction_other_error.py`

**当前实现**（多次调用，浪费资源）：
```python
def execute(self):
    # 第一次调用：采集 MEMORY 相关日志
    self.gather_log.grep("MEMORY")
    logs_memory = self.gather_log.execute(save_path=work_path_memory)
    
    # 第二次调用：采集 EASY SLOW 相关日志
    self.gather_log.reset()
    self.gather_log.grep("EASY SLOW")
    logs_easy_slow = self.gather_log.execute(save_path=work_path_easy_slow)
    
    # 第三次调用：采集 post trans 相关日志
    self.gather_log.reset()
    self.gather_log.grep("post trans")
    logs_post_trans = self.gather_log.execute(save_path=work_path_post_trans)
```

**建议改造**（一次性采集+本地分析）：
```python
def execute(self):
    # 一次性采集所有相关日志（不设置 grep 或设置最宽泛的过滤）
    self.gather_log.set_parameters("scope", "observer")
    self.gather_log.set_parameters("since", "30m")  # 设置时间范围
    
    # 一次性执行采集
    all_logs = self.gather_log.execute(save_path=work_path_all)
    
    # 在本地对采集的日志进行分析
    memory_logs = []
    easy_slow_logs = []
    post_trans_logs = []
    
    for log_file in all_logs:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
            
            # 本地分析：查找 MEMORY 相关日志
            memory_lines = [line for line in lines if "MEMORY" in line]
            if memory_lines:
                memory_logs.extend(memory_lines)
            
            # 本地分析：查找 EASY SLOW 相关日志
            easy_slow_lines = [line for line in lines if "EASY SLOW" in line]
            if easy_slow_lines:
                easy_slow_logs.extend(easy_slow_lines)
            
            # 本地分析：查找 post trans 相关日志
            post_trans_lines = [line for line in lines if "post trans" in line]
            if post_trans_lines:
                post_trans_logs.extend(post_trans_lines)
    
    # 保存分析结果到不同文件（如果需要）
    if memory_logs:
        self._save_analysis_result(work_path_memory, memory_logs)
    if easy_slow_logs:
        self._save_analysis_result(work_path_easy_slow, easy_slow_logs)
    if post_trans_logs:
        self._save_analysis_result(work_path_post_trans, post_trans_logs)
```

**优势**：
- **性能提升**：从 3 次网络传输+文件 I/O+压缩 减少到 1 次
- **资源节约**：显著减少服务器和网络资源消耗
- **灵活性**：本地分析可以更灵活地组合多个关键词

**改造难度**：中（需要重构本地分析逻辑）

---

#### 3.1.3 `src/handler/analyzer/analyze_memory.py` - `__pharse_log_file` 方法

**当前实现**：
```python
def __pharse_log_file(self, ssh_client, node, log_name, gather_path, local_store_dir):
    # 使用直接 SSH grep 命令
    grep_cmd = "grep -e '{grep_args}' {log_dir}/{log_name} >> {gather_path}/{log_name}".format(...)
    ssh_client.exec_cmd(grep_cmd)
    download_file(ssh_client, log_full_path, local_store_path, self.stdio)
```

**建议改造**：
```python
def __pharse_log_file(self, ssh_client, node, log_name, gather_path, local_store_dir):
    """Parse log file using GatherComponentLogHandler"""
    handler = GatherComponentLogHandler()
    handler.init(
        self.context,
        target="observer",
        scope="all",  # 或根据 log_name 确定具体 scope
        grep=[self.grep_args] if self.grep_args else None,
        nodes=[node],
        store_dir=local_store_dir,
        is_scene=True,
    )
    handler.handle()
    # 如果需要特定文件名，可以从 handler 的结果中提取
```

**优势**：
- 统一日志采集逻辑
- 支持多节点并发采集
- 自动处理日志文件查找、过滤、下载

**改造难度**：中（需要适配现有的 log_name 参数逻辑）

---

#### 3.1.4 `src/handler/analyzer/analyze_queue.py` - `__pharse_log_file` 方法

**当前实现**：
```python
def __pharse_log_file(self, ssh_client, node, log_name, gather_path, local_store_dir):
    # 使用直接 SSH grep 命令
    search_pattern = '"dump tenant info(tenant={{id:{tenant_id},"'
    grep_cmd = 'grep {search_pattern} {obs_log_path} >> {gather_log_path}'.format(...)
    ssh_client.exec_cmd(grep_cmd)
    download_file(ssh_client, log_full_path, local_store_path, self.stdio)
```

**建议改造**：
```python
def __pharse_log_file(self, ssh_client, node, log_name, gather_path, local_store_dir):
    """Parse log file using GatherComponentLogHandler"""
    handler = GatherComponentLogHandler()
    handler.init(
        self.context,
        target="observer",
        scope="all",
        grep=[f'dump tenant info(tenant={{id:{self.tenant_id},'],  # 使用 tenant_id 过滤
        nodes=[node],
        store_dir=local_store_dir,
        is_scene=True,
    )
    handler.handle()
```

**优势**：
- 统一日志采集逻辑
- 支持多节点并发采集
- 自动处理日志文件查找、过滤、下载

**改造难度**：中（需要适配现有的 log_name 和 tenant_id 参数逻辑）

---

### 3.2 中优先级（可以后续优化）

#### 3.2.1 `plugins/rca/major_hold.py` - 其他直接 SSH grep 的地方

**位置**：
- `_handle_schedule_medium_failed`：使用 `grep "schedule_medium_failed"`
- `_handle_error_no`：使用 `grep "{err_trace}"`
- `_handle_memtable_dag_failure`：使用 `grep "{thread_id}"`

**建议**：
这些方法主要用于快速定位特定错误信息，使用直接 grep 可能更高效。但如果需要完整的日志文件，建议使用 `GatherComponentLogHandler`。

**改造难度**：中（需要评估性能影响）

---

#### 3.2.2 `plugins/rca/major_hold.py` - `_collect_dmesg_logs` 方法

**当前实现**：
```python
def _collect_dmesg_logs(self, tenant_record):
    ssh_client.exec_cmd("dmesg -T > {0}".format(remote_log))
    ssh_client.download(remote_log, local_log)
```

**说明**：
`dmesg` 是系统内核日志，不属于组件日志，不适合使用 `GatherComponentLogHandler`。当前实现合理。

---

#### 3.2.3 `plugins/rca/oms_obcdc.py` - 直接 SSH grep 的地方

**位置**：
- `check_KBA`：使用多个 `grep` 命令查找特定日志内容

**说明**：
这些是日志分析逻辑，不是日志采集逻辑，不适合使用 `GatherComponentLogHandler`。当前实现合理。

---

## 四、改造建议与优先级

### 4.1 优先级排序

| 优先级 | 文件 | 方法 | 改造难度 | 收益 | 说明 |
|--------|------|------|----------|------|------|
| **P0** | `plugins/rca/major_hold.py` | `_collect_observer_logs` | 低 | 高 | 应使用 `gather_log` 插件（中间件），而非直接调用 `GatherComponentLogHandler` |
| **P0** | `plugins/rca/transaction_other_error.py` | `execute` | 中 | 高 | **性能优化**：多次调用改为一次性采集+本地分析 |
| **P0** | `plugins/rca/transaction_rollback.py` | `execute` | 中 | 高 | **性能优化**：多次调用改为一次性采集+本地分析 |
| **P0** | `plugins/rca/transaction_wait_timeout.py` | `execute` | 中 | 高 | **性能优化**：多次调用改为一次性采集+本地分析 |
| **P0** | `plugins/rca/lock_conflict.py` | `execute` | 中 | 高 | **性能优化**：多次调用改为一次性采集+本地分析 |
| **P1** | `src/handler/analyzer/analyze_memory.py` | `__pharse_log_file` | 中 | 高 | 可直接使用 `GatherComponentLogHandler`（非 RCA 场景） |
| **P1** | `src/handler/analyzer/analyze_queue.py` | `__pharse_log_file` | 中 | 高 | 可直接使用 `GatherComponentLogHandler`（非 RCA 场景） |
| **P2** | `plugins/rca/clog_disk_full.py` | 多个方法 | 中 | 中 | 评估：虽然多次调用，但都基于相同的 tenant_id/ls_id，可优化 |
| **P2** | `plugins/rca/index_ddl_error.py` | 多个方法 | 中 | 中 | 评估：虽然多次调用，但都基于相同的 trace_id，可优化 |
| **P2** | `plugins/rca/major_hold.py` | 其他 SSH grep（可选） | 中 | 中 | 评估是否适合使用 `gather_log` 插件 |

### 4.2 改造步骤

1. **第一步（性能优化）**：优化多次调用日志采集的场景
   - 优先改造 `transaction_other_error.py`、`transaction_rollback.py`、`transaction_wait_timeout.py`、`lock_conflict.py`
   - **改造模式**：
     ```python
     # 改造前：多次调用
     self.gather_log.grep("keyword1")
     logs1 = self.gather_log.execute(save_path="path1")
     self.gather_log.reset()
     self.gather_log.grep("keyword2")
     logs2 = self.gather_log.execute(save_path="path2")
     
     # 改造后：一次性采集+本地分析
     # 不设置 grep 或设置最宽泛的过滤
     all_logs = self.gather_log.execute(save_path="all_logs")
     # 本地分析
     for log_file in all_logs:
         with open(log_file, 'r') as f:
             content = f.read()
             if "keyword1" in content:
                 # 处理 keyword1
             if "keyword2" in content:
                 # 处理 keyword2
     ```
   - **收益**：显著减少资源消耗（网络传输、文件 I/O、压缩等）

2. **第二步**：改造 `major_hold.py` 的 `_collect_observer_logs` 方法
   - 影响范围小，改造简单
   - 使用已有的 `gather_log` 插件（中间件），参考 `_handle_weak_read_not_ready` 方法的使用方式
   - 可以验证复用方案的可行性

3. **第三步**：改造 `analyze_memory.py` 和 `analyze_queue.py`
   - 这些是 analyzer handler，不是 RCA 场景，没有 `gather_log` 插件
   - 可以直接使用 `GatherComponentLogHandler`
   - 需要适配现有的参数传递逻辑
   - 可能需要调整返回值处理

4. **第四步**：评估其他场景的改造价值
   - 根据实际使用情况决定是否改造
   - **注意**：RCA 场景应使用 `gather_log` 插件，非 RCA 场景可直接使用 `GatherComponentLogHandler`
   - 对于 `clog_disk_full.py` 和 `index_ddl_error.py`，虽然多次调用但都基于相同的基础过滤条件（tenant_id/ls_id 或 trace_id），可以考虑优化

### 4.3 注意事项

1. **使用场景区分**：
   - **RCA 场景**：应使用 `gather_log` 插件（中间件），该插件在 `RcaScene.init()` 中通过 `context.get_variable("gather_log")` 获取
   - **非 RCA 场景**（如 analyzer handler）：可直接使用 `GatherComponentLogHandler`
   - `gather_log` 插件内部封装了 `GatherComponentLogHandler`，提供了更友好的 API

2. **性能优化原则（重要）**：
   - **日志采集原则上不要重复调用**，因为相对比较消耗资源（涉及网络传输、文件 I/O、压缩等）
   - **如果需要对多个关键词进行分析**：
     - ✅ **正确做法**：先一次性采集日志（可以不带 grep 或使用最宽泛的过滤），然后在本地对采集回来的日志文件进行多次 grep 分析
     - ❌ **错误做法**：多次调用 `gather_log.execute()`，每次使用不同的 grep 关键词
   - **如果确实需要多个关键词过滤**：
     - 使用 AND 逻辑：多次调用 `gather_log.grep()`，然后一次性执行 `gather_log.execute()`
     - 注意：多个 `grep()` 调用是 AND 关系（日志行必须同时包含所有关键词）
   - **性能对比**：
     - 多次调用：N 次网络传输 + N 次文件 I/O + N 次压缩 = 高资源消耗
     - 一次性采集：1 次网络传输 + 1 次文件 I/O + 1 次压缩 + 本地多次 grep = 低资源消耗

3. **参数适配**：
   - 现有代码可能依赖特定的日志文件名或路径
   - 需要确保改造后能正确获取所需的日志文件
   - 使用 `gather_log` 插件时，注意调用 `reset()` 方法重置状态（如果确实需要多次使用）

4. **向后兼容**：
   - 改造时应保持接口兼容性
   - 确保现有调用方式仍然有效

5. **需要优化的场景**：
   - `plugins/rca/transaction_other_error.py`：多次调用，每次不同关键词
   - `plugins/rca/transaction_rollback.py`：多次调用
   - `plugins/rca/transaction_wait_timeout.py`：多次调用
   - `plugins/rca/lock_conflict.py`：多次调用
   - `plugins/rca/clog_disk_full.py`：多次调用（但都基于相同的 tenant_id 和 ls_id）
   - `plugins/rca/index_ddl_error.py`：多次调用（但都基于相同的 trace_id）

---

## 五、总结

### 5.1 复用现状

- **已复用**：约 10+ 个场景已经使用或通过插件间接使用 `GatherComponentLogHandler`
- **可复用**：约 3-5 个场景可以使用但当前使用直接 SSH 命令

### 5.2 改造收益

1. **代码复用**：减少重复的日志采集代码
2. **功能统一**：统一支持日志脱敏、并发采集、时间过滤等功能
3. **维护成本**：集中维护日志采集逻辑，降低维护成本
4. **扩展性**：新增日志采集功能时，只需扩展 `GatherComponentLogHandler`

### 5.3 下一步行动

1. 优先改造 `major_hold.py` 的 `_collect_observer_logs` 方法
2. 评估 `analyze_memory.py` 和 `analyze_queue.py` 的改造方案
3. 根据实际使用情况决定其他场景的改造优先级

---

*文档版本：v1.0*  
*创建时间：2026-02-04*  
*分析范围：src/ 和 plugins/ 目录下的所有代码*
