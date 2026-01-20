# MLForge

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/streamlit-1.37+-red.svg)](https://streamlit.io/)
[![LangChain](https://img.shields.io/badge/langchain-0.3+-green.svg)](https://langchain.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**MLForge** is an agentic AI application for machine learning and data science workflows. It combines a conversational interface with autonomous code execution, creating a powerful workbench where AI assists every stage of the ML lifecycle.

## ✨ Features

- 🤖 **Agentic Workflow** — AI agent plans and executes multi-step ML tasks with user approval
- 💬 **Natural Language Interface** — Describe goals in plain English; MLForge handles the implementation
- 📄 **Living Document** — Results accumulate in a rich document with LaTeX equations and inline visualizations
- ⚡ **Background Jobs** — Long-running training jobs with real-time progress and cancellation support
- 🔧 **Isolated Workspaces** — Each project gets a dedicated environment managed by `uv`
- 🌐 **Web Research** — Agent searches docs, Kaggle, and UCI for datasets and solutions
- 🔌 **Configurable LLMs** — Supports Anthropic Claude, OpenAI GPT, and local models

## 🚀 Quick Start
```bash
# Clone the repository
git clone https://github.com/yourusername/mlforge.git
cd mlforge

# Setup environment
uv venv && source .venv/bin/activate
uv pip install -e .

# Configure LLM provider
cp .env.example .env
# Edit .env with your API keys

# Initialize workspace
python scripts/setup_workspace.py

# Launch MLForge
streamlit run src/main.py
```

## 🏗️ Architecture

MLForge uses a **plan-then-execute** agent architecture built on LangChain. The agent:

1. **Plans** — Breaks down your request into discrete steps
2. **Seeks Approval** — Presents the plan for your review before executing code
3. **Executes** — Runs each step, streaming updates tool-by-tool
4. **Documents** — Inserts results into the running document

Long-running jobs execute in isolated subprocesses, communicating status via SQLite.

## 📦 Pre-installed Data Science Stack

Projects come with a full DS environment including:
- **Core:** NumPy, Pandas, SciPy, Polars
- **ML:** Scikit-learn, XGBoost, LightGBM, CatBoost
- **Deep Learning:** PyTorch, Transformers
- **Visualization:** Matplotlib, Seaborn, Plotly
- **Statistics:** Statsmodels, Pingouin

## 🛠️ Agent Tools

| Tool | Description |
|------|-------------|
| `file_ops` | Read, write, list, and manage project files |
| `python_exec` | Execute Python code with streaming output |
| `bash_exec` | Run shell commands in project context |
| `web_search` | Search documentation, Kaggle, UCI via Playwright |
| `todo_list` | Track agent's task progress |

## 📖 Documentation

- [AGENT.md](./AGENT.md) — Full specification and design document
- [Configuration Guide](./docs/configuration.md)
- [Tool Development](./docs/tools.md)
- [Contributing](./CONTRIBUTING.md)

## 📄 License

MIT License — see [LICENSE](./LICENSE) for details.