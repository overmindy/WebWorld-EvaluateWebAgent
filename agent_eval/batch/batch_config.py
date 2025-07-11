"""Batch Configuration System - Simplified and optimized."""

import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger


@dataclass
class TaskDefinition:
    """Single task definition."""
    task_id: str
    description: str
    success_criteria: Union[List[str], Dict[str, Any]] = field(default_factory=list)
    timeout: Optional[int] = None
    max_steps: Optional[int] = None
    agent_config: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class HTMLFileDefinition:
    """HTML file with associated tasks."""
    file_id: str
    file_path: str
    tasks: List[TaskDefinition]
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class BatchSettings:
    """Batch execution settings."""
    parallel_execution: bool = False
    max_parallel_workers: int = 3
    continue_on_failure: bool = True
    global_timeout: Optional[int] = None
    retry_failed_tasks: bool = False
    max_retries: int = 1
    save_screenshots: bool = True
    save_individual_results: bool = True
    export_formats: List[str] = field(default_factory=lambda: ["json"])
    reuse_browser_per_file: bool = True  # Reuse browser for tasks on same HTML file


@dataclass
class BatchConfig:
    """Complete batch evaluation configuration."""
    batch_name: str
    html_files_directory: str
    html_files: List[HTMLFileDefinition]
    batch_settings: BatchSettings
    description: Optional[str] = None
    output_directory: str = "batch_results"
    global_agent_config: Optional[Dict[str, Any]] = None
    global_browser_config: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate_html_directory()
        self._validate_html_files()

    def _validate_html_directory(self):
        """Validate HTML files directory exists."""
        path = Path(self.html_files_directory)
        if not path.exists() or not path.is_dir():
            raise ValueError(f"Invalid HTML directory: {self.html_files_directory}")
        self.html_files_directory = str(path.resolve())

    def _validate_html_files(self):
        """Validate HTML files and tasks."""
        if not self.html_files:
            raise ValueError("At least one HTML file must be specified")

        file_ids = set()
        html_dir = Path(self.html_files_directory)

        for html_file in self.html_files:
            if html_file.file_id in file_ids:
                raise ValueError(f"Duplicate file ID: {html_file.file_id}")
            file_ids.add(html_file.file_id)

            file_path = html_dir / html_file.file_path
            if not file_path.exists():
                raise ValueError(f"HTML file not found: {file_path}")

            if not html_file.tasks:
                raise ValueError(f"File {html_file.file_id} needs at least one task")

            task_ids = {task.task_id for task in html_file.tasks}
            if len(task_ids) != len(html_file.tasks):
                raise ValueError(f"Duplicate task IDs in file {html_file.file_id}")


def load_batch_config(config_path: Union[str, Path]) -> BatchConfig:
    """Load and validate batch configuration from JSON or YAML file."""
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    # Load configuration data
    with open(config_path, 'r', encoding='utf-8') as f:
        if config_path.suffix.lower() in ['.yaml', '.yml']:
            config_data = yaml.safe_load(f)
        elif config_path.suffix.lower() == '.json':
            config_data = json.load(f)
        else:
            raise ValueError(f"Unsupported file format: {config_path.suffix}")

    try:
        # Parse HTML files and tasks
        html_files = []
        for file_data in config_data.get('html_files', []):
            tasks = [TaskDefinition(**task_data) for task_data in file_data.get('tasks', [])]
            html_file = HTMLFileDefinition(
                file_id=file_data['file_id'],
                file_path=file_data['file_path'],
                tasks=tasks,
                metadata=file_data.get('metadata')
            )
            html_files.append(html_file)

        # Parse batch settings
        batch_settings = BatchSettings(**config_data.get('batch_settings', {}))

        # Create and validate batch config
        batch_config = BatchConfig(
            batch_name=config_data['batch_name'],
            html_files_directory=config_data['html_files_directory'],
            html_files=html_files,
            batch_settings=batch_settings,
            description=config_data.get('description'),
            output_directory=config_data.get('output_directory', 'batch_results'),
            global_agent_config=config_data.get('global_agent_config'),
            global_browser_config=config_data.get('global_browser_config')
        )

        total_tasks = sum(len(hf.tasks) for hf in batch_config.html_files)
        logger.info(f"Loaded batch '{batch_config.batch_name}': {len(batch_config.html_files)} files, {total_tasks} tasks")

        return batch_config

    except Exception as e:
        raise ValueError(f"Invalid batch configuration: {e}")


def create_sample_batch_config(output_path: Union[str, Path]) -> None:
    """Create a sample batch configuration file."""
    sample_config = {
        "batch_name": "sample_batch_evaluation",
        "description": "Sample batch evaluation configuration",
        "html_files_directory": "test_html_files",
        "output_directory": "batch_results",
        "html_files": [
            {
                "file_id": "login_page",
                "file_path": "login.html",
                "tasks": [
                    {
                        "task_id": "valid_login",
                        "description": "Enter valid credentials and click login",
                        "success_criteria": ["Login successful"],
                        "timeout": 30,
                        "max_steps": 10
                    }
                ],
                "metadata": {"category": "authentication"}
            },
            {
                "file_id": "contact_form",
                "file_path": "contact.html",
                "tasks": [
                    {
                        "task_id": "fill_form",
                        "description": "Fill out the contact form",
                        "success_criteria": ["Form submitted"],
                        "timeout": 45,
                        "max_steps": 15
                    }
                ],
                "metadata": {"category": "forms"}
            }
        ],
        "batch_settings": {
            "parallel_execution": False,
            "max_parallel_workers": 2,
            "continue_on_failure": True,
            "save_screenshots": True,
            "export_formats": ["json", "csv"]
        },
        "global_agent_config": {"type": "placeholder"},
        "global_browser_config": {"type": "chromium", "headless": False}
    }

    output_path = Path(output_path)

    # Determine format and save
    if output_path.suffix.lower() in ['.yaml', '.yml']:
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(sample_config, f, default_flow_style=False, indent=2)
    else:
        # Default to JSON
        if not output_path.suffix:
            output_path = output_path.with_suffix('.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(sample_config, f, indent=2)

    logger.info(f"Sample configuration created: {output_path}")


@dataclass
class BatchResults:
    """Container for batch evaluation results."""
    batch_id: str
    batch_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_tasks: int = 0
    completed_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    individual_results: List[Dict[str, Any]] = field(default_factory=list)
    summary_stats: Dict[str, Any] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        """Calculate batch duration in seconds."""
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    @property
    def success_rate(self) -> float:
        """Calculate overall success rate."""
        return self.successful_tasks / self.completed_tasks if self.completed_tasks > 0 else 0.0

    @property
    def completion_rate(self) -> float:
        """Calculate completion rate."""
        return self.completed_tasks / self.total_tasks if self.total_tasks > 0 else 0.0

    @property
    def average_score(self) -> float:
        """Calculate average task score across all completed tasks."""
        if not self.individual_results:
            return 0.0

        scores = [r.get('task_score', 0.0) for r in self.individual_results if 'task_score' in r]
        return sum(scores) / len(scores) if scores else 0.0

    @property
    def total_fields(self) -> int:
        """Calculate total number of fields across all tasks."""
        return sum(r.get('final_validation_result', {}).get('total_fields', 0)
                  for r in self.individual_results)

    @property
    def correct_fields(self) -> int:
        """Calculate total number of correct fields across all tasks."""
        return sum(r.get('final_validation_result', {}).get('correct_fields', 0)
                  for r in self.individual_results)

    @property
    def field_accuracy(self) -> float:
        """Calculate overall field-level accuracy."""
        total = self.total_fields
        return self.correct_fields / total if total > 0 else 0.0
