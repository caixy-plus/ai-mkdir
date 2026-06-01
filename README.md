# ai-mkdir

`mkdir --ai` — 用自然语言描述项目，AI 自动生成英文目录名，创建并 cd 进入。

```bash
mkdir --ai 智能客服
# → AI 建议 5 个英文名 → 上下键选择 → 创建目录 + 自动 cd
```

## 安装

### macOS

```bash
curl -fsSL https://raw.githubusercontent.com/caixy-plus/ai-mkdir/main/install.sh | sh
```

`install.sh` 会完成：
1. `pip install --user .` 安装 `mkai` 命令
2. 在 `~/.zshrc` 添加 `mkdir --ai` 包装函数，实现自动 cd

### 其他平台（Linux / WSL / ...）

从源码安装：

```bash
git clone https://github.com/caixy-plus/ai-mkdir.git
cd ai-mkdir
pip install --user .
```

然后手动将以下函数添加到 `~/.bashrc` 或 `~/.zshrc`：

```bash
mkdir() {
    if [[ "$1" == "--ai" ]]; then
        shift
        eval $(command mkai "$@")
    else
        command mkdir "$@"
    fi
}
```

> **依赖**: Python >= 3.9, `requests` 库

## 配置

```bash
mkai --setup
```

支持三种协议：

| 协议 | 适用场景 |
|------|----------|
| ollama | 本地模型，无需 API key |
| openai-compatible | OpenAI / DeepSeek / Groq / vLLM 等任意 `/chat/completions` 接口 |
| anthropic | Claude 或 Anthropic Messages API 兼容接口（支持 thinking 模型） |

## 使用

```bash
# 交互模式
mkdir --ai 用户管理后台    # 同 mkai 用户管理后台
mkdir --ai "real-time chat app"

# 指定提供商
mkai -p ollama 数据分析平台

# 其他命令
mkai --setup              # 重新配置
mkai --list-providers     # 查看已配置的提供商
```

## 原理

子进程无法改变父 shell 的当前目录，因此工具将所有交互输出到 stderr，仅将 `cd /path` 输出到 stdout，由 shell 函数 `eval` 执行：

```zsh
mkdir() {
    if [[ "$1" == "--ai" ]]; then
        shift
        eval $(command mkai "$@")
    else
        command mkdir "$@"
    fi
}
```

## License

MIT
