"""
Terminal Agent Implementation

An interactive agent that allows manual control through terminal input.
Users can input action commands directly via the terminal interface.
"""

from typing import Dict, Any, Optional, List, Tuple
from PIL import Image
from loguru import logger

from .base_agent import BaseAgent, AgentResponse, ActionCommand


class TerminalAgent(BaseAgent):
    """
    Interactive terminal agent for manual action input.
    
    This agent prompts the user in the terminal to input action commands,
    coordinates, and parameters, then returns appropriate ActionCommand objects.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize terminal agent."""
        super().__init__(config)
        self.agent_type = "terminal"
        self.task_count = 0

        # Configuration options
        self.show_screenshot_info = self.config.get("show_screenshot_info", True)
        self.show_help_on_start = self.config.get("show_help_on_start", True)
        self.single_action_mode = self.config.get("single_action_mode", True)

        # State tracking for single action mode
        self.current_action_prompt = True  # Whether to prompt for next action
        self.user_indicated_completion = False

        logger.info("TerminalAgent initialized for interactive control")
    
    async def predict(self, screenshot: Image.Image, task_description: str) -> AgentResponse:
        """
        Present task to user and collect action commands via terminal input.
        
        Args:
            screenshot: PIL Image of current page state
            task_description: Text description of the task to perform
            
        Returns:
            AgentResponse: Response with user-inputted actions
        """
        self.task_count += 1
        logger.info(f"Starting terminal interaction for task {self.task_count}")
        
        try:
            # Display task information
            await self._display_task_info(screenshot, task_description)
            
            # Collect single action from user (maintaining proper separation of concerns)
            action, task_complete = await self._collect_single_action()
            actions = [action] if action else []

            # Generate response
            return AgentResponse(
                actions=actions,
                reasoning=f"User provided {len(actions)} action(s) via terminal input",
                task_complete=task_complete,
                needs_more_info=False
            )
            
        except KeyboardInterrupt:
            logger.info("Terminal interaction interrupted by user")
            return AgentResponse(
                actions=[],
                reasoning="User interrupted terminal interaction",
                task_complete=False,
                needs_more_info=False,
                error_message="User interrupted"
            )
        except Exception as e:
            logger.error(f"Terminal agent error: {e}")
            return AgentResponse(
                actions=[],
                error_message=f"Terminal agent error: {str(e)}",
                task_complete=False,
                needs_more_info=False
            )
    
    async def _display_task_info(self, screenshot: Image.Image, task_description: str) -> None:
        """Display task information and screenshot details to user."""
        print("\n" + "="*70)
        print("🖥️  TERMINAL AGENT - INTERACTIVE CONTROL")
        print("="*70)
        print(f"📋 Task #{self.task_count}")
        print(f"📝 Description: {task_description}")
        
        if self.show_screenshot_info and screenshot:
            print(f"📸 Screenshot: {screenshot.size[0]}x{screenshot.size[1]} pixels")
        
        print("="*70)
        
        if self.show_help_on_start and self.task_count == 1:
            self._display_help()
    
    def _display_help(self) -> None:
        """Display help information about available commands."""
        print("\n📖 AVAILABLE ACTIONS:")
        print("  click <x> <y>           - Click at coordinates (x, y)")
        print("  type <text>             - Type text at current focus")
        print("  scroll <direction> <amount> - Scroll (up/down/left/right)")
        print("  drag <x1> <y1> <x2> <y2> - Drag from (x1,y1) to (x2,y2)")
        print("  wait <seconds>          - Wait for specified seconds")
        print("  navigate <url>          - Navigate to URL")
        print("  done                    - Mark task as complete")
        print("  help                    - Show this help")
        print("  quit                    - Exit without completing task")
        print("\n💡 TIPS:")
        print("  - Enter ONE action at a time for immediate execution")
        print("  - Watch the browser window to see results after each action")
        print("  - Use 'done' when you think the task is complete")
        print("  - Coordinates are in pixels from top-left corner")
        print("  - Use browser dev tools (F12) to find coordinates")
        print("  - Each action executes through proper evaluation flow")
        print("-"*70)

    async def _collect_single_action(self) -> Tuple[Optional[ActionCommand], bool]:
        """
        Collect a single action from user input.

        This maintains proper separation of concerns by only collecting the action,
        not executing it. The EvaluationController will execute the action through
        the normal flow, providing real-time feedback.

        Returns:
            Tuple of (action, task_complete)
        """
        try:
            # Show prompt for action input
            if self.current_action_prompt:
                print(f"\n🎯 Enter next action command:")
                print(f"💡 Action will be executed immediately after you enter it")
                print(f"👀 Watch the browser window for results")

            user_input = input("👤 Action: ").strip()

            if not user_input:
                # Empty input, ask again
                return None, False

            # Handle special commands
            if user_input.lower() == "help":
                self._display_help()
                return None, False
            elif user_input.lower() == "done":
                print("✅ Task marked as complete!")
                self.user_indicated_completion = True
                return None, True
            elif user_input.lower() == "quit":
                raise KeyboardInterrupt("User quit")

            # Parse action command
            action = self._parse_action_command(user_input)
            if action:
                print(f"📝 Action queued: {action.action_type} - {action.description}")
                print(f"⏳ Executing action...")
                return action, False
            else:
                print(f"❌ Invalid action: {user_input}")
                print(f"💡 Type 'help' for command reference")
                return None, False

        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"❌ Error processing input: {e}")
            return None, False


    
    def _parse_action_command(self, command: str) -> Optional[ActionCommand]:
        """Parse a single action command string into ActionCommand object."""
        try:
            parts = command.split()
            if not parts:
                return None
            
            action_type = parts[0].lower()
            
            if action_type == "click":
                if len(parts) >= 3:
                    x, y = int(parts[1]), int(parts[2])
                    return ActionCommand(
                        action_type="click",
                        parameters={"x": x, "y": y},
                        description=f"Click at ({x}, {y})"
                    )
            
            elif action_type == "type":
                if len(parts) >= 2:
                    text = " ".join(parts[1:])
                    return ActionCommand(
                        action_type="input_text",
                        parameters={"text": text},
                        description=f"Type: {text[:50]}..."
                    )
            
            elif action_type == "scroll":
                if len(parts) >= 3:
                    direction = parts[1].lower()
                    amount = int(parts[2])
                    return ActionCommand(
                        action_type="scroll",
                        parameters={"direction": direction, "amount": amount},
                        description=f"Scroll {direction} by {amount}"
                    )
            
            elif action_type == "drag":
                if len(parts) >= 5:
                    x1, y1, x2, y2 = int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
                    return ActionCommand(
                        action_type="drag",
                        parameters={"start_x": x1, "start_y": y1, "end_x": x2, "end_y": y2},
                        description=f"Drag from ({x1}, {y1}) to ({x2}, {y2})"
                    )
            
            elif action_type == "wait":
                if len(parts) >= 2:
                    duration = float(parts[1])
                    return ActionCommand(
                        action_type="wait",
                        parameters={"duration": duration},
                        description=f"Wait {duration} seconds"
                    )
            
            elif action_type == "navigate":
                if len(parts) >= 2:
                    url = parts[1]
                    return ActionCommand(
                        action_type="navigate",
                        parameters={"url": url},
                        description=f"Navigate to {url}"
                    )
            
            return None
            
        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse action command '{command}': {e}")
            return None
    
    async def _check_task_completion(self) -> bool:
        """Ask user if they think the task is complete."""
        try:
            print(f"\n❓ Do you think the task is complete?")
            response = input("👤 Task complete? (y/n): ").strip().lower()
            return response in ['y', 'yes', 'true', '1']
        except KeyboardInterrupt:
            return False
        except Exception:
            return False
    
    async def reset(self) -> None:
        """Reset terminal agent state."""
        await super().reset()
        self.task_count = 0
        self.current_action_prompt = True
        self.user_indicated_completion = False
        logger.info("TerminalAgent reset")
    
    def get_capabilities(self) -> List[str]:
        """Get terminal agent capabilities."""
        return ["click", "input_text", "scroll", "drag", "wait", "navigate", "manual_control"]
    
    def get_info(self) -> Dict[str, Any]:
        """Get terminal agent information."""
        info = super().get_info()
        info.update({
            "description": "Interactive terminal agent for manual action input",
            "interaction_mode": "terminal",
            "requires_user_input": True,
            "single_action_mode": self.single_action_mode,
            "tasks_processed": self.task_count
        })
        return info
