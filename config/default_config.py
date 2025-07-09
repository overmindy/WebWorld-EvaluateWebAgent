"""Default configuration for agent evaluation framework"""

from typing import Dict, Any

DEFAULT_CONFIG: Dict[str, Any] = {
    # Browser settings
    "browser": {
        "type": "chromium",  # chromium, firefox, webkit
        "headless": False,
        "viewport": {"width": 1280, "height": 720},
        "timeout": 30000,  # milliseconds
        "slow_mo": 100,  # milliseconds delay between actions
    },
    
    # Agent settings
    "agent": {
        "type": "human",  # human, terminal
        "timeout": 10,  # seconds
        "max_retries": 3,
    },
    
    # Evaluation settings
    "evaluation": {
        "max_steps": 50,
        "step_timeout": 30,  # seconds
        "screenshot_on_error": True,
        "save_screenshots": True,
        "screenshot_dir": "logs/screenshots",
    },
    
    # Logging settings
    "logging": {
        "level": "INFO",
        "log_dir": "logs",
        "log_file": "evaluation.log",
        "console_output": True,
    },
    
    # Task settings
    "task": {
        "description": "",
        "success_criteria": [],
        "max_duration": 300,  # seconds
    }
}
