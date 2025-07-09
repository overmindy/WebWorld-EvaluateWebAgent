#!/usr/bin/env python3
"""
Quick Start Script for Task Annotation Tool

Simple launcher that checks dependencies and starts the annotation workflow.
"""

import sys
import subprocess
import asyncio
import os
from pathlib import Path


def check_dependencies():
    """Check if required dependencies are installed."""
    print("Checking dependencies...")

    try:
        import playwright
        print("✓ Playwright installed")
    except ImportError:
        print("✗ Playwright not found. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright"])
        print("✓ Playwright installed")

    try:
        import requests
        print("✓ Requests installed")
    except ImportError:
        print("✗ Requests not found. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "requests"])
        print("✓ Requests installed")
    
    # Check if chromium is installed
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        print("✓ Chromium browser available")
    except Exception:
        print("✗ Chromium browser not found. Installing...")
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])
        print("✓ Chromium browser installed")


def check_directories():
    """Check if required directories exist."""
    print("\nChecking directories...")
    
    eval_dataset = Path("Eval_dataset")
    if eval_dataset.exists():
        components = list(eval_dataset.glob("*/component.html"))
        print(f"✓ Eval_dataset found with {len(components)} components")
    else:
        print("✗ Eval_dataset directory not found!")
        print("Please ensure the Eval_dataset directory exists in the current directory.")
        return False
    
    # Create output directories if they don't exist
    Path("annotated_configs").mkdir(exist_ok=True)
    Path("consolidated_configs").mkdir(exist_ok=True)
    print("✓ Output directories ready")
    
    return True


async def main():
    """Main function."""
    print("Task Configuration Annotation Tool - Quick Start")
    print("="*60)

    # Load environment variables
    try:
        from config_api import load_env_file
        load_env_file()
    except ImportError:
        pass

    # Check dependencies
    try:
        check_dependencies()
    except Exception as e:
        print(f"Error checking dependencies: {e}")
        print("Please install dependencies manually:")
        print("  pip install playwright requests")
        print("  playwright install chromium")
        return

    # Check directories
    if not check_directories():
        return

    # Check API configuration for regeneration feature
    base_url = os.getenv("BASE_URL", "https://api.openai.com/v1")
    api_key = os.getenv("OPENAI_API_KEY", "")

    print(f"API Base URL: {base_url}")
    if api_key:
        print("✓ API key found - component regeneration available")
    else:
        print("⚠ No API key found - component regeneration will be disabled")
        print("  Run 'python config_api.py' to set up API configuration")

    print("\n✓ All checks passed! Starting annotation workflow...")
    print("="*60)

    # Start the annotation workflow
    try:
        from annotation_workflow import AnnotationWorkflow
        workflow = AnnotationWorkflow()
        await workflow.run()
    except ImportError:
        print("Error: annotation_workflow.py not found!")
        print("Please ensure all tool files are in the current directory.")
    except Exception as e:
        print(f"Error starting workflow: {e}")


if __name__ == "__main__":
    asyncio.run(main())
