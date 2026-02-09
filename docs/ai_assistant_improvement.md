# AI Assistant 改进方案：直接调用 Handler

## 问题分析

当前 AI Assistant 的实现存在以下问题：

### 1. **架构分裂**
- AI Assistant 通过 `subprocess` 执行命令行指令调用 obdiag 功能
- 需要重新解析命令行参数、构建命令字符串
- 与 obdiag 核心代码库分离，维护成本高

### 2. **性能问题**
- 每次调用都启动新进程，开销大
- 进程间通信效率低
- 无法共享已初始化的连接和上下文

### 3. **错误处理困难**
- 只能通过 stdout/stderr 获取错误信息
- 无法捕获和传递结构化异常
- 错误信息可能丢失或格式不统一

### 4. **数据访问受限**
- 只能获取文本输出，无法访问结构化数据
- `ObdiagResult` 中的结构化数据无法利用
- 需要重新解析输出文本

## 改进方案

### 方案概述

**直接调用 Handler**：通过 `HandlerInvoker` 直接实例化和调用 obdiag 的 Handler，而不是通过命令行。

### 架构设计

```
AI Assistant
    ↓
MCP Server
    ↓
HandlerInvoker (新增)
    ↓
HandlerFactory → Handler → handle()
    ↓
ObdiagResult (结构化返回)
```

### 核心组件

#### 1. HandlerInvoker (`src/handler/ai/handler_invoker.py`)

统一接口，直接调用 Handler：

```python
class HandlerInvoker:
    """直接调用 Handler 的统一接口"""
    
    def invoke(self, tool_name: str, arguments: Dict) -> Dict:
        """
        直接调用 Handler，返回结构化结果
        
        返回:
        {
            "success": bool,
            "result": ObdiagResult,  # 结构化结果
            "stdout": str,
            "stderr": str,
            "data": Any,  # 结构化数据
        }
        """
```

**优势：**
- ✅ 直接访问 `ObdiagResult` 结构化数据
- ✅ 更好的性能（无进程开销）
- ✅ 统一的错误处理
- ✅ 代码复用，无需重复实现

#### 2. 更新的 MCP Server

`mcp_server.py` 现在支持两种模式：

1. **直接调用模式**（默认，推荐）：使用 `HandlerInvoker`
2. **兼容模式**：回退到 subprocess（向后兼容）

```python
# 自动选择最佳方式
if self.use_direct_invocation and self.handler_invoker:
    result = self._execute_handler_directly(tool_name, arguments)
else:
    result = self._execute_obdiag_command(tool_name, arguments)  # 兼容模式
```

## 使用方式

### 自动启用（默认）

改进后的代码会自动尝试使用直接调用模式。如果初始化失败，会自动回退到 subprocess 模式。

### 手动配置

如果需要强制使用某种模式，可以在初始化时指定：

```python
# 强制使用直接调用（推荐）
mcp_server = MCPServer(
    config_path=config_path,
    stdio=stdio,
    use_direct_invocation=True
)

# 强制使用 subprocess（兼容模式）
mcp_server = MCPServer(
    config_path=config_path,
    stdio=stdio,
    use_direct_invocation=False
)
```

## 改进效果对比

| 特性 | 旧方案 (subprocess) | 新方案 (直接调用) |
|------|---------------------|------------------|
| **性能** | 每次启动新进程，开销大 | 直接调用，性能好 |
| **错误处理** | 只能通过文本输出 | 结构化异常，完整堆栈 |
| **数据访问** | 仅文本输出 | 结构化 `ObdiagResult` |
| **代码维护** | 需要维护命令行构建逻辑 | 复用现有 Handler 代码 |
| **调试** | 难以调试子进程 | 直接调试，IDE 友好 |
| **资源利用** | 无法共享连接 | 共享已初始化连接 |

## 迁移指南

### 对于开发者

无需修改现有代码，改进是向后兼容的。如果遇到问题，可以：

1. 检查日志中的 "Handler invoker initialized" 消息
2. 如果看到 "falling back to subprocess"，检查错误原因
3. 确保 `HandlerInvoker` 可以正确初始化

### 对于扩展

如果要添加新的工具支持：

1. 在 `HandlerInvoker.TOOL_TO_HANDLER_MAP` 中添加映射
2. 确保对应的 Handler 已注册到 `HandlerFactory`
3. 测试直接调用和 subprocess 两种模式

## 未来优化方向

1. **完全移除 subprocess 模式**：在所有 Handler 稳定后，可以移除兼容代码
2. **异步支持**：对于长时间运行的任务，可以添加异步调用支持
3. **结果缓存**：对于相同参数的调用，可以缓存结果
4. **批量调用**：支持一次调用多个 Handler

## 总结

通过直接调用 Handler，我们实现了：

- ✅ **统一的代码库**：不再需要维护命令行构建逻辑
- ✅ **更好的性能**：消除了进程启动开销
- ✅ **更好的错误处理**：结构化异常和完整堆栈
- ✅ **更好的数据访问**：直接访问 `ObdiagResult` 结构化数据
- ✅ **向后兼容**：自动回退到 subprocess 模式

这个改进让 AI Assistant 与 obdiag 核心功能更加紧密集成，为未来的功能扩展打下了良好基础。
