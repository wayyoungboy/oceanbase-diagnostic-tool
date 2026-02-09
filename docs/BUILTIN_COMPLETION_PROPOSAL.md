# obdiag 内置补全功能实现方案

## 一、可行性分析

### 1.1 当前架构

obdiag 使用 `optparse` 进行命令行解析，命令结构通过 `MainCommand` 和 `MajorCommand` 类注册管理。

**优势**：
- ✅ 命令结构清晰，易于提取
- ✅ Python 代码可以直接访问命令注册表
- ✅ 可以动态生成补全信息

**挑战**：
- ⚠️ optparse 本身不支持补全（argparse 支持更好）
- ⚠️ 需要检测补全环境变量
- ⚠️ 需要输出特定格式供 shell 使用

---

## 二、实现方案

### 方案1：添加 `obdiag complete` 子命令（推荐）

**原理**：添加一个专门的补全子命令，输出补全信息供 shell 使用

**优点**：
- ✅ 不依赖外部库
- ✅ 实现简单
- ✅ 可以输出多种格式（bash/zsh）
- ✅ 用户友好，易于理解

**实现步骤**：

#### 2.1.1 添加 CompleteCommand 类

```python
# src/common/diag_cmd.py

class ObdiagCompleteCommand(BaseCommand):
    """Generate shell completion for obdiag"""
    
    def __init__(self):
        super(ObdiagCompleteCommand, self).__init__('complete', 'Generate shell completion')
    
    def do_command(self):
        import sys
        
        # 获取补全上下文
        comp_line = os.environ.get('COMP_LINE', '')
        comp_point = int(os.environ.get('COMP_POINT', len(comp_line)))
        comp_cword = int(os.environ.get('COMP_CWORD', 0))
        
        # 解析当前命令
        words = comp_line[:comp_point].split()
        if len(words) < comp_cword + 1:
            return
        
        cur_word = words[comp_cword] if comp_cword < len(words) else ''
        prev_word = words[comp_cword - 1] if comp_cword > 0 else ''
        
        # 获取补全建议
        completions = self._get_completions(words, comp_cword, cur_word, prev_word)
        
        # 输出补全列表（每行一个）
        for comp in completions:
            if comp.startswith(cur_word):
                print(comp)
        
        return True
    
    def _get_completions(self, words, comp_cword, cur_word, prev_word):
        """根据命令上下文返回补全建议"""
        main_cmd = MainCommand()
        completions = []
        
        # 第一层：主命令
        if comp_cword == 1:
            for cmd_name, cmd_obj in main_cmd.commands.items():
                if not getattr(cmd_obj, 'hidden', False):
                    completions.append(cmd_name)
            completions.extend(['--version', '--help'])
        
        # 第二层：子命令
        elif comp_cword == 2:
            cmd_name = words[1] if len(words) > 1 else ''
            if cmd_name in main_cmd.commands:
                cmd_obj = main_cmd.commands[cmd_name]
                if hasattr(cmd_obj, 'commands'):
                    for subcmd_name, subcmd_obj in cmd_obj.commands.items():
                        if not getattr(subcmd_obj, 'hidden', False):
                            completions.append(subcmd_name)
        
        # 第三层及以下：特殊处理
        elif comp_cword >= 3:
            cmd_name = words[1] if len(words) > 1 else ''
            subcmd_name = words[2] if len(words) > 2 else ''
            
            # gather scene / display scene
            if cmd_name in ['gather', 'display'] and subcmd_name == 'scene':
                completions = ['list', 'run']
            
            # analyze parameter
            elif cmd_name == 'analyze' and subcmd_name == 'parameter':
                completions = ['diff', 'default']
            
            # analyze variable
            elif cmd_name == 'analyze' and subcmd_name == 'variable':
                completions = ['diff']
            
            # 选项补全
            else:
                completions = self._get_option_completions(cmd_name, subcmd_name, prev_word)
        
        return completions
    
    def _get_option_completions(self, cmd_name, subcmd_name, prev_word):
        """获取选项补全"""
        completions = []
        
        # 根据前一个词判断选项类型
        if prev_word in ['--since']:
            completions = ['5m', '10m', '30m', '1h', '2h', '6h', '12h', '1d', '3d', '7d']
        elif prev_word in ['--scope']:
            completions = ['observer', 'election', 'rootservice', 'all']
        elif prev_word in ['-c', '--config', '--store_dir', '--report_path']:
            # 文件/目录补全由 shell 处理，返回空
            pass
        else:
            # 通用选项
            completions = ['--from', '--to', '--since', '--scope', '--grep', 
                          '--store_dir', '-c', '--config', '--help']
        
        return completions
```

#### 2.1.2 注册命令

```python
# src/common/diag_cmd.py - MainCommand.__init__

class MainCommand(MajorCommand):
    def __init__(self):
        super(MainCommand, self).__init__('obdiag', '')
        # ... 现有命令 ...
        self.register_command(ObdiagCompleteCommand())  # 添加这行
```

#### 2.1.3 创建补全包装脚本

```bash
# scripts/obdiag-complete.bash
#!/usr/bin/env bash
# obdiag completion function using built-in complete command

_obdiag_completion() {
    local cur_word="${COMP_WORDS[COMP_CWORD]}"
    local prev_word="${COMP_WORDS[COMP_CWORD-1]}"
    
    # 设置补全环境变量
    export COMP_LINE="${COMP_LINE}"
    export COMP_POINT="${COMP_POINT}"
    export COMP_CWORD="${COMP_CWORD}"
    
    # 调用 obdiag complete 获取补全建议
    local completions=$(obdiag complete 2>/dev/null)
    
    # 过滤匹配当前输入
    COMPREPLY=($(compgen -W "$completions" -- "$cur_word"))
}

complete -F _obdiag_completion obdiag
```

#### 2.1.4 在 init.sh 中安装

```bash
# rpm/init.sh 中添加

# Install completion script
if [ -f "/opt/oceanbase-diagnostic-tool/scripts/obdiag-complete.bash" ]; then
    cp -f /opt/oceanbase-diagnostic-tool/scripts/obdiag-complete.bash /etc/bash_completion.d/obdiag 2>/dev/null || \
    echo "source /opt/oceanbase-diagnostic-tool/scripts/obdiag-complete.bash" >> ~/.bashrc
fi
```

---

### 方案2：集成 argcomplete（最佳体验）

**原理**：使用 argcomplete 库，在代码层面直接支持补全

**优点**：
- ✅ 功能最强大
- ✅ 自动处理所有补全逻辑
- ✅ 支持选项和参数补全
- ✅ 用户体验最好

**实现步骤**：

#### 2.2.1 添加依赖（可选）

```toml
# pyproject.toml
[project.optional-dependencies]
completion = ["argcomplete>=2.0.0"]
```

#### 2.2.2 集成 argcomplete

```python
# src/common/diag_cmd.py 顶部

import os
try:
    import argcomplete
    HAS_ARGCOMPLETE = True
except ImportError:
    HAS_ARGCOMPLETE = False

# 检测是否在补全环境中
def _is_completion_mode():
    """检测是否在补全模式"""
    return any(key in os.environ for key in ['COMP_LINE', 'COMP_POINT', '_ARGCOMPLETE'])

# 在 MainCommand.__init__ 末尾添加
class MainCommand(MajorCommand):
    def __init__(self):
        super(MainCommand, self).__init__('obdiag', '')
        # ... 注册命令 ...
        
        # 启用 argcomplete（如果可用且在补全模式）
        if HAS_ARGCOMPLETE and _is_completion_mode():
            argcomplete.autocomplete(self.parser)
```

#### 2.2.3 注册补全脚本

```bash
# 在安装后执行
if command -v register-python-argcomplete >/dev/null 2>&1; then
    register-python-argcomplete obdiag > /etc/bash_completion.d/obdiag || \
    register-python-argcomplete obdiag > ~/.obdiag/obdiag-complete.bash
fi
```

**注意**：argcomplete 需要用户安装，但可以通过可选依赖提供。

---

### 方案3：混合方案（推荐用于生产）

**原理**：内置补全命令 + 可选 argcomplete 支持

**优点**：
- ✅ 不依赖外部库（基础功能）
- ✅ 可选增强（argcomplete）
- ✅ 向后兼容
- ✅ 渐进式改进

**实现**：

1. **基础版本**：实现 `obdiag complete` 命令
2. **增强版本**：如果检测到 argcomplete，使用更强大的补全
3. **降级处理**：如果没有 argcomplete，使用内置补全

```python
# src/common/diag_cmd.py

class MainCommand(MajorCommand):
    def __init__(self):
        super(MainCommand, self).__init__('obdiag', '')
        # ... 注册命令 ...
        
        # 尝试使用 argcomplete（如果可用）
        if HAS_ARGCOMPLETE and _is_completion_mode():
            try:
                argcomplete.autocomplete(self.parser)
                return  # 使用 argcomplete，不需要额外处理
            except Exception:
                pass  # 降级到内置补全
        
        # 否则使用内置补全命令
        self.register_command(ObdiagCompleteCommand())
```

---

## 三、方案对比

| 方案 | 实现难度 | 用户体验 | 维护成本 | 依赖要求 | 推荐度 |
|------|---------|---------|---------|---------|--------|
| **方案1：内置complete命令** | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | 无 | ⭐⭐⭐⭐⭐ |
| **方案2：argcomplete集成** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | argcomplete | ⭐⭐⭐⭐ |
| **方案3：混合方案** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | 可选 | ⭐⭐⭐⭐⭐ |

---

## 四、推荐实施方案

### 阶段1：实现内置 complete 命令（立即）

**优势**：
- 不依赖外部库
- 实现简单
- 立即可用

**实现要点**：
1. 添加 `ObdiagCompleteCommand` 类
2. 实现命令和选项补全逻辑
3. 创建补全包装脚本
4. 在安装时自动配置

### 阶段2：可选集成 argcomplete（后续）

**优势**：
- 提供更强大的补全
- 自动处理复杂场景

**实现要点**：
1. 添加可选依赖
2. 检测并使用 argcomplete
3. 降级到内置补全

---

## 五、完整实现示例

### 5.1 Python 代码实现

```python
# src/common/diag_cmd.py

import os
import sys

# 尝试导入 argcomplete
try:
    import argcomplete
    HAS_ARGCOMPLETE = True
except ImportError:
    HAS_ARGCOMPLETE = False
    argcomplete = None

def _is_completion_mode():
    """检测是否在补全模式"""
    return any(key in os.environ for key in ['COMP_LINE', 'COMP_POINT', '_ARGCOMPLETE'])

class ObdiagCompleteCommand(BaseCommand):
    """Generate shell completion for obdiag"""
    
    def __init__(self):
        super(ObdiagCompleteCommand, self).__init__('complete', 'Generate shell completion')
        self.hidden = True  # 隐藏命令，不在help中显示
    
    def do_command(self):
        """处理补全请求"""
        # 获取补全上下文
        comp_line = os.environ.get('COMP_LINE', '')
        comp_point = int(os.environ.get('COMP_POINT', len(comp_line)))
        comp_cword = int(os.environ.get('COMP_CWORD', 0))
        
        # 解析命令
        words = comp_line[:comp_point].split() if comp_line else []
        if len(words) < comp_cword:
            return
        
        cur_word = words[comp_cword] if comp_cword < len(words) else ''
        
        # 获取补全建议
        completions = self._get_completions(words, comp_cword, cur_word)
        
        # 输出补全列表
        for comp in completions:
            if comp.startswith(cur_word):
                print(comp)
        
        return True
    
    def _get_completions(self, words, comp_cword, cur_word):
        """根据上下文返回补全建议"""
        main_cmd = MainCommand()
        completions = []
        
        try:
            # 第一层：主命令
            if comp_cword == 1:
                for cmd_name, cmd_obj in main_cmd.commands.items():
                    if not getattr(cmd_obj, 'hidden', False):
                        completions.append(cmd_name)
                completions.extend(['--version', '--help'])
            
            # 第二层：子命令
            elif comp_cword == 2 and len(words) > 1:
                cmd_name = words[1]
                if cmd_name in main_cmd.commands:
                    cmd_obj = main_cmd.commands[cmd_name]
                    if hasattr(cmd_obj, 'commands'):
                        for subcmd_name, subcmd_obj in cmd_obj.commands.items():
                            if not getattr(subcmd_obj, 'hidden', False):
                                completions.append(subcmd_name)
            
            # 第三层及以下
            elif comp_cword >= 3 and len(words) >= 2:
                cmd_name = words[1]
                subcmd_name = words[2] if len(words) > 2 else ''
                prev_word = words[comp_cword - 1] if comp_cword > 0 else ''
                
                # 特殊命令处理
                if cmd_name in ['gather', 'display'] and subcmd_name == 'scene':
                    completions = ['list', 'run']
                elif cmd_name == 'analyze' and subcmd_name == 'parameter':
                    completions = ['diff', 'default']
                elif cmd_name == 'analyze' and subcmd_name == 'variable':
                    completions = ['diff']
                else:
                    # 选项补全
                    completions = self._get_option_completions(prev_word)
        except Exception:
            # 出错时返回空列表
            pass
        
        return completions
    
    def _get_option_completions(self, prev_word):
        """获取选项补全"""
        if prev_word == '--since':
            return ['5m', '10m', '30m', '1h', '2h', '6h', '12h', '1d', '3d', '7d']
        elif prev_word == '--scope':
            return ['observer', 'election', 'rootservice', 'all']
        else:
            return ['--from', '--to', '--since', '--scope', '--grep', 
                   '--store_dir', '-c', '--config', '--help']

# 在 MainCommand.__init__ 中
class MainCommand(MajorCommand):
    def __init__(self):
        super(MainCommand, self).__init__('obdiag', '')
        # ... 现有命令注册 ...
        
        # 注册补全命令（如果不在补全模式中）
        if not _is_completion_mode():
            self.register_command(ObdiagCompleteCommand())
        
        # 尝试使用 argcomplete
        if HAS_ARGCOMPLETE and _is_completion_mode():
            try:
                argcomplete.autocomplete(self.parser)
            except Exception:
                pass
```

### 5.2 Bash 补全脚本

```bash
#!/usr/bin/env bash
# obdiag completion using built-in complete command

_obdiag_completion() {
    local cur_word="${COMP_WORDS[COMP_CWORD]}"
    
    # 设置环境变量供 obdiag complete 使用
    export COMP_LINE="${COMP_LINE}"
    export COMP_POINT="${COMP_POINT}"
    export COMP_CWORD="${COMP_CWORD}"
    
    # 调用 obdiag complete 获取补全建议
    local completions
    completions=$(obdiag complete 2>/dev/null)
    
    # 过滤匹配当前输入
    COMPREPLY=($(compgen -W "$completions" -- "$cur_word"))
}

complete -F _obdiag_completion obdiag
```

### 5.3 安装脚本集成

```bash
# rpm/init.sh 中添加

# Install completion
COMPLETION_SCRIPT="/opt/oceanbase-diagnostic-tool/scripts/obdiag-complete.bash"
if [ -f "$COMPLETION_SCRIPT" ]; then
    # 尝试安装到系统目录
    if [ -d "/etc/bash_completion.d" ]; then
        cp -f "$COMPLETION_SCRIPT" /etc/bash_completion.d/obdiag
    fi
    
    # 或者添加到用户 bashrc
    if [ -f ~/.bashrc ] && ! grep -q "obdiag-complete.bash" ~/.bashrc; then
        echo "" >> ~/.bashrc
        echo "# obdiag completion" >> ~/.bashrc
        echo "source $COMPLETION_SCRIPT" >> ~/.bashrc
    fi
fi
```

---

## 六、优势总结

### 6.1 内置补全的优势

1. **零依赖**：不需要安装额外库
2. **自动同步**：命令结构变化时自动更新
3. **用户友好**：用户只需安装一次
4. **易于维护**：补全逻辑在代码中，易于更新

### 6.2 与外部脚本对比

| 特性 | 外部脚本 | 内置补全 |
|------|---------|---------|
| 维护成本 | 高（需要手动更新） | 低（自动同步） |
| 同步性 | 可能不同步 | 始终同步 |
| 用户体验 | 需要手动配置 | 自动配置 |
| 功能扩展 | 困难 | 容易 |

---

## 七、实施建议

### 立即实施

1. ✅ 实现 `ObdiagCompleteCommand` 类
2. ✅ 创建 bash 补全包装脚本
3. ✅ 在安装脚本中自动配置
4. ✅ 测试验证

### 后续优化

1. 可选集成 argcomplete
2. 支持 zsh 补全
3. 添加选项描述
4. 支持动态场景列表补全

---

## 八、总结

**推荐方案**：实现内置 `obdiag complete` 命令

**理由**：
- ✅ 不依赖外部库
- ✅ 自动同步命令结构
- ✅ 实现简单，风险低
- ✅ 用户体验好
- ✅ 易于维护和扩展

这种方式让 obdiag 具备了原生的补全能力，用户安装后即可使用，无需额外配置，且补全信息始终与命令结构保持同步。
