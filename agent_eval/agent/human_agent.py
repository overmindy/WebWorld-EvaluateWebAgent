"""
Human Agent Implementation

A human-in-the-loop agent that opens webpages in browser for human interaction
and waits for human input on task completion.
"""

import asyncio
import webbrowser
from typing import Dict, Any, Optional, List
from PIL import Image
from loguru import logger

from .base_agent import BaseAgent, AgentResponse, ActionCommand


class HumanAgent(BaseAgent):
    """
    Human-in-the-loop agent for manual evaluation.
    
    This agent opens webpages in the default browser and waits for human
    operators to complete tasks manually, then report completion status.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize human agent."""
        super().__init__(config)
        self.agent_type = "human"
        self.current_url = None
        self.task_count = 0
        
        # Configuration options
        self.auto_open_browser = self.config.get("auto_open_browser", True)
        self.show_task_dialog = self.config.get("show_task_dialog", True)
        self.timeout_minutes = self.config.get("timeout_minutes", 10)
        
        logger.info("HumanAgent initialized for manual evaluation")
    
    async def predict(self, screenshot: Image.Image, task_description: str) -> AgentResponse:
        """
        Present task to human operator and wait for completion status.
        
        Args:
            screenshot: PIL Image of current page state (not used for human agent)
            task_description: Text description of the task to perform
            
        Returns:
            AgentResponse: Response based on human input
        """
        self.task_count += 1
        logger.info(f"Starting human evaluation task {self.task_count}")
        
        try:
            # Display task information to human operator
            await self._present_task_to_human(task_description)
            
            # Wait for human to complete the task
            completion_status = await self._wait_for_human_completion(task_description)
            
            # Generate response based on human input
            if completion_status["completed"]:
                return AgentResponse(
                    actions=[],  # No automated actions for human agent
                    reasoning=f"Human operator completed task: {completion_status.get('notes', 'No additional notes')}",
                    task_complete=True,
                    needs_more_info=False
                )
            else:
                return AgentResponse(
                    actions=[],
                    reasoning=f"Human operator reported task failure: {completion_status.get('notes', 'No additional notes')}",
                    task_complete=False,
                    needs_more_info=False,
                    error_message=completion_status.get("error_reason", "Task not completed")
                )
                
        except Exception as e:
            logger.error(f"Human agent evaluation failed: {e}")
            return AgentResponse(
                actions=[],
                error_message=f"Human evaluation error: {str(e)}",
                task_complete=False,
                needs_more_info=False
            )
    
    async def _present_task_to_human(self, task_description: str) -> None:
        """Present the task information to the human operator."""
        print("\n" + "="*60)
        print("🤖 HUMAN AGENT EVALUATION")
        print("="*60)
        print(f"📋 Task #{self.task_count}")
        print(f"📝 Description: {task_description}")
        print(f"🌐 Current URL: {self.current_url or 'Not set'}")
        print("="*60)
        
        if self.show_task_dialog:
            print("📖 Instructions:")
            print("1. The webpage should already be open in your browser")
            print("2. Complete the task as described above")
            print("3. Return to this console when finished")
            print("4. Report the completion status")
            print("-"*60)
    
    async def _wait_for_human_completion(self, task_description: str) -> Dict[str, Any]:
        """
        Wait for human operator to complete the task and report status.
        
        Returns:
            Dict containing completion status and notes
        """
        print(f"\n⏳ Waiting for human to complete task...")
        print(f"💡 Task: {task_description}")
        
        while True:
            try:
                # Get completion status from human
                print(f"\n❓ Did you complete the task successfully?")
                print("   Enter 'y' for Yes (success)")
                print("   Enter 'n' for No (failure)")
                print("   Enter 'r' to retry/continue working")
                print("   Enter 'q' to quit evaluation")
                
                response = input("👤 Your response (y/n/r/q): ").strip().lower()
                
                if response == 'y':
                    notes = input("📝 Optional notes about completion (press Enter to skip): ").strip()
                    return {
                        "completed": True,
                        "notes": notes or "Task completed successfully",
                        "status": "success"
                    }
                
                elif response == 'n':
                    error_reason = input("❌ What went wrong? (optional): ").strip()
                    return {
                        "completed": False,
                        "notes": f"Task failed: {error_reason}" if error_reason else "Task failed",
                        "error_reason": error_reason or "Task could not be completed",
                        "status": "failure"
                    }
                
                elif response == 'r':
                    print("🔄 Continue working on the task...")
                    continue
                
                elif response == 'q':
                    print("🛑 Evaluation stopped by user")
                    return {
                        "completed": False,
                        "notes": "Evaluation stopped by user",
                        "error_reason": "User quit evaluation",
                        "status": "quit"
                    }
                
                else:
                    print("❌ Invalid response. Please enter 'y', 'n', 'r', or 'q'")
                    continue
                    
            except KeyboardInterrupt:
                print("\n🛑 Evaluation interrupted by user")
                return {
                    "completed": False,
                    "notes": "Evaluation interrupted",
                    "error_reason": "Keyboard interrupt",
                    "status": "interrupted"
                }
            except Exception as e:
                print(f"❌ Error getting user input: {e}")
                continue
    
    def set_current_url(self, url: str, auto_open: bool = None) -> None:
        """Set the current URL being evaluated.

        Args:
            url: The URL to set as current
            auto_open: Override auto_open_browser setting. If None, uses config setting.
                      Set to False when WebEnvironment is already handling the browser.
        """
        self.current_url = url
        logger.info(f"HumanAgent current URL set to: {url}")

        # Determine if we should auto-open browser
        should_auto_open = auto_open if auto_open is not None else self.auto_open_browser

        # Optionally open in browser (only if not already handled by WebEnvironment)
        if should_auto_open and url:
            try:
                webbrowser.open(url)
                logger.info(f"HumanAgent opened URL in default browser: {url}")
            except Exception as e:
                logger.warning(f"Could not open browser automatically: {e}")
                print(f"⚠️  Please manually open this URL in your browser: {url}")
        else:
            logger.info(f"HumanAgent skipped browser opening (auto_open={should_auto_open}): {url}")
    
    async def reset(self) -> None:
        """Reset human agent state."""
        await super().reset()
        self.task_count = 0
        self.current_url = None
        logger.info("HumanAgent reset")
    
    def get_capabilities(self) -> List[str]:
        """Get human agent capabilities."""
        return ["manual_interaction", "human_judgment", "complex_reasoning", "visual_assessment"]
    
    def get_info(self) -> Dict[str, Any]:
        """Get human agent information."""
        info = super().get_info()
        info.update({
            "description": "Human-in-the-loop agent for manual evaluation",
            "interaction_mode": "manual",
            "requires_human_operator": True,
            "auto_open_browser": self.auto_open_browser,
            "timeout_minutes": self.timeout_minutes,
            "tasks_completed": self.task_count
        })
        return info
