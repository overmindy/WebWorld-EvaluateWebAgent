"""Batch Evaluation Controller - Streamlined and optimized."""

import asyncio
import time
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from loguru import logger

from ..controller.evaluation_controller import EvaluationController
from ..agent.human_agent import HumanAgent
from .batch_config import BatchConfig, HTMLFileDefinition, TaskDefinition, BatchResults
from .batch_aggregator import BatchResultsAggregator


class BatchProgressTracker:
    """Tracks batch evaluation progress."""

    def __init__(self, total_tasks: int):
        self.total_tasks = total_tasks
        self.completed_tasks = 0
        self.successful_tasks = 0
        self.failed_tasks = 0
        self.current_task = None
        self.start_time = datetime.now()
        self.callbacks: List[Callable] = []

    def add_callback(self, callback: Callable):
        """Add progress callback function."""
        self.callbacks.append(callback)

    def update_progress(self, task_id: str, status: str, success: bool = False):
        """Update progress and notify callbacks."""
        self.current_task = task_id

        if status == "completed":
            self.completed_tasks += 1
            if success:
                self.successful_tasks += 1
            else:
                self.failed_tasks += 1

        # Notify callbacks safely
        for callback in self.callbacks:
            try:
                callback(self)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")

    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        return (self.completed_tasks / self.total_tasks) * 100 if self.total_tasks > 0 else 0.0

    @property
    def elapsed_time(self) -> float:
        """Get elapsed time in seconds."""
        return (datetime.now() - self.start_time).total_seconds()

    @property
    def estimated_remaining_time(self) -> float:
        """Estimate remaining time in seconds."""
        if 0 < self.completed_tasks < self.total_tasks:
            avg_time = self.elapsed_time / self.completed_tasks
            return avg_time * (self.total_tasks - self.completed_tasks)
        return 0.0


class BatchEvaluationController:
    """Controller for batch evaluation of multiple HTML files and tasks."""

    def __init__(self, batch_config: BatchConfig):
        """Initialize batch evaluation controller."""
        self.batch_config = batch_config
        self.batch_id = f"batch_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        self.output_dir = Path(batch_config.output_directory) / self.batch_id
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.progress_tracker: Optional[BatchProgressTracker] = None
        self.results_aggregator = BatchResultsAggregator(self.output_dir)
        self.individual_controllers: List[EvaluationController] = []
        self.total_tasks = sum(len(html_file.tasks) for html_file in batch_config.html_files)

        logger.info(f"Batch controller initialized: {self.batch_id} ({self.total_tasks} tasks)")

    def add_progress_callback(self, callback: Callable):
        """Add progress tracking callback."""
        if self.progress_tracker:
            self.progress_tracker.add_callback(callback)
    
    async def run_batch_evaluation(self) -> BatchResults:
        """Run complete batch evaluation."""
        logger.info(f"Starting batch evaluation: {self.batch_config.batch_name}")

        self.progress_tracker = BatchProgressTracker(self.total_tasks)
        batch_results = BatchResults(
            batch_id=self.batch_id,
            batch_name=self.batch_config.batch_name,
            start_time=datetime.now(),
            total_tasks=self.total_tasks
        )

        try:
            # Execute evaluations
            if self.batch_config.batch_settings.parallel_execution:
                individual_results = await self._run_parallel_evaluations()
            else:
                individual_results = await self._run_sequential_evaluations()

            # Update results
            batch_results.end_time = datetime.now()
            batch_results.individual_results = individual_results
            batch_results.completed_tasks = len(individual_results)
            # Use task_success field from validation results instead of just status
            batch_results.successful_tasks = sum(1 for r in individual_results if r.get('task_success') == True)
            batch_results.failed_tasks = batch_results.completed_tasks - batch_results.successful_tasks
            batch_results.summary_stats = self._generate_summary_stats(individual_results)

            # Save and export results
            await self.results_aggregator.save_batch_results(batch_results)
            await self._export_results(batch_results)

            logger.info(f"Batch evaluation completed: {batch_results.success_rate:.1%} success rate, "
                       f"{batch_results.average_score:.2f} average score, "
                       f"{batch_results.field_accuracy:.1%} field accuracy")
            return batch_results

        except Exception as e:
            logger.error(f"Batch evaluation failed: {e}")
            batch_results.end_time = datetime.now()
            batch_results.errors.append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "type": "batch_failure"
            })
            return batch_results
        finally:
            await self._cleanup()
    
    async def _run_sequential_evaluations(self) -> List[Dict[str, Any]]:
        """Run evaluations sequentially."""
        results = []
        
        for html_file in self.batch_config.html_files:
            for task in html_file.tasks:
                try:
                    result = await self._run_single_evaluation(html_file, task)
                    results.append(result)

                    # Use task_success from validation results instead of just status
                    success = result.get('task_success') == True
                    self.progress_tracker.update_progress(
                        f"{html_file.file_id}:{task.task_id}",
                        "completed",
                        success
                    )
                    
                    # Continue on failure if configured
                    if not success and not self.batch_config.batch_settings.continue_on_failure:
                        logger.warning("Stopping batch due to failure (continue_on_failure=False)")
                        break
                        
                except Exception as e:
                    logger.error(f"Task {html_file.file_id}:{task.task_id} failed: {e}")
                    results.append({
                        "html_file_id": html_file.file_id,
                        "task_id": task.task_id,
                        "status": "failed",
                        "error_message": str(e),
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    self.progress_tracker.update_progress(
                        f"{html_file.file_id}:{task.task_id}",
                        "completed",
                        False
                    )
        
        return results
    
    async def _run_parallel_evaluations(self) -> List[Dict[str, Any]]:
        """Run evaluations in parallel."""
        semaphore = asyncio.Semaphore(self.batch_config.batch_settings.max_parallel_workers)
        
        async def run_with_semaphore(html_file: HTMLFileDefinition, task: TaskDefinition):
            async with semaphore:
                return await self._run_single_evaluation(html_file, task)
        
        # Create tasks for all evaluations
        evaluation_tasks = []
        for html_file in self.batch_config.html_files:
            for task in html_file.tasks:
                evaluation_tasks.append(run_with_semaphore(html_file, task))
        
        # Execute all tasks
        results = []
        completed_tasks = 0
        
        for coro in asyncio.as_completed(evaluation_tasks):
            try:
                result = await coro
                results.append(result)

                # Use task_success from validation results instead of just status
                success = result.get('task_success') == True
                completed_tasks += 1

                self.progress_tracker.update_progress(
                    f"{result.get('html_file_id')}:{result.get('task_id')}",
                    "completed",
                    success
                )
                
            except Exception as e:
                logger.error(f"Parallel evaluation task failed: {e}")
                results.append({
                    "status": "failed",
                    "error_message": str(e),
                    "timestamp": datetime.now().isoformat()
                })
                
                completed_tasks += 1
                self.progress_tracker.update_progress("unknown", "completed", False)
        
        return results

    async def _run_single_evaluation(self, html_file: HTMLFileDefinition, task: TaskDefinition) -> Dict[str, Any]:
        """Run a single evaluation for an HTML file and task."""
        task_id = f"{html_file.file_id}:{task.task_id}"
        logger.info(f"Starting evaluation: {task_id}")

        try:
            # Setup evaluation
            controller = self._setup_evaluation_controller(html_file, task)
            html_file_path = self._get_html_file_path(html_file)

            # Execute evaluation
            result = await self._execute_evaluation_with_timeout(controller, task, html_file_path)

            # Process result
            enhanced_result = self._enhance_evaluation_result(result, html_file, task)

            # Save if configured
            if self.batch_config.batch_settings.save_individual_results:
                await self._save_individual_result(task_id, enhanced_result)

            logger.info(f"Completed evaluation: {task_id} - Status: {enhanced_result.get('status')}")
            return enhanced_result

        except asyncio.TimeoutError:
            return self._create_timeout_result(html_file, task)

        except Exception as e:
            return self._create_error_result(html_file, task, e)

    def _setup_evaluation_controller(self, html_file: HTMLFileDefinition, task: TaskDefinition) -> EvaluationController:
        """Setup evaluation controller with proper configuration."""
        eval_config = self._create_evaluation_config(html_file, task)
        controller = EvaluationController(eval_config)
        self.individual_controllers.append(controller)
        return controller

    def _get_html_file_path(self, html_file: HTMLFileDefinition) -> Path:
        """Get absolute path to HTML file."""
        return Path(self.batch_config.html_files_directory) / html_file.file_path

    async def _execute_evaluation_with_timeout(self, controller: EvaluationController,
                                             task: TaskDefinition, html_file_path: Path) -> Dict[str, Any]:
        """Execute evaluation with optional timeout."""
        timeout = task.timeout or self.batch_config.batch_settings.global_timeout

        if timeout:
            return await asyncio.wait_for(
                controller.run_full_evaluation(
                    task_description=task.description,
                    target_url=str(html_file_path.absolute())
                ),
                timeout=timeout
            )
        else:
            return await controller.run_full_evaluation(
                task_description=task.description,
                target_url=str(html_file_path.absolute())
            )

    def _enhance_evaluation_result(self, result: Dict[str, Any], html_file: HTMLFileDefinition,
                                 task: TaskDefinition) -> Dict[str, Any]:
        """Enhance result with batch-specific information."""
        result.update({
            "html_file_id": html_file.file_id,
            "html_file_path": html_file.file_path,
            "task_id": task.task_id,
            "task_description": task.description,
            "success_criteria": task.success_criteria,
            "batch_id": self.batch_id,
            "evaluation_order": len(self.individual_controllers)
        })
        return result

    def _create_timeout_result(self, html_file: HTMLFileDefinition, task: TaskDefinition) -> Dict[str, Any]:
        """Create result for timeout error."""
        task_id = f"{html_file.file_id}:{task.task_id}"
        timeout = task.timeout or self.batch_config.batch_settings.global_timeout
        logger.error(f"Evaluation timed out: {task_id}")

        return {
            "html_file_id": html_file.file_id,
            "task_id": task.task_id,
            "status": "timeout",
            "error_message": f"Evaluation timed out after {timeout} seconds",
            "timestamp": datetime.now().isoformat()
        }

    def _create_error_result(self, html_file: HTMLFileDefinition, task: TaskDefinition,
                           error: Exception) -> Dict[str, Any]:
        """Create result for general error."""
        task_id = f"{html_file.file_id}:{task.task_id}"
        logger.error(f"Evaluation failed: {task_id} - {error}")

        return {
            "html_file_id": html_file.file_id,
            "task_id": task.task_id,
            "status": "failed",
            "error_message": str(error),
            "timestamp": datetime.now().isoformat()
        }

    def _create_evaluation_config(self, html_file: HTMLFileDefinition, task: TaskDefinition) -> Dict[str, Any]:
        """Create evaluation configuration for a specific task."""
        # Start with global configuration
        config = {}

        # Add global browser config
        if self.batch_config.global_browser_config:
            config["browser"] = self.batch_config.global_browser_config.copy()

        # Add global agent config
        if self.batch_config.global_agent_config:
            config["agent"] = self.batch_config.global_agent_config.copy()

        # Override with task-specific agent config
        if task.agent_config:
            if "agent" not in config:
                config["agent"] = {}
            config["agent"].update(task.agent_config)

        # Add evaluation settings
        config["evaluation"] = {
            "max_steps": task.max_steps or 50,
            "save_screenshots": self.batch_config.batch_settings.save_screenshots,
            "screenshot_dir": str(self.output_dir / "screenshots" / f"{html_file.file_id}_{task.task_id}")
        }

        # Add task-specific success criteria
        if task.success_criteria:
            config["success_criteria"] = task.success_criteria

        # Add logging settings
        config["logging"] = {
            "level": "INFO",
            "log_dir": str(self.output_dir / "logs"),
            "log_file": f"{html_file.file_id}_{task.task_id}.log"
        }

        return config

    async def _save_individual_result(self, task_id: str, result: Dict[str, Any]) -> None:
        """Save individual evaluation result."""
        try:
            result_file = self.output_dir / "individual_results" / f"{task_id.replace(':', '_')}.json"
            result_file.parent.mkdir(parents=True, exist_ok=True)

            import json
            with open(result_file, 'w') as f:
                json.dump(result, f, indent=2, default=str)

        except Exception as e:
            logger.error(f"Failed to save individual result for {task_id}: {e}")

    def _generate_summary_stats(self, individual_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary statistics from individual results."""
        if not individual_results:
            return {}

        # Basic stats
        total_duration = sum(r.get('duration_seconds', 0) for r in individual_results)
        avg_duration = total_duration / len(individual_results) if individual_results else 0

        # Status breakdown
        status_counts = {}
        for result in individual_results:
            status = result.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1

        # Success rate and scoring by HTML file
        file_stats = {}
        for result in individual_results:
            file_id = result.get('html_file_id', 'unknown')
            if file_id not in file_stats:
                file_stats[file_id] = {
                    'total': 0,
                    'successful': 0,
                    'total_score': 0.0,
                    'total_fields': 0,
                    'correct_fields': 0
                }

            file_stats[file_id]['total'] += 1
            # Use task_success from validation results instead of just status
            if result.get('task_success') == True:
                file_stats[file_id]['successful'] += 1

            # Add scoring metrics
            file_stats[file_id]['total_score'] += result.get('task_score', 0.0)
            validation_result = result.get('final_validation_result', {})
            file_stats[file_id]['total_fields'] += validation_result.get('total_fields', 0)
            file_stats[file_id]['correct_fields'] += validation_result.get('correct_fields', 0)

        # Calculate success rates and scoring metrics
        for file_id, stats in file_stats.items():
            stats['success_rate'] = stats['successful'] / stats['total'] if stats['total'] > 0 else 0
            stats['average_score'] = stats['total_score'] / stats['total'] if stats['total'] > 0 else 0
            stats['field_accuracy'] = stats['correct_fields'] / stats['total_fields'] if stats['total_fields'] > 0 else 0

        # Calculate overall scoring metrics
        overall_average_score = sum(r.get('task_score', 0.0) for r in individual_results) / len(individual_results) if individual_results else 0
        overall_total_fields = sum(r.get('final_validation_result', {}).get('total_fields', 0) for r in individual_results)
        overall_correct_fields = sum(r.get('final_validation_result', {}).get('correct_fields', 0) for r in individual_results)
        overall_field_accuracy = overall_correct_fields / overall_total_fields if overall_total_fields > 0 else 0

        return {
            "total_evaluations": len(individual_results),
            "total_duration_seconds": total_duration,
            "average_duration_seconds": avg_duration,
            "status_breakdown": status_counts,
            "file_statistics": file_stats,
            # Use task_success from validation results instead of just status
            "overall_success_rate": sum(1 for r in individual_results if r.get('task_success') == True) / len(individual_results) if individual_results else 0,
            "overall_average_score": overall_average_score,
            "overall_total_fields": overall_total_fields,
            "overall_correct_fields": overall_correct_fields,
            "overall_field_accuracy": overall_field_accuracy
        }

    async def _export_results(self, batch_results: BatchResults) -> None:
        """Export results in configured formats."""
        for export_format in self.batch_config.batch_settings.export_formats:
            try:
                await self.results_aggregator.export_results(batch_results, export_format)
            except Exception as e:
                logger.error(f"Failed to export results in {export_format} format: {e}")

    async def _cleanup(self) -> None:
        """Clean up resources."""
        logger.info("Cleaning up batch evaluation resources...")

        # Cleanup individual controllers
        for controller in self.individual_controllers:
            try:
                await controller._cleanup()
            except Exception as e:
                logger.warning(f"Error cleaning up controller: {e}")

        self.individual_controllers.clear()
        logger.info("Batch evaluation cleanup completed")

    def get_progress_info(self) -> Dict[str, Any]:
        """Get current progress information."""
        if not self.progress_tracker:
            return {"status": "not_started"}

        return {
            "batch_id": self.batch_id,
            "total_tasks": self.progress_tracker.total_tasks,
            "completed_tasks": self.progress_tracker.completed_tasks,
            "successful_tasks": self.progress_tracker.successful_tasks,
            "failed_tasks": self.progress_tracker.failed_tasks,
            "progress_percentage": self.progress_tracker.progress_percentage,
            "elapsed_time_seconds": self.progress_tracker.elapsed_time,
            "estimated_remaining_seconds": self.progress_tracker.estimated_remaining_time,
            "current_task": self.progress_tracker.current_task
        }
