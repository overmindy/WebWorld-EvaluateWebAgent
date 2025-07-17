"""Batch Evaluation Controller - Streamlined and optimized."""

import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from loguru import logger

from ..controller.evaluation_controller import EvaluationController
from .batch_config import BatchConfig, HTMLFileDefinition, TaskDefinition, BatchResults
from .batch_aggregator import BatchResultsAggregator
from .checkpoint_manager import TaskExecutionTracker, CheckpointData  # Keep only TaskExecutionTracker for now
from .result_scanner import ResultScanner


class BatchProgressTracker:
    """Tracks batch evaluation progress with enhanced reporting."""

    def __init__(self, total_tasks: int, num_runs_per_task: int = 1):
        """Initialize progress tracker."""
        self.total_tasks = total_tasks
        self.num_runs_per_task = num_runs_per_task
        self.total_runs = total_tasks * num_runs_per_task
        self.completed_tasks = 0
        self.successful_tasks = 0
        self.failed_tasks = 0
        self.completed_runs = 0
        self.successful_runs = 0
        self.failed_runs = 0
        self.current_task = None
        self.start_time = datetime.now()
        self.callbacks: List[Callable] = []
        self.last_progress_time = self.start_time
        self.completed_task_ids = set()  # Track which tasks are already completed

    def add_callback(self, callback: Callable):
        """Add progress callback function."""
        self.callbacks.append(callback)

    def restore_progress(self, checkpoint_data, task_execution_tracker):
        """Restore progress from checkpoint data - simple version."""
        try:
            # Calculate actual progress from task execution tracker (more reliable)
            total_runs = 0
            successful_runs = 0
            failed_runs = 0
            completed_task_ids = set()
            successful_task_ids = set()
            failed_task_ids = set()

            for task_id, results in task_execution_tracker.task_results.items():
                total_runs += len(results)
                task_successful_runs = 0
                task_failed_runs = 0

                for result in results:
                    if result.get('task_success') == True:
                        successful_runs += 1
                        task_successful_runs += 1
                    elif result.get('task_success') == False:
                        failed_runs += 1
                        task_failed_runs += 1

                # Determine if task is completed (has expected number of runs)
                expected_runs = checkpoint_data.num_runs_per_task
                if len(results) >= expected_runs:
                    completed_task_ids.add(task_id)
                    # Task is successful if majority of runs are successful
                    if task_successful_runs > task_failed_runs:
                        successful_task_ids.add(task_id)
                    else:
                        failed_task_ids.add(task_id)

            # Set progress based on actual data
            self.completed_tasks = len(completed_task_ids)
            self.successful_tasks = len(successful_task_ids)
            self.failed_tasks = len(failed_task_ids)
            self.completed_runs = total_runs
            self.successful_runs = successful_runs
            self.failed_runs = failed_runs
            self.completed_task_ids = completed_task_ids  # Remember which tasks are completed

            logger.info(f"Progress restored: {self.completed_tasks}/{self.total_tasks} tasks, {self.completed_runs}/{self.total_runs} runs")
            logger.info(f"Task breakdown: {self.successful_tasks} successful, {self.failed_tasks} failed")

        except Exception as e:
            logger.warning(f"Failed to restore progress: {e}")
            # Keep default values if restoration fails



    def update_progress(self, task_id: str, status: str, success: bool = False, is_run_complete: bool = True):
        """Update progress and notify callbacks."""
        self.current_task = task_id

        if status == "completed" and is_run_complete:
            self.completed_runs += 1
            if success:
                self.successful_runs += 1
            else:
                self.failed_runs += 1

        # Update task-level progress (when all runs for a task are complete)
        if status == "task_completed":
            # Only count if this task hasn't been completed before (avoid double counting)
            if task_id not in self.completed_task_ids:
                self.completed_tasks += 1
                self.completed_task_ids.add(task_id)
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
        """Calculate progress percentage based on completed runs."""
        return (self.completed_runs / self.total_runs) * 100 if self.total_runs > 0 else 0.0

    @property
    def task_progress_percentage(self) -> float:
        """Calculate progress percentage based on completed tasks."""
        return (self.completed_tasks / self.total_tasks) * 100 if self.total_tasks > 0 else 0.0

    @property
    def success_rate(self) -> float:
        """Calculate success rate based on completed runs."""
        return (self.successful_runs / self.completed_runs) * 100 if self.completed_runs > 0 else 0.0

    @property
    def task_success_rate(self) -> float:
        """Calculate success rate based on completed tasks."""
        return (self.successful_tasks / self.completed_tasks) * 100 if self.completed_tasks > 0 else 0.0

    @property
    def elapsed_time(self) -> float:
        """Get elapsed time in seconds."""
        return (datetime.now() - self.start_time).total_seconds()

    @property
    def estimated_remaining_time(self) -> Optional[float]:
        """Estimate remaining time based on current progress."""
        if self.completed_runs == 0:
            return None

        elapsed = self.elapsed_time
        if elapsed <= 0:  # Prevent division by zero
            return None

        rate = self.completed_runs / elapsed  # runs per second
        remaining_runs = self.total_runs - self.completed_runs

        return remaining_runs / rate if rate > 0 else None

    def print_progress_summary(self):
        """Print detailed progress summary to console."""
        current_time = datetime.now()

        # Format elapsed time
        elapsed = self.elapsed_time
        elapsed_str = f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d}"

        # Format estimated remaining time
        eta = self.estimated_remaining_time
        eta_str = f"{int(eta // 60):02d}:{int(eta % 60):02d}" if eta else "N/A"

        logger.success(f"\n📊 Progress Update [{current_time.strftime('%H:%M:%S')}]")
        logger.success("=" * 50)

        if self.num_runs_per_task > 1:
            logger.success(f"Tasks:     {self.completed_tasks:3d}/{self.total_tasks} ({self.task_progress_percentage:5.1f}%)")
            logger.success(f"Runs:      {self.completed_runs:3d}/{self.total_runs} ({self.progress_percentage:5.1f}%)")
            success_rate_str = f"{self.success_rate:5.1f}%" if self.completed_runs > 0 else "N/A"
            logger.success(f"Success:   {self.successful_runs:3d}/{self.completed_runs} ({success_rate_str})")
            logger.success(f"Failed:    {self.failed_runs:3d}/{self.completed_runs}")
        else:
            logger.success(f"Tasks:     {self.completed_tasks:3d}/{self.total_tasks} ({self.progress_percentage:5.1f}%)")
            task_success_rate_str = f"{self.task_success_rate:5.1f}%" if self.completed_tasks > 0 else "N/A"
            logger.success(f"Success:   {self.successful_tasks:3d}/{self.completed_tasks} ({task_success_rate_str})")
            logger.success(f"Failed:    {self.failed_tasks:3d}/{self.completed_tasks}")

        logger.success(f"Elapsed:   {elapsed_str}")
        logger.success(f"ETA:       {eta_str}")
        logger.success("=" * 50)


class BatchEvaluationController:
    """Controller for batch evaluation of multiple HTML files and tasks."""

    def __init__(self, batch_config: BatchConfig, resume_from_checkpoint: bool = False, output_dir_override: Optional[str] = None):
        """Initialize batch evaluation controller."""
        self.batch_config = batch_config
        self.resume_from_checkpoint = resume_from_checkpoint

        # Create deterministic batch_id based on batch_name for resume functionality
        import hashlib
        batch_name_hash = hashlib.md5(batch_config.batch_name.encode()).hexdigest()[:8]
        self.batch_id = f"batch_{batch_config.batch_name.replace(' ', '_').replace('/', '_')}_{batch_name_hash}"

        # Use output directory override if provided, otherwise use config
        base_output_dir = output_dir_override or batch_config.output_directory
        self.output_dir = Path(base_output_dir) / self.batch_id

        # Initialize result scanner for simple resume functionality
        self.result_scanner = ResultScanner(self.output_dir)

        # Initialize task execution tracker for multiple runs
        self.num_runs_per_task = batch_config.batch_settings.num_runs_per_task
        self.task_execution_tracker = TaskExecutionTracker(self.num_runs_per_task)

        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.progress_tracker: Optional[BatchProgressTracker] = None
        self.results_aggregator = BatchResultsAggregator(self.output_dir)
        self.individual_controllers: List[EvaluationController] = []
        self.total_tasks = sum(len(html_file.tasks) for html_file in batch_config.html_files)
        self._cancelled = False

        logger.info(f"Batch controller initialized: {self.batch_id} ({self.total_tasks} tasks, {self.num_runs_per_task} runs per task)")

    def add_progress_callback(self, callback: Callable):
        """Add progress tracking callback."""
        if self.progress_tracker:
            self.progress_tracker.add_callback(callback)



    # Legacy checkpoint methods removed - using result file scanning instead
    
    async def run_batch_evaluation(self, checkpoint_data: Optional[CheckpointData] = None) -> BatchResults:
        """Run complete batch evaluation with result file scanning for resume."""
        logger.info(f"Starting batch evaluation: {self.batch_config.batch_name}")

        # Log checkpoint information if provided (for compatibility)
        if checkpoint_data:
            logger.info(f"Checkpoint data provided: {checkpoint_data.checkpoint_timestamp}")

        # Scan existing results for resume functionality
        completed_tasks = self.result_scanner.scan_completed_tasks()

        # Clean up old checkpoint files
        self.result_scanner.clean_old_checkpoints()

        # Get resume summary
        if completed_tasks:
            resume_summary = self.result_scanner.get_resume_summary(
                completed_tasks, self.total_tasks, self.num_runs_per_task
            )
            logger.info(f"Resuming batch evaluation:")
            logger.info(f"  Completed runs: {resume_summary['completed_runs']}/{resume_summary['total_runs']}")
            logger.info(f"  Successful runs: {resume_summary['successful_runs']}")
            logger.info(f"  Failed runs: {resume_summary['failed_runs']}")
            logger.info(f"  Progress: {resume_summary['completion_percentage']:.1f}%")

        # Initialize progress tracker with multiple runs support
        self.progress_tracker = BatchProgressTracker(self.total_tasks, self.num_runs_per_task)

        batch_results = BatchResults(
            batch_id=self.batch_id,
            batch_name=self.batch_config.batch_name,
            start_time=datetime.now(),
            total_tasks=self.total_tasks
        )

        # Restore previous results if resuming
        if completed_tasks:
            batch_results.individual_results = list(completed_tasks.values())
            batch_results.completed_tasks = len(completed_tasks)
            batch_results.successful_tasks = sum(1 for r in completed_tasks.values() if r.get('task_success') == True)
            batch_results.failed_tasks = batch_results.completed_tasks - batch_results.successful_tasks

        try:
            # Execute evaluations
            if self.batch_config.batch_settings.parallel_execution:
                individual_results = await self._run_parallel_evaluations_with_multiple_runs()
            else:
                individual_results = await self._run_sequential_evaluations_with_multiple_runs()

            # Aggregate results from multiple runs
            aggregated_results = self._aggregate_multiple_run_results(individual_results)

            # Update results
            batch_results.end_time = datetime.now()
            batch_results.individual_results = aggregated_results
            batch_results.completed_tasks = len(aggregated_results)
            # Use task_success field from validation results instead of just status
            batch_results.successful_tasks = sum(1 for r in aggregated_results if r.get('task_success') == True)
            batch_results.failed_tasks = batch_results.completed_tasks - batch_results.successful_tasks
            batch_results.summary_stats = self._generate_summary_stats(aggregated_results)

            # Save and export results
            await self.results_aggregator.save_batch_results(batch_results)
            await self._export_results(batch_results)

            # Clean up checkpoint on successful completion
            # if self.batch_config.batch_settings.enable_checkpoints:
            #     self.checkpoint_manager.delete_checkpoint()

            logger.info(f"Batch evaluation completed: {batch_results.success_rate:.1%} success rate")
            return batch_results

        except KeyboardInterrupt:
            logger.info("Batch evaluation interrupted by user")
            batch_results.end_time = datetime.now()

            # Legacy checkpoint saving disabled - results are saved individually
            logger.debug("Checkpoint saving disabled - using individual result files for resume")
            return batch_results
        except Exception as e:
            logger.error(f"Batch evaluation failed: {e}")
            batch_results.end_time = datetime.now()
            batch_results.errors.append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "type": "batch_failure"
            })

            # Try to save partial results even if batch failed
            try:
                # Get any completed results
                if hasattr(self, 'task_execution_tracker'):
                    partial_results = []
                    for _, results in self.task_execution_tracker.task_results.items():
                        if results:
                            # Use the latest result for each task
                            latest_result = results[-1].copy()
                            latest_result.update({
                                'total_runs': len(results),
                                'partial_batch': True
                            })
                            partial_results.append(latest_result)

                    batch_results.individual_results = partial_results
                    batch_results.completed_tasks = len(partial_results)
                    batch_results.successful_tasks = sum(1 for r in partial_results if r.get('task_success') == True)
                    batch_results.failed_tasks = batch_results.completed_tasks - batch_results.successful_tasks

                    logger.info(f"Saved partial results: {batch_results.completed_tasks} tasks completed")
            except Exception as save_error:
                logger.warning(f"Failed to save partial results: {save_error}")

            return batch_results
        finally:
            # Ensure cleanup happens even on interrupt
            try:
                await self._cleanup()
            except Exception as cleanup_error:
                logger.warning(f"Error during final cleanup: {cleanup_error}")
    
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

    async def _run_single_evaluation(self, html_file: HTMLFileDefinition, task: TaskDefinition, run_number: int = 1) -> Dict[str, Any]:
        """Run a single evaluation for an HTML file and task."""
        task_id = f"{html_file.file_id}:{task.task_id}"
        logger.info(f"Starting evaluation: {task_id} (Run {run_number})")

        try:
            # Setup evaluation
            controller = self._setup_evaluation_controller(html_file, task)
            html_file_path = self._get_html_file_path(html_file)

            # Prepare run information for unique session ID generation
            run_info = {
                'task_id': task_id,
                'run_number': run_number
            }

            # Execute evaluation
            result = await self._execute_evaluation_with_timeout(controller, task, html_file_path, run_info)

            # Process result
            enhanced_result = self._enhance_evaluation_result(result, html_file, task)

        except asyncio.TimeoutError:
            enhanced_result = self._create_timeout_result(html_file, task)
            logger.error(f"Evaluation timed out: {task_id}")

        except Exception as e:
            enhanced_result = self._create_error_result(html_file, task, e)
            logger.error(f"Evaluation failed: {task_id} - {e}")

        # Always save result (success, timeout, or error) if configured
        if self.batch_config.batch_settings.save_individual_results:
            await self._save_individual_result(task_id, enhanced_result, run_number)

        logger.info(f"Completed evaluation: {task_id} - Status: {enhanced_result.get('status')}")
        return enhanced_result

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
                                             task: TaskDefinition, html_file_path: Path,
                                             run_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute evaluation with optional timeout and cancellation support."""
        timeout = task.timeout or self.batch_config.batch_settings.global_timeout

        try:
            if timeout:
                return await asyncio.wait_for(
                    controller.run_full_evaluation(
                        task_description=task.description,
                        target_url=str(html_file_path.absolute()),
                        run_info=run_info
                    ),
                    timeout=timeout
                )
            else:
                return await controller.run_full_evaluation(
                    task_description=task.description,
                    target_url=str(html_file_path.absolute()),
                    run_info=run_info
                )
        except asyncio.CancelledError:
            logger.info("Evaluation cancelled by user interrupt")
            # Return a cancelled result
            return {
                "status": "cancelled",
                "task_success": False,
                "error_message": "Evaluation cancelled by user",
                "timestamp": datetime.now().isoformat()
            }

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
            "log_file": f"{html_file.file_id}_{task.task_id}.log",
            "save_individual_session_results": False  # Disable duplicate session result saving
        }

        return config

    async def _save_individual_result(self, task_id: str, result: Dict[str, Any], run_number: int = 1) -> None:
        """Save individual evaluation result with run number in filename."""
        try:
            # Include run number in filename to prevent overwrites
            base_filename = task_id.replace(':', '_')
            if self.num_runs_per_task > 1:
                filename = f"{base_filename}_run{run_number}.json"
            else:
                filename = f"{base_filename}.json"

            result_file = self.output_dir / "individual_results" / filename
            result_file.parent.mkdir(parents=True, exist_ok=True)

            # Add run information to result data
            result['run_number'] = run_number
            result['total_runs'] = self.num_runs_per_task

            import json
            with open(result_file, 'w') as f:
                json.dump(result, f, indent=2, default=str)

            logger.debug(f"Saved individual result: {filename}")

        except Exception as e:
            logger.error(f"Failed to save individual result for {task_id} run {run_number}: {e}")

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

    async def _run_sequential_evaluations_with_multiple_runs(self) -> List[Dict[str, Any]]:
        """Run evaluations sequentially with support for multiple runs per task."""
        all_results = []

        for html_file in self.batch_config.html_files:
            for task in html_file.tasks:
                task_id = f"{html_file.file_id}:{task.task_id}"

                # Run the task multiple times
                for run_number in range(1, self.num_runs_per_task + 1):
                    # Check for global cancellation
                    if hasattr(self, '_cancelled') and self._cancelled:
                        logger.info(f"Batch evaluation cancelled, stopping at {task_id} run {run_number}")
                        return all_results

                    # Skip if this run was already completed (result file scanning)
                    completed_tasks = self.result_scanner.scan_completed_tasks()
                    if self.result_scanner.should_skip_task(task_id, run_number, completed_tasks, self.num_runs_per_task):
                        logger.debug(f"Skipping {task_id} run {run_number} - already completed")
                        continue

                    try:
                        logger.info(f"Running {task_id} - Run {run_number}/{self.num_runs_per_task}")
                        result = await self._run_single_evaluation(html_file, task, run_number)

                        # Run information is already added in _save_individual_result

                        all_results.append(result)
                        self.task_execution_tracker.record_task_execution(task_id, result)

                        # Update progress for this run
                        success = result.get('task_success') == True
                        self.progress_tracker.update_progress(task_id, "completed", success, is_run_complete=True)

                        # Print progress summary after each run
                        self.progress_tracker.print_progress_summary()

                        # Legacy checkpoint saving disabled - results are saved individually

                        # Continue on failure if configured
                        if not success and not self.batch_config.batch_settings.continue_on_failure:
                            logger.warning("Stopping batch due to failure (continue_on_failure=False)")
                            return all_results

                    except Exception as e:
                        logger.error(f"Task {task_id} run {run_number} failed: {e}")
                        error_result = {
                            "html_file_id": html_file.file_id,
                            "task_id": task.task_id,
                            "run_number": run_number,
                            "total_runs": self.num_runs_per_task,
                            "status": "failed",
                            "task_success": False,
                            "error_message": str(e),
                            "timestamp": datetime.now().isoformat()
                        }
                        all_results.append(error_result)
                        self.task_execution_tracker.record_task_execution(task_id, error_result)

                        self.progress_tracker.update_progress(task_id, "completed", False, is_run_complete=True)
                        self.progress_tracker.print_progress_summary()

                # Mark task as completed after all runs
                try:
                    task_success_rate = self._calculate_task_success_rate(task_id)
                    self.progress_tracker.update_progress(task_id, "task_completed", task_success_rate > 0.5)
                except Exception as e:
                    logger.warning(f"Error calculating task success rate for {task_id}: {e}")
                    # Default to failed if we can't calculate success rate
                    self.progress_tracker.update_progress(task_id, "task_completed", False)

        return all_results

    async def _run_parallel_evaluations_with_multiple_runs(self) -> List[Dict[str, Any]]:
        """Run evaluations in parallel with support for multiple runs per task."""
        semaphore = asyncio.Semaphore(self.batch_config.batch_settings.max_parallel_workers)

        async def run_single_with_semaphore(html_file: HTMLFileDefinition, task: TaskDefinition, run_number: int):
            async with semaphore:
                result = await self._run_single_evaluation(html_file, task, run_number)
                # Run information is already added in _save_individual_result
                return result

        # Create tasks for all evaluations (including multiple runs)
        evaluation_tasks = []
        for html_file in self.batch_config.html_files:
            for task in html_file.tasks:
                task_id = f"{html_file.file_id}:{task.task_id}"

                for run_number in range(1, self.num_runs_per_task + 1):
                    # Skip if this run was already completed (result file scanning)
                    completed_tasks = self.result_scanner.scan_completed_tasks()
                    if self.result_scanner.should_skip_task(task_id, run_number, completed_tasks, self.num_runs_per_task):
                        logger.debug(f"Skipping {task_id} run {run_number} - already completed")
                        continue

                    evaluation_tasks.append(run_single_with_semaphore(html_file, task, run_number))

        # Execute all tasks
        all_results = []
        completed_runs = 0

        for coro in asyncio.as_completed(evaluation_tasks):
            try:
                result = await coro
                all_results.append(result)

                task_id = f"{result.get('html_file_id')}:{result.get('task_id')}"
                self.task_execution_tracker.record_task_execution(task_id, result)

                success = result.get('task_success') == True
                completed_runs += 1

                self.progress_tracker.update_progress(task_id, "completed", success, is_run_complete=True)

                # Print progress summary periodically
                if completed_runs % max(1, len(evaluation_tasks) // 10) == 0:
                    self.progress_tracker.print_progress_summary()

            except Exception as e:
                logger.error(f"Parallel evaluation task failed: {e}")
                error_result = {
                    "status": "failed",
                    "task_success": False,
                    "error_message": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                all_results.append(error_result)

                completed_runs += 1
                self.progress_tracker.update_progress("unknown", "completed", False, is_run_complete=True)

        return all_results

    def _aggregate_multiple_run_results(self, all_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Aggregate results from multiple runs into per-task results."""
        if self.num_runs_per_task == 1:
            return all_results

        # Group results by task
        task_results = {}
        for result in all_results:
            task_key = f"{result.get('html_file_id')}:{result.get('task_id')}"
            if task_key not in task_results:
                task_results[task_key] = []
            task_results[task_key].append(result)

        # Aggregate each task's results
        aggregated_results = []
        for task_key, results in task_results.items():
            try:
                aggregated_result = self.task_execution_tracker.get_aggregated_task_result(task_key)
                if aggregated_result:
                    aggregated_results.append(aggregated_result)
                else:
                    logger.warning(f"No aggregated result for task {task_key}, using latest result")
                    # Use the latest result if aggregation fails
                    if results:
                        latest_result = results[-1].copy()
                        latest_result.update({
                            'total_runs': len(results),
                            'successful_runs': sum(1 for r in results if r.get('task_success') == True),
                            'failed_runs': len(results) - sum(1 for r in results if r.get('task_success') == True),
                            'success_rate_across_runs': sum(1 for r in results if r.get('task_success') == True) / len(results),
                            'all_run_results': results
                        })
                        aggregated_results.append(latest_result)
            except Exception as e:
                logger.error(f"Error aggregating results for task {task_key}: {e}")
                # Create a fallback result
                if results:
                    fallback_result = results[-1].copy()
                    fallback_result.update({
                        'aggregation_error': str(e),
                        'total_runs': len(results),
                        'all_run_results': results
                    })
                    aggregated_results.append(fallback_result)

        return aggregated_results

    def _calculate_task_success_rate(self, task_id: str) -> float:
        """Calculate success rate for a specific task across all runs."""
        try:
            results = self.task_execution_tracker.get_task_results(task_id)
            if not results:
                logger.warning(f"No results found for task {task_id}")
                return 0.0

            successful_runs = sum(1 for r in results if r.get('task_success') == True)
            success_rate = successful_runs / len(results)
            logger.debug(f"Task {task_id} success rate: {success_rate:.2f} ({successful_runs}/{len(results)})")
            return success_rate
        except Exception as e:
            logger.error(f"Error calculating success rate for task {task_id}: {e}")
            return 0.0

    # Legacy checkpoint save method removed - using individual result files instead
