"""
Text-Based Agent Implementation

An AI agent that uses DOM and accessibility tree text information for web interaction.
This agent leverages semantic understanding of web page structure rather than relying
solely on visual information from screenshots.
"""

import asyncio
import json
import re
import os
import aiohttp
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image
from loguru import logger
from openai import OpenAI

from .base_agent import BaseAgent, AgentResponse, ActionCommand


class TextAgent(BaseAgent):
    """
    Text-based agent that uses DOM and accessibility tree information for web interaction.
    
    This agent processes text representations of web pages to understand structure,
    identify interactive elements, and generate appropriate actions based on semantic
    understanding rather than visual analysis.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the TextAgent with configuration."""
        super().__init__(config)

        # Text extraction preferences
        self.observation_type = self.config.get("observation_type", "accessibility_tree")
        self.current_viewport_only = self.config.get("current_viewport_only", True)



        # API configuration from environment
        from dotenv import load_dotenv
        # 加载 .env 文件
        load_dotenv()
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_API_BASE_URL", "https://api.openai.com/v1")
        
        # Configure HTTP client to bypass proxy for direct connection
        import httpx
        http_client = httpx.Client(
            proxy=None,  # Explicitly disable proxy
            trust_env=False  # Don't use environment proxy settings
        )
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            http_client=http_client
        )

        # History tracking
        self.action_history: List[str] = []
        self.step_count = 0

        # WebEnvironment reference (set by evaluation framework)
        self.web_environment = None
        self.device_scale_factor = None

        logger.info(f"TextAgent initialized with observation_type: {self.observation_type}")

    def set_web_environment(self, web_env):
        """Set the WebEnvironment instance for text extraction."""
        self.web_environment = web_env
        self.device_scale_factor = web_env.browser_config.get("device_scale_factor", 1.0)
        logger.debug(f"Device scale factor set to: {self.device_scale_factor}")
        logger.info("WebEnvironment reference set for TextAgent")

    async def predict(self, screenshot: Image.Image, task_description: str) -> AgentResponse:
        """
        Process screenshot and task description to generate actions using text information.
        
        Args:
            screenshot: Current page screenshot (used for fallback/validation)
            task_description: Description of the task to complete
            
        Returns:
            AgentResponse: Response with text-based action predictions
        """
        try:
            logger.info(f"TextAgent processing task: {task_description}...")
            
            # Extract text information from the current page
            # Note: This requires access to the WebEnvironment instance
            # In a real implementation, this would be passed through the evaluation framework
            text_info = await self._extract_page_text_info()
            
            if not text_info:
                logger.warning("No text information available, falling back to basic response")
                return AgentResponse(
                    actions=[],
                    reasoning="No text information available from page",
                    task_complete=False,
                    needs_more_info=True,
                    error_message="Failed to extract page text information"
                )
            
            # Process text information and generate actions
            actions, reasoning, task_complete = await self._process_text_and_generate_actions(text_info, task_description)

            # Update history
            self._update_history()
            
            return AgentResponse(
                actions=actions,
                reasoning=reasoning,
                task_complete=task_complete,
                needs_more_info=False
            )
            
        except Exception as e:
            logger.error(f"TextAgent prediction failed: {e}")
            return AgentResponse(
                actions=[],
                reasoning=f"Agent prediction failed: {str(e)}",
                task_complete=False,
                needs_more_info=False,
                error_message=str(e)
            )

    async def _extract_page_text_info(self) -> Optional[str]:
        """
        Extract text information from the current page using WebEnvironment.
        """
        if not self.web_environment:
            logger.error("WebEnvironment not set - cannot extract text information")
            return None

        try:
            # Extract text information using the WebEnvironment's text extraction capabilities
            text_info = await self.web_environment.get_page_text_info(
                observation_type=self.observation_type,
                current_viewport_only=self.current_viewport_only
            )

            logger.debug(f"Extracted {len(text_info)} characters of text information")
            return text_info

        except Exception as e:
            logger.error(f"Failed to extract page text info: {e}")
            return None

    async def _process_text_and_generate_actions(
        self,
        text_info: str,
        task_description: str
    ) -> Tuple[List[ActionCommand], str, bool]:
        """
        Process text information and generate appropriate actions using LLM/prompt-based approach.

        Args:
            text_info: Text representation of the page (DOM or accessibility tree)
            task_description: Task to complete

        Returns:
            Tuple of (actions, reasoning, task_complete)
        """
        actions = []
        reasoning = ""
        task_complete = False

        try:
            # Construct messages for LLM conversation using the prompt template
            messages = await self._construct_llm_messages(text_info, task_description)

            # Get LLM response
            llm_response = await self._call_llm_api(messages)

            if not llm_response:
                logger.warning("No LLM response received, falling back to simple action")
                action = await self._generate_simple_action(text_info, task_description)
                if action:
                    actions.append(action)
                reasoning = "LLM API unavailable, used fallback action generation"
                return actions, reasoning, task_complete

            # Parse LLM response to extract thought and action
            thought, action_text = self._parse_llm_response(llm_response)
            reasoning = thought
            logger.debug(f"\nLLM Response:\n{llm_response}")
            # Record the full LLM response in history
            self.step_count += 1
            full_response = f"Step {self.step_count}:\nThought: {thought}\nAction: {action_text}"
            self.action_history.append(full_response)

            # Check if task is complete (stop action)
            if action_text.startswith("stop"):
                task_complete = True
                logger.info("Task completion detected from LLM response")
                return actions, reasoning, task_complete

            # Convert action text to ActionCommand objects based on prompt format
            actions = await self._convert_prompt_action_to_commands(action_text)

            logger.info(f"Generated {len(actions)} actions from LLM analysis")

        except Exception as e:
            logger.error(f"Failed to process text and generate actions: {e}")
            # Fallback to simple action generation
            action = await self._generate_simple_action(text_info, task_description)
            if action:
                actions.append(action)
            reasoning = f"Error in LLM processing: {str(e)}, used fallback"

        return actions, reasoning, task_complete

    async def _generate_simple_action(self, text_info: str, task_description: str) -> Optional[ActionCommand]:
        """
        简单的动作生成逻辑（临时实现，后续应该用LLM替换）
        """
        task_lower = task_description.lower()

        # 简单的关键词匹配
        if "click" in task_lower and "button" in task_lower:
            # 在文本中查找button
            import re
            button_match = re.search(r'\[(\d+)\]\s+button\s+[\'"]([^\'"]*)[\'"]', text_info)
            if button_match:
                element_id = button_match.group(1)
                button_name = button_match.group(2)

                # 获取坐标
                coordinates = await self._get_element_coordinates(element_id)
                if coordinates:
                    x, y = coordinates
                    return ActionCommand(
                        action_type="click",
                        parameters={"x": x, "y": y},
                        description=f"Click button '{button_name}'",
                        confidence=0.8
                    )

        return None

    async def _construct_llm_messages(self, text_info: str, task_description: str) -> List[Dict[str, Any]]:
        """
        Construct messages array for LLM conversation using the CoT prompt template.

        Args:
            text_info: Text representation of the page
            task_description: Task to complete

        Returns:
            List of messages in chat completion format
        """
        # Import the prompt template
        from .prompts.text_agent_prompts import TEXT_AGENT_COT_PROMPT

        # Use the system prompt from the template
        system_prompt = TEXT_AGENT_COT_PROMPT["intro"]

        # Construct current observation using the template format
        previous_action = "None"
        if self.action_history:
            # 使用最近的10条历史记录,用换行符连接
            previous_action = "\n".join(self.action_history[-10:])

        current_selected_data = await self.web_environment.execute_javascript("getSelectedValues()")

        # Format the user message according to the template
        user_message = TEXT_AGENT_COT_PROMPT["template"].format(
            accessibility_tree=text_info,
            objective=task_description,
            previous_action=previous_action,
            current_selected_data=current_selected_data
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        return messages

    async def _call_llm_api(self, messages: List[Dict[str, Any]]) -> Optional[str]:
        """
        Call LLM API to get response.

        Args:
            messages: List of messages in chat completion format

        Returns:
            LLM response content or None if failed
        """
        if not self.api_key:
            logger.error("API key not found. Please set OPENAI_API_KEY environment variable.")
            return None

        try:
            logger.debug(f"Calling LLM API: {self.base_url}")
            response = self.client.chat.completions.create(
                model="claude-sonnet-4-20250514",
                # model="gpt-4o-mini",
                messages=messages,
                temperature=0.7
            )
            content = response.choices[0].message.content
            logger.info("LLM API call successful")
            return content

        except Exception as e:
            logger.error(f"Error calling LLM API: {e}")
            return None

    def _parse_llm_response(self, response: str) -> Tuple[str, str]:
        """
        Parse LLM response to extract thought and action with robust code block and parameter handling.

        Args:
            response: Raw LLM response

        Returns:
            Tuple of (thought, action_text)
        """
        thought = ""
        action_text = ""

        try:
            response = response.strip()

            # Step 1: Extract content from code blocks if present
            # The thought and action are only a small portion wrapped in ```
            if "```" in response:
                # Find the first occurrence of ``` and extract content until the closing ```
                start_idx = response.find("```")
                if start_idx != -1:
                    # Look for content after the opening ```
                    content_start = start_idx + 3

                    # Skip language identifier line if present
                    remaining = response[content_start:].strip()
                    if remaining and not remaining.startswith(("Thought:", "Action:")):
                        # Check if first line is a language identifier
                        first_line_end = remaining.find('\n')
                        if first_line_end != -1:
                            first_line = remaining[:first_line_end].strip()
                            # If first line doesn't contain Thought: or Action:, skip it
                            if not any(keyword in first_line for keyword in ["Thought:", "Action:"]):
                                remaining = remaining[first_line_end + 1:].strip()

                    # Find the closing ```
                    end_idx = remaining.find("```")
                    if end_idx != -1:
                        response = remaining[:end_idx].strip()
                    else:
                        response = remaining
                else:
                    # No opening ``` found, use original response
                    pass

            # Step 2: Extract thought
            thought_pattern = r"Thought:\s*(.*?)(?=\s*Action:|$)"
            thought_match = re.search(thought_pattern, response, re.DOTALL | re.IGNORECASE)
            if thought_match:
                thought = thought_match.group(1).strip()

            # Step 3: Extract action
            if "Action:" in response:
                action_text = response.split("Action:")[-1].strip()

                # Clean up action text - take the first valid action line
                action_lines = action_text.split('\n')
                clean_action = ""

                for line in action_lines:
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('```'):
                        # Look for valid action patterns
                        if line.startswith(('click', 'type', 'scroll', 'stop', 'drag')):
                            clean_action = line
                            break
                    elif line.startswith('```'):
                        break  # Stop at code block end

                action_text = clean_action if clean_action else action_text.split('\n')[0].strip()
            else:
                logger.warning("No 'Action:' found in response")
                action_text = "retrying for llm response"

        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            thought = "Error parsing response"
            action_text = "retrying for llm response"

        return thought, action_text

    async def _convert_prompt_action_to_commands(self, action_text: str) -> List[ActionCommand]:
        """
        Convert action text from prompt format to ActionCommand objects.

        Based on the prompt template, actions are in format:
        - click [id]
        - type [id] [content]
        - scroll [id] [direction=down|up]
        - stop [answer]

        Args:
            action_text: Action string from LLM

        Returns:
            List of ActionCommand objects
        """
        actions = []

        try:
            action_text = action_text.strip()

            # Helper function to strip brackets from parameters
            def strip_brackets(param_str: str) -> str:
                """Strip square brackets from both ends of parameter string."""
                param_str = param_str.strip()
                if param_str.startswith('[') and param_str.endswith(']'):
                    return param_str[1:-1]
                return param_str

            # Parse click actions: click [id] or click id
            click_match = re.search(r'click\s+(\[?\d+\]?)', action_text)
            if click_match:
                element_id = strip_brackets(click_match.group(1))
                coordinates = await self._get_element_coordinates(element_id)
                if coordinates:
                    x, y = coordinates
                    actions.append(ActionCommand(
                        action_type="click",
                        parameters={"x": x, "y": y},
                        description=f"Click element [{element_id}] at ({x}, {y})",
                    ))
                else:
                    logger.warning(f"Could not find coordinates for element [{element_id}]")
                return actions

            # Parse type actions: type [id] [content] or type id content
            type_match = re.search(r'type\s+(\[?\d+\]?)\s+(.+)', action_text)
            if type_match:
                element_id = strip_brackets(type_match.group(1))
                content = type_match.group(2).strip()
                # Remove brackets from content if present
                content = strip_brackets(content)
                coordinates = await self._get_element_coordinates(element_id)
                if coordinates:
                    x, y = coordinates
                    actions.append(ActionCommand(
                        action_type="set_text",
                        parameters={"text": content, "x": x, "y": y},
                        description=f"Type '{content}' in element [{element_id}] at ({x}, {y})",
                    ))
                else:
                    logger.warning(f"Could not find coordinates for element [{element_id}]")
                return actions

            # Parse scroll actions with flexible parameter formats:
            # 1. Standard: scroll [213] [direction=left] [distance=medium]
            # 2. Simplified: scroll [213] left medium
            # 3. Mixed: scroll 213 direction=left distance=medium
            scroll_match = re.search(r'scroll\s+(\[?\d+\]?)\s+(.+)', action_text)
            if scroll_match:
                element_id = strip_brackets(scroll_match.group(1))
                params_text = scroll_match.group(2).strip()

                # Parse direction and distance from the remaining parameters
                direction = "down"  # default
                distance = "medium"  # default

                # Try to extract direction and distance using multiple patterns
                # Pattern 1: [direction=value] [distance=value] format
                dir_match = re.search(r'\[?direction=(\w+)\]?', params_text)
                if dir_match:
                    direction = strip_brackets(dir_match.group(1))

                dist_match = re.search(r'\[?distance=(\w+)\]?', params_text)
                if dist_match:
                    distance = strip_brackets(dist_match.group(1))

                # Pattern 2: Simple space-separated format (direction distance)
                if not dir_match and not dist_match:
                    # Split remaining parameters and try to identify direction and distance
                    params = params_text.split()
                    clean_params = [strip_brackets(p) for p in params]

                    # Look for direction keywords
                    direction_keywords = ['up', 'down', 'left', 'right']
                    distance_keywords = ['small', 'medium', 'large', 'xlarge']

                    for param in clean_params:
                        if param in direction_keywords:
                            direction = param
                        elif param in distance_keywords:
                            distance = param

                coordinates = await self._get_element_coordinates(element_id)
                if coordinates:
                    x, y = coordinates

                    # Convert distance to pixel values
                    distance_map = {
                        "small": 33,
                        "medium": 100,
                        "large": 300,
                        "xlarge": 900
                    }
                    scroll_pixels = distance_map.get(distance, 300)  # default to medium

                    # Convert direction to scroll distance
                    dx, dy = 0, 0
                    if direction == "down" or direction == "up":
                        dy = scroll_pixels
                    elif direction == "left" or direction == "right":
                        dx = scroll_pixels

                    actions.append(ActionCommand(
                        action_type="scroll",
                        parameters={"x": x, "y": y, "dx": dx, "dy": dy,"direction": direction,"amount": 0},
                        description=f"Scroll {direction} ({distance}) from element [{element_id}]",
                    ))
                else:
                    logger.warning(f"Could not find coordinates for element [{element_id}]")
                return actions

            logger.warning(f"Could not parse action: {action_text}")

        except Exception as e:
            logger.error(f"Error converting action text '{action_text}': {e}")

        return actions

    async def _get_element_coordinates(self, element_id: str) -> Optional[Tuple[int, int]]:
        """
        Get screen coordinates for an element using WebEnvironment.

        Args:
            element_id: Element ID from accessibility tree

        Returns:
            Tuple of (x, y) coordinates or None if not found
        """
        if not self.web_environment:
            logger.error("WebEnvironment not available for coordinate mapping")
            return None

        try:
            # Get element center as viewport ratios
            center_ratios = await self.web_environment.get_element_center(element_id)
            if not center_ratios:
                return None

            # Convert ratios to screen coordinates
            # Get viewport size
            viewport = await self.web_environment.page.evaluate(
                "() => ({ width: window.innerWidth, height: window.innerHeight })"
            )

            x = int(center_ratios[0] * viewport["width"] * self.device_scale_factor)
            y = int(center_ratios[1] * viewport["height"] * self.device_scale_factor)

            logger.debug(f"Element {element_id} coordinates: ({x}, {y})")
            return (x, y)

        except Exception as e:
            logger.error(f"Failed to get coordinates for element {element_id}: {e}")
            return None

    def _update_history(self) -> None:
        """Update action history management."""
        # Keep history manageable - limit to last 10 full responses
        if len(self.action_history) > 10:
            self.action_history = self.action_history[-10:]
