#!/usr/bin/env python3
"""
Configuration Consolidator

Tool to consolidate individual task configuration files into a complete batch evaluation configuration.
Reads all JSON files from annotated_configs directory and creates a unified configuration file.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime


class ConfigConsolidator:
    def __init__(self, input_dir: str = "annotated_configs", output_dir: str = "consolidated_configs",
                 enable_checkpoints: bool = True, checkpoint_interval: int = 1,
                 num_runs_per_task: int = 1, parallel_execution: bool = False,
                 max_parallel_workers: int = 1):
        """
        Initialize ConfigConsolidator with enhanced batch evaluation settings.

        Args:
            input_dir: Directory containing individual task configurations
            output_dir: Directory to save consolidated batch configurations
            enable_checkpoints: Enable automatic checkpoint saving
            checkpoint_interval: Save checkpoint after N completed tasks
            num_runs_per_task: Number of times to run each task
            parallel_execution: Enable parallel task execution
            max_parallel_workers: Maximum number of parallel workers
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Enhanced batch evaluation settings
        self.enable_checkpoints = enable_checkpoints
        self.checkpoint_interval = checkpoint_interval
        self.num_runs_per_task = num_runs_per_task
        self.parallel_execution = parallel_execution
        self.max_parallel_workers = max_parallel_workers
    
    def load_individual_configs(self) -> List[Dict[str, Any]]:
        """Load all individual configuration files."""
        configs = []
        
        if not self.input_dir.exists():
            print(f"Input directory {self.input_dir} does not exist!")
            return configs
        
        for config_file in self.input_dir.glob("task_config_*.json"):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    configs.append(config)
                    print(f"✓ Loaded: {config_file.name}")
            except Exception as e:
                print(f"✗ Error loading {config_file.name}: {e}")
        
        return configs
    
    def create_batch_config(self, individual_configs: List[Dict[str, Any]], 
                          batch_name: str = None, description: str = None) -> Dict[str, Any]:
        """Create a complete batch configuration from individual configs."""
        
        if not batch_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            batch_name = f"annotated_batch_{timestamp}"
        
        if not description:
            description = f"Batch evaluation configuration created from {len(individual_configs)} annotated components"
        
        # Create the batch configuration structure
        batch_config = {
            "batch_name": batch_name,
            "description": description,
            "html_files_directory": "Eval_dataset",
            "output_directory": f"{batch_name}_results",
            "html_files": [],
            "batch_settings": {
                "parallel_execution": self.parallel_execution,
                "max_parallel_workers": self.max_parallel_workers,
                "continue_on_failure": True,
                "global_timeout": 1200,
                "retry_failed_tasks": False,
                "max_retries": 0,
                "save_screenshots": True,
                "save_individual_results": True,
                "export_formats": ["json", "csv"],
                # Enhanced batch evaluation features
                "enable_checkpoints": self.enable_checkpoints,
                "checkpoint_interval": self.checkpoint_interval,
                "num_runs_per_task": self.num_runs_per_task
            },
            "global_agent_config": {
                "type": "uitars",
                "show_screenshot_info": True,
                "show_help_on_start": True,
                "single_action_mode": True
            },
            "global_browser_config": {
                "type": "chromium",
                "headless": False,
                "viewport": {
                    "width": 1280,
                    "height": 720
                },
                "window_position": {
                    "x": 100,
                    "y": 50
                },
                "device_scale_factor": 1.5,
                "slow_mo": 500,
                "mobile_emulation": {
                    "deviceName": "Pixel 7"
                }
            }
        }
        
        # Add individual configurations to html_files
        for config in individual_configs:
            # Find the actual component path
            component_path = self.find_component_path(config["file_id"])
            
            html_file_config = {
                "file_id": config["file_id"],
                "file_path": component_path,
                "tasks": config["tasks"],
                "metadata": config["metadata"]
            }
            
            batch_config["html_files"].append(html_file_config)
        
        return batch_config
    
    def find_component_path(self, file_id: str) -> str:
        """Find the relative path to component.html for a given file_id."""
        # Look for the component in Eval_dataset
        eval_dataset = Path("Eval_dataset")
        component_dir = eval_dataset / file_id
        
        if component_dir.exists() and (component_dir / "component.html").exists():
            return f"{file_id}/component.html"
        else:
            # Fallback to just the filename
            return "component.html"
    
    def save_batch_config(self, batch_config: Dict[str, Any], filename: str = None) -> str:
        """Save the consolidated batch configuration."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"batch_config_{timestamp}.json"
        
        output_path = self.output_dir / filename
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(batch_config, f, indent=2, ensure_ascii=False)
            
            print(f"✓ Batch configuration saved to: {output_path}")
            return str(output_path)
        except Exception as e:
            print(f"✗ Error saving batch configuration: {e}")
            return ""
    
    def generate_summary(self, batch_config: Dict[str, Any]) -> None:
        """Generate a summary of the batch configuration."""
        print("\n" + "="*60)
        print("Batch Configuration Summary")
        print("="*60)
        print(f"Batch Name: {batch_config['batch_name']}")
        print(f"Description: {batch_config['description']}")
        print(f"Total Components: {len(batch_config['html_files'])}")
        
        # Count tasks by difficulty and category
        difficulties = {}
        categories = {}
        total_tasks = 0
        
        for html_file in batch_config['html_files']:
            for task in html_file['tasks']:
                total_tasks += 1
                
                difficulty = task['metadata'].get('difficulty', 'unknown')
                category = task['metadata'].get('category', 'unknown')
                
                difficulties[difficulty] = difficulties.get(difficulty, 0) + 1
                categories[category] = categories.get(category, 0) + 1
        
        print(f"Total Tasks: {total_tasks}")
        print(f"Difficulties: {dict(difficulties)}")
        print(f"Categories: {dict(categories)}")
        print("="*60)
    
    def consolidate(self, batch_name: str = None, description: str = None) -> str:
        """Main consolidation process."""
        print("Configuration Consolidator")
        print("="*50)
        
        # Load individual configurations
        individual_configs = self.load_individual_configs()
        
        if not individual_configs:
            print("No configuration files found to consolidate!")
            return ""
        
        print(f"\nLoaded {len(individual_configs)} configuration files")
        
        # Create batch configuration
        batch_config = self.create_batch_config(individual_configs, batch_name, description)
        
        # Generate summary
        self.generate_summary(batch_config)
        
        # Save batch configuration
        output_path = self.save_batch_config(batch_config)
        
        return output_path

    def upgrade_existing_config(self, config_file_path: str,
                               enable_checkpoints: bool = None,
                               checkpoint_interval: int = None,
                               num_runs_per_task: int = None,
                               parallel_execution: bool = None,
                               max_parallel_workers: int = None) -> str:
        """
        Upgrade an existing batch configuration file with enhanced features.

        Args:
            config_file_path: Path to existing configuration file
            enable_checkpoints: Enable checkpoint functionality (None = use current setting)
            checkpoint_interval: Checkpoint save interval (None = use current setting)
            num_runs_per_task: Number of runs per task (None = use current setting)
            parallel_execution: Enable parallel execution (None = use current setting)
            max_parallel_workers: Max parallel workers (None = use current setting)

        Returns:
            Path to upgraded configuration file
        """
        try:
            # Load existing configuration
            with open(config_file_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            print(f"📂 Loading existing configuration: {config_file_path}")

            # Update batch_settings with enhanced features
            batch_settings = config.get('batch_settings', {})

            # Add enhanced features with provided values or defaults
            enhanced_settings = {
                'enable_checkpoints': enable_checkpoints if enable_checkpoints is not None else self.enable_checkpoints,
                'checkpoint_interval': checkpoint_interval if checkpoint_interval is not None else self.checkpoint_interval,
                'num_runs_per_task': num_runs_per_task if num_runs_per_task is not None else self.num_runs_per_task
            }

            # Update parallel execution settings if provided
            if parallel_execution is not None:
                batch_settings['parallel_execution'] = parallel_execution
            if max_parallel_workers is not None:
                batch_settings['max_parallel_workers'] = max_parallel_workers

            # Add enhanced settings
            batch_settings.update(enhanced_settings)
            config['batch_settings'] = batch_settings

            # Create backup of original file
            backup_path = Path(config_file_path).with_suffix('.backup.json')
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            print(f"💾 Backup created: {backup_path}")

            # Save upgraded configuration
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            upgraded_filename = f"upgraded_{Path(config_file_path).stem}_{timestamp}.json"
            upgraded_path = self.output_dir / upgraded_filename

            with open(upgraded_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            print(f"✅ Upgraded configuration saved: {upgraded_path}")

            # Show what was added
            print("\n🔧 Enhanced Features Added:")
            for key, value in enhanced_settings.items():
                print(f"  • {key}: {value}")

            return str(upgraded_path)

        except Exception as e:
            print(f"❌ Error upgrading configuration: {e}")
            return ""

    def create_enhanced_template(self, template_name: str = "enhanced_template") -> str:
        """
        Create a template configuration file with all enhanced features enabled.

        Args:
            template_name: Name for the template file

        Returns:
            Path to created template file
        """
        template_config = {
            "batch_name": f"{template_name}_batch",
            "description": "Enhanced batch evaluation template with checkpoint, multiple runs, and progress reporting",
            "html_files_directory": "test_html",
            "output_directory": f"{template_name}_results",
            "html_files": [
                {
                    "file_id": "simple_form",
                    "file_path": "simple_form.html",
                    "tasks": [
                        {
                            "task_id": "task_1",
                            "description": "Example task description",
                            "success_criteria": {
                                "type": "single",
                                "values": [{"example": "value"}]
                            },
                            "timeout": 750,
                            "max_steps": 30,
                            "metadata": {
                                "difficulty": "medium",
                                "category": "component_interaction"
                            }
                        }
                    ],
                    "metadata": {
                        "file_type": "component",
                        "complexity": "medium",
                        "estimated_time_minutes": 5
                    }
                }
            ],
            "batch_settings": {
                "parallel_execution": self.parallel_execution,
                "max_parallel_workers": self.max_parallel_workers,
                "continue_on_failure": True,
                "global_timeout": 1200,
                "retry_failed_tasks": False,
                "max_retries": 0,
                "save_screenshots": True,
                "save_individual_results": True,
                "export_formats": ["json", "csv"],
                # Enhanced batch evaluation features
                "enable_checkpoints": self.enable_checkpoints,
                "checkpoint_interval": self.checkpoint_interval,
                "num_runs_per_task": self.num_runs_per_task
            },
            "global_agent_config": {
                "type": "uitars",
                "show_screenshot_info": True,
                "show_help_on_start": True,
                "single_action_mode": True
            },
            "global_browser_config": {
                "type": "chromium",
                "headless": False,
                "viewport": {
                    "width": 1280,
                    "height": 720
                },
                "window_position": {
                    "x": 100,
                    "y": 50
                },
                "device_scale_factor": 1.5,
                "slow_mo": 500,
                "mobile_emulation": {
                    "deviceName": "Pixel 7"
                }
            }
        }

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        template_filename = f"{template_name}_{timestamp}.json"
        template_path = self.output_dir / template_filename

        try:
            with open(template_path, 'w', encoding='utf-8') as f:
                json.dump(template_config, f, indent=2, ensure_ascii=False)

            print(f"📋 Enhanced template created: {template_path}")
            print("\n🚀 Template Features:")
            print(f"  • Checkpoints: {self.enable_checkpoints}")
            print(f"  • Checkpoint interval: {self.checkpoint_interval}")
            print(f"  • Runs per task: {self.num_runs_per_task}")
            print(f"  • Parallel execution: {self.parallel_execution}")
            print(f"  • Max workers: {self.max_parallel_workers}")

            return str(template_path)

        except Exception as e:
            print(f"❌ Error creating template: {e}")
            return ""


def main():
    """Main function for interactive consolidation."""
    consolidator = ConfigConsolidator()
    
    print("Configuration Consolidator")
    print("="*50)
    print("This tool will consolidate all individual task configurations")
    print("from the annotated_configs directory into a batch configuration.")
    print()
    
    # Get user input for batch details
    batch_name = input("Enter batch name (or press Enter for auto-generated): ").strip()
    if not batch_name:
        batch_name = None
    
    description = input("Enter batch description (or press Enter for auto-generated): ").strip()
    if not description:
        description = None
    
    # Perform consolidation
    output_path = consolidator.consolidate(batch_name, description)
    
    if output_path:
        print(f"\n✓ Consolidation complete!")
        print(f"Output file: {output_path}")
        print("\nYou can now use this configuration file with your evaluation framework.")
    else:
        print("\n✗ Consolidation failed!")


if __name__ == "__main__":
    main()
