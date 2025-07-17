"""
Result File Scanner - Simple resume functionality based on existing result files.

Replaces the complex checkpoint system with a simpler approach that scans
existing result files to determine completion status and enable resume.
"""

import json
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
from loguru import logger


class ResultScanner:
    """Scans existing result files to determine task completion status."""
    
    def __init__(self, output_dir: Path):
        """Initialize result scanner."""
        self.output_dir = Path(output_dir)
        self.results_dir = self.output_dir / "individual_results"
        
    def scan_completed_tasks(self) -> Dict[str, Dict]:
        """
        Scan existing result files to determine completed tasks.
        
        Returns:
            Dict mapping task_id to result data for completed tasks
        """
        completed_tasks = {}
        
        if not self.results_dir.exists():
            logger.info("No results directory found - starting fresh")
            return completed_tasks
            
        try:
            for result_file in self.results_dir.glob("*.json"):
                try:
                    with open(result_file, 'r', encoding='utf-8') as f:
                        result_data = json.load(f)
                    
                    # Extract task ID from filename or result data
                    task_id = self._extract_task_id(result_file.stem, result_data)
                    if task_id:
                        # Use filename as unique key to avoid overwriting multiple runs
                        unique_key = result_file.stem
                        completed_tasks[unique_key] = result_data
                        logger.debug(f"Found completed task: {task_id} (file: {unique_key})")
                        
                except Exception as e:
                    logger.warning(f"Failed to read result file {result_file}: {e}")
                    continue
                    
            logger.info(f"Found {len(completed_tasks)} completed tasks")
            return completed_tasks
            
        except Exception as e:
            logger.error(f"Failed to scan result files: {e}")
            return {}
    
    def _extract_task_id(self, filename: str, result_data: Dict) -> Optional[str]:
        """Extract task ID from filename or result data."""
        try:
            # Try to get from result data first
            if 'html_file_id' in result_data and 'task_id' in result_data:
                return f"{result_data['html_file_id']}:{result_data['task_id']}"
            
            # Fallback to filename parsing (format: html_file_id_task_id.json)
            if '_' in filename:
                # Convert back from filename format (colons replaced with underscores)
                parts = filename.split('_')
                if len(parts) >= 2:
                    # Reconstruct: everything except last part is html_file_id, last part is task_id
                    html_file_id = '_'.join(parts[:-1])
                    task_id = parts[-1]
                    return f"{html_file_id}:{task_id}"
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to extract task ID from {filename}: {e}")
            return None
    
    def get_task_run_counts(self, completed_tasks: Dict[str, Dict]) -> Dict[str, int]:
        """
        Get run counts for tasks with multiple runs.
        
        Args:
            completed_tasks: Dict of completed task results
            
        Returns:
            Dict mapping task_id to number of completed runs
        """
        run_counts = {}
        
        for task_id, result_data in completed_tasks.items():
            # Count runs by looking for run_number in result data
            if 'run_number' in result_data:
                # This is a single run result
                base_task_id = self._get_base_task_id(task_id)
                run_counts[base_task_id] = run_counts.get(base_task_id, 0) + 1
            else:
                # Legacy result without run information - count as 1 run
                run_counts[task_id] = 1
                
        return run_counts
    
    def _get_base_task_id(self, task_id: str) -> str:
        """Get base task ID without run information."""
        # For now, just return the task_id as-is since run info is in result data
        return task_id
    
    def should_skip_task(self, task_id: str, run_number: int, completed_tasks: Dict[str, Dict],
                        num_runs_per_task: int) -> bool:
        """
        Determine if a task run should be skipped based on existing results.

        Args:
            task_id: Task identifier
            run_number: Current run number (1-based)
            completed_tasks: Dict of completed task results (keyed by filename)
            num_runs_per_task: Total number of runs per task

        Returns:
            True if this task run should be skipped
        """
        try:
            # Count existing runs for this task by checking result data
            existing_runs = 0
            for filename, result_data in completed_tasks.items():
                result_task_id = f"{result_data.get('html_file_id')}:{result_data.get('task_id')}"
                if result_task_id == task_id:
                    existing_runs += 1

                    # Check if this specific run number already exists
                    if result_data.get('run_number') == run_number:
                        logger.debug(f"Skipping {task_id} run {run_number} - already completed")
                        return True

            # Skip if we already have enough runs
            if existing_runs >= num_runs_per_task:
                logger.debug(f"Skipping {task_id} run {run_number} - already have {existing_runs} runs")
                return True

            return False

        except Exception as e:
            logger.warning(f"Error checking if task should be skipped: {e}")
            return False
    
    def get_resume_summary(self, completed_tasks: Dict[str, Dict], total_tasks: int, 
                          num_runs_per_task: int) -> Dict[str, int]:
        """
        Get summary of resume status.
        
        Returns:
            Dict with resume statistics
        """
        total_runs = total_tasks * num_runs_per_task
        completed_runs = len(completed_tasks)
        
        # Count successful vs failed runs
        successful_runs = sum(1 for result in completed_tasks.values() 
                            if result.get('task_success') == True)
        failed_runs = completed_runs - successful_runs
        
        return {
            'total_tasks': total_tasks,
            'total_runs': total_runs,
            'completed_runs': completed_runs,
            'successful_runs': successful_runs,
            'failed_runs': failed_runs,
            'remaining_runs': total_runs - completed_runs,
            'completion_percentage': (completed_runs / total_runs * 100) if total_runs > 0 else 0
        }
    
    def clean_old_checkpoints(self) -> None:
        """Remove old checkpoint files since we're using result file scanning."""
        try:
            checkpoint_files = list(self.output_dir.glob("*_checkpoint.json"))
            for checkpoint_file in checkpoint_files:
                try:
                    checkpoint_file.unlink()
                    logger.debug(f"Removed old checkpoint file: {checkpoint_file}")
                except Exception as e:
                    logger.warning(f"Failed to remove checkpoint file {checkpoint_file}: {e}")
                    
            if checkpoint_files:
                logger.info(f"Cleaned up {len(checkpoint_files)} old checkpoint files")
                
        except Exception as e:
            logger.warning(f"Failed to clean old checkpoints: {e}")
