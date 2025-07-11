"""
UITARS Agent Implementation

A GUI agent that uses the UITARS (UI-TARS) approach with thinking/reasoning
before taking actions. This agent is adapted to work with our evaluation framework.
"""

import asyncio
import ast
import base64
import json
import re
from io import BytesIO
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image
from loguru import logger

from .base_agent import BaseAgent, AgentResponse, ActionCommand


def parse_action_ast(action_str: str) -> Optional[Dict[str, Any]]:
    """
    Parse action string using AST for more reliable parsing.
    Based on reference UITARS implementation.

    Args:
        action_str: Action string like "click(start_box='(100,200)')"

    Returns:
        Dict with 'function' and 'args' keys, or None if parsing fails
    """
    try:
        # Clean up the action string
        action_str = action_str.strip()

        # Parse string as AST node
        node = ast.parse(action_str, mode='eval')

        # Ensure node is an expression
        if not isinstance(node, ast.Expression):
            raise ValueError("Not an expression")

        # Get expression body
        call = node.body

        # Ensure body is a function call
        if not isinstance(call, ast.Call):
            raise ValueError("Not a function call")

        # Get function name
        if isinstance(call.func, ast.Name):
            func_name = call.func.id
        elif isinstance(call.func, ast.Attribute):
            func_name = call.func.attr
        else:
            func_name = None

        # Get keyword arguments
        kwargs = {}
        for kw in call.keywords:
            key = kw.arg
            # Handle different types of values
            if isinstance(kw.value, ast.Constant):
                value = kw.value.value
            elif isinstance(kw.value, ast.Str):  # Compatibility with older Python
                value = kw.value.s
            else:
                value = None
            kwargs[key] = value

        # Also handle positional arguments for simplified format
        args = []
        for arg in call.args:
            if isinstance(arg, ast.Constant):
                args.append(arg.value)
            elif isinstance(arg, ast.Num):  # Compatibility with older Python
                args.append(arg.n)
            elif isinstance(arg, ast.Str):  # Compatibility with older Python
                args.append(arg.s)

        return {
            'function': func_name,
            'args': kwargs,
            'positional_args': args
        }

    except Exception as e:
        logger.debug(f"AST parsing failed for '{action_str}': {e}")
        return None


def escape_single_quotes(text: str) -> str:
    """Escape unescaped single quotes in text."""
    # Match unescaped single quotes (not matching \\')
    pattern = r"(?<!\\)'"
    return re.sub(pattern, r"\\'", text)


class UITARSAgent(BaseAgent):
    """
    UITARS agent implementation that uses thinking/reasoning approach.
    
    This agent follows the UITARS pattern of:
    1. Analyzing screenshots and task context
    2. Thinking through the next action
    3. Executing the planned action
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize UITARS agent."""
        super().__init__(config)
        self.agent_type = "uitars"

        # UITARS-specific configuration
        self.max_history_steps = self.config.get("max_history_steps", 5)
        self.history_n = self.config.get("history_n", 3)  # Max conversation turns to send to LLM
        self.language = self.config.get("language", "English")

        # Local LLM configuration
        self.llm_config = self.config.get("llm", {})
        self.server_url = self.llm_config.get("server_url", "http://localhost:7999")
        self.endpoint = self.llm_config.get("endpoint", "/v1/chat/completions")
        self.model_name = self.llm_config.get("model", "ui-tars")
        self.temperature = self.llm_config.get("temperature", 0.7)
        self.max_tokens = self.llm_config.get("max_tokens", 512)

        # History tracking
        self.history_screenshots: List[Image.Image] = []
        self.history_responses: List[str] = []  # Store full LLM responses
        self.step_count = 0

        # Simplified action space definition
        self.action_space = """
click(start_box='<|box_start|>(x1,y1)<|box_end|>')
drag(start_box='<|box_start|>(x1,y1)<|box_end|>', end_box='<|box_start|>(x3,y3)<|box_end|>')
type(content='') #If you want to submit your input, use "\\n" at the end of `content`.
scroll(start_box='<|box_start|>(x1,y1)<|box_end|>', direction='down or up or right or left')
finished(content='xxx') # Use escape characters \\', \\", and \\n in content part to ensure we can parse the content in normal python string format.
"""

        # System prompt for multi-turn conversation
        self.system_prompt = """You are a GUI agent. You are given a task and your action history, with screenshots. You need to perform the next action to complete the task.

## Output Format
```
Thought: ...
Action: ...
```

## Action Space
{action_space}

## Note
- Use {language} in `Thought` part.
- Write a small plan and finally summarize your next action (with its target element) in one sentence in `Thought` part.
- Output absolute coordinates directly based on the screenshot.

## User Instruction
{instruction}
"""

        logger.info(f"UITARSAgent initialized with {self.max_history_steps} history steps")
    
    async def predict(self, screenshot: Image.Image, task_description: str) -> AgentResponse:
        """
        Process screenshot and task description to generate actions using UITARS approach.
        
        Args:
            screenshot: PIL Image of current page state
            task_description: Text description of the task to perform
            
        Returns:
            AgentResponse: Response with actions and reasoning
        """
        self.step_count += 1
        logger.info(f"UITARS agent processing step {self.step_count}")
        
        try:
            # Store screenshot in history
            self.history_screenshots.append(screenshot)

            # Construct messages array for multi-turn conversation
            messages = self._construct_messages(task_description)

            # Get LLM response from local server
            llm_response = await self._get_llm_response(messages)

            # Parse response to extract thought and action
            thought, action_text = self._parse_llm_response(llm_response)

            # Convert action to ActionCommand
            actions = self._convert_to_action_commands(action_text)

            # Store the full LLM response in history
            self.history_responses.append(llm_response)

            # Maintain history limits
            self._trim_history()
            
            # Check if task is complete
            task_complete = self._is_task_complete(action_text)
            
            return AgentResponse(
                actions=actions,
                reasoning=thought,
                task_complete=task_complete,
                needs_more_info=False
            )
            
        except Exception as e:
            logger.error(f"UITARS agent prediction failed: {e}")
            return AgentResponse(
                actions=[],
                reasoning=f"Error in UITARS agent: {str(e)}",
                task_complete=False,
                needs_more_info=False,
                error_message=str(e)
            )
    

    
    def _trim_history(self) -> None:
        """
        Trim history to maintain storage limits.
        """
        # Maintain max_history_steps for local storage
        if len(self.history_screenshots) > self.max_history_steps:
            self.history_screenshots.pop(0)
        if len(self.history_responses) > self.max_history_steps:
            self.history_responses.pop(0)

    def _construct_messages(self, task_description: str) -> List[Dict[str, Any]]:
        """
        Construct messages array for multi-turn conversation.

        Args:
            task_description: The task to perform

        Returns:
            List of messages in OpenAI chat completion format
        """
        messages = []

        # Add system message
        system_content = self.system_prompt.format(
            action_space=self.action_space.strip(),
            language=self.language,
            instruction=task_description
        )
        messages.append({
            "role": "system",
            "content": [{"type": "text", "text": system_content}]
        })

        # Determine how many conversation turns to include
        # Each turn consists of a user message (screenshot) + assistant response
        num_history_pairs = min(len(self.history_responses), self.history_n)

        # Add historical conversation turns
        for i in range(-num_history_pairs, 0):  # Get last N pairs
            # Add user message with historical screenshot
            if i + len(self.history_screenshots) >= 0:
                screenshot_idx = i + len(self.history_screenshots) - 1  # Adjust for current screenshot not yet in responses
                if screenshot_idx >= 0 and screenshot_idx < len(self.history_screenshots):
                    screenshot_base64 = self._image_to_base64(self.history_screenshots[screenshot_idx])
                    messages.append({
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{screenshot_base64}"
                                }
                            }
                        ]
                    })

            # Add assistant response
            if i + len(self.history_responses) >= 0:
                response_idx = i + len(self.history_responses)
                if response_idx >= 0 and response_idx < len(self.history_responses):
                    messages.append({
                        "role": "assistant",
                        "content": [{"type": "text", "text": self.history_responses[response_idx]}]
                    })

        # Add current screenshot as final user message
        current_screenshot_base64 = self._image_to_base64(self.history_screenshots[-1])
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{current_screenshot_base64}"
                    }
                }
            ]
        })

        return messages

    def _image_to_base64(self, image: Image.Image) -> str:
        """
        Convert PIL Image to base64 string.

        Args:
            image: PIL Image to convert

        Returns:
            Base64 encoded image string
        """
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def _get_recent_screenshots(self, count: int = 3) -> List[Image.Image]:
        """
        Get the most recent screenshots for context.

        Args:
            count: Number of recent screenshots to return

        Returns:
            List of recent PIL Images
        """
        if not self.history_screenshots:
            return []

        return self.history_screenshots[-count:] if len(self.history_screenshots) >= count else self.history_screenshots
    
    async def _get_llm_response(self, messages: List[Dict[str, Any]]) -> str:
        """
        Get response from local LLM server using messages array.

        Args:
            messages: List of messages in chat completion format

        Returns:
            LLM response text
        """
        try:
            return await self._get_local_llm_response(messages)
        except Exception as e:
            logger.error(f"Error getting LLM response: {e}")
            return self._get_placeholder_response()



    async def _get_local_llm_response(self, messages: List[Dict[str, Any]]) -> str:
        """Get response from local LLM server using messages array."""
        try:
            import aiohttp

            # Prepare request payload with messages array
            payload = {
                "model": self.model_name,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }

            # Make request to local server
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.server_url}{self.endpoint}",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        pipe_result=result["choices"][0]["message"]["content"]
                        res=pipe_result[0]['generated_text'][-1]['content']
                        logger.info(f"\nLocal LLM response: \n{res}")
                        return res
                    else:
                        logger.error(f"Local LLM server error: {response.status}")
                        return self._get_placeholder_response()

        except Exception as e:
            logger.error(f"Local LLM error: {e}")
            return self._get_placeholder_response()

    def _get_placeholder_response(self) -> str:
        """Get a placeholder response when LLM is not available."""
        return """
Thought: I need to analyze the current screenshot and determine the next action to complete the task. Since I don't have access to a language model, I'll wait for the next step.

Action: wait()
"""
    
    def _parse_llm_response(self, response: str) -> Tuple[str, str]:
        """
        Parse LLM response to extract thought and action.
        
        Args:
            response: Raw LLM response
            
        Returns:
            Tuple of (thought, action)
        """
        thought = ""
        action_text = ""

        # Ensure response is a string
        if not isinstance(response, str):
            logger.error(f"Expected string response, got {type(response)}: {response}")
            return "Error: Invalid response format", "wait()"

        try:
            response = response.strip()

            # Support multiple thought patterns like reference implementation
            if response.startswith("Thought:"):
                thought_pattern = r"Thought:\s*(.*?)(?=\s*Action:|$)"
            elif response.startswith("Reflection:"):
                thought_pattern = r"Reflection:\s*(.*?)Action_Summary:\s*(.*?)(?=\s*Action:|$)"
            elif response.startswith("Action_Summary:"):
                thought_pattern = r"Action_Summary:\s*(.*?)(?=\s*Action:|$)"
            else:
                thought_pattern = r"Thought:\s*(.*?)(?=\s*Action:|$)"

            # Extract thought/reflection
            thought_match = re.search(thought_pattern, response, re.DOTALL | re.IGNORECASE)
            if thought_match:
                if len(thought_match.groups()) == 1:
                    thought = thought_match.group(1).strip()
                elif len(thought_match.groups()) == 2:
                    # Handle Reflection + Action_Summary format
                    reflection = thought_match.group(1).strip()
                    action_summary = thought_match.group(2).strip()
                    thought = f"Reflection: {reflection}\nAction Summary: {action_summary}"

            # Extract action - must have "Action:" in response
            if "Action:" in response:
                action_text = response.split("Action:")[-1].strip()

                # Clean up action text - remove trailing content after action
                action_lines = action_text.split('\n')
                clean_action_lines = []

                for line in action_lines:
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('```'):
                        clean_action_lines.append(line)
                    elif line.startswith('```'):
                        break  # Stop at code block end

                action_text = '\n'.join(clean_action_lines).strip()

                # If multiple lines, take the first valid action
                if '\n' in action_text:
                    for line in action_text.split('\n'):
                        line = line.strip()
                        if line and ('(' in line and ')' in line):
                            action_text = line
                            break
            else:
                logger.warning("No 'Action:' found in response")
                action_text = "wait()"

        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            thought = "Error parsing response"
            action_text = "wait()"

        return thought, action_text
    
    def _convert_to_action_commands(self, action_text: str) -> List[ActionCommand]:
        """
        Convert simplified action text to ActionCommand objects.

        Args:
            action_text: Action string with absolute coordinates

        Returns:
            List of ActionCommand objects
        """
        actions = []

        # Clean up action text
        action_text = action_text.strip()

        try:
            # Handle multiple actions separated by double newlines (like reference implementation)
            action_strings = action_text.split('\n\n')

            for action_str in action_strings:
                action_str = action_str.strip()
                if not action_str:
                    continue

                # Special handling for type actions with content parameter
                if "type(content" in action_str:
                    action_str = self._preprocess_type_action(action_str)

                # Try AST parsing first (more reliable)
                parsed_action = parse_action_ast(action_str)
                if parsed_action:
                    action_cmd = self._convert_parsed_action_to_command(parsed_action)
                    if action_cmd:
                        actions.append(action_cmd)
                        continue
                    # Check if this is a finish action (which doesn't create ActionCommand)
                    elif parsed_action.get('function') in ['finish', 'finished']:
                        logger.debug(f"Task completion action detected: {action_str}")
                        continue

                # Fallback to regex parsing for compatibility
                action_cmd = self._parse_action_with_regex(action_str)
                if action_cmd:
                    actions.append(action_cmd)
                else:
                    # Check if this is a finish action before warning
                    if self._is_task_complete(action_str):
                        logger.debug(f"Task completion action detected: {action_str}")
                    else:
                        logger.warning(f"Could not parse action: {action_str}")

        except Exception as e:
            logger.error(f"Error converting action '{action_text}': {e}")

        return actions

    def _preprocess_type_action(self, action_str: str) -> str:
        """Preprocess type action to handle content parameter properly."""
        try:
            # Extract content from type(content='...') and escape quotes
            def escape_quotes(match):
                content = match.group(1)
                return content

            pattern = r"type\(content='(.*?)'\)"
            content = re.sub(pattern, escape_quotes, action_str)

            # Escape single quotes in content
            content = escape_single_quotes(content)
            return f"type(content='{content}')"
        except Exception as e:
            logger.debug(f"Error preprocessing type action: {e}")
            return action_str

    def _convert_parsed_action_to_command(self, parsed_action: Dict[str, Any]) -> Optional[ActionCommand]:
        """Convert parsed action dict to ActionCommand."""
        try:
            action_type = parsed_action['function']
            args = parsed_action['args']
            positional_args = parsed_action.get('positional_args', [])

            if action_type == "click":
                return self._create_click_command(args, positional_args)
            elif action_type == "type":
                return self._create_type_command(args, positional_args)
            elif action_type == "scroll":
                return self._create_scroll_command(args, positional_args)
            elif action_type == "drag":
                return self._create_drag_command(args, positional_args)
            elif action_type in ["finish", "finished"]:
                # Task completion handled elsewhere
                return None
            else:
                logger.warning(f"Unknown action type: {action_type}")
                return None

        except Exception as e:
            logger.error(f"Error converting parsed action: {e}")
            return None

    def _parse_action_with_regex(self, action_text: str) -> Optional[ActionCommand]:
        """Fallback regex parsing for action strings."""
        try:
            # Handle core action types
            if "click(" in action_text:
                return self._parse_click_action(action_text)
            elif "type(" in action_text:
                return self._parse_type_action(action_text)
            elif "drag(" in action_text:
                return self._parse_drag_action(action_text)
            elif "scroll(" in action_text:
                return self._parse_scroll_action(action_text)
            elif "finish()" in action_text or "finished(" in action_text:
                return None  # Task completion handled elsewhere
            else:
                logger.warning(f"Unknown action: {action_text}")
                return None
        except Exception as e:
            logger.error(f"Error in regex parsing: {e}")
            return None

    def _create_click_command(self, args: Dict[str, Any], positional_args: List[Any]) -> Optional[ActionCommand]:
        """Create click command from parsed arguments."""
        try:
            # Handle positional arguments (simplified format)
            if len(positional_args) >= 2:
                x, y = int(positional_args[0]), int(positional_args[1])
                return ActionCommand(
                    action_type="click",
                    parameters={"x": x, "y": y},
                    description=f"Click at coordinates ({x}, {y})"
                )

            # Handle keyword arguments (UITARS format)
            if "start_box" in args:
                coords = self._extract_coordinates_from_box(args["start_box"])
                if coords:
                    x, y = coords[0], coords[1]
                    return ActionCommand(
                        action_type="click",
                        parameters={"x": x, "y": y},
                        description=f"Click at coordinates ({x}, {y})"
                    )

            return None
        except Exception as e:
            logger.error(f"Error creating click command: {e}")
            return None

    def _create_type_command(self, args: Dict[str, Any], positional_args: List[Any]) -> Optional[ActionCommand]:
        """Create type command from parsed arguments."""
        try:
            text = None
            replace_mode = True

            # Handle positional arguments (simplified format)
            if len(positional_args) >= 1:
                text = str(positional_args[0])

            # Handle keyword arguments (UITARS format)
            elif "content" in args:
                text = str(args["content"])

            if text is None:
                return None

            # Check for delete operations
            if text.lower() in ['delete', 'backspace']:
                return ActionCommand(
                    action_type="input_text",
                    parameters={"text": text},
                    description=f"Delete operation: {text}"
                )

            # Check for replace mode indicator (optional enhancement)
            if "replace" in args and args["replace"]:
                replace_mode = True

            return ActionCommand(
                action_type="input_text",
                parameters={
                    "text": text,
                    "replace_mode": replace_mode
                },
                description=f"Type text: {text[:50]}{'...' if len(text) > 50 else ''}"
            )

        except Exception as e:
            logger.error(f"Error creating type command: {e}")
            return None

    def _create_scroll_command(self, args: Dict[str, Any], positional_args: List[Any]) -> Optional[ActionCommand]:
        """Create scroll command from parsed arguments."""
        try:
            direction = None
            x, y = None, None

            # Handle positional arguments (simplified format)
            # Support: scroll(direction) or scroll(x, y, direction)
            if len(positional_args) >= 1:
                if len(positional_args) >= 3:
                    # Format: scroll(x, y, direction)
                    x, y = int(positional_args[0]), int(positional_args[1])
                    direction = str(positional_args[2]).lower()
                else:
                    # Format: scroll(direction)
                    direction = str(positional_args[0]).lower()

            # Handle keyword arguments (UITARS format)
            elif "direction" in args:
                direction = str(args["direction"]).lower()

                # Check for coordinate parameters
                if "x" in args and "y" in args:
                    x, y = int(args["x"]), int(args["y"])
                elif "start_box" in args:
                    coords = self._extract_coordinates_from_box(args["start_box"])
                    if coords:
                        x, y = coords[0], coords[1]

            if direction in ["down", "up", "left", "right"]:
                parameters = {
                    "direction": direction,
                    "amount": 100,
                    "dx": 0,
                    "dy": 0
                }

                # Add coordinates if provided
                if x is not None and y is not None:
                    parameters["x"] = x
                    parameters["y"] = y
                    description = f"Scroll {direction} from coordinates ({x}, {y})"
                else:
                    description = f"Scroll {direction}"

                return ActionCommand(
                    action_type="scroll",
                    parameters=parameters,
                    description=description
                )

            return None
        except Exception as e:
            logger.error(f"Error creating scroll command: {e}")
            return None

    def _create_drag_command(self, args: Dict[str, Any], positional_args: List[Any]) -> Optional[ActionCommand]:
        """Create drag command from parsed arguments."""
        try:
            # Handle positional arguments (simplified format)
            if len(positional_args) >= 4:
                start_x, start_y, end_x, end_y = map(int, positional_args[:4])
                return ActionCommand(
                    action_type="drag",
                    parameters={
                        "start_x": start_x,
                        "start_y": start_y,
                        "end_x": end_x,
                        "end_y": end_y
                    },
                    description=f"Drag from ({start_x}, {start_y}) to ({end_x}, {end_y})"
                )

            # Handle keyword arguments (UITARS format)
            if "start_box" in args and "end_box" in args:
                start_coords = self._extract_coordinates_from_box(args["start_box"])
                end_coords = self._extract_coordinates_from_box(args["end_box"])

                if start_coords and end_coords:
                    start_x, start_y = start_coords[0], start_coords[1]
                    end_x, end_y = end_coords[0], end_coords[1]
                    return ActionCommand(
                        action_type="drag",
                        parameters={
                            "start_x": start_x,
                            "start_y": start_y,
                            "end_x": end_x,
                            "end_y": end_y
                        },
                        description=f"Drag from ({start_x}, {start_y}) to ({end_x}, {end_y})"
                    )

            return None
        except Exception as e:
            logger.error(f"Error creating drag command: {e}")
            return None

    def _extract_coordinates_from_box(self, box_str: str) -> Optional[Tuple[int, int]]:
        """Extract coordinates from box string like '(100,200)'."""
        try:
            # Remove parentheses and split by comma
            coords_str = str(box_str).replace("(", "").replace(")", "")
            coords = coords_str.split(",")

            if len(coords) >= 2:
                x, y = int(float(coords[0])), int(float(coords[1]))
                return (x, y)

            return None
        except Exception as e:
            logger.debug(f"Error extracting coordinates from '{box_str}': {e}")
            return None

    def _parse_click_action(self, action_text: str) -> Optional[ActionCommand]:
        """Parse click action with absolute coordinates."""
        try:
            # Extract coordinates from click(x, y) format
            match = re.search(r'click\((\d+),\s*(\d+)\)', action_text)
            if match:
                x, y = int(match.group(1)), int(match.group(2))
                return ActionCommand(
                    action_type="click",
                    parameters={"x": x, "y": y},
                    description=f"Click at coordinates ({x}, {y})"
                )

            # Also handle UITARS format: click(start_box='(x,y)')
            uitars_match = re.search(r'click\(start_box=[\'"]?\([\'"]?(\d+),\s*(\d+)[\'"]?\)[\'"]?\)', action_text)
            if uitars_match:
                x, y = int(uitars_match.group(1)), int(uitars_match.group(2))
                return ActionCommand(
                    action_type="click",
                    parameters={"x": x, "y": y},
                    description=f"Click at coordinates ({x}, {y})"
                )
        except Exception as e:
            logger.error(f"Error parsing click action: {e}")
        return None

    def _parse_drag_action(self, action_text: str) -> Optional[ActionCommand]:
        """Parse drag action with absolute coordinates."""
        try:
            # Extract coordinates from drag(start_x, start_y, end_x, end_y) format
            match = re.search(r'drag\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)', action_text)
            if match:
                start_x, start_y, end_x, end_y = map(int, match.groups())
                return ActionCommand(
                    action_type="drag",
                    parameters={
                        "start_x": start_x,
                        "start_y": start_y,
                        "end_x": end_x,
                        "end_y": end_y
                    },
                    description=f"Drag from ({start_x}, {start_y}) to ({end_x}, {end_y})"
                )

            # Also handle UITARS format: drag(start_box='(x1,y1)', end_box='(x2,y2)')
            uitars_match = re.search(r'drag\(start_box=[\'"]?\([\'"]?(\d+),\s*(\d+)[\'"]?\)[\'"]?,\s*end_box=[\'"]?\([\'"]?(\d+),\s*(\d+)[\'"]?\)[\'"]?\)', action_text)
            if uitars_match:
                start_x, start_y, end_x, end_y = map(int, uitars_match.groups())
                return ActionCommand(
                    action_type="drag",
                    parameters={
                        "start_x": start_x,
                        "start_y": start_y,
                        "end_x": end_x,
                        "end_y": end_y
                    },
                    description=f"Drag from ({start_x}, {start_y}) to ({end_x}, {end_y})"
                )
        except Exception as e:
            logger.error(f"Error parsing drag action: {e}")
        return None

    def _parse_type_action(self, action_text: str) -> Optional[ActionCommand]:
        """Parse type action."""
        try:
            # First try UITARS format: type(content='text')
            uitars_match = re.search(r'type\(content=[\'"]([^\'"]*)[\'"]', action_text)
            if uitars_match:
                text = uitars_match.group(1)
                # Handle escape sequences
                text = text.replace('\\n', '\n').replace('\\"', '"').replace("\\'", "'")

                # Check for delete operations
                if text.lower() in ['delete', 'backspace']:
                    return ActionCommand(
                        action_type="input_text",
                        parameters={"text": text},
                        description=f"Delete operation: {text}"
                    )

                return ActionCommand(
                    action_type="input_text",
                    parameters={"text": text},
                    description=f"Type text: {text[:50]}{'...' if len(text) > 50 else ''}"
                )

            # Then try simplified format: type(content)
            match = re.search(r'type\(([^)]+)\)', action_text)
            if match:
                text = match.group(1).strip('\'"')
                return ActionCommand(
                    action_type="input_text",
                    parameters={"text": text},
                    description=f"Type text: {text[:50]}{'...' if len(text) > 50 else ''}"
                )
        except Exception as e:
            logger.error(f"Error parsing type action: {e}")
        return None

    def _parse_scroll_action(self, action_text: str) -> Optional[ActionCommand]:
        """Parse scroll action."""
        try:
            # Handle coordinate-based scroll: scroll(x=100, y=200, direction='down')
            coord_match = re.search(r'scroll\(x=(\d+),\s*y=(\d+),\s*direction=[\'"]([^\'"]+)[\'"]', action_text)
            if coord_match:
                x, y = int(coord_match.group(1)), int(coord_match.group(2))
                direction = coord_match.group(3).lower()

                direction_map = {
                    "down": "down",
                    "up": "up",
                    "left": "left",
                    "right": "right"
                }

                if direction in direction_map:
                    return ActionCommand(
                        action_type="scroll",
                        parameters={
                            "direction": direction_map[direction],
                            "amount": 100,
                            "dx": 0,
                            "dy": 0,
                            "x": x,
                            "y": y
                        },
                        description=f"Scroll {direction} from coordinates ({x}, {y})"
                    )

            # Handle three-parameter format: scroll(x, y, direction)
            three_param_match = re.search(r'scroll\((\d+),\s*(\d+),\s*[\'"]?([^\'")\s]+)[\'"]?\)', action_text)
            if three_param_match:
                x, y = int(three_param_match.group(1)), int(three_param_match.group(2))
                direction = three_param_match.group(3).lower()

                direction_map = {
                    "down": "down",
                    "up": "up",
                    "left": "left",
                    "right": "right"
                }

                if direction in direction_map:
                    return ActionCommand(
                        action_type="scroll",
                        parameters={
                            "direction": direction_map[direction],
                            "amount": 100,
                            "dx": 0,
                            "dy": 0,
                            "x": x,
                            "y": y
                        },
                        description=f"Scroll {direction} from coordinates ({x}, {y})"
                    )

            # Extract direction from scroll(direction) format
            match = re.search(r'scroll\(([^)]+)\)', action_text)
            if match:
                direction = match.group(1).strip('\'"').lower()

                # Map directions to our framework
                direction_map = {
                    "down": "down",
                    "up": "up",
                    "left": "left",
                    "right": "right"
                }

                if direction in direction_map:
                    return ActionCommand(
                        action_type="scroll",
                        parameters={
                            "direction": direction_map[direction],
                            "amount": 100,  # Default scroll amount
                            "dx": 0,
                            "dy": 0
                        },
                        description=f"Scroll {direction}"
                    )

            # Also handle UITARS format: scroll(start_box='(x,y)', direction='down')
            uitars_match = re.search(r'scroll\(start_box=[\'"]?\(([\'"]?\d+),\s*(\d+[\'"]?)\)[\'"]?,\s*direction=[\'"]([^\'"]+)[\'"]', action_text)
            if uitars_match:
                x = int(uitars_match.group(1).strip('\'"'))
                y = int(uitars_match.group(2).strip('\'"'))
                direction = uitars_match.group(3).lower()

                direction_map = {
                    "down": "down",
                    "up": "up",
                    "left": "left",
                    "right": "right"
                }

                if direction in direction_map:
                    return ActionCommand(
                        action_type="scroll",
                        parameters={
                            "direction": direction_map[direction],
                            "amount": 100,  # Default scroll amount
                            "dx": 0,
                            "dy": 0,
                            "x": x,
                            "y": y
                        },
                        description=f"Scroll {direction} from coordinates ({x}, {y})"
                    )
        except Exception as e:
            logger.error(f"Error parsing scroll action: {e}")
        return None
    
    def _is_task_complete(self, action_text: str) -> bool:
        """
        Check if the task is marked as complete.

        Args:
            action_text: Action string

        Returns:
            True if task is complete
        """
        return "finish()" in action_text.lower() or "finished(" in action_text.lower()
    
    async def reset(self) -> None:
        """Reset agent state."""
        await super().reset()
        self.history_screenshots.clear()
        self.history_responses.clear()
        self.step_count = 0
        logger.info("UITARSAgent reset")
    
    def get_capabilities(self) -> List[str]:
        """Get UITARS agent capabilities."""
        return ["click", "type", "scroll", "drag", "finish", "visual_reasoning", "thought_process"]
    
    def get_info(self) -> Dict[str, Any]:
        """Get UITARS agent information."""
        info = super().get_info()
        info.update({
            "description": "UITARS agent with multi-turn conversation and local LLM deployment",
            "max_history_steps": self.max_history_steps,
            "history_n": self.history_n,
            "language": self.language,
            "model_name": self.model_name,
            "server_url": self.server_url,
            "steps_processed": self.step_count
        })
        return info
