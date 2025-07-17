"""
Simple Text-Based Agent Implementation

一个简洁的基于文本信息的Agent，专注于核心功能：
1. 提取页面文本信息（accessibility tree）
2. 构建prompt发送给LLM
3. 解析LLM响应生成ActionCommand
"""

import asyncio
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image
from loguru import logger

from .base_agent import BaseAgent, AgentResponse, ActionCommand
from .prompts.text_agent_prompts import AVAILABLE_PROMPTS


class SimpleTextAgent(BaseAgent):
    """
    简洁的文本代理，专注于核心的LLM调用逻辑
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化TextAgent"""
        super().__init__(config)
        
        # 文本提取设置
        self.observation_type = self.config.get("observation_type", "accessibility_tree")
        self.current_viewport_only = self.config.get("current_viewport_only", True)
        self.max_text_length = self.config.get("max_text_length", 4096)
        
        # LLM设置
        self.llm_provider = self.config.get("llm_provider", "openai")
        self.llm_model = self.config.get("llm_model", "gpt-4")
        self.temperature = self.config.get("temperature", 0.1)
        
        # Prompt设置
        self.prompt_type = self.config.get("prompt_type", "simple")
        self.prompt_template = AVAILABLE_PROMPTS.get(self.prompt_type, AVAILABLE_PROMPTS["simple"])
        
        # WebEnvironment引用
        self.web_environment = None
        
        # 历史记录
        self.action_history: List[str] = []
        
        logger.info(f"SimpleTextAgent initialized with prompt_type: {self.prompt_type}")

    def set_web_environment(self, web_env):
        """设置WebEnvironment实例"""
        self.web_environment = web_env
        logger.info("WebEnvironment reference set for SimpleTextAgent")

    async def predict(self, screenshot: Image.Image, task_description: str) -> AgentResponse:
        """
        核心预测方法：提取文本 -> 构建prompt -> 调用LLM -> 解析响应
        """
        try:
            logger.info(f"SimpleTextAgent processing task: {task_description[:100]}...")
            
            # 1. 提取页面文本信息
            text_info = await self._extract_page_text_info()
            if not text_info:
                return AgentResponse(
                    actions=[],
                    reasoning="No text information available",
                    task_complete=False,
                    needs_more_info=True,
                    error_message="Failed to extract page text information"
                )
            
            # 2. 构建prompt
            prompt = self._build_prompt(text_info, task_description)
            
            # 3. 调用LLM（目前是模拟实现）
            llm_response = await self._call_llm(prompt)
            
            # 4. 解析LLM响应生成ActionCommand
            actions = await self._parse_llm_response(llm_response, text_info)
            
            # 5. 生成推理说明
            reasoning = self._generate_reasoning(text_info, task_description, actions, llm_response)
            
            # 6. 判断任务是否完成
            task_complete = self._is_task_complete(llm_response, actions)
            
            # 7. 更新历史
            self._update_history(actions)
            
            return AgentResponse(
                actions=actions,
                reasoning=reasoning,
                task_complete=task_complete,
                needs_more_info=False
            )
            
        except Exception as e:
            logger.error(f"SimpleTextAgent prediction failed: {e}")
            return AgentResponse(
                actions=[],
                reasoning=f"Agent prediction failed: {str(e)}",
                task_complete=False,
                needs_more_info=False,
                error_message=str(e)
            )

    async def _extract_page_text_info(self) -> Optional[str]:
        """提取页面文本信息"""
        if not self.web_environment:
            logger.error("WebEnvironment not set")
            return None
        
        try:
            text_info = await self.web_environment.get_page_text_info(
                observation_type=self.observation_type,
                current_viewport_only=self.current_viewport_only
            )
            
            # 截断过长的文本
            if len(text_info) > self.max_text_length:
                text_info = text_info[:self.max_text_length] + "\n... (truncated)"
            
            logger.debug(f"Extracted {len(text_info)} characters of text information")
            return text_info
            
        except Exception as e:
            logger.error(f"Failed to extract page text info: {e}")
            return None

    def _build_prompt(self, text_info: str, task_description: str) -> str:
        """构建发送给LLM的prompt"""
        try:
            # 获取上一个动作的描述
            previous_action = self.action_history[-1] if self.action_history else "None"
            
            # 使用prompt模板构建完整prompt
            prompt = self.prompt_template["template"].format(
                accessibility_tree=text_info,
                objective=task_description,
                previous_action=previous_action
            )
            
            # 添加指令和示例
            full_prompt = f"{self.prompt_template['intro']}\n\n"
            
            if self.prompt_template.get("examples"):
                full_prompt += "Examples:\n"
                for example_input, example_output in self.prompt_template["examples"]:
                    full_prompt += f"\nInput:\n{example_input}\n"
                    full_prompt += f"Output:\n{example_output}\n"
            
            full_prompt += f"\nNow solve this:\n{prompt}\n"
            
            return full_prompt
            
        except Exception as e:
            logger.error(f"Failed to build prompt: {e}")
            return f"Task: {task_description}\nPage: {text_info[:500]}..."

    async def _call_llm(self, prompt: str) -> str:
        """
        调用LLM获取响应
        
        TODO: 这里需要实现真正的LLM调用
        目前是模拟实现
        """
        try:
            # 模拟LLM响应
            if "click" in prompt.lower() and "button" in prompt.lower():
                return "I need to click the button. Action: click(300, 150)"
            elif "search" in prompt.lower() and "textbox" in prompt.lower():
                return "I need to enter text in the search box. Action: input_text('search term', 400, 100, true)"
            elif "finish" in prompt.lower() or "complete" in prompt.lower():
                return "Task appears to be complete. Action: finish()"
            else:
                return "I need to analyze the page further. Action: click(400, 200)"
                
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return "Error occurred. Action: finish()"

    async def _parse_llm_response(self, llm_response: str, text_info: str) -> List[ActionCommand]:
        """解析LLM响应生成ActionCommand"""
        actions = []
        
        try:
            # 提取Action部分
            action_match = re.search(r'Action:\s*(.+)', llm_response, re.IGNORECASE)
            if not action_match:
                logger.warning("No action found in LLM response")
                return actions
            
            action_str = action_match.group(1).strip()
            
            # 解析不同类型的动作
            if action_str.startswith("click("):
                action = await self._parse_click_action(action_str, text_info)
                if action:
                    actions.append(action)
            
            elif action_str.startswith("input_text("):
                action = await self._parse_input_action(action_str, text_info)
                if action:
                    actions.append(action)
            
            elif action_str.startswith("scroll("):
                action = self._parse_scroll_action(action_str)
                if action:
                    actions.append(action)
            
            elif action_str.startswith("finish()"):
                actions.append(ActionCommand(
                    action_type="finish",
                    parameters={},
                    description="Task completed",
                    confidence=1.0
                ))
            
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
        
        return actions

    async def _parse_click_action(self, action_str: str, text_info: str) -> Optional[ActionCommand]:
        """解析点击动作"""
        try:
            # 提取坐标
            coord_match = re.search(r'click\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)', action_str)
            if coord_match:
                x, y = int(coord_match.group(1)), int(coord_match.group(2))
                return ActionCommand(
                    action_type="click",
                    parameters={"x": x, "y": y},
                    description=f"Click at coordinates ({x}, {y})",
                    confidence=0.8
                )
        except Exception as e:
            logger.error(f"Failed to parse click action: {e}")
        
        return None

    async def _parse_input_action(self, action_str: str, text_info: str) -> Optional[ActionCommand]:
        """解析输入动作"""
        try:
            # 提取文本和坐标
            input_match = re.search(r"input_text\s*\(\s*['\"]([^'\"]*)['\"]?\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*(true|false))?\s*\)", action_str)
            if input_match:
                text = input_match.group(1)
                x, y = int(input_match.group(2)), int(input_match.group(3))
                replace_mode = input_match.group(4) == "true" if input_match.group(4) else True
                
                return ActionCommand(
                    action_type="input_text",
                    parameters={
                        "text": text,
                        "x": x,
                        "y": y,
                        "replace_mode": replace_mode
                    },
                    description=f"Input '{text}' at coordinates ({x}, {y})",
                    confidence=0.8
                )
        except Exception as e:
            logger.error(f"Failed to parse input action: {e}")
        
        return None

    def _parse_scroll_action(self, action_str: str) -> Optional[ActionCommand]:
        """解析滚动动作"""
        try:
            scroll_match = re.search(r"scroll\s*\(\s*['\"]?(\w+)['\"]?\s*,\s*(\d+)\s*\)", action_str)
            if scroll_match:
                direction, amount = scroll_match.group(1), int(scroll_match.group(2))
                return ActionCommand(
                    action_type="scroll",
                    parameters={
                        "direction": direction,
                        "amount": amount,
                        "dx": 0,
                        "dy": 0,
                        "x": None,
                        "y": None
                    },
                    description=f"Scroll {direction} by {amount}",
                    confidence=0.7
                )
        except Exception as e:
            logger.error(f"Failed to parse scroll action: {e}")
        
        return None

    def _generate_reasoning(self, text_info: str, task_description: str, actions: List[ActionCommand], llm_response: str) -> str:
        """生成推理说明"""
        reasoning_parts = []
        reasoning_parts.append(f"Task: {task_description}")
        reasoning_parts.append(f"Page text length: {len(text_info)} characters")
        reasoning_parts.append(f"LLM response: {llm_response[:200]}...")
        
        if actions:
            reasoning_parts.append(f"Generated {len(actions)} action(s):")
            for i, action in enumerate(actions, 1):
                reasoning_parts.append(f"  {i}. {action.description}")
        else:
            reasoning_parts.append("No actions generated")
        
        return "\n".join(reasoning_parts)

    def _is_task_complete(self, llm_response: str, actions: List[ActionCommand]) -> bool:
        """判断任务是否完成"""
        # 检查是否有finish动作
        for action in actions:
            if action.action_type == "finish":
                return True
        
        # 检查LLM响应中的完成指示
        completion_keywords = ["complete", "done", "finished", "success"]
        return any(keyword in llm_response.lower() for keyword in completion_keywords)

    def _update_history(self, actions: List[ActionCommand]) -> None:
        """更新动作历史"""
        for action in actions:
            self.action_history.append(action.description or f"{action.action_type}")
        
        # 保持历史记录在合理范围内
        if len(self.action_history) > 10:
            self.action_history = self.action_history[-10:]
