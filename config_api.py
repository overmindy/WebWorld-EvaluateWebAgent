#!/usr/bin/env python3
"""
API Configuration for Task Annotation Tool

Simple configuration script to set up API keys for component regeneration.
"""

import os
from pathlib import Path


def setup_api_config():
    """Setup API configuration for component regeneration."""
    print("API Configuration")
    print("=" * 40)
    print("To use the component regeneration feature, you need to configure:")
    print("1. API Base URL (default: https://api.openai.com/v1)")
    print("2. API Key")
    print()

    current_base_url = os.getenv("BASE_URL", "https://api.openai.com/v1")
    current_key = os.getenv("OPENAI_API_KEY", "")

    print(f"Current base URL: {current_base_url}")
    if current_key:
        print(f"Current API key: {current_key[:8]}...{current_key[-4:] if len(current_key) > 12 else current_key}")
    else:
        print("No API key currently set.")

    print()
    print("Options:")
    print("1. Configure for this session only")
    print("2. Configure permanently (save to .env file)")
    print("3. Skip configuration")

    choice = input("Select option (1-3): ").strip()

    if choice in ['1', '2']:
        # Get base URL
        base_url = input(f"Enter API base URL [{current_base_url}]: ").strip()
        if not base_url:
            base_url = current_base_url

        # Get API key
        api_key = input("Enter your API key: ").strip()
        if not api_key:
            print("No API key provided.")
            return

        # Set for session
        os.environ["BASE_URL"] = base_url
        os.environ["OPENAI_API_KEY"] = api_key

        if choice == '1':
            print("✓ API configuration set for this session.")

        elif choice == '2':
            # Save to .env file
            env_file = Path(".env")
            env_content = []

            # Read existing .env file if it exists
            if env_file.exists():
                with open(env_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            if not line.startswith("BASE_URL=") and not line.startswith("OPENAI_API_KEY="):
                                env_content.append(line)

            # Add new configuration
            env_content.append(f"BASE_URL={base_url}")
            env_content.append(f"OPENAI_API_KEY={api_key}")

            # Write to .env file
            with open(env_file, "w") as f:
                f.write("\n".join(env_content) + "\n")

            print(f"✓ API configuration saved to {env_file}")
            print("Note: You may need to restart your terminal to load the new configuration.")

    elif choice == '3':
        print("API configuration skipped. Component regeneration will not be available.")

    else:
        print("Invalid option.")


def load_env_file():
    """Load environment variables from .env file if it exists."""
    env_file = Path(".env")
    if env_file.exists():
        try:
            with open(env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ[key.strip()] = value.strip()
            print("✓ Loaded environment variables from .env file")
        except Exception as e:
            print(f"Error loading .env file: {e}")


if __name__ == "__main__":
    load_env_file()
    setup_api_config()
