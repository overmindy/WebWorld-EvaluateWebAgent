"""
Agent Evaluation Framework

A minimal but functional framework for testing AI agents on web-based tasks.
"""

__version__ = "0.1.0"
__author__ = "Agent Evaluation Framework"

from .controller.evaluation_controller import EvaluationController
from .environment.web_environment import WebEnvironment
from .agent.base_agent import BaseAgent
from .agent.uitars_agent import UITARSAgent

# Import batch functionality
try:
    from .batch.batch_controller import BatchEvaluationController
    from .batch.batch_config import BatchConfig, load_batch_config, create_sample_batch_config
    from .batch.batch_aggregator import BatchResultsAggregator

    __all__ = [
        "EvaluationController",
        "WebEnvironment",
        "BaseAgent",
        "BatchEvaluationController",
        "BatchConfig",
        "load_batch_config",
        "create_sample_batch_config",
        "BatchResultsAggregator"
    ]
except ImportError:
    # Batch functionality not available (missing dependencies)
    __all__ = [
        "EvaluationController",
        "WebEnvironment",
        "BaseAgent"
    ]
