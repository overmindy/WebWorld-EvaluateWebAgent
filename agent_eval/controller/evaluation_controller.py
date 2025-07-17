"""
Central Controller Module

Orchestrates the entire evaluation workflow and coordinates communication
between environment and agent modules.
"""

import asyncio
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from loguru import logger

from ..environment.web_environment import WebEnvironment
from ..agent.base_agent import BaseAgent, AgentResponse, ActionCommand
from ..agent.human_agent import HumanAgent
from ..agent.terminal_agent import TerminalAgent
from ..agent.uitars_agent import UITARSAgent
from ..agent.uitars_pro import UITARSProAgent
from ..agent.text_agent import TextAgent
from ..validation.task_completion_validator import TaskCompletionValidator


class EvaluationSession:
    """Represents a single evaluation session."""
    
    def __init__(self, session_id: str, config: Dict[str, Any]):
        self.session_id = session_id
        self.config = config
        self.start_time = datetime.now()
        self.end_time = None
        self.status = "initialized"  # initialized, running, completed, failed
        self.steps = []
        self.results = {}
        self.error_message = None
        self.final_validation_result = None
        self.task_success = None
        self.task_score = 0.0  # Partial credit score (0.0-1.0)


class EvaluationStep:
    """Represents a single step in an evaluation session."""
    
    def __init__(self, step_id: int, screenshot_path: Optional[str] = None):
        self.step_id = step_id
        self.timestamp = datetime.now()
        self.screenshot_path = screenshot_path
        self.agent_response = None
        self.actions_executed = []
        self.success = False
        self.error_message = None
        self.duration = 0.0
        self.validation_result = None


class EvaluationController:
    """
    Central controller that orchestrates the evaluation workflow.
    
    Manages communication between environment and agent modules,
    handles configuration, logging, and error recovery.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize evaluation controller.
        
        Args:
            config: Configuration dictionary
        """
        # Load default config if none provided
        if config is None:
            try:
                from ...config.default_config import DEFAULT_CONFIG
                config = DEFAULT_CONFIG.copy()
            except ImportError:
                # Fallback to basic config if import fails
                config = {
                    "browser": {"type": "chromium", "headless": False},
                    "agent": {"type": "placeholder"},
                    "evaluation": {"max_steps": 50, "save_screenshots": True},
                    "logging": {"level": "INFO", "log_dir": "logs"}
                }
        
        self.config = config
        self.current_session: Optional[EvaluationSession] = None
        self.environment: Optional[WebEnvironment] = None
        self.agent: Optional[BaseAgent] = None
        self.task_validator: Optional[TaskCompletionValidator] = None
        self._cancelled = False
        self._log_handler_id = None  # For log handler cleanup
        
        # Setup logging
        self._setup_logging()
        
        logger.info("EvaluationController initialized")

    def cancel_evaluation(self) -> None:
        """Cancel the current evaluation."""
        self._cancelled = True
        logger.info("Evaluation cancellation requested")

    def _setup_logging(self) -> None:
        """Setup logging configuration."""
        log_config = self.config.get("logging", {})
        log_dir = Path(log_config.get("log_dir", "logs"))
        log_dir.mkdir(exist_ok=True)



        # Configure loguru - only add handler if console output is enabled
        if log_config.get("console_output", True):
            log_file = log_dir / log_config.get("log_file", "evaluation.log")

            # Add handler and store ID for later removal
            self._log_handler_id = logger.add(
                log_file,
                level=log_config.get("level", "INFO"),
                rotation="10 MB",
                retention="7 days",
                format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"
            )
    
    async def start_evaluation(self, task_description: str,
                             target_url: Optional[str] = None,
                             agent_config: Optional[Dict[str, Any]] = None,
                             run_info: Optional[Dict[str, Any]] = None) -> str:
        """
        Start a new evaluation session.

        Args:
            task_description: Description of the task to perform
            target_url: URL to navigate to (optional)
            agent_config: Agent-specific configuration (optional)
            run_info: Run information for unique session ID generation (optional)
                     Expected keys: 'task_id', 'run_number'

        Returns:
            str: Session ID
        """
        try:
            # Generate unique session ID
            import random
            timestamp = int(time.time())
            random_suffix = random.randint(1000, 9999)

            if run_info and 'task_id' in run_info and 'run_number' in run_info:
                # Include task and run info for uniqueness in multiple runs
                task_id_safe = run_info['task_id'].replace(':', '_').replace('/', '_')
                session_id = f"eval_{timestamp}_{random_suffix}_{task_id_safe}_run{run_info['run_number']}"
            else:
                # Fallback for single runs or when run_info is not provided
                session_id = f"eval_{timestamp}_{random_suffix}"
            
            # Create session
            session_config = self.config.copy()

            # Store task description directly in session config
            session_config["current_task_description"] = task_description

            if target_url:
                session_config["target_url"] = target_url
            if agent_config:
                if "agent" not in session_config:
                    session_config["agent"] = {}
                session_config["agent"].update(agent_config)
            
            self.current_session = EvaluationSession(session_id, session_config)
            
            # Initialize environment
            self.environment = WebEnvironment(session_config)
            await self.environment.initialize()

            # Initialize task completion validator
            self.task_validator = TaskCompletionValidator(self.environment)
            
            # Initialize agent
            agent_type = session_config.get("agent", {}).get("type", "human")
            if agent_type == "human":
                self.agent = HumanAgent(session_config.get("agent", {}))
            elif agent_type == "terminal":
                self.agent = TerminalAgent(session_config.get("agent", {}))
            elif agent_type == "uitars":
                self.agent = UITARSAgent(session_config.get("agent", {}))
            elif agent_type == "uitars_pro":
                self.agent = UITARSProAgent(session_config.get("agent", {}))
            elif agent_type == "text":
                self.agent = TextAgent(session_config.get("agent", {}))
                # Set WebEnvironment reference for text extraction
                if hasattr(self.agent, 'set_web_environment'):
                    self.agent.set_web_environment(self.environment)
            else:
                raise ValueError(f"Unsupported agent type: {agent_type}. Supported types: 'human', 'terminal', 'uitars', 'uitars_pro', 'text'")
            
            await self.agent.reset()

            # Navigate to target URL if provided
            if target_url:
                success = await self.environment.launch_webpage(target_url)
                if not success:
                    raise Exception(f"Failed to navigate to {target_url}")

                # Notify HumanAgent of current URL if applicable
                # Pass auto_open=False since WebEnvironment already opened the browser
                if isinstance(self.agent, HumanAgent):
                    self.agent.set_current_url(target_url, auto_open=False)
            
            self.current_session.status = "running"
            logger.info(f"Started evaluation session {session_id}")
            
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to start evaluation: {e}")
            if self.current_session:
                self.current_session.status = "failed"
                self.current_session.error_message = str(e)
            await self._cleanup()
            raise
    
    async def run_evaluation_step(self) -> bool:
        """
        Execute a single evaluation step.
        
        Returns:
            bool: True if step successful, False if failed or task complete
        """
        if not self.current_session or self.current_session.status != "running":
            logger.error("No active evaluation session")
            return False
        
        step_start_time = time.time()
        step_id = len(self.current_session.steps) + 1
        step = EvaluationStep(step_id)
        
        try:
            logger.success(f"Executing evaluation step {step_id}")

            # Check for cancellation before proceeding
            if hasattr(self, '_cancelled') and self._cancelled:
                logger.info("Evaluation step cancelled")
                return False

            # Capture screenshot
            screenshot = await self.environment.get_screenshot()
            if not screenshot:
                raise Exception("Failed to capture screenshot")

            # Save screenshot if configured
            if self.config.get("evaluation", {}).get("save_screenshots", True):
                screenshot_dir = Path(self.config.get("evaluation", {}).get("screenshot_dir", "logs/screenshots"))
                screenshot_dir.mkdir(parents=True, exist_ok=True)
                screenshot_path = screenshot_dir / f"{self.current_session.session_id}_step_{step_id}.png"
                screenshot.save(screenshot_path)
                step.screenshot_path = str(screenshot_path)

            # Check for cancellation before agent prediction
            if hasattr(self, '_cancelled') and self._cancelled:
                logger.info("Evaluation cancelled before agent prediction")
                return False

            # Get agent prediction (can be cancelled)
            task_description = self.current_session.config.get("current_task_description", "")
            try:
                agent_response = await self.agent.predict(screenshot, task_description)
            except asyncio.CancelledError:
                logger.info("Agent prediction cancelled")
                return False
            step.agent_response = agent_response
            
            # Check if task is complete
            if agent_response.task_complete:
                logger.info("Agent indicates task is complete")

                # Log completion action to indicate intentional task completion
                completion_action = {
                    "action": {
                        "action_type": "finish",
                        "parameters": {},
                        "description": "Task completed by agent",
                        "confidence": 1.0
                    },
                    "success": True
                }
                step.actions_executed.append(completion_action)
                step.success = True
                step.duration = time.time() - step_start_time
                self.current_session.steps.append(step)
                return False  # End evaluation
            
            # Execute actions through normal flow
            task_finished_by_action = False
            if agent_response.actions:
                for action in agent_response.actions:
                    # Check if this is a finish action
                    if action.action_type == "finish":
                        logger.info("Agent sent finish action - task completed")
                        step.actions_executed.append({
                            "action": action.model_dump(),
                            "success": True
                        })
                        task_finished_by_action = True
                        break

                    action_success = await self._execute_action(action)
                    step.actions_executed.append({
                        "action": action.model_dump(),
                        "success": action_success
                    })

                    if not action_success:
                        logger.warning(f"Action failed: {action}")
                    else:
                        # For TerminalAgent, provide immediate feedback
                        if isinstance(self.agent, TerminalAgent):
                            logger.info(f"✅ Action executed: {action.action_type} - {action.description}")
            
            step.success = True
            step.duration = time.time() - step_start_time
            self.current_session.steps.append(step)

            # End evaluation if finish action was executed
            if task_finished_by_action:
                return False

            # Check step limits
            max_steps = self.config.get("evaluation", {}).get("max_steps", 30)
            if len(self.current_session.steps) >= max_steps:
                logger.info(f"Reached maximum steps ({max_steps})")
                return False

            return True
            
        except Exception as e:
            logger.error(f"Evaluation step {step_id} failed: {e}")
            step.error_message = str(e)
            step.duration = time.time() - step_start_time
            self.current_session.steps.append(step)
            return False

    async def _execute_action(self, action: ActionCommand) -> bool:
        """
        Execute a single action command.

        Args:
            action: Action command to execute

        Returns:
            bool: True if action successful, False otherwise
        """
        try:
            if action.action_type == "click":
                return await self.environment.click(
                    action.parameters["x"],
                    action.parameters["y"]
                )

            elif action.action_type == "scroll":
                return await self.environment.scroll(
                    action.parameters["direction"],
                    action.parameters["amount"],
                    action.parameters.get("dx", 0),
                    action.parameters.get("dy", 0),
                    action.parameters.get("x"),
                    action.parameters.get("y")
                )

            elif action.action_type == "drag":
                return await self.environment.drag(
                    action.parameters["start_x"],
                    action.parameters["start_y"],
                    action.parameters["end_x"],
                    action.parameters["end_y"]
                )

            elif action.action_type == "input_text":
                return await self.environment.input_text(
                    action.parameters["text"],
                    action.parameters.get("element_selector"),
                    action.parameters.get("x"),
                    action.parameters.get("y"),
                    action.parameters.get("replace_mode", False)
                )

            elif action.action_type == "set_text":
                return await self.environment.set_text_at_coordinates(
                    action.parameters["text"],
                    action.parameters["x"],
                    action.parameters["y"]
                )

            elif action.action_type == "navigate":
                return await self.environment.launch_webpage(
                    action.parameters["url"]
                )

            elif action.action_type == "wait":
                await asyncio.sleep(action.parameters["duration"])
                return True

            else:
                logger.error(f"Unknown action type: {action.action_type}")
                return False

        except Exception as e:
            logger.error(f"Failed to execute action {action.action_type}: {e}")
            return False

    async def run_full_evaluation(self, task_description: str,
                                target_url: Optional[str] = None,
                                agent_config: Optional[Dict[str, Any]] = None,
                                run_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Run a complete evaluation session.

        Args:
            task_description: Description of the task to perform
            target_url: URL to navigate to (optional)
            agent_config: Agent-specific configuration (optional)
            run_info: Run information for unique session ID generation (optional)

        Returns:
            Dict[str, Any]: Evaluation results
        """
        try:
            # Start evaluation
            session_id = await self.start_evaluation(task_description, target_url, agent_config, run_info)

            # Run evaluation steps
            step_timeout = self.config.get("evaluation", {}).get("step_timeout", 150)

            while self.current_session.status == "running":
                try:
                    # Run step with timeout
                    continue_evaluation = await asyncio.wait_for(
                        self.run_evaluation_step(),
                        timeout=step_timeout
                    )

                    if not continue_evaluation:
                        break

                except asyncio.TimeoutError:
                    logger.error(f"Evaluation step timed out after {step_timeout} seconds")
                    break
                except Exception as e:
                    logger.error(f"Evaluation step failed: {e}")
                    break

            # Complete evaluation
            return await self.stop_evaluation()

        except Exception as e:
            logger.error(f"Full evaluation failed: {e}")
            if self.current_session:
                self.current_session.status = "failed"
                self.current_session.error_message = str(e)
            return await self.stop_evaluation()

    async def stop_evaluation(self) -> Dict[str, Any]:
        """
        Stop current evaluation session and return results.

        Returns:
            Dict[str, Any]: Evaluation results
        """
        if not self.current_session:
            logger.warning("No active evaluation session to stop")
            return {}

        try:
            # Mark session as completed
            self.current_session.end_time = datetime.now()
            if self.current_session.status == "running":
                self.current_session.status = "completed"

            # Perform final task validation regardless of agent's assessment
            await self._perform_final_validation()

            # Generate results
            results = self._generate_results()
            self.current_session.results = results

            # Save results
            await self._save_results()

            logger.info(f"Evaluation session {self.current_session.session_id} completed")

            return results

        except Exception as e:
            logger.error(f"Error stopping evaluation: {e}")
            return {}
        finally:
            await self._cleanup()

    async def _perform_final_validation(self):
        """
        Perform final task validation regardless of agent's assessment.
        This ensures we always validate the actual task completion.
        """
        if not self.current_session or not self.task_validator:
            return

        try:
            success_criteria = self.current_session.config.get("success_criteria")
            if not success_criteria:
                logger.info("No success criteria defined, skipping final validation")
                return

            logger.info("Performing final task validation...")
            validation_result = await self.task_validator.validate_task_completion(success_criteria)

            # Store validation result in session
            self.current_session.final_validation_result = validation_result

            # Update session success based on validation
            task_score = validation_result.get("task_score", 0.0)
            self.current_session.task_score = task_score

            if validation_result["is_valid"]:
                logger.info(f"✅ Final validation: Task completed successfully (score: {task_score:.2f})")
                self.current_session.task_success = True
            else:
                logger.info(f"❌ Final validation: Task failed (score: {task_score:.2f}) - {validation_result.get('error_message', 'Unknown error')}")
                self.current_session.task_success = False

            logger.info(f"Validation details: {validation_result['validation_details']}")

        except Exception as e:
            logger.error(f"Final validation failed with exception: {e}")
            self.current_session.final_validation_result = {
                "is_valid": False,
                "error_message": f"Validation exception: {str(e)}",
                "validation_details": "Final validation failed due to exception",
                "task_score": 0.0,
                "total_fields": 0,
                "correct_fields": 0,
                "field_validation_details": []
            }
            self.current_session.task_success = False
            self.current_session.task_score = 0.0

    def _generate_results(self) -> Dict[str, Any]:
        """Generate evaluation results summary."""
        if not self.current_session:
            return {}

        session = self.current_session
        total_steps = len(session.steps)
        successful_steps = sum(1 for step in session.steps if step.success)

        duration = (session.end_time - session.start_time).total_seconds() if session.end_time else 0

        return {
            "session_id": session.session_id,
            "status": session.status,
            "task_description": session.config.get("current_task_description", ""),
            "start_time": session.start_time.isoformat(),
            "end_time": session.end_time.isoformat() if session.end_time else None,
            "duration_seconds": duration,
            "total_steps": total_steps,
            "successful_steps": successful_steps,
            "success_rate": successful_steps / total_steps if total_steps > 0 else 0,
            "error_message": session.error_message,
            "agent_info": self.agent.get_info() if self.agent else None,
            "task_success": session.task_success,
            "task_score": session.task_score,
            "final_validation_result": session.final_validation_result,
            "steps": [
                {
                    "step_id": step.step_id,
                    "timestamp": step.timestamp.isoformat(),
                    "success": step.success,
                    "duration": step.duration,
                    "actions_count": len(step.actions_executed),
                    "actions_executed": step.actions_executed,  # Include full action details
                    "error_message": step.error_message,
                    "validation_result": getattr(step, 'validation_result', None),
                    # Include complete agent response data
                    "agent_response": {
                        "reasoning": step.agent_response.reasoning if step.agent_response else None,
                        "task_complete": step.agent_response.task_complete if step.agent_response else None,
                        "needs_more_info": step.agent_response.needs_more_info if step.agent_response else None,
                        "error_message": step.agent_response.error_message if step.agent_response else None
                    } if step.agent_response else None
                }
                for step in session.steps
            ]
        }

    async def _save_results(self) -> None:
        """Save evaluation results to file (only if enabled in config)."""
        if not self.current_session:
            return

        # Check if individual result saving is disabled (to avoid duplication)
        if not self.config.get("logging", {}).get("save_individual_session_results", True):
            logger.debug("Individual session result saving disabled")
            return

        try:
            log_dir = Path(self.config.get("logging", {}).get("log_dir", "logs"))
            log_dir.mkdir(exist_ok=True)

            results_file = log_dir / f"{self.current_session.session_id}_results.json"
            with open(results_file, 'w') as f:
                json.dump(self.current_session.results, f, indent=2)

            logger.info(f"Results saved to {results_file}")

        except Exception as e:
            logger.error(f"Failed to save results: {e}")

    async def _cleanup(self) -> None:
        """Clean up resources."""
        try:
            if self.environment:
                await self.environment.cleanup()
                self.environment = None

            if self.agent:
                await self.agent.reset()
                self.agent = None

            # Remove log handler to prevent duplication
            if hasattr(self, '_log_handler_id') and self._log_handler_id is not None:
                try:
                    logger.remove(self._log_handler_id)
                    self._log_handler_id = None
                except Exception as log_error:
                    # Don't fail cleanup if log handler removal fails
                    pass

            self.current_session = None
            logger.info("Cleanup completed")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def get_current_status(self) -> Dict[str, Any]:
        """Get current evaluation status."""
        if not self.current_session:
            return {"status": "no_active_session"}

        return {
            "session_id": self.current_session.session_id,
            "status": self.current_session.status,
            "steps_completed": len(self.current_session.steps),
            "current_step": len(self.current_session.steps) + 1 if self.current_session.status == "running" else None
        }
