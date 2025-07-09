# Web Agent Evaluation Framework

A professional Web Agent evaluation tool built with Python and Playwright, providing a complete solution for evaluating web automation agents. Supports multiple agent types, batch testing, and advanced features.

## 🎯 Project Overview

This framework is a modular Web Agent evaluation system with the following core components:

- **🎮 Controller Module** - Unified evaluation workflow orchestration and session management
- **🌐 Web Environment** - Playwright-based browser interaction management
- **🤖 Agent Interface** - Support for multiple agent types (Human, Terminal, UITARS)
- **📊 Batch Evaluation** - Parallel execution of multiple tasks with various export formats
- **✅ Task Validation** - Intelligent task completion validation system

## ✨ Key Features

### 🚀 Performance Optimizations
- **CDP Screenshot Technology** - Uses Chrome DevTools Protocol to avoid DOM focus loss
- **Non-intrusive Screenshots** - Screenshot process doesn't affect page state or user interactions
- **Smart Coordinate Mapping** - Automatic handling of device scale factor coordinate transformations
- **Precise Scroll Control** - Support for coordinate-based precise scrolling operations

### 🎯 Diverse Agent Support
- **HumanAgent** - Human interaction agent, opens browser and waits for manual operations
- **TerminalAgent** - Terminal interaction agent, controls operations via command line
- **UITARSAgent** - Intelligent AI agent with multi-turn conversation and history management

### 📊 Powerful Batch Evaluation
- **Parallel Execution** - Support for multi-task parallel processing
- **Multiple Export Formats** - JSON, CSV, HTML, Excel, etc.
- **Failure Retry** - Automatic retry of failed tasks
- **Detailed Reports** - Generate comprehensive evaluation reports and statistics

## 🚀 Quick Start

### 1. Environment Setup

```bash
# Clone the project
git clone <repository-url>
cd Agent_Eval

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install
```

### 2. Basic Usage

#### Single Task Evaluation
```bash
# Human agent (default) - opens browser for manual interaction
python main.py single "Click the search button"

# Terminal agent - command line interaction control
python main.py single "Fill out the form" --agent terminal

# With specific URL
python main.py single "Navigate to products page" --url https://example.com

# Headless mode
python main.py single "Click the menu button" --headless

# UITARS AI agent
python main.py single "Complete the login process" --agent uitars
```

#### Batch Evaluation
```bash
# Run batch evaluation
python main.py batch eval_data/human_evaluation_config.json
python main.py batch eval_data/terminal_evaluation_config.json
python main.py batch eval_data/uitars_eval.json

# Create configuration template
python main.py create-config my_batch_config.json
```

#### Task Configuration Annotation Tools
```bash
# Start task annotation tool
python start_annotation.py

# Use configuration consolidator
python config_consolidator.py
```

### 3. Configuration Examples

#### Basic Task Configuration
```json
{
  "batch_name": "web_ui_evaluation",
  "description": "Web UI component interaction testing",
  "html_files_directory": "eval_data",
  "output_directory": "eval_results",
  "html_files": [
    {
      "file_id": "login_page",
      "file_path": "login.html",
      "tasks": [
        {
          "task_id": "login_test",
          "description": "Login to the system using username 'admin' and password 'password'",
          "success_criteria": [
            "Successfully navigate to dashboard page",
            "Display welcome message"
          ],
          "timeout": 300,
          "max_steps": 5
        }
      ]
    }
  ],
  "batch_settings": {
    "parallel_execution": true,
    "max_parallel_workers": 3,
    "continue_on_failure": true,
    "export_formats": ["json", "html", "excel"]
  }
}
```

## 📁 Project Structure

```
Agent_Eval/
├── agent_eval/                    # Core framework package
│   ├── controller/               # Controller module
│   │   └── evaluation_controller.py
│   ├── environment/              # Web environment module
│   │   └── web_environment.py
│   ├── agent/                    # Agent module
│   │   ├── base_agent.py        # Base agent interface
│   │   ├── human_agent.py       # Human interaction agent
│   │   ├── terminal_agent.py    # Terminal interaction agent
│   │   └── uitars_agent.py      # UITARS AI agent
│   ├── batch/                    # Batch evaluation module
│   │   ├── batch_controller.py  # Batch controller
│   │   ├── batch_config.py      # Configuration management
│   │   └── batch_aggregator.py  # Result aggregation
│   └── validation/               # Validation module
│       └── task_completion_validator.py
├── config/                       # Configuration files
│   └── default_config.py
├── eval_data/                    # Test data and configurations
│   ├── *.html                   # Test pages
│   └── *_config.json           # Evaluation configurations
├── Eval_dataset/                 # Large dataset
├── logs/                         # Logs and results
├── *_eval_results/              # Various evaluation results
├── annotation_workflow.py       # Annotation workflow
├── task_annotation_tool.py      # Task annotation tool
├── config_consolidator.py       # Configuration consolidator
├── main.py                      # 🎯 Unified entry point
├── start_annotation.py          # Annotation tool launcher
└── requirements.txt             # Dependencies list
```

## 🔧 Core API Interfaces

### Web Environment Interface
```python
# Page navigation
await env.launch_webpage(url)

# Screenshots and state
screenshot = await env.get_screenshot()
page_info = await env.get_page_info()

# Interaction operations
await env.click(x, y)
await env.input_text(text)
await env.scroll(x, y, direction, amount)
await env.drag(start_x, start_y, end_x, end_y)
```

### Agent Interface
```python
# Basic prediction interface
action = await agent.predict(screenshot, task_description)

# History management (UITARS Agent)
agent.add_to_history(step_info)
conversation = agent.get_conversation_history()
```

### Batch Evaluation Interface
```python
# Load and run
config = load_batch_config("config.json")
results = await batch_controller.run_batch_evaluation(config)

# Export results
await batch_controller.export_results(["json", "excel", "html"])
```

## 🎮 Agent Types Explained

### 1. HumanAgent
- **Purpose**: Manual testing and benchmark establishment
- **Features**: Opens browser, waits for manual task completion
- **Use Cases**: Complex task validation, user experience testing

### 2. TerminalAgent
- **Purpose**: Programmatic control and debugging
- **Features**: Controls browser operations via terminal input
- **Use Cases**: Automation script development, precise operation control

### 3. UITARSAgent
- **Purpose**: Intelligent automated testing
- **Features**: Visual understanding-based intelligent operations
- **Use Cases**: Large-scale automated testing, intelligent regression testing

## 📊 Evaluation Results and Reports

### Result Formats
- **JSON**: Detailed structured data
- **CSV**: Tabular data for easy analysis
- **HTML**: Visual reports with screenshots
- **Excel**: Multi-sheet detailed reports

### Key Metrics
- **Success Rate**: Task completion percentage
- **Execution Time**: Average and total execution time
- **Step Statistics**: Operation step analysis
- **Error Analysis**: Failure reason classification

## 🛠️ Advanced Features

### Task Validation System
- Automatic task completion status validation
- Support for multiple validation criteria
- Intelligent result judgment

### Configuration Annotation Tools
- Visual task configuration
- Browser-integrated annotation
- Automatic configuration generation

## 🔍 Troubleshooting

### Common Issues

1. **Playwright Installation Issues**
   ```bash
   playwright install --force
   ```

2. **Permission Issues**
   ```bash
   # Windows
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

   # Linux/Mac
   chmod +x main.py
   ```

3. **Browser Launch Failures**
   - Check system dependencies
   - Try headless mode
   - Check detailed logs

### Logging and Debugging
```bash
# Check log files
tail -f logs/evaluation.log
```

## 🤝 Contributing

1. Fork the project
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Playwright](https://playwright.dev/) - Powerful browser automation tool
- [Pydantic](https://pydantic-docs.helpmanual.io/) - Data validation and settings management
- [Loguru](https://github.com/Delgan/loguru) - Elegant logging

---

**📧 Contact**: For questions or suggestions, please submit an Issue or Pull Request.
