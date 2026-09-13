# 网文创作 Skill 蒸馏系统 / Novel Skill Distiller

[![Tests](https://github.com/biggodofziyang/novel-skill-distiller/actions/workflows/codeql.yml/badge.svg)](https://github.com/biggodofziyang/novel-skill-distiller/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

一个面向长篇网文创作的本地工作台。它把素材拆解、规则蒸馏、分步创作、章节写作和质量反馈放在同一个可持续迭代的项目空间里，并通过 OpenAI 兼容接口调用模型。

> This is a local-first writing workspace for long-form web fiction. It combines material analysis, rule distillation, step-by-step story planning, chapter writing, and quality feedback in a versionable project space, using OpenAI-compatible APIs.

## 主要能力

- **创作对话**：在一个类似 ChatGPT 的工作区中切换素材拆解、分步创作、章节写作和规则蒸馏四种模式。
- **素材拆解**：导入 TXT、Markdown 或 DOCX，选择 Skill 后生成可编辑的分析结果。
- **Skill 迭代**：编辑拆解结果并补充自己的创作要求，生成新的 Markdown Skill 或 ZIP Skill 包。
- **分步创作**：独立生成并保存世界观、人物关系、黄金三章等基础资产。
- **章节写作**：结合项目设定、已保存文件和 Skill 进行章节创作，并保留本地版本。
- **规则蒸馏与质量反馈**：从已完成的创作结果中提炼规则，记录迭代、正负反馈和审查结果。
- **本地文件工作区**：项目文件可浏览、编辑、新建文件夹、创建文件、保存历史版本和删除。
- **桌面启动**：Windows 可直接运行 `launcher.pyw` 或 `启动小说软件.bat`。

## 安装

需要 Python 3.10 或更高版本。

```powershell
python -m venv .venv
.venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
```

## API 配置

复制示例配置后填写自己的 OpenAI 兼容接口：

```powershell
Copy-Item config/api_config.example.yaml config/api_config.yaml
```

也可以启动后在“API 设置”页面填写和测试。`config/api_config.yaml` 已被 Git 忽略，API 密钥不会进入公开仓库。

支持类似以下结构的接口：

```yaml
primary:
  provider: openai
  base_url: https://api.openai.com/v1
  model: gpt-4o-mini
  api_key: your-api-key
  timeout: 120
  max_retries: 3
backup:
  provider: openai
  base_url: https://api.openai.com/v1
  model: gpt-4o-mini
  api_key: your-backup-key
  timeout: 120
  max_retries: 3
parameters:
  temperature: 0.7
  top_p: 0.9
```

## 启动

### Windows 桌面启动

双击 `launcher.pyw`，或运行 `启动小说软件.bat`。启动器会在本机启动服务并打开独立浏览器窗口。

### 命令行启动

```powershell
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

浏览器访问 `http://127.0.0.1:8501/`。

## 数据和隐私

本项目默认把工作区数据保存在本地 `data/` 目录。小说原文、拆解结果、Skill 压缩包、日志、缓存和 API 配置都不会被提交到 GitHub；这些内容也可能受版权或隐私保护，请不要直接公开上传。

调用模型时，发送给接口的内容取决于当前选择的 Skill、素材和对话上下文。请根据所使用的 API 服务商的隐私政策自行判断哪些内容可以发送。

## 项目结构

```text
app.py                 Streamlit 入口
launcher.pyw           Windows 桌面启动器
core/                  数据模型、存储、拆解和创作核心逻辑
services/              LLM、Skill、文本处理和反馈服务
ui/                    工作台界面
utils/                 校验、日志和通用工具
config/                默认设置和提示词模板
tests/                 自动化测试
```

## 开发与测试

```powershell
python -m pytest -q
```

欢迎提交问题、改进建议和 Pull Request。请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 参与项目

你可以通过 GitHub Issues 报告问题，通过 Discussions 分享写作流程、Skill 和使用案例，也可以提交 Pull Request。请不要上传小说原文、API 密钥或未经授权的第三方材料。

## 路线图

- 更完善的多模型路由和 API 错误诊断
- Skill 版本对比、回滚和冲突合并
- 可导出的项目模板与匿名示例工程
- 更完整的自动化端到端测试

## 许可证

本项目使用 MIT License，详见 [LICENSE](LICENSE)。

## English

### Features

- **Unified creative chat** with four selectable modes: material analysis, step-by-step creation, chapter writing, and rule distillation.
- **Material analysis** for TXT, Markdown, and DOCX files, with selectable Skills and editable results.
- **Skill iteration**: combine analysis results with author notes and export a new Markdown Skill or ZIP package.
- **Step-by-step creation** for worldbuilding, character relationships, and the opening chapters, saved as independent assets.
- **Chapter writing** with project settings, saved files, Skills, and local version history.
- **Rule distillation and review** with iteration records, positive/negative feedback, and quality checks.
- **Local file workspace** with folders, file creation, editing, version history, and deletion.
- **Windows desktop launcher** through `launcher.pyw` or `启动小说软件.bat`.

### Install

Python 3.10 or newer is required.

```powershell
python -m venv .venv
.venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
```

### Configure an API

Copy the example configuration and fill in an OpenAI-compatible endpoint:

```powershell
Copy-Item config/api_config.example.yaml config/api_config.yaml
```

You can also configure and test the endpoint from the **API Settings** page. The real `config/api_config.yaml` file is ignored by Git and must never be committed.

### Run

On Windows, double-click `launcher.pyw` or run `启动小说软件.bat`. For a terminal launch:

```powershell
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

Then open `http://127.0.0.1:8501/`.

### Privacy

Local workspaces, source novels, generated analysis, Skill packages, logs, caches, and API configuration are intentionally excluded from the public repository. The content sent to an AI provider depends on the selected Skill, source material, and conversation context. Review your provider's privacy policy before sending confidential or copyrighted material.

### Development

```powershell
python -m pytest -q
```

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a Pull Request. Security reports should follow [SECURITY.md](SECURITY.md).
