#!/usr/bin/env python3
"""
Task Configuration Annotation Tool

A terminal-based tool for annotating HTML components with task configurations.
Allows users to:
1. Browse component.html files in Eval_dataset directory
2. Open files in browser for visual inspection
3. Execute getSelectedValues() function and capture results
4. Input task configuration data
5. Save configurations as JSON files
"""

import os
import json
import asyncio
import webbrowser
from pathlib import Path
from typing import List, Dict, Any, Optional
from playwright.async_api import async_playwright, Browser, Page
import uuid
from datetime import datetime
import requests
import re


class TaskAnnotationTool:
    def __init__(self):
        self.eval_dataset_path = Path("Eval_dataset")
        self.output_directory = Path("annotated_configs")
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.current_component_path: Optional[Path] = None

        # LLM API configuration
        self.base_url = os.getenv("BASE_URL", "https://api.openai.com/v1")
        self.api_url = f"{self.base_url.rstrip('/')}/chat/completions"
        self.api_key = os.getenv("OPENAI_API_KEY", "")

        # Ensure output directory exists
        self.output_directory.mkdir(exist_ok=True)
    
    def scan_components(self) -> List[Dict[str, str]]:
        """Scan Eval_dataset directory for component.html files."""
        components = []
        
        if not self.eval_dataset_path.exists():
            print(f"Error: {self.eval_dataset_path} directory not found!")
            return components
        
        for item in self.eval_dataset_path.iterdir():
            if item.is_dir():
                component_file = item / "component.html"
                if component_file.exists():
                    components.append({
                        "id": item.name,
                        "path": str(component_file),
                        "relative_path": str(component_file)
                    })
        
        return sorted(components, key=lambda x: x["id"])
    
    def display_components(self, components: List[Dict[str, str]]) -> None:
        """Display available components for selection."""
        print("\n" + "="*60)
        print("Available Components for Annotation")
        print("="*60)
        
        for i, component in enumerate(components, 1):
            print(f"{i:3d}. {component['id']}")
        
        print(f"\nTotal: {len(components)} components found")
        print("="*60)
    
    async def open_in_browser(self, component_path: str) -> bool:
        """Open component.html file in browser using Playwright."""
        try:
            if not self.browser:
                playwright = await async_playwright().start()
                self.browser = await playwright.chromium.launch(
                    headless=False,
                    args=[
                        "--window-size=1280,720",
                        "--window-position=100,50"
                    ]
                )
            
            if self.page:
                await self.page.close()
            
            self.page = await self.browser.new_page()
            
            # Convert to absolute file URL
            abs_path = Path(component_path).resolve()
            file_url = f"file://{abs_path}"
            
            await self.page.goto(file_url)
            self.current_component_path = Path(component_path)
            
            print(f"✓ Opened {component_path} in browser")
            return True
            
        except Exception as e:
            print(f"✗ Error opening browser: {e}")
            return False
    
    async def execute_get_selected_values(self) -> Optional[Dict]:
        """Execute getSelectedValues() function in the browser and return results."""
        if not self.page:
            print("✗ No browser page available. Please open a component first.")
            return None

        try:
            print("Executing getSelectedValues()...")
            result = await self.page.evaluate("getSelectedValues()")
            print(f"✓ getSelectedValues() result: {json.dumps(result, indent=2)}")
            return result
        except Exception as e:
            print(f"✗ Error executing getSelectedValues(): {e}")
            print("Note: Make sure the component has the getSelectedValues() function defined.")
            return None

    def delete_component(self, component_path: str) -> bool:
        """Delete the current component.html file."""
        try:
            component_file = Path(component_path)
            if component_file.exists():
                component_file.unlink()
                print(f"✓ Deleted component: {component_path}")
                return True
            else:
                print(f"✗ Component file not found: {component_path}")
                return False
        except Exception as e:
            print(f"✗ Error deleting component: {e}")
            return False

    def load_prompt_messages(self, component_dir: Path) -> Optional[Dict]:
        """Load prompt_messages.json from component directory."""
        try:
            prompt_file = component_dir / "prompt_messages.json"
            if prompt_file.exists():
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                print(f"✗ prompt_messages.json not found in {component_dir}")
                return None
        except Exception as e:
            print(f"✗ Error loading prompt_messages.json: {e}")
            return None

    def call_llm_api(self, system_prompt: str, user_message: str) -> Optional[str]:
        """Call LLM API to generate new component."""
        if not self.api_key:
            print("✗ API key not found. Please set OPENAI_API_KEY environment variable.")
            return None

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            data = {
                "model": "claude-sonnet-4-20250514",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "temperature": 0.7,
            }

            print(f"Calling LLM API: {self.api_url}")
            print(f"Using base URL: {self.base_url}")
            response = requests.post(self.api_url, headers=headers, json=data, timeout=150)

            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                print("✓ LLM API call successful")
                return content
            else:
                print(f"✗ LLM API call failed: {response.status_code}")
                print(f"Response: {response.text[:200]}...")
                return None

        except Exception as e:
            print(f"✗ Error calling LLM API: {e}")
            return None

    def extract_html_from_response(self, llm_response: str) -> Optional[str]:
        """Extract HTML content from LLM response."""
        try:
            # Look for HTML content between ```html and ``` or <!DOCTYPE html> to </html>
            html_patterns = [
                r'```html\s*(.*?)\s*```',
                r'(<!DOCTYPE html>.*?</html>)',
                r'(<html.*?</html>)'
            ]

            for pattern in html_patterns:
                match = re.search(pattern, llm_response, re.DOTALL | re.IGNORECASE)
                if match:
                    html_content = match.group(1).strip()
                    print("✓ HTML content extracted from LLM response")
                    return html_content

            # If no pattern matches, assume the entire response is HTML
            if "<!DOCTYPE html>" in llm_response or "<html" in llm_response:
                print("✓ Using entire LLM response as HTML content")
                return llm_response.strip()

            print("✗ No HTML content found in LLM response")
            return None

        except Exception as e:
            print(f"✗ Error extracting HTML: {e}")
            return None

    def save_new_component(self, component_dir: Path, html_content: str) -> bool:
        """Save new component.html file."""
        try:
            component_file = component_dir / "component.html"
            with open(component_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"✓ New component saved: {component_file}")
            return True
        except Exception as e:
            print(f"✗ Error saving new component: {e}")
            return False

    async def regenerate_component(self, component_path: str) -> bool:
        """Delete current component and regenerate using LLM API."""
        component_file = Path(component_path)
        component_dir = component_file.parent

        print(f"\nRegenerating component: {component_dir.name}")
        print("-" * 50)

        # Load prompt messages
        prompt_data = self.load_prompt_messages(component_dir)
        if not prompt_data:
            return False

        system_prompt = prompt_data.get("system_prompt", "")
        user_message = prompt_data.get("user_message", "")

        if not system_prompt or not user_message:
            print("✗ Invalid prompt_messages.json: missing system_prompt or user_message")
            return False

        # Delete current component
        if not self.delete_component(component_path):
            return False

        # Call LLM API
        llm_response = self.call_llm_api(system_prompt, user_message)
        if not llm_response:
            return False

        # Extract HTML content
        html_content = self.extract_html_from_response(llm_response)
        if not html_content:
            return False

        # Save new component
        if self.save_new_component(component_dir, html_content):
            print("✓ Component regeneration completed successfully!")
            return True
        else:
            return False
    
    async def get_task_input(self) -> Dict[str, Any]:
        """Get task configuration input from user."""
        print("\n" + "-"*50)
        print("Task Configuration Input")
        print("-"*50)
        
        # Get file_id
        default_file_id = self.current_component_path.parent.name if self.current_component_path else ""
        file_id = input(f"File ID [{default_file_id}]: ").strip() or default_file_id
        
        # Get task information
        tasks = []
        task_num = 1
        
        while True:
            print(f"\n--- Task {task_num} ---")
            description = input("Task description (or 'done' to finish): ").strip()
            
            if description.lower() == 'done':
                break
            
            if not description:
                print("Description cannot be empty!")
                continue
            
            criteria_type = input("Select type (1-3): ").strip()
            criteria_map = {"1": "single", "2": "range", "3": "multiple"}
            criteria_type = criteria_map.get(criteria_type, "single")
            
            # Get timeout and max_steps
            timeout = input("Timeout (ms) [750]: ").strip() or "750"
            max_steps = input("Max steps [30]: ").strip() or "30"
            
            # Get difficulty and category
            difficulty = input("Difficulty (easy/medium/hard) [medium]: ").strip() or "medium"
            category = input("Category [component_interaction]: ").strip() or "component_interaction"
            
            # Ask if user wants to use getSelectedValues() result
            print("\n--- Success Criteria Values ---")
            print("Options for filling success criteria values:")
            print("1. Use current getSelectedValues() result (recommended)")
            print("2. Enter values manually")
            print("3. Leave empty (fill later)")

            choice = input("Select option (1-3) [1]: ").strip() or "1"
            values = []

            if choice == "1":
                # Execute getSelectedValues() and use the result
                if self.page:
                    try:
                        print("Executing getSelectedValues()...")
                        result = await self.page.evaluate("getSelectedValues()")
                        print(f"getSelectedValues() result: {json.dumps(result, indent=2)}")

                        if result and "values" in result:
                            values = result["values"]
                            print(f"✓ Using {len(values)} values from getSelectedValues()")
                        else:
                            print("✗ getSelectedValues() returned no valid values")
                            print("Falling back to manual input...")
                            choice = "2"
                    except Exception as e:
                        print(f"✗ Error executing getSelectedValues(): {e}")
                        print("Falling back to manual input...")
                        choice = "2"
                else:
                    print("✗ No browser page available")
                    print("Falling back to manual input...")
                    choice = "2"

            if choice == "2":
                # Manual input option
                print("\nManual value input:")
                print("Enter values as JSON objects (e.g., {\"time\": \"14:30\"}) or simple strings")
                print("Examples:")
                print("  {\"time\": \"14:30\"}")
                print("  {\"date\": \"2024-01-01\", \"time\": \"09:00\"}")
                print("  simple_value")
                print("Enter empty line to finish.")

                while True:
                    value_input = input("Value: ").strip()
                    if not value_input:
                        break
                    try:
                        # Try to parse as JSON for structured values
                        value = json.loads(value_input)
                        values.append(value)
                        print(f"  Added: {value}")
                    except:
                        # If not JSON, treat as simple string value
                        values.append({"value": value_input})
                        print(f"  Added: {{\"value\": \"{value_input}\"}}")

            elif choice == "3":
                print("✓ Success criteria values left empty (can be filled later)")

            print(f"Final values: {values}")

            task = {
                "task_id": f"task_{task_num}",
                "description": description,
                "success_criteria": {
                    "type": criteria_type,
                    "values": values
                },
                "timeout": int(timeout),
                "max_steps": int(max_steps),
                "metadata": {
                    "difficulty": difficulty,
                    "category": category
                }
            }
            
            tasks.append(task)
            task_num += 1
        
        # Get file metadata
        print("\n--- File Metadata ---")
        file_type = input("File type [component]: ").strip() or "component"
        complexity = input("Complexity (low/medium/high) [medium]: ").strip() or "medium"
        estimated_time = input("Estimated time (minutes) [5]: ").strip() or "5"
        
        return {
            "file_id": file_id,
            "file_path": str(self.current_component_path.name) if self.current_component_path else "",
            "tasks": tasks,
            "metadata": {
                "file_type": file_type,
                "complexity": complexity,
                "estimated_time_minutes": int(estimated_time)
            }
        }
    
    def save_configuration(self, config: Dict[str, Any]) -> str:
        """Save task configuration to JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"task_config_{config['file_id']}_{timestamp}.json"
        filepath = self.output_directory / filename
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            print(f"✓ Configuration saved to: {filepath}")
            return str(filepath)
        except Exception as e:
            print(f"✗ Error saving configuration: {e}")
            return ""
    
    async def cleanup(self):
        """Clean up browser resources."""
        if self.page:
            await self.page.close()
        if self.browser:
            await self.browser.close()
    
    def show_menu(self) -> str:
        """Show main menu and get user choice."""
        print("\n" + "="*50)
        print("Task Annotation Tool - Main Menu")
        print("="*50)
        print("1. Open component in browser")
        print("2. Execute getSelectedValues()")
        print("3. Add task configuration")
        print("4. Save current configuration")
        print("5. Delete and regenerate component")
        print("6. Return to component selection")
        print("7. Exit")
        print("-"*50)

        return input("Select option (1-7): ").strip()


async def main():
    """Main function to run the task annotation tool."""
    tool = TaskAnnotationTool()
    current_config = None
    
    try:
        print("Task Configuration Annotation Tool")
        print("=" * 50)
        
        while True:
            # Scan and display components
            components = tool.scan_components()
            if not components:
                print("No component.html files found in Eval_dataset directory!")
                break
            
            tool.display_components(components)
            
            # Component selection
            try:
                choice = input(f"\nSelect component (1-{len(components)}) or 'q' to quit: ").strip()
                if choice.lower() == 'q':
                    break
                
                component_idx = int(choice) - 1
                if component_idx < 0 or component_idx >= len(components):
                    print("Invalid selection!")
                    continue
                
                selected_component = components[component_idx]
                print(f"\nSelected: {selected_component['id']}")
                
                # Component annotation workflow
                while True:
                    choice = tool.show_menu()
                    
                    if choice == '1':
                        await tool.open_in_browser(selected_component['path'])
                    
                    elif choice == '2':
                        result = await tool.execute_get_selected_values()
                        if result:
                            print("You can use this result for task validation criteria.")
                    
                    elif choice == '3':
                        config = await tool.get_task_input()
                        current_config = config
                        print("✓ Task configuration added")
                    
                    elif choice == '4':
                        if current_config:
                            tool.save_configuration(current_config)
                        else:
                            print("No configuration to save. Please add task configuration first.")

                    elif choice == '5':
                        # Delete and regenerate component
                        confirm = input("Are you sure you want to delete and regenerate this component? (y/N): ").strip().lower()
                        if confirm == 'y':
                            success = await tool.regenerate_component(selected_component['path'])
                            if success:
                                print("Component regenerated successfully! You may want to reopen it in browser.")
                                current_config = None  # Reset current config
                            else:
                                print("Component regeneration failed.")
                        else:
                            print("Regeneration cancelled.")

                    elif choice == '6':
                        break  # Return to component selection

                    elif choice == '7':
                        return  # Exit program

                    else:
                        print("Invalid option!")
                
            except ValueError:
                print("Invalid input! Please enter a number.")
            except KeyboardInterrupt:
                print("\nOperation cancelled.")
                break
    
    finally:
        await tool.cleanup()
        print("\nGoodbye!")


if __name__ == "__main__":
    asyncio.run(main())
