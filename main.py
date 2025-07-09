"""Agent Evaluation Framework - Main Entry Point."""

import asyncio
import argparse
import sys
import time
from pathlib import Path

from agent_eval import EvaluationController
from agent_eval.batch import BatchEvaluationController, load_batch_config, create_sample_batch_config
from agent_eval.agent.human_agent import HumanAgent
from config.default_config import DEFAULT_CONFIG


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


async def run_batch_evaluation(config_file: str, progress: bool = True):
    """Run a batch evaluation from configuration file."""
    try:
        print(f"🚀 Starting batch evaluation...")
        print(f"Configuration: {config_file}")
        print("-" * 50)

        batch_config = load_batch_config(config_file)

        print(f"Batch: {batch_config.batch_name}")
        print(f"HTML files: {len(batch_config.html_files)}")
        total_tasks = sum(len(hf.tasks) for hf in batch_config.html_files)
        print(f"Total tasks: {total_tasks}")
        print(f"Parallel execution: {batch_config.batch_settings.parallel_execution}")
        print("-" * 50)

        controller = BatchEvaluationController(batch_config)

        # Add progress callback if requested
        if progress:
            def progress_callback(tracker):
                print(f"\rProgress: {tracker.progress_percentage:5.1f}% | "
                      f"Completed: {tracker.completed_tasks:2d}/{tracker.total_tasks} | "
                      f"Success: {tracker.successful_tasks:2d} | "
                      f"Failed: {tracker.failed_tasks:2d}", end="", flush=True)
                if tracker.completed_tasks == tracker.total_tasks:
                    print()

            controller.add_progress_callback(progress_callback)

        start_time = time.time()
        results = await controller.run_batch_evaluation()
        end_time = time.time()

        # Display results
        print(f"\n📊 Batch Evaluation Results:")
        print("=" * 40)
        print(f"Batch ID: {results.batch_id}")
        print(f"Duration: {end_time - start_time:.2f} seconds")
        print(f"Total Tasks: {results.total_tasks}")
        print(f"Completed: {results.completed_tasks}")
        print(f"Successful: {results.successful_tasks}")
        print(f"Failed: {results.failed_tasks}")
        print(f"Success Rate: {results.success_rate:.1%}")

        output_dir = Path(batch_config.output_directory) / results.batch_id
        print(f"\n💾 Results saved to: {output_dir}")

        export_formats = batch_config.batch_settings.export_formats
        if export_formats:
            print(f"📄 Exported formats: {', '.join(export_formats)}")

        return results

    except Exception as e:
        print(f"❌ Batch evaluation failed: {e}")
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
  python main.py "Click the search button"
  python main.py "Fill out the contact form" --url https://example.com
  python main.py "Navigate to products page" --headless

  # Batch evaluation
  python main.py --batch config/batch_config.json
  python main.py --batch config/batch_config.json --no-progress

  # Create sample configuration
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

    # Configuration creation
    config_parser = subparsers.add_parser('create-config', help='Create sample configuration')
    config_parser.add_argument(
        "output",
        help="Output file path for sample configuration"
    )

    # Global arguments
    parser.add_argument(
        "--batch",
        help="Run batch evaluation with configuration file"
    )
    parser.add_argument(
        "--create-config",
        help="Create sample batch configuration file"
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress updates (for batch mode)"
    )



    parser.add_argument(
        "--version",
        action="version",
        version="Agent Evaluation Framework 0.1.0"
    )

    args = parser.parse_args()

    # Handle different modes
    try:
        # Create configuration mode
        if args.create_config:
            success = create_sample_config(args.create_config)
            sys.exit(0 if success else 1)

        # Batch evaluation mode
        elif args.batch:
            results = asyncio.run(run_batch_evaluation(
                config_file=args.batch,
                progress=not args.no_progress
            ))

            if results and results.success_rate > 0:
                sys.exit(0)
            else:
                sys.exit(1)

        # Subparser modes
        elif args.mode == 'batch':
            results = asyncio.run(run_batch_evaluation(
                config_file=args.config,
                progress=not args.no_progress
            ))

            if results and results.success_rate > 0:
                sys.exit(0)
            else:
                sys.exit(1)

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
