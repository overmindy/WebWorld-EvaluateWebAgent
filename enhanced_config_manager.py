#!/usr/bin/env python3
"""
Enhanced Configuration Manager

Tool to manage batch evaluation configurations with enhanced features:
- Upgrade existing configurations with checkpoint/resume functionality
- Create templates with multiple runs per task
- Manage enhanced batch evaluation settings
"""

import argparse
import sys
from pathlib import Path
from config_consolidator import ConfigConsolidator


def upgrade_existing_config(args):
    """Upgrade an existing configuration file with enhanced features."""
    print("🔧 Upgrading Existing Configuration")
    print("=" * 50)
    
    if not Path(args.config_file).exists():
        print(f"❌ Configuration file not found: {args.config_file}")
        return False
    
    # Create consolidator with enhanced settings
    consolidator = ConfigConsolidator(
        enable_checkpoints=args.enable_checkpoints,
        checkpoint_interval=args.checkpoint_interval,
        num_runs_per_task=args.num_runs,
        parallel_execution=args.parallel,
        max_parallel_workers=args.workers
    )
    
    # Upgrade the configuration
    upgraded_path = consolidator.upgrade_existing_config(
        config_file_path=args.config_file,
        enable_checkpoints=args.enable_checkpoints,
        checkpoint_interval=args.checkpoint_interval,
        num_runs_per_task=args.num_runs,
        parallel_execution=args.parallel,
        max_parallel_workers=args.workers
    )
    
    if upgraded_path:
        print(f"\n✅ Configuration successfully upgraded!")
        print(f"📁 New file: {upgraded_path}")
        print(f"💾 Backup: {Path(args.config_file).with_suffix('.backup.json')}")
        return True
    else:
        print("❌ Failed to upgrade configuration")
        return False


def create_enhanced_template(args):
    """Create a new enhanced configuration template."""
    print("📋 Creating Enhanced Configuration Template")
    print("=" * 50)
    
    # Create consolidator with enhanced settings
    consolidator = ConfigConsolidator(
        enable_checkpoints=args.enable_checkpoints,
        checkpoint_interval=args.checkpoint_interval,
        num_runs_per_task=args.num_runs,
        parallel_execution=args.parallel,
        max_parallel_workers=args.workers
    )
    
    # Create template
    template_path = consolidator.create_enhanced_template(args.template_name)
    
    if template_path:
        print(f"\n✅ Enhanced template created successfully!")
        print(f"📁 Template file: {template_path}")
        print("\n📝 Next steps:")
        print("1. Edit the template to add your specific HTML files and tasks")
        print("2. Use with: python main.py batch <template_file>")
        print("3. For multiple runs: python main.py batch <template_file> --num-runs 3")
        print("4. For checkpoints: python main.py batch <template_file> --resume <checkpoint_file>")
        return True
    else:
        print("❌ Failed to create template")
        return False


def consolidate_with_enhanced_features(args):
    """Consolidate individual configs with enhanced features."""
    print("🔄 Consolidating Configurations with Enhanced Features")
    print("=" * 50)
    
    # Create consolidator with enhanced settings
    consolidator = ConfigConsolidator(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        enable_checkpoints=args.enable_checkpoints,
        checkpoint_interval=args.checkpoint_interval,
        num_runs_per_task=args.num_runs,
        parallel_execution=args.parallel,
        max_parallel_workers=args.workers
    )
    
    # Run consolidation
    output_path = consolidator.consolidate(args.batch_name, args.description)
    
    if output_path:
        print(f"\n✅ Consolidation completed successfully!")
        print(f"📁 Batch configuration: {output_path}")
        print("\n🚀 Enhanced features included:")
        print(f"  • Checkpoints: {args.enable_checkpoints}")
        print(f"  • Checkpoint interval: {args.checkpoint_interval}")
        print(f"  • Runs per task: {args.num_runs}")
        print(f"  • Parallel execution: {args.parallel}")
        print(f"  • Max workers: {args.workers}")
        return True
    else:
        print("❌ Consolidation failed")
        return False


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Enhanced Configuration Manager for Agent Evaluation Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upgrade existing configuration with enhanced features
  python enhanced_config_manager.py upgrade config.json --num-runs 3 --enable-checkpoints

  # Create enhanced template
  python enhanced_config_manager.py template --template-name my_enhanced_batch --num-runs 5

  # Consolidate with enhanced features
  python enhanced_config_manager.py consolidate --num-runs 2 --parallel --workers 3

  # Upgrade with specific settings
  python enhanced_config_manager.py upgrade config.json --checkpoint-interval 5 --num-runs 10
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Upgrade command
    upgrade_parser = subparsers.add_parser('upgrade', help='Upgrade existing configuration')
    upgrade_parser.add_argument('config_file', help='Path to existing configuration file')
    
    # Template command
    template_parser = subparsers.add_parser('template', help='Create enhanced template')
    template_parser.add_argument('--template-name', default='enhanced_template',
                                help='Name for the template (default: enhanced_template)')
    
    # Consolidate command
    consolidate_parser = subparsers.add_parser('consolidate', help='Consolidate with enhanced features')
    consolidate_parser.add_argument('--input-dir', default='annotated_configs',
                                   help='Input directory (default: annotated_configs)')
    consolidate_parser.add_argument('--output-dir', default='consolidated_configs',
                                   help='Output directory (default: consolidated_configs)')
    consolidate_parser.add_argument('--batch-name', help='Custom batch name')
    consolidate_parser.add_argument('--description', help='Custom batch description')
    
    # Enhanced feature arguments (common to all commands)
    for subparser in [upgrade_parser, template_parser, consolidate_parser]:
        subparser.add_argument('--enable-checkpoints', action='store_true', default=True,
                              help='Enable checkpoint functionality (default: True)')
        subparser.add_argument('--disable-checkpoints', action='store_true',
                              help='Disable checkpoint functionality')
        subparser.add_argument('--checkpoint-interval', type=int, default=1,
                              help='Checkpoint save interval (default: 1)')
        subparser.add_argument('--num-runs', type=int, default=1,
                              help='Number of runs per task (default: 1)')
        subparser.add_argument('--parallel', action='store_true',
                              help='Enable parallel execution')
        subparser.add_argument('--workers', type=int, default=1,
                              help='Max parallel workers (default: 1)')
    
    args = parser.parse_args()
    
    # Handle disable-checkpoints flag
    if hasattr(args, 'disable_checkpoints') and args.disable_checkpoints:
        args.enable_checkpoints = False
    
    # Validate arguments
    if args.checkpoint_interval < 1:
        print("❌ Checkpoint interval must be >= 1")
        return 1
    
    if args.num_runs < 1:
        print("❌ Number of runs per task must be >= 1")
        return 1
    
    if args.workers < 1:
        print("❌ Number of workers must be >= 1")
        return 1
    
    # Execute command
    try:
        if args.command == 'upgrade':
            success = upgrade_existing_config(args)
        elif args.command == 'template':
            success = create_enhanced_template(args)
        elif args.command == 'consolidate':
            success = consolidate_with_enhanced_features(args)
        else:
            parser.print_help()
            return 1
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n⏹️  Operation interrupted by user")
        return 130
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
