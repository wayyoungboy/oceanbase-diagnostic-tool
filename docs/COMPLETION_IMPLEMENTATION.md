# obdiag 内置补全功能实现说明

## 一、实现概述

obdiag 现在具备了内置的命令补全能力，通过添加一个隐藏的 `complete` 子命令来实现。当 shell 需要补全时，会调用 `obdiag complete`，obdiag 会从命令注册表中动态提取补全建议并返回。

## 二、实现组件

### 2.1 Python 代码

**文件**: `src/common/diag_cmd.py`

**新增类**: `ObdiagCompleteCommand`

- **位置**: 在 `MainCommand` 类之后定义
- **功能**: 
  - 从环境变量读取补全上下文（`COMP_LINE`, `COMP_POINT`, `COMP_CWORD`）
  - 解析当前命令和位置
  - 从 `MainCommand` 的命令注册表中提取补全建议
  - 输出匹配的补全列表

**关键方法**:
- `do_command()`: 处理补全请求的主方法
- `_get_completions()`: 根据上下文获取补全建议
- `_get_option_completions()`: 获取选项补全建议

### 2.2 Bash 补全脚本

**文件**: `scripts/obdiag-complete.bash`

**功能**:
- 设置补全环境变量
- 调用 `obdiag complete` 获取补全建议
- 使用 `compgen` 过滤匹配当前输入

### 2.3 安装脚本集成

**RPM 安装** (`rpm/init.sh`):
- 自动安装补全脚本到 `/etc/bash_completion.d/` 或用户 `~/.bashrc`
- 修复了硬编码路径问题（使用 `obdiag` 命令而非 `/opt/oceanbase-diagnostic-tool/obdiag`）

**macOS 安装** (`macos/install.sh`):
- 优先使用内置补全脚本
- 如果内置脚本不可用，降级到静态补全

**RPM Spec** (`rpm/oceanbase-diagnostic-tool.spec`):
- 将补全脚本复制到安装目录

## 三、工作原理

### 3.1 补全流程

1. **用户输入**: 用户在 shell 中输入 `obdiag <TAB>`
2. **Shell 调用**: Bash 调用 `_obdiag_completion` 函数
3. **环境变量**: Shell 设置 `COMP_LINE`, `COMP_POINT`, `COMP_CWORD`
4. **调用 obdiag**: 补全脚本调用 `obdiag complete`
5. **解析上下文**: `ObdiagCompleteCommand` 解析命令和位置
6. **提取补全**: 从 `MainCommand` 的命令注册表中提取匹配的命令
7. **返回结果**: 输出补全列表，shell 显示给用户

### 3.2 补全层级

- **第一层**: 主命令（`gather`, `analyze`, `check` 等）
- **第二层**: 子命令（如 `gather log`, `analyze parameter` 等）
- **第三层**: 特殊命令（如 `gather scene list/run`）
- **选项补全**: 根据前一个词提供选项建议（如 `--since` 后补全时间单位）

## 四、优势

### 4.1 自动同步

- ✅ 命令结构变化时自动更新
- ✅ 无需手动维护补全列表
- ✅ 新增命令自动支持补全

### 4.2 零依赖

- ✅ 不需要外部库
- ✅ 不需要额外安装步骤
- ✅ 完全内置实现

### 4.3 用户友好

- ✅ 安装后自动配置
- ✅ 无需手动设置
- ✅ 隐藏命令，不影响正常使用

## 五、使用说明

### 5.1 安装后自动启用

安装 obdiag 后，补全功能会自动配置：

```bash
# RPM 安装
source /opt/oceanbase-diagnostic-tool/init.sh

# macOS 安装
# 补全脚本会自动安装到系统目录或 ~/.bashrc
```

### 5.2 手动启用（如果需要）

如果补全未自动启用，可以手动添加：

```bash
# 方法1: 添加到 ~/.bashrc
echo "source /opt/oceanbase-diagnostic-tool/scripts/obdiag-complete.bash" >> ~/.bashrc
source ~/.bashrc

# 方法2: 复制到系统目录
sudo cp /opt/oceanbase-diagnostic-tool/scripts/obdiag-complete.bash /etc/bash_completion.d/obdiag
```

### 5.3 测试补全

```bash
# 测试主命令补全
obdiag <TAB>

# 测试子命令补全
obdiag gather <TAB>

# 测试选项补全
obdiag gather log --since <TAB>
```

## 六、技术细节

### 6.1 循环依赖处理

`ObdiagCompleteCommand` 在 `MainCommand` 之后定义，但在 `MainCommand.__init__` 中注册。这通过以下方式解决：

- Python 允许在同一模块中引用后续定义的类
- `ObdiagCompleteCommand._get_completions()` 中创建 `MainCommand` 实例时，类已完全定义
- 补全调用在独立进程中，不会影响主进程

### 6.2 错误处理

- 补全过程中的异常会被静默捕获，避免破坏 shell 补全
- 如果补全失败，返回空列表，shell 会显示默认补全

### 6.3 性能优化

- 补全调用是轻量级的，只创建必要的对象
- 补全结果会被 shell 缓存，不会频繁调用

## 七、未来改进

### 7.1 可选增强

可以考虑集成 `argcomplete` 库以提供更强大的补全：
- 选项描述
- 参数验证
- 更智能的上下文感知

### 7.2 扩展功能

- 支持 zsh 补全（已有基础实现）
- 支持动态场景列表补全
- 支持配置文件路径补全

## 八、测试验证

### 8.1 功能测试

```bash
# 1. 测试主命令补全
COMP_LINE="obdiag " COMP_POINT=7 COMP_CWORD=1 obdiag complete
# 应该输出: gather, analyze, check, rca, display, tool, config, update, display-trace, --version, --help

# 2. 测试子命令补全
COMP_LINE="obdiag gather " COMP_POINT=15 COMP_CWORD=2 obdiag complete
# 应该输出: log, clog, slog, plan_monitor, stack, perf, sysstat, obproxy_log, all, scene, ash, tabledump, parameter, variable, dbms_xplan, core

# 3. 测试特殊命令补全
COMP_LINE="obdiag gather scene " COMP_POINT=22 COMP_CWORD=3 obdiag complete
# 应该输出: list, run
```

### 8.2 集成测试

安装后，在 shell 中测试：
```bash
# 重新加载 shell 配置
source ~/.bashrc

# 测试补全
obdiag <TAB>
obdiag gather <TAB>
obdiag gather log --since <TAB>
```

## 九、总结

obdiag 现在具备了原生的命令补全能力，通过内置的 `complete` 子命令实现。这种方式：

- ✅ **自动同步**: 命令结构变化时自动更新
- ✅ **零依赖**: 不需要外部库
- ✅ **用户友好**: 安装后自动配置
- ✅ **易于维护**: 补全逻辑在代码中，易于更新

用户安装 obdiag 后即可享受自动补全功能，无需额外配置。
