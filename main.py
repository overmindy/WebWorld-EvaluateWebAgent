"""Agent Evaluation Framework - Main Entry Point."""

import asyncio
import argparse
import signal
import sys
import time
from pathlib import Path

from agent_eval import EvaluationController
from agent_eval.batch import BatchEvaluationController, load_batch_config, create_sample_batch_config, CheckpointManager, CheckpointData
from config.default_config import DEFAULT_CONFIG


# Global variable to track if we're shutting down
_shutdown_requested = False


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    global _shutdown_requested
    if not _shutdown_requested:
        _shutdown_requested = True
        print("\n⏹️  Shutdown requested. Cleaning up...")
        print("   Please wait for cleanup to complete...")
        print("   Press Ctrl+C again to force exit")
    else:
        print("\n💥 Force exit requested!")
        sys.exit(1)


async def run_evaluation(task: str, url: str = None, headless: bool = False, agent_type: str = "human"):
    """Run a single evaluation."""
    config = DEFAULT_CONFIG.copy()
    if headless:
        config["browser"]["headless"] = True

    # Set agent type
    config["agent"]["type"] = agent_type

    controller = EvaluationController(config)

    try:
        print(f"🚀 Starting evaluation...")
        print(f"Task: {task}")
        if url:
            print(f"URL: {url}")
        print(f"Headless: {headless}")
        print("-" * 50)

        results = await controller.run_full_evaluation(
            task_description=task,
            target_url=url
        )

        print("\n📊 Results:")
        print(f"Status: {results.get('status', 'Unknown')}")
        print(f"Steps: {results.get('total_steps', 0)}")
        print(f"Success Rate: {results.get('success_rate', 0):.1%}")
        print(f"Duration: {results.get('duration_seconds', 0):.1f}s")

        if results.get('error_message'):
            print(f"Error: {results['error_message']}")

        return results

    except Exception as e:
        print(f"❌ Evaluation failed: {e}")
        return None


async def run_batch_evaluation(config_file: str, progress: bool = True, resume_checkpoint: str = None,
                              num_runs: int = None, list_checkpoints: bool = False, output_dir: str = None):
    """Run a batch evaluation from configuration file with checkpoint and multiple runs support."""
    try:
        # Handle checkpoint listing
        if list_checkpoints:
            return await list_available_checkpoints(config_file)

        print(f"🚀 Starting batch evaluation...")
        print(f"Configuration: {config_file}")
        print("-" * 50)

        batch_config = load_batch_config(config_file)

        # Override num_runs_per_task if specified
        if num_runs is not None:
            batch_config.batch_settings.num_runs_per_task = num_runs

        print(f"Batch: {batch_config.batch_name}")
        print(f"HTML files: {len(batch_config.html_files)}")
        total_tasks = sum(len(hf.tasks) for hf in batch_config.html_files)
        print(f"Total tasks: {total_tasks}")
        print(f"Runs per task: {batch_config.batch_settings.num_runs_per_task}")
        print(f"Total runs: {total_tasks * batch_config.batch_settings.num_runs_per_task}")
        print(f"Parallel execution: {batch_config.batch_settings.parallel_execution}")
        print(f"Checkpoints enabled: {batch_config.batch_settings.enable_checkpoints}")
        print("-" * 50)

        # Handle checkpoint resumption
        checkpoint_data = None
        if resume_checkpoint:
            checkpoint_data = await load_checkpoint_data(resume_checkpoint, batch_config)
            if checkpoint_data:
                print(f"📂 Resuming from checkpoint: {checkpoint_data.checkpoint_timestamp}")
                print(f"   Previous progress: {checkpoint_data.completed_tasks}/{checkpoint_data.total_tasks} tasks")
                print("-" * 50)

        controller = BatchEvaluationController(batch_config, resume_from_checkpoint=bool(checkpoint_data), output_dir_override=output_dir)

        # Add enhanced progress callback if requested
        if progress:
            def progress_callback(tracker):
                # Use the built-in progress summary for enhanced reporting
                pass  # The tracker will print its own summary

            controller.add_progress_callback(progress_callback)

        start_time = time.time()

        # Setup signal handler for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)

        try:
            results = await controller.run_batch_evaluation(checkpoint_data)
        except KeyboardInterrupt:
            print("\n⏹️  Evaluation interrupted by user")
            # The controller should have saved checkpoint already
            results = None

        end_time = time.time()

        # Display final results
        if results is not None:
            if _shutdown_requested:
                print(f"\n⏹️  Batch Evaluation Interrupted!")
            else:
                print(f"\n🎉 Batch Evaluation Completed!")
            print("=" * 50)
            print(f"Batch ID: {results.batch_id}")
            print(f"Duration: {end_time - start_time:.2f} seconds")
            print(f"Total Tasks: {results.total_tasks}")
            print(f"Completed: {results.completed_tasks}")
            print(f"Successful: {results.successful_tasks}")
            print(f"Failed: {results.failed_tasks}")
            print(f"Success Rate: {results.success_rate:.1%}")

            if batch_config.batch_settings.num_runs_per_task > 1:
                total_runs = results.total_tasks * batch_config.batch_settings.num_runs_per_task
                successful_runs = sum(r.get('successful_runs', 0) for r in results.individual_results)
                print(f"Total Runs: {total_runs}")
                print(f"Successful Runs: {successful_runs}")
                print(f"Run Success Rate: {successful_runs / total_runs * 100:.1f}%")

            # Use the actual output directory from the controller
            actual_output_dir = output_dir or batch_config.output_directory
            final_output_dir = Path(actual_output_dir) / results.batch_id
            print(f"\n💾 Results saved to: {final_output_dir}")

            export_formats = batch_config.batch_settings.export_formats
            if export_formats:
                print(f"📄 Exported formats: {', '.join(export_formats)}")

            if _shutdown_requested and batch_config.batch_settings.enable_checkpoints:
                print(f"\n📂 Progress saved to checkpoint for resumption")
        else:
            print(f"\n⏹️  Evaluation was interrupted")
            print(f"Duration: {end_time - start_time:.2f} seconds")
            if batch_config.batch_settings.enable_checkpoints:
                print(f"📂 Progress should be saved to checkpoint for resumption")

        return results

    except Exception as e:
        print(f"❌ Batch evaluation failed: {e}")
        return None


async def list_available_checkpoints(config_file: str):
    """List available checkpoint files."""
    try:
        batch_config = load_batch_config(config_file)
        output_dir = Path(batch_config.output_directory)

        checkpoint_files = CheckpointManager.find_checkpoint_files(output_dir)

        if not checkpoint_files:
            print("📂 No checkpoint files found.")
            return None

        print("📂 Available Checkpoints:")
        print("=" * 60)

        for checkpoint_file in checkpoint_files:
            info = CheckpointManager.get_checkpoint_info(checkpoint_file)
            if info:
                print(f"File: {checkpoint_file.name}")
                print(f"  Batch: {info['batch_name']}")
                print(f"  Progress: {info['progress']}")
                print(f"  Success Rate: {info['success_rate']}")
                print(f"  Timestamp: {info['checkpoint_timestamp']}")
                print("-" * 40)

        return checkpoint_files

    except Exception as e:
        print(f"❌ Failed to list checkpoints: {e}")
        return None


async def load_checkpoint_data(checkpoint_path: str, batch_config) -> CheckpointData:
    """Load checkpoint data from file path."""
    try:
        checkpoint_file = Path(checkpoint_path)

        # If it's just a filename, look in the batch output directory
        if not checkpoint_file.is_absolute():
            output_dir = Path(batch_config.output_directory)
            checkpoint_file = output_dir / checkpoint_path

        if not checkpoint_file.exists():
            print(f"❌ Checkpoint file not found: {checkpoint_file}")
            return None

        # Create a temporary checkpoint manager to load the data
        temp_manager = CheckpointManager(checkpoint_file.parent, "temp")
        temp_manager.checkpoint_file = checkpoint_file

        return temp_manager.load_checkpoint()

    except Exception as e:
        print(f"❌ Failed to load checkpoint: {e}")
        return None


def create_sample_config(output_file: str):
    """Create a sample batch configuration file."""
    try:
        output_path = Path(output_file)
        create_sample_batch_config(output_path)
        print(f"✅ Sample configuration created: {output_path}")
        print("📝 Edit this file to customize your batch evaluation")
        return True
    except Exception as e:
        print(f"❌ Failed to create sample configuration: {e}")
        return False


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Agent Evaluation Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single task evaluation
  python main.py single "Click the search button"
  python main.py single "Fill out the contact form" --url https://example.com
  python main.py single "Navigate to products page" --headless --agent terminal

  # Batch evaluation
  python main.py batch config/batch_config.json
  python main.py batch config/batch_config.json --no-progress
  python main.py batch config/batch_config.json --num-runs 3
  python main.py batch config/batch_config.json --resume checkpoint.json
  python main.py batch config/batch_config.json --output-dir custom_results

  # Create sample configuration
  python main.py create-config sample_batch.json

  # Legacy support (deprecated)
  python main.py --batch config/batch_config.json
  python main.py --create-config sample_batch.json
        """
    )

    # Create subparsers for different modes
    subparsers = parser.add_subparsers(dest='mode', help='Evaluation mode')

    # Single task evaluation (default)
    single_parser = subparsers.add_parser('single', help='Single task evaluation (default)')
    single_parser.add_argument(
        "task",
        help="Task description for the agent to perform"
    )
    single_parser.add_argument(
        "--url",
        help="Target URL to navigate to (optional)"
    )
    single_parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode"
    )
    single_parser.add_argument(
        "--agent",
        choices=["human", "terminal", "uitars"],
        default="human",
        help="Agent type to use (default: human)"
    )

    # Batch evaluation
    batch_parser = subparsers.add_parser('batch', help='Batch evaluation mode')
    batch_parser.add_argument(
        "config",
        help="Path to batch configuration file (JSON or YAML)"
    )
    batch_parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress updates"
    )
    batch_parser.add_argument(
        "--resume",
        help="Resume from checkpoint file (path to checkpoint file)"
    )
    batch_parser.add_argument(
        "--num-runs",
        type=int,
        help="Number of runs per task (overrides config file setting)"
    )
    batch_parser.add_argument(
        "--list-checkpoints",
        action="store_true",
        help="List available checkpoint files and exit"
    )
    batch_parser.add_argument(
        "--output-dir",
        help="Override output directory (for resume functionality)"
    )

    # Configuration creation
    config_parser = subparsers.add_parser('create-config', help='Create sample configuration')
    config_parser.add_argument(
        "output",
        help="Output file path for sample configuration"
    )

    # Global arguments (legacy support for backward compatibility)
    parser.add_argument(
        "--batch",
        help="Run batch evaluation with configuration file (legacy)"
    )
    parser.add_argument(
        "--create-config",
        help="Create sample batch configuration file (legacy)"
    )



    parser.add_argument(
        "--version",
        action="version",
        version="Agent Evaluation Framework 0.1.0"
    )

    args = parser.parse_args()

    # Handle different modes
    try:
        # Legacy global argument support
        if args.create_config:
            success = create_sample_config(args.create_config)
            sys.exit(0 if success else 1)
        elif args.batch:
            # Legacy batch mode - redirect to subparser logic
            results = asyncio.run(run_batch_evaluation(
                config_file=args.batch,
                progress=True,  # Default to progress for legacy mode
                resume_checkpoint=None,
                num_runs=None,
                list_checkpoints=False,
                output_dir=None
            ))
            sys.exit(0 if results and (isinstance(results, list) or results.success_rate > 0) else 1)

        # Subparser modes (primary interface)
        elif args.mode == 'batch':
            results = asyncio.run(run_batch_evaluation(
                config_file=args.config,
                progress=not args.no_progress,
                resume_checkpoint=getattr(args, 'resume', None),
                num_runs=getattr(args, 'num_runs', None),
                list_checkpoints=getattr(args, 'list_checkpoints', False),
                output_dir=getattr(args, 'output_dir', None)
            ))
            sys.exit(0 if results and (isinstance(results, list) or results.success_rate > 0) else 1)

        elif args.mode == 'create-config':
            success = create_sample_config(args.output)
            sys.exit(0 if success else 1)

        # Single task evaluation
        elif args.mode == 'single':
            task = args.task
            url = args.url
            headless = args.headless
            agent_type = args.agent

            if not task:
                print("❌ Task description is required for single evaluation")
                parser.print_help()
                sys.exit(1)

            results = asyncio.run(run_evaluation(
                task=task,
                url=url,
                headless=headless,
                agent_type=agent_type
            ))

            if results and results.get('status') == 'completed':
                sys.exit(0)
            else:
                sys.exit(1)

        else:
            # No mode specified, show help
            parser.print_help()
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⏹️  Evaluation interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
