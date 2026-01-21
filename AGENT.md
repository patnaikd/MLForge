# AGENT.md - Agentic ML/Data Science Application

## Project Overview

An agentic AI application for machine learning and data science workflows. Users interact with an AI agent through a chat interface, with analysis results accumulating in a running document. The system supports long-running jobs, multi-user access, and configurable LLM providers.

---

## Requirements

### Functional Requirements

#### FR1: Chat Interface
- FR1.1: Real-time chat interface for user-agent interaction
- FR1.2: Streaming responses with tool-by-tool granularity
- FR1.3: Message history display within current session
- FR1.4: Session persistence with ability to resume past conversations
- FR1.5: Username-based user identification (no authentication required)

#### FR2: Document System
- FR2.1: Running document panel displaying analysis results
- FR2.2: LaTeX rendering for equations and mathematical notation
- FR2.3: Inline image display via file path references
- FR2.4: Sequential display of content blocks (text, code, images, tables)
- FR2.5: Agent inserts content at designated location
- FR2.6: Pure Streamlit component-based rendering (read-only acceptable)

#### FR3: Project Management
- FR3.1: Auto-generated project folders with format `{agent-prefix}-{yyyy-MM-dd-HH-mm}`
- FR3.2: Project list view showing all projects across users
- FR3.3: File/folder explorer rooted at project directory
- FR3.4: Data upload capability to project's `data/` directory
- FR3.5: Image storage in project's `images/` directory
- FR3.6: Disk usage tracking per project and workspace total
- FR3.7: Resume capability for past projects

#### FR4: Code Execution Environment
- FR4.1: Isolated Python environment managed by `uv`
- FR4.2: Shared parent environment for all projects with pre-installed DS packages
- FR4.3: Arbitrary Python code execution in project workspace
- FR4.4: Bash command execution capability
- FR4.5: Activity timeout: 5 minutes (no log output)
- FR4.6: Overall timeout: 60 minutes
- FR4.7: Globally configurable timeout settings

#### FR5: Agent Capabilities
- FR5.1: Plan-then-execute architecture (planning phase before execution)
- FR5.2: User approval step before code execution
- FR5.3: Configurable LLM provider (Anthropic Claude, OpenAI, etc.)
- FR5.4: Session-isolated conversation memory
- FR5.5: Support for all ML/DS tasks: EDA, model training, feature engineering, visualization, statistical analysis

#### FR6: Agent Tools
- FR6.1: File operations (read, write, list, delete, move)
- FR6.2: Bash execution with output capture
- FR6.3: Python code interpreter with streaming output
- FR6.4: Web search via Playwright (documentation, APIs, Kaggle, UCI datasets)
- FR6.5: Todo list for agent task tracking
- FR6.6: Email notification (future enhancement)

#### FR7: Long-Running Jobs
- FR7.1: Background process execution for long tasks
- FR7.2: SQLite-based job communication and status tracking
- FR7.3: Job cancellation capability
- FR7.4: Progress updates communicated to UI
- FR7.5: Support for jobs running minutes to hours

#### FR8: Multi-User Support
- FR8.1: Username entry for user identification
- FR8.2: Shared visibility of all projects across users
- FR8.3: Single local deployment instance
- FR8.4: Concurrent user support via Streamlit sessions

### Non-Functional Requirements

#### NFR1: Performance
- NFR1.1: Streaming updates with minimal latency
- NFR1.2: Responsive UI during long-running operations
- NFR1.3: Efficient SQLite queries for job status polling

#### NFR2: Reliability
- NFR2.1: Graceful handling of job failures
- NFR2.2: Session state persistence across page refreshes
- NFR2.3: Proper cleanup of cancelled jobs

#### NFR3: Maintainability
- NFR3.1: Modular architecture with clear separation of concerns
- NFR3.2: Comprehensive logging
- NFR3.3: Configuration-driven settings

---

## System Design

### Architecture Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                         Streamlit UI Layer                         │
├──────────────┬──────────────┬──────────────┬───────────────────────┤
│  Chat Panel  │  Document    │    File      │   Project Manager     │
│              │  Panel       │   Explorer   │                       │
└──────┬───────┴──────┬───────┴──────┬───────┴───────────┬───────────┘
       │              │              │                   │
       ▼              ▼              ▼                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Application Core                               │
├─────────────────┬─────────────────┬─────────────────────────────────┤
│  Agent Engine   │  Document       │  Project Service                │
│  (LangChain)    │  Service        │                                 │
└────────┬────────┴────────┬────────┴────────┬────────────────────────┘
         │                 │                 │
         ▼                 ▼                 ▼
┌────────────────────────────────────────────────────────────────────┐
│                       Infrastructure Layer                         │
├──────────────┬──────────────┬──────────────┬───────────────────────┤
│   SQLite     │  Job Runner  │  Code        │   LLM Providers       │
│   Database   │  (subprocess)│  Executor    │   (Claude/OpenAI)     │
└──────────────┴──────────────┴──────────────┴───────────────────────┘
         │                           │
         ▼                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        File System                                  │
├─────────────────────────────────────────────────────────────────────┤
│  workspace/                                                         │
│  ├── .venv/                    (shared uv environment)              │
│  ├── {project-prefix}-{timestamp}/                                  │
│  │   ├── data/                 (uploaded datasets)                  │
│  │   ├── images/               (generated visualizations)           │
│  │   ├── code/                 (generated scripts)                  │
│  │   └── outputs/              (model artifacts, results)           │
│  └── agent.db                  (SQLite database)                    │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Design

#### 1. Agent Engine (LangChain)

```python
# Simplified architecture
class AgentEngine:
    def __init__(self, llm_provider: LLMProvider, tools: List[Tool]):
        self.planner = PlannerAgent(llm_provider)
        self.executor = ExecutorAgent(llm_provider, tools)
        self.memory = ConversationMemory()
    
    async def run(self, user_input: str) -> AsyncGenerator[StreamEvent]:
        # Phase 1: Planning
        plan = await self.planner.create_plan(user_input, self.memory)
        yield PlanCreatedEvent(plan)
        
        # Phase 2: User Approval
        yield ApprovalRequestEvent(plan)
        # Wait for approval...
        
        # Phase 3: Execution
        for step in plan.steps:
            async for event in self.executor.execute_step(step):
                yield event
```

#### 2. Document Service

```python
class DocumentService:
    """Manages the running document with LaTeX support"""
    
    def __init__(self, project_path: Path):
        self.blocks: List[ContentBlock] = []
        self.project_path = project_path
    
    def add_text(self, content: str, latex: bool = False) -> None:
        """Add text block, optionally with LaTeX"""
        
    def add_code(self, code: str, language: str, output: str = None) -> None:
        """Add code block with optional output"""
        
    def add_image(self, image_path: Path, caption: str = None) -> None:
        """Add image reference"""
        
    def add_table(self, df: pd.DataFrame, caption: str = None) -> None:
        """Add dataframe as formatted table"""
        
    def render(self) -> List[StreamlitComponent]:
        """Convert blocks to Streamlit components"""
```

#### 3. Job Runner

```python
class JobRunner:
    """Manages long-running background jobs"""
    
    def __init__(self, db: Database):
        self.db = db
        self.active_jobs: Dict[str, subprocess.Popen] = {}
    
    def submit_job(self, job: Job) -> str:
        """Submit job for background execution"""
        
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job"""
        
    def get_status(self, job_id: str) -> JobStatus:
        """Get current job status from database"""
        
    def monitor_job(self, job_id: str) -> AsyncGenerator[JobUpdate]:
        """Stream job updates"""
```

#### 4. Code Executor

```python
class CodeExecutor:
    """Executes Python/Bash with timeout management"""
    
    def __init__(self, 
                 project_path: Path,
                 activity_timeout: int = 300,  # 5 minutes
                 overall_timeout: int = 3600):  # 60 minutes
        self.project_path = project_path
        self.activity_timeout = activity_timeout
        self.overall_timeout = overall_timeout
    
    async def execute_python(self, code: str) -> AsyncGenerator[OutputChunk]:
        """Execute Python code with streaming output"""
        
    async def execute_bash(self, command: str) -> AsyncGenerator[OutputChunk]:
        """Execute bash command with streaming output"""
```

### Database Schema

```sql
-- Projects table
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    folder_path TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    disk_usage_bytes INTEGER DEFAULT 0
);

-- Conversations table
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    user_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    messages JSON NOT NULL DEFAULT '[]',
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- Jobs table
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    conversation_id TEXT,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    command TEXT NOT NULL,
    output TEXT,
    error TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

-- Document blocks table
CREATE TABLE document_blocks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    block_type TEXT NOT NULL,
    content JSON NOT NULL,
    position INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- Agent todo list
CREATE TABLE agent_todos (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    conversation_id TEXT,
    task TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- Global settings
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Streaming Architecture

```
User Input
    │
    ▼
┌─────────────────┐
│  Agent Engine   │
└────────┬────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│           Streaming Handler                  │
│  ┌──────────────────────────────────────┐    │
│  │  Event Types:                        │    │
│  │  - PlanCreatedEvent                  │    │
│  │  - ApprovalRequestEvent              │    │
│  │  - ToolStartEvent                    │    │
│  │  - ToolOutputEvent                   │    │
│  │  - ToolCompleteEvent                 │    │
│  │  - DocumentUpdateEvent               │    │
│  │  - JobStatusEvent                    │    │
│  │  - ErrorEvent                        │    │
│  └──────────────────────────────────────┘    │
└────────────────────┬─────────────────────────┘
                     │
                     ▼
            ┌────────────────┐
            │  Streamlit UI  │
            │  (st.empty()   │
            │   containers)  │
            └────────────────┘
```

---

## Tools & Technologies

### Core Framework
| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| UI Framework | Streamlit | ≥1.37 | Web interface |
| Agent Framework | LangChain | ≥0.3 | Agent orchestration |
| Python Environment | uv | ≥0.4 | Package management |
| Database | SQLite | 3.x | Data persistence |

### LLM Providers
| Provider | Library | Purpose |
|----------|---------|---------|
| Anthropic | anthropic, langchain-anthropic | Claude models |
| OpenAI | openai, langchain-openai | GPT models |
| Local | ollama, langchain-ollama | Local model support (optional) |

### Data Science Stack (Pre-installed)
```toml
# pyproject.toml dependencies for workspace environment
[project]
dependencies = [
    # Core
    "numpy>=1.26",
    "pandas>=2.2",
    "scipy>=1.13",
    
    # Machine Learning
    "scikit-learn>=1.5",
    "xgboost>=2.0",
    "lightgbm>=4.4",
    "catboost>=1.2",
    
    # Deep Learning (optional)
    "torch>=2.3",
    "transformers>=4.41",
    
    # Visualization
    "matplotlib>=3.9",
    "seaborn>=0.13",
    "plotly>=5.22",
    
    # Data Processing
    "polars>=1.0",
    "pyarrow>=16.0",
    "openpyxl>=3.1",
    
    # Statistics
    "statsmodels>=0.14",
    "pingouin>=0.5",
    
    # Utilities
    "tqdm>=4.66",
    "joblib>=1.4",
    "python-dotenv>=1.0",
]
```

### Agent Tools Dependencies
| Tool | Library | Purpose |
|------|---------|---------|
| Web Search | playwright | Browser automation for web scraping |
| File Operations | pathlib, shutil | File system operations |
| Code Execution | subprocess, asyncio | Process management |

### Development Tools
| Tool | Purpose |
|------|---------|
| pytest | Testing |
| ruff | Linting and formatting |
| mypy | Type checking |
| pre-commit | Git hooks |

---

## Implementation Phases

### Phase 1: Foundation (Week 1-2)
**Goal**: Basic infrastructure and project structure

#### Tasks:
- [ ] 1.1 Project scaffolding and directory structure
- [ ] 1.2 SQLite database setup with schema
- [ ] 1.3 uv environment configuration with DS packages
- [ ] 1.4 Basic Streamlit app shell with multi-page layout
- [ ] 1.5 Configuration management (LLM providers, timeouts)
- [ ] 1.6 Project service (create, list, load projects)
- [ ] 1.7 File explorer component

#### Deliverables:
- Working Streamlit app with project management
- Database operations functional
- Environment setup scripts

### Phase 2: Agent Core (Week 3-4)
**Goal**: LangChain agent with plan-then-execute pattern

#### Tasks:
- [ ] 2.1 LLM provider abstraction layer
- [ ] 2.2 Planner agent implementation
- [ ] 2.3 Executor agent implementation
- [ ] 2.4 Streaming handler for tool-by-tool updates
- [ ] 2.5 Conversation memory with SQLite persistence
- [ ] 2.6 Basic chat UI with streaming display

#### Deliverables:
- Functional agent with planning capability
- Streaming responses working
- Conversation persistence

### Phase 3: Tool Implementation (Week 5-6)
**Goal**: All agent tools functional

#### Tasks:
- [ ] 3.1 File operations tool
- [ ] 3.2 Bash execution tool with timeout handling
- [ ] 3.3 Python code interpreter with streaming output
- [ ] 3.4 Web search tool with Playwright
- [ ] 3.5 Todo list tool for agent task tracking
- [ ] 3.6 Approval workflow for code execution

#### Deliverables:
- All tools functional and tested
- Timeout system working
- User approval flow implemented

### Phase 4: Document System (Week 7-8)
**Goal**: Running document with LaTeX support

#### Tasks:
- [ ] 4.1 Document service with block management
- [ ] 4.2 Text block rendering with LaTeX (st.latex)
- [ ] 4.3 Code block rendering with syntax highlighting
- [ ] 4.4 Image block rendering from file paths
- [ ] 4.5 Table rendering for dataframes
- [ ] 4.6 Document panel in Streamlit UI
- [ ] 4.7 Agent integration for document updates

#### Deliverables:
- Document panel rendering all block types
- LaTeX equations displaying correctly
- Images loading from project folder

### Phase 5: Long-Running Jobs (Week 9-10)
**Goal**: Background job execution system

#### Tasks:
- [ ] 5.1 Job runner with subprocess management
- [ ] 5.2 Job status tracking in SQLite
- [ ] 5.3 Activity timeout detection
- [ ] 5.4 Overall timeout enforcement
- [ ] 5.5 Job cancellation mechanism
- [ ] 5.6 Progress updates to UI
- [ ] 5.7 Job history and results storage

#### Deliverables:
- Jobs running in background
- Cancellation working
- Timeouts enforced
- UI showing job status

### Phase 6: Polish & Integration (Week 11-12)
**Goal**: Complete integration and UX refinement

#### Tasks:
- [ ] 6.1 Multi-user session handling
- [ ] 6.2 Disk usage tracking and display
- [ ] 6.3 Data upload functionality
- [ ] 6.4 Project resume capability
- [ ] 6.5 Error handling and recovery
- [ ] 6.6 UI/UX improvements
- [ ] 6.7 Conversation export to JSON
- [ ] 6.8 Global settings management

#### Deliverables:
- Fully integrated application
- All features working together
- Polished user experience

### Phase 7: Future Enhancements (Post-MVP)
- [ ] 7.1 Email notification system
- [ ] 7.2 Unified memory across sessions
- [ ] 7.3 Automatic project cleanup policies
- [ ] 7.4 Advanced visualization options
- [ ] 7.5 Model versioning and tracking
- [ ] 7.6 Collaborative editing features

---

## Testing Strategy

### Unit Tests

#### Agent Tests
```python
# tests/test_agent/test_planner.py
class TestPlannerAgent:
    def test_creates_valid_plan(self):
        """Planner creates structured plan from user input"""
        
    def test_handles_ambiguous_input(self):
        """Planner asks clarifying questions for ambiguous requests"""
        
    def test_plan_includes_approval_steps(self):
        """Plan marks steps requiring user approval"""

# tests/test_agent/test_executor.py
class TestExecutorAgent:
    def test_executes_plan_steps_in_order(self):
        """Executor processes steps sequentially"""
        
    def test_handles_step_failure(self):
        """Executor handles individual step failures gracefully"""
        
    def test_respects_approval_requirements(self):
        """Executor waits for approval on marked steps"""
```

#### Tool Tests
```python
# tests/test_tools/test_code_executor.py
class TestCodeExecutor:
    def test_executes_python_code(self):
        """Executes valid Python and returns output"""
        
    def test_activity_timeout(self):
        """Triggers timeout when no output for 5 minutes"""
        
    def test_overall_timeout(self):
        """Triggers timeout after 60 minutes total"""
        
    def test_captures_stderr(self):
        """Captures and returns error output"""

# tests/test_tools/test_file_operations.py
class TestFileOperations:
    def test_read_file(self):
        """Reads file content correctly"""
        
    def test_write_file(self):
        """Writes content to file"""
        
    def test_respects_project_boundary(self):
        """Prevents access outside project directory"""
```

#### Service Tests
```python
# tests/test_services/test_document_service.py
class TestDocumentService:
    def test_add_text_block(self):
        """Adds text block to document"""
        
    def test_add_latex_block(self):
        """Adds LaTeX block with proper rendering"""
        
    def test_add_image_block(self):
        """Adds image reference block"""
        
    def test_block_ordering(self):
        """Maintains correct block order"""

# tests/test_services/test_job_runner.py
class TestJobRunner:
    def test_submit_job(self):
        """Submits job and returns job ID"""
        
    def test_cancel_job(self):
        """Cancels running job"""
        
    def test_job_status_updates(self):
        """Job status updates in database"""
```

### Integration Tests

```python
# tests/integration/test_agent_workflow.py
class TestAgentWorkflow:
    def test_complete_eda_workflow(self):
        """Agent performs complete EDA on sample dataset"""
        
    def test_model_training_workflow(self):
        """Agent trains and evaluates a model"""
        
    def test_long_running_job_workflow(self):
        """Agent submits and monitors long-running job"""

# tests/integration/test_document_flow.py
class TestDocumentFlow:
    def test_analysis_populates_document(self):
        """Agent analysis results appear in document"""
        
    def test_images_render_correctly(self):
        """Generated plots display in document"""
```

### End-to-End Tests

```python
# tests/e2e/test_streamlit_app.py
class TestStreamlitApp:
    def test_create_new_project(self):
        """User can create new project"""
        
    def test_upload_data(self):
        """User can upload dataset"""
        
    def test_chat_interaction(self):
        """User can chat with agent"""
        
    def test_approve_code_execution(self):
        """User can approve/reject code execution"""
        
    def test_resume_project(self):
        """User can resume previous project"""
```

### Test Data

```
tests/
├── fixtures/
│   ├── sample_datasets/
│   │   ├── iris.csv
│   │   ├── titanic.csv
│   │   └── housing.csv
│   ├── sample_code/
│   │   ├── valid_analysis.py
│   │   ├── timeout_code.py
│   │   └── error_code.py
│   └── sample_conversations/
│       └── eda_conversation.json
```

### Test Coverage Requirements
- Unit tests: ≥80% coverage
- Integration tests: All critical workflows
- E2E tests: Core user journeys

### CI/CD Testing Pipeline
```yaml
# .github/workflows/test.yml
stages:
  - lint:
      - ruff check
      - mypy
  - unit-tests:
      - pytest tests/test_agent
      - pytest tests/test_tools
      - pytest tests/test_services
  - integration-tests:
      - pytest tests/integration
  - e2e-tests:
      - pytest tests/e2e
```

---

## Directory Structure

```
agent-ml/
├── README.md
├── AGENT.md
├── pyproject.toml
├── uv.lock
├── .env.example
├── .gitignore
│
├── src/
│   ├── __init__.py
│   ├── main.py                      # Streamlit entry point
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py              # Global configuration
│   │   └── llm_providers.py         # LLM provider configs
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── engine.py                # Main agent orchestrator
│   │   ├── planner.py               # Plan-then-execute planner
│   │   ├── executor.py              # Step executor
│   │   ├── memory.py                # Conversation memory
│   │   └── streaming.py             # Streaming handler
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py                  # Base tool class
│   │   ├── file_operations.py       # File read/write/list
│   │   ├── bash_executor.py         # Bash command execution
│   │   ├── python_executor.py       # Python code execution
│   │   ├── web_search.py            # Playwright web search
│   │   └── todo_list.py             # Agent todo tracking
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── project_service.py       # Project management
│   │   ├── document_service.py      # Document block management
│   │   ├── job_service.py           # Long-running jobs
│   │   └── storage_service.py       # Disk usage tracking
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py            # SQLite connection
│   │   ├── models.py                # Data models
│   │   └── migrations.py            # Schema migrations
│   │
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── pages/
│   │   │   ├── home.py              # Project list
│   │   │   └── workspace.py         # Main workspace
│   │   ├── components/
│   │   │   ├── chat_panel.py        # Chat interface
│   │   │   ├── document_panel.py    # Document display
│   │   │   ├── file_explorer.py     # File browser
│   │   │   ├── job_status.py        # Job monitoring
│   │   │   └── approval_dialog.py   # Code approval
│   │   └── styles/
│   │       └── custom.css
│   │
│   └── utils/
│       ├── __init__.py
│       ├── timeout.py               # Timeout management
│       ├── logging.py               # Logging setup
│       └── validators.py            # Input validation
│
├── workspace/                        # Runtime workspace (gitignored)
│   ├── .venv/                       # Shared uv environment
│   ├── agent.db                     # SQLite database
│   └── {project-folders}/
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── fixtures/
│   ├── test_agent/
│   ├── test_tools/
│   ├── test_services/
│   ├── integration/
│   └── e2e/
│
└── scripts/
    ├── setup_workspace.py           # Initialize workspace
    ├── init_db.py                   # Create database schema
    └── install_ds_packages.py       # Install DS stack
```

---

## Configuration

### Environment Variables (.env)
```bash
# LLM Configuration
LLM_PROVIDER=anthropic              # anthropic, openai, ollama
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Model Selection
ANTHROPIC_MODEL=claude-sonnet-4-20250514
OPENAI_MODEL=gpt-4o

# Workspace
WORKSPACE_PATH=./workspace

# Timeouts (seconds)
ACTIVITY_TIMEOUT=300                # 5 minutes
OVERALL_TIMEOUT=3600                # 60 minutes

# Database
DATABASE_PATH=./workspace/agent.db

# Streamlit
STREAMLIT_SERVER_PORT=8501
```

### Global Settings (stored in SQLite)
```json
{
  "activity_timeout": 300,
  "overall_timeout": 3600,
  "default_llm_provider": "anthropic",
  "max_concurrent_jobs": 3,
  "disk_usage_warning_gb": 10
}
```

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Code execution security | High | Sandboxed execution, user approval, timeouts |
| LLM API costs | Medium | Token tracking, rate limiting, caching |
| Long job failures | Medium | Checkpointing, job recovery, detailed logging |
| Data loss | High | Regular DB backups, project export |
| Memory leaks | Medium | Process isolation, resource monitoring |
| Concurrent access | Low | SQLite WAL mode, session isolation |

---

## Success Metrics

1. **Functional**: All agent tools working with <1% error rate
2. **Performance**: Streaming latency <500ms per update
3. **Reliability**: 99% uptime for local deployment
4. **Usability**: Users can complete EDA workflow in <10 interactions
5. **Test Coverage**: ≥80% unit test coverage

---

## Appendix

### A. LangChain Agent Setup Reference

```python
from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain_anthropic import ChatAnthropic

# Example setup (actual implementation will differ)
llm = ChatAnthropic(model="claude-sonnet-4-20250514")

tools = [
    FileOperationsTool(),
    BashExecutorTool(),
    PythonExecutorTool(),
    WebSearchTool(),
    TodoListTool(),
]

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a data science assistant..."),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

agent = create_react_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools)
```

### B. Streaming Handler Reference

```python
from typing import AsyncGenerator
from langchain_core.callbacks import AsyncCallbackHandler

class StreamingHandler(AsyncCallbackHandler):
    async def on_tool_start(self, tool_name: str, tool_input: dict):
        yield ToolStartEvent(tool_name, tool_input)
    
    async def on_tool_end(self, tool_output: str):
        yield ToolCompleteEvent(tool_output)
    
    async def on_llm_new_token(self, token: str):
        # Aggregate tokens, emit on tool boundaries
        pass
```

### C. Useful Commands

```bash
# Setup workspace
uv venv workspace/.venv
uv pip install -r requirements-ds.txt

# Run application
streamlit run src/main.py

# Run tests
pytest tests/ -v --cov=src

# Lint and format
ruff check src/ tests/
ruff format src/ tests/
```
