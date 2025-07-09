"""Base Agent Module - Simplified agent interface."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from PIL import Image
from pydantic import BaseModel
from loguru import logger


class ActionCommand(BaseModel):
    """Structured action command that can be executed by the environment."""
    action_type: str  # 'click', 'scroll', 'drag', 'input_text', 'wait', 'navigate'
    parameters: Dict[str, Any]  # Action-specific parameters
    description: Optional[str] = None  # Human-readable description
    confidence: Optional[float] = None  # Confidence score (0.0 to 1.0)


class AgentResponse(BaseModel):
    """Response from agent prediction."""
    actions: List[ActionCommand]  # List of actions to execute
    reasoning: Optional[str] = None  # Agent's reasoning process
    task_complete: bool = False  # Whether agent thinks task is complete
    needs_more_info: bool = False  # Whether agent needs more information
    error_message: Optional[str] = None  # Error message if prediction failed


class BaseAgent(ABC):
    """Abstract base class for AI agents."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the agent with configuration."""
        self.config = config or {}
        self.agent_type = self.config.get("type", "base")
        self.timeout = self.config.get("timeout", 10)
        self.max_retries = self.config.get("max_retries", 3)

        logger.info(f"Initialized {self.__class__.__name__}")

    @abstractmethod
    async def predict(self, screenshot: Image.Image, task_description: str) -> AgentResponse:
        """Process screenshot and task description to generate actions."""
        pass
    
    def validate_action(self, action: ActionCommand) -> bool:
        """
        Validate that an action command is properly formatted.
        
        Args:
            action: Action command to validate
            
        Returns:
            bool: True if action is valid, False otherwise
        """
        try:
            # Check required fields
            if not action.action_type or not action.parameters:
                return False
            
            # Validate specific action types
            if action.action_type == "click":
                return "x" in action.parameters and "y" in action.parameters
            elif action.action_type == "scroll":
                return ("direction" in action.parameters and 
                       "amount" in action.parameters)
            elif action.action_type == "drag":
                return all(key in action.parameters for key in 
                          ["start_x", "start_y", "end_x", "end_y"])
            elif action.action_type == "input_text":
                return "text" in action.parameters
            elif action.action_type == "navigate":
                return "url" in action.parameters
            elif action.action_type == "wait":
                return "duration" in action.parameters
            else:
                logger.warning(f"Unknown action type: {action.action_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error validating action: {e}")
            return False
    
    def preprocess_screenshot(self, screenshot: Image.Image) -> Image.Image:
        """
        Preprocess screenshot before analysis (can be overridden by subclasses).
        
        Args:
            screenshot: Original screenshot
            
        Returns:
            Image.Image: Processed screenshot
        """
        # Default: return original image
        # Subclasses can override for resizing, filtering, etc.
        return screenshot
    
    def postprocess_response(self, response: AgentResponse) -> AgentResponse:
        """
        Postprocess agent response (can be overridden by subclasses).
        
        Args:
            response: Original response
            
        Returns:
            AgentResponse: Processed response
        """
        # Validate all actions
        valid_actions = []
        for action in response.actions:
            if self.validate_action(action):
                valid_actions.append(action)
            else:
                logger.warning(f"Invalid action removed: {action}")
        
        response.actions = valid_actions
        return response
    
    async def reset(self) -> None:
        """
        Reset agent state (can be overridden by subclasses).
        
        Called when starting a new evaluation session.
        """
        logger.info(f"Resetting {self.__class__.__name__}")
        # Default implementation does nothing
        pass
    
    def get_capabilities(self) -> List[str]:
        """
        Get list of capabilities supported by this agent.
        
        Returns:
            List[str]: List of supported action types
        """
        return ["click", "scroll", "drag", "input_text", "navigate", "wait"]
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get agent information and metadata.
        
        Returns:
            Dict[str, Any]: Agent information
        """
        return {
            "name": self.__class__.__name__,
            "type": self.agent_type,
            "capabilities": self.get_capabilities(),
            "config": self.config
        }
