"""Checkpoint Manager for Batch Evaluation System."""

import json
import pickle
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
from dataclasses import dataclass, asdict
from loguru import logger


@dataclass
class CheckpointData:
    """Container for checkpoint state data."""
    batch_id: str
    batch_name: str
    checkpoint_timestamp: datetime
    total_tasks: int
    completed_tasks: int
    successful_tasks: int
    failed_tasks: int
    completed_task_ids: Set[str]
    current_task_index: int
    individual_results: List[Dict[str, Any]]
    batch_config_path: str
    num_runs_per_task: int
    task_run_counts: Dict[str, int]  # Track how many runs completed per task
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['checkpoint_timestamp'] = self.checkpoint_timestamp.isoformat()
        data['completed_task_ids'] = list(self.completed_task_ids)
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CheckpointData':
        """Create from dictionary loaded from JSON."""
        data['checkpoint_timestamp'] = datetime.fromisoformat(data['checkpoint_timestamp'])
        data['completed_task_ids'] = set(data['completed_task_ids'])
        return cls(**data)


class CheckpointManager:
    """Manages checkpoint save/restore functionality for batch evaluations."""
    
    def __init__(self, output_dir: Path, batch_id: str):
        """Initialize checkpoint manager."""
        self.output_dir = Path(output_dir)
        self.batch_id = batch_id
        self.checkpoint_file = self.output_dir / f"{batch_id}_checkpoint.json"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Checkpoint manager initialized: {self.checkpoint_file}")
    
    def save_checkpoint(self, checkpoint_data: CheckpointData) -> None:
        """Save checkpoint data to file."""
        try:
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data.to_dict(), f, indent=2, default=str)
            
            logger.info(f"Checkpoint saved: {checkpoint_data.completed_tasks}/{checkpoint_data.total_tasks} tasks completed")
            
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            raise
    
    def load_checkpoint(self) -> Optional[CheckpointData]:
        """Load checkpoint data from file."""
        try:
            if not self.checkpoint_file.exists():
                logger.info("No checkpoint file found")
                return None
            
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            checkpoint_data = CheckpointData.from_dict(data)
            logger.info(f"Checkpoint loaded: {checkpoint_data.completed_tasks}/{checkpoint_data.total_tasks} tasks completed")
            return checkpoint_data
            
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None
    
    def checkpoint_exists(self) -> bool:
        """Check if a checkpoint file exists."""
        return self.checkpoint_file.exists()
    
    def delete_checkpoint(self) -> None:
        """Delete checkpoint file."""
        try:
            if self.checkpoint_file.exists():
                self.checkpoint_file.unlink()
                logger.info("Checkpoint file deleted")
        except Exception as e:
            logger.warning(f"Failed to delete checkpoint file: {e}")
    
    @staticmethod
    def find_checkpoint_files(output_dir: Path) -> List[Path]:
        """Find all checkpoint files in output directory."""
        try:
            return list(output_dir.glob("*_checkpoint.json"))
        except Exception as e:
            logger.error(f"Failed to find checkpoint files: {e}")
            return []
    
    @staticmethod
    def get_checkpoint_info(checkpoint_file: Path) -> Optional[Dict[str, Any]]:
        """Get basic info about a checkpoint file."""
        try:
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return {
                'batch_id': data.get('batch_id'),
                'batch_name': data.get('batch_name'),
                'checkpoint_timestamp': data.get('checkpoint_timestamp'),
                'progress': f"{data.get('completed_tasks', 0)}/{data.get('total_tasks', 0)}",
                'success_rate': f"{data.get('successful_tasks', 0)}/{data.get('completed_tasks', 0)}" if data.get('completed_tasks', 0) > 0 else "0/0"
            }
            
        except Exception as e:
            logger.error(f"Failed to read checkpoint info: {e}")
            return None


class TaskExecutionTracker:
    """Tracks task execution for multiple runs per task."""
    
    def __init__(self, num_runs_per_task: int = 1):
        """Initialize task execution tracker."""
        self.num_runs_per_task = num_runs_per_task
        self.task_run_counts: Dict[str, int] = {}
        self.task_results: Dict[str, List[Dict[str, Any]]] = {}
    
    def should_execute_task(self, task_id: str) -> bool:
        """Check if task should be executed (hasn't reached max runs)."""
        current_runs = self.task_run_counts.get(task_id, 0)
        return current_runs < self.num_runs_per_task
    
    def record_task_execution(self, task_id: str, result: Dict[str, Any]) -> None:
        """Record a task execution result."""
        if task_id not in self.task_run_counts:
            self.task_run_counts[task_id] = 0
            self.task_results[task_id] = []
        
        self.task_run_counts[task_id] += 1
        self.task_results[task_id].append(result)
    
    def get_task_run_count(self, task_id: str) -> int:
        """Get current run count for a task."""
        return self.task_run_counts.get(task_id, 0)
    
    def get_task_results(self, task_id: str) -> List[Dict[str, Any]]:
        """Get all results for a task."""
        return self.task_results.get(task_id, [])
    
    def get_aggregated_task_result(self, task_id: str) -> Dict[str, Any]:
        """Get aggregated result for a task across all runs."""
        results = self.get_task_results(task_id)
        if not results:
            return {}
        
        # Calculate success rate across runs
        successful_runs = sum(1 for r in results if r.get('task_success') == True)
        total_runs = len(results)
        success_rate = successful_runs / total_runs if total_runs > 0 else 0.0
        
        # Use the most recent result as base, but add aggregated stats
        latest_result = results[-1].copy()
        latest_result.update({
            'total_runs': total_runs,
            'successful_runs': successful_runs,
            'failed_runs': total_runs - successful_runs,
            'success_rate_across_runs': success_rate,
            'all_run_results': results
        })
        
        return latest_result
    
    def is_task_complete(self, task_id: str) -> bool:
        """Check if task has completed all required runs."""
        return self.get_task_run_count(task_id) >= self.num_runs_per_task
    
    def get_completion_stats(self) -> Dict[str, Any]:
        """Get overall completion statistics."""
        total_tasks = len(self.task_run_counts)
        completed_tasks = sum(1 for task_id in self.task_run_counts if self.is_task_complete(task_id))
        
        total_runs_executed = sum(self.task_run_counts.values())
        total_runs_expected = total_tasks * self.num_runs_per_task
        
        return {
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'total_runs_executed': total_runs_executed,
            'total_runs_expected': total_runs_expected,
            'task_completion_rate': completed_tasks / total_tasks if total_tasks > 0 else 0.0,
            'run_completion_rate': total_runs_executed / total_runs_expected if total_runs_expected > 0 else 0.0
        }
