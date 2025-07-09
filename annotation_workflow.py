#!/usr/bin/env python3
"""
Complete Annotation Workflow

A comprehensive workflow tool that combines task annotation and configuration consolidation.
Provides a streamlined process for annotating components and creating batch configurations.
"""

import asyncio
import os
import sys
from pathlib import Path

# Import our custom tools
from task_annotation_tool import TaskAnnotationTool
from config_consolidator import ConfigConsolidator


class AnnotationWorkflow:
    def __init__(self):
        self.annotation_tool = TaskAnnotationTool()
        self.consolidator = ConfigConsolidator()
    
    def show_main_menu(self) -> str:
        """Show the main workflow menu."""
        print("\n" + "="*60)
        print("Task Configuration Annotation Workflow")
        print("="*60)
        print("1. Annotate individual components")
        print("2. Consolidate configurations into batch")
        print("3. View annotation statistics")
        print("4. Clean up annotation files")
        print("5. Exit")
        print("-"*60)
        
        return input("Select option (1-5): ").strip()
    
    async def run_annotation_tool(self):
        """Run the annotation tool."""
        print("\nStarting annotation tool...")
        print("Use this to annotate individual components with task configurations.")
        print("Press Ctrl+C to return to main menu.\n")
        
        try:
            # Import and run the main function from task_annotation_tool
            from task_annotation_tool import main as annotation_main
            await annotation_main()
        except KeyboardInterrupt:
            print("\nReturning to main menu...")
        except Exception as e:
            print(f"Error running annotation tool: {e}")
    
    def run_consolidation(self):
        """Run the configuration consolidation."""
        print("\nStarting configuration consolidation...")
        print("This will combine all individual configurations into a batch configuration.\n")
        
        try:
            output_path = self.consolidator.consolidate()
            if output_path:
                print(f"\n✓ Batch configuration created: {output_path}")
            else:
                print("\n✗ Consolidation failed or no configurations found.")
        except Exception as e:
            print(f"Error during consolidation: {e}")
    
    def show_statistics(self):
        """Show annotation statistics."""
        print("\n" + "-"*50)
        print("Annotation Statistics")
        print("-"*50)
        
        # Count components
        components = self.annotation_tool.scan_components()
        print(f"Total components available: {len(components)}")
        
        # Count annotated configurations
        annotated_configs = list(self.annotation_tool.output_directory.glob("task_config_*.json"))
        print(f"Annotated configurations: {len(annotated_configs)}")
        
        if annotated_configs:
            print("\nRecent annotations:")
            for config_file in sorted(annotated_configs, key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
                print(f"  - {config_file.name}")
        
        # Count consolidated configurations
        consolidated_configs = list(self.consolidator.output_dir.glob("batch_config_*.json"))
        print(f"Consolidated batch configs: {len(consolidated_configs)}")
        
        if consolidated_configs:
            print("\nRecent batch configurations:")
            for config_file in sorted(consolidated_configs, key=lambda x: x.stat().st_mtime, reverse=True)[:3]:
                print(f"  - {config_file.name}")
        
        # Calculate progress
        if components:
            progress = (len(annotated_configs) / len(components)) * 100
            print(f"\nAnnotation progress: {progress:.1f}% ({len(annotated_configs)}/{len(components)})")
        
        print("-"*50)
    
    def cleanup_files(self):
        """Clean up annotation files."""
        print("\n" + "-"*50)
        print("File Cleanup")
        print("-"*50)
        print("1. Delete all individual annotations")
        print("2. Delete all batch configurations")
        print("3. Delete everything")
        print("4. Cancel")
        
        choice = input("Select cleanup option (1-4): ").strip()
        
        if choice == '1':
            self._delete_files(self.annotation_tool.output_directory, "task_config_*.json", "individual annotations")
        elif choice == '2':
            self._delete_files(self.consolidator.output_dir, "batch_config_*.json", "batch configurations")
        elif choice == '3':
            self._delete_files(self.annotation_tool.output_directory, "*.json", "all annotation files")
            self._delete_files(self.consolidator.output_dir, "*.json", "all batch configuration files")
        elif choice == '4':
            print("Cleanup cancelled.")
        else:
            print("Invalid option.")
    
    def _delete_files(self, directory: Path, pattern: str, description: str):
        """Delete files matching pattern in directory."""
        files = list(directory.glob(pattern))
        
        if not files:
            print(f"No {description} found.")
            return
        
        print(f"Found {len(files)} {description}:")
        for f in files[:5]:  # Show first 5
            print(f"  - {f.name}")
        if len(files) > 5:
            print(f"  ... and {len(files) - 5} more")
        
        confirm = input(f"\nDelete {len(files)} {description}? (y/N): ").strip().lower()
        
        if confirm == 'y':
            deleted = 0
            for f in files:
                try:
                    f.unlink()
                    deleted += 1
                except Exception as e:
                    print(f"Error deleting {f.name}: {e}")
            
            print(f"✓ Deleted {deleted} files.")
        else:
            print("Deletion cancelled.")
    
    async def run(self):
        """Run the main workflow."""
        print("Task Configuration Annotation Workflow")
        print("="*60)
        print("This tool helps you annotate HTML components and create batch configurations.")
        print("Follow the workflow: Annotate → Consolidate → Use in evaluation framework")
        
        try:
            while True:
                choice = self.show_main_menu()
                
                if choice == '1':
                    await self.run_annotation_tool()
                elif choice == '2':
                    self.run_consolidation()
                elif choice == '3':
                    self.show_statistics()
                elif choice == '4':
                    self.cleanup_files()
                elif choice == '5':
                    break
                else:
                    print("Invalid option! Please select 1-5.")
        
        except KeyboardInterrupt:
            print("\nWorkflow interrupted.")
        
        finally:
            await self.annotation_tool.cleanup()
            print("\nGoodbye!")


async def main():
    """Main entry point."""
    workflow = AnnotationWorkflow()
    await workflow.run()


if __name__ == "__main__":
    asyncio.run(main())
