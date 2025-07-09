# Web Agent 测评框架

一个专业的 Web Agent 测评工具，基于 Python 和 Playwright 构建，提供完整的 Web 自动化代理评估解决方案。支持多种代理类型、批量测试等高级功能。

## 🎯 项目概述

本框架是一个模块化的 Web Agent 评估系统，包含以下核心组件：

- **🎮 控制器模块** - 统一的评估流程编排和会话管理
- **🌐 Web 环境** - 基于 Playwright 的浏览器交互管理
- **🤖 Agent 接口** - 支持多种代理类型（人工、终端、UITARS）
- **📊 批量评估** - 并行执行多任务，支持多种导出格式
- **✅ 任务验证** - 智能任务完成度验证系统

## ✨ 主要特性

### 🚀 高性能优化
- **CDP 截图技术** - 使用 Chrome DevTools Protocol 避免 DOM 焦点丢失
- **无干扰截图** - 截图过程不影响页面状态和用户交互
- **智能坐标映射** - 自动处理设备缩放因子的坐标转换
- **精确滚动控制** - 支持基于坐标的精确滚动操作

### 🎯 多样化 Agent 支持
- **HumanAgent** - 人工交互代理，打开浏览器等待人工操作
- **TerminalAgent** - 终端交互代理，通过命令行控制操作
- **UITARSAgent** - 智能 AI 代理，支持多轮对话和历史管理

### 📊 强大的批量评估
- **并行执行** - 支持多任务并行处理
- **多格式导出** - JSON、CSV、HTML、Excel 等格式
- **失败重试** - 自动重试失败的任务
- **详细报告** - 生成完整的评估报告和统计信息

## 🚀 快速开始

### 1. 环境安装

```bash
# 克隆项目
git clone <repository-url>
cd Agent_Eval

# 安装 Python 依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install
```

### 2. 基础使用

#### 单任务评估
```bash
# 人工代理（默认）- 打开浏览器进行手动交互
python main.py single "点击搜索按钮"

# 终端代理 - 通过命令行交互控制
python main.py single "填写表单" --agent terminal

# 指定 URL
python main.py single "导航到产品页面" --url https://example.com

# 无头模式
python main.py single "点击菜单按钮" --headless

# UITARS AI 代理
python main.py single "完成登录流程" --agent uitars
```

#### 批量评估
```bash
# 运行批量评估
python main.py batch eval_data/human_evaluation_config.json
python main.py batch eval_data/terminal_evaluation_config.json
python main.py batch eval_data/uitars_eval.json

# 创建配置模板
python main.py create-config my_batch_config.json
```

#### 任务配置标注工具
```bash
# 启动任务标注工具
python start_annotation.py

# 使用配置整合工具
python config_consolidator.py
```

### 3. 配置文件示例

#### 基础任务配置
```json
{
  "batch_name": "web_ui_evaluation",
  "description": "Web UI 组件交互测试",
  "html_files_directory": "eval_data",
  "output_directory": "eval_results",
  "html_files": [
    {
      "file_id": "login_page",
      "file_path": "login.html",
      "tasks": [
        {
          "task_id": "login_test",
          "description": "使用用户名 'admin' 和密码 'password' 登录系统",
          "success_criteria": [
            "成功跳转到仪表板页面",
            "显示欢迎消息"
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

## 📁 项目结构

```
Agent_Eval/
├── agent_eval/                    # 核心框架包
│   ├── controller/               # 控制器模块
│   │   └── evaluation_controller.py
│   ├── environment/              # Web 环境模块
│   │   └── web_environment.py
│   ├── agent/                    # Agent 模块
│   │   ├── base_agent.py        # 基础 Agent 接口
│   │   ├── human_agent.py       # 人工交互 Agent
│   │   ├── terminal_agent.py    # 终端交互 Agent
│   │   └── uitars_agent.py      # UITARS AI Agent
│   ├── batch/                    # 批量评估模块
│   │   ├── batch_controller.py  # 批量控制器
│   │   ├── batch_config.py      # 配置管理
│   │   └── batch_aggregator.py  # 结果聚合
│   └── validation/               # 验证模块
│       └── task_completion_validator.py
├── config/                       # 配置文件
│   └── default_config.py
├── eval_data/                    # 测试数据和配置
│   ├── *.html                   # 测试页面
│   └── *_config.json           # 评估配置
├── Eval_dataset/                 # 大型数据集
├── logs/                         # 日志和结果
├── *_eval_results/              # 各类型评估结果
├── annotation_workflow.py       # 标注工作流
├── task_annotation_tool.py      # 任务标注工具
├── config_consolidator.py       # 配置整合工具
├── main.py                      # 🎯 统一入口点
├── start_annotation.py          # 标注工具启动器
└── requirements.txt             # 依赖列表
```

## 🔧 核心 API 接口

### Web 环境接口
```python
# 页面导航
await env.launch_webpage(url)

# 截图和状态
screenshot = await env.get_screenshot()
page_info = await env.get_page_info()

# 交互操作
await env.click(x, y)
await env.input_text(text)
await env.scroll(x, y, direction, amount)
await env.drag(start_x, start_y, end_x, end_y)
```

### Agent 接口
```python
# 基础预测接口
action = await agent.predict(screenshot, task_description)

# 历史管理（UITARS Agent）
agent.add_to_history(step_info)
conversation = agent.get_conversation_history()
```

### 批量评估接口
```python
# 加载和运行
config = load_batch_config("config.json")
results = await batch_controller.run_batch_evaluation(config)

# 结果导出
await batch_controller.export_results(["json", "excel", "html"])
```

## 🎮 Agent 类型详解

### 1. HumanAgent（人工代理）
- **用途**: 人工测试和基准建立
- **特点**: 打开浏览器，等待人工完成任务
- **适用场景**: 复杂任务验证、用户体验测试

### 2. TerminalAgent（终端代理）
- **用途**: 程序化控制和调试
- **特点**: 通过终端输入控制浏览器操作
- **适用场景**: 自动化脚本开发、精确操作控制

### 3. UITARSAgent（AI 代理）
- **用途**: 智能自动化测试
- **特点**: 基于视觉理解的智能操作
- **适用场景**: 大规模自动化测试、智能回归测试

## 📊 评估结果和报告

### 结果格式
- **JSON**: 详细的结构化数据
- **CSV**: 表格数据，便于分析
- **HTML**: 可视化报告，包含截图
- **Excel**: 多工作表详细报告

### 关键指标
- **成功率**: 任务完成百分比
- **执行时间**: 平均和总执行时间
- **步骤统计**: 操作步骤分析
- **错误分析**: 失败原因分类

## 🛠️ 高级功能

### 任务验证系统
- 自动验证任务完成状态
- 支持多种验证标准
- 智能结果判断

### 配置标注工具
- 可视化任务配置
- 浏览器集成标注
- 自动配置生成

## 🔍 故障排除

### 常见问题

1. **Playwright 安装问题**
   ```bash
   playwright install --force
   ```

2. **权限问题**
   ```bash
   # Windows
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   
   # Linux/Mac
   chmod +x main.py
   ```

3. **浏览器启动失败**
   - 检查系统依赖
   - 尝试无头模式
   - 查看详细日志

### 日志和调试
```bash
# 查看日志文件
tail -f logs/evaluation.log
```

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

- [Playwright](https://playwright.dev/) - 强大的浏览器自动化工具
- [Pydantic](https://pydantic-docs.helpmanual.io/) - 数据验证和设置管理
- [Loguru](https://github.com/Delgan/loguru) - 优雅的日志记录

---

**📧 联系方式**: 如有问题或建议，请提交 Issue 或 Pull Request。
