"""Task Completion Validator for Web-based Time Selection Tasks."""

import json
from typing import Dict, List, Any, Optional, Union
from loguru import logger

from agent_eval.environment.web_environment import WebEnvironment


class TaskCompletionValidator:
    """
    Validates task completion by comparing expected success criteria 
    with actual values from the browser's getSelectedValues() function.
    """

    def __init__(self, web_environment: WebEnvironment):
        """
        Initialize the validator with a web environment.
        
        Args:
            web_environment: WebEnvironment instance for browser interaction
        """
        self.web_environment = web_environment

    async def validate_task_completion(self, success_criteria: Union[Dict[str, Any], List[str]]) -> Dict[str, Any]:
        """
        Validate task completion by comparing expected criteria with actual browser state.
        
        Args:
            success_criteria: Expected success criteria in new format or legacy format
            
        Returns:
            Dict containing validation results with keys:
            - is_valid: bool indicating if task was completed successfully
            - actual_values: values returned by getSelectedValues()
            - expected_values: expected values from success_criteria
            - validation_details: detailed comparison results
            - error_message: error message if validation failed
        """
        try:
            # Handle legacy format (list of strings) - return success for backward compatibility
            if isinstance(success_criteria, list):
                logger.warning("Legacy success_criteria format detected, skipping validation")
                return {
                    "is_valid": True,
                    "actual_values": None,
                    "expected_values": success_criteria,
                    "validation_details": "Legacy format - validation skipped",
                    "error_message": None
                }

            # Get actual values from browser
            actual_values = await self._get_selected_values_from_browser()
            if actual_values is None:
                return {
                    "is_valid": False,
                    "actual_values": None,
                    "expected_values": success_criteria,
                    "validation_details": "Failed to retrieve values from browser",
                    "error_message": "Could not execute getSelectedValues() in browser"
                }

            # Validate the structure and values
            validation_result = self._compare_values(actual_values, success_criteria)
            
            return {
                "is_valid": validation_result["is_valid"],
                "actual_values": actual_values,
                "expected_values": success_criteria,
                "validation_details": validation_result["details"],
                "error_message": validation_result.get("error_message")
            }

        except Exception as e:
            logger.error(f"Task completion validation failed: {e}")
            return {
                "is_valid": False,
                "actual_values": None,
                "expected_values": success_criteria,
                "validation_details": f"Validation error: {str(e)}",
                "error_message": str(e)
            }

    async def _get_selected_values_from_browser(self) -> Optional[Dict[str, Any]]:
        """
        Execute getSelectedValues() function in the browser and return the result.
        
        Returns:
            Dict containing the selected values or None if failed
        """
        try:
            # Execute the getSelectedValues() function in the browser
            result = await self.web_environment.execute_javascript("getSelectedValues()")
            
            if result is None:
                logger.error("getSelectedValues() returned null/undefined")
                return None
                
            # Ensure result is a dictionary with expected structure
            if not isinstance(result, dict):
                logger.error(f"getSelectedValues() returned unexpected type: {type(result)}")
                return None
                
            if "type" not in result or "values" not in result:
                logger.error(f"getSelectedValues() returned invalid structure: {result}")
                return None
                
            logger.debug(f"Retrieved selected values: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to get selected values from browser: {e}")
            return None

    def _compare_values(self, actual: Dict[str, Any], expected: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare actual values with expected success criteria.
        
        Args:
            actual: Actual values from getSelectedValues()
            expected: Expected values from success_criteria
            
        Returns:
            Dict with validation results
        """
        try:
            details = []
            
            # Check type match
            actual_type = actual.get("type")
            expected_type = expected.get("type")
            
            if actual_type != expected_type:
                return {
                    "is_valid": False,
                    "details": f"Type mismatch: expected '{expected_type}', got '{actual_type}'",
                    "error_message": f"Selection type mismatch"
                }
            
            details.append(f"Type match: {actual_type}")
            
            # Get values arrays
            actual_values = actual.get("values", [])
            expected_values = expected.get("values", [])
            
            # Check value count based on type
            if expected_type == "single":
                if len(actual_values) != 1:
                    return {
                        "is_valid": False,
                        "details": f"Single selection should have exactly 1 value, got {len(actual_values)}",
                        "error_message": "Invalid number of selected values for single selection"
                    }
                if len(expected_values) != 1:
                    return {
                        "is_valid": False,
                        "details": f"Expected single selection should have exactly 1 value, got {len(expected_values)}",
                        "error_message": "Invalid expected values configuration"
                    }
            elif expected_type == "range":
                if len(actual_values) != 2:
                    return {
                        "is_valid": False,
                        "details": f"Range selection should have exactly 2 values, got {len(actual_values)}",
                        "error_message": "Invalid number of selected values for range selection"
                    }
                if len(expected_values) != 2:
                    return {
                        "is_valid": False,
                        "details": f"Expected range selection should have exactly 2 values, got {len(expected_values)}",
                        "error_message": "Invalid expected values configuration"
                    }
            elif expected_type == "multiple":
                if len(actual_values) < 1:
                    return {
                        "is_valid": False,
                        "details": f"Multiple selection should have at least 1 value, got {len(actual_values)}",
                        "error_message": "No values selected for multiple selection"
                    }
                if len(expected_values) < 1:
                    return {
                        "is_valid": False,
                        "details": f"Expected multiple selection should have at least 1 value, got {len(expected_values)}",
                        "error_message": "Invalid expected values configuration"
                    }
            
            details.append(f"Value count check passed: {len(actual_values)} values")
            
            # Compare individual values
            value_matches = []
            for i, (actual_val, expected_val) in enumerate(zip(actual_values, expected_values)):
                match_result = self._compare_single_value(actual_val, expected_val, i)
                value_matches.append(match_result)
                details.append(match_result["details"])
                
                if not match_result["is_valid"]:
                    return {
                        "is_valid": False,
                        "details": "; ".join(details),
                        "error_message": match_result["error_message"]
                    }
            
            return {
                "is_valid": True,
                "details": "; ".join(details)
            }
            
        except Exception as e:
            return {
                "is_valid": False,
                "details": f"Comparison failed: {str(e)}",
                "error_message": f"Value comparison error: {str(e)}"
            }

    def _compare_single_value(self, actual: Dict[str, Any], expected: Dict[str, Any], index: int) -> Dict[str, Any]:
        """
        Compare a single value object.
        
        Args:
            actual: Single actual value object
            expected: Single expected value object
            index: Index of the value being compared
            
        Returns:
            Dict with comparison results
        """
        try:
            details = []
            
            # Check each possible field
            fields_to_check = ["date", "time", "days", "hours", "minutes", "seconds"]
            
            for field in fields_to_check:
                expected_val = expected.get(field)
                actual_val = actual.get(field)
                
                # If expected field is specified, it must match
                if expected_val is not None:
                    if actual_val != expected_val:
                        return {
                            "is_valid": False,
                            "details": f"Value {index}: {field} mismatch - expected {expected_val}, got {actual_val}",
                            "error_message": f"Field '{field}' does not match expected value"
                        }
                    details.append(f"{field}={actual_val}")
            
            return {
                "is_valid": True,
                "details": f"Value {index}: {', '.join(details) if details else 'no fields to compare'}"
            }
            
        except Exception as e:
            return {
                "is_valid": False,
                "details": f"Value {index}: comparison failed - {str(e)}",
                "error_message": f"Single value comparison error: {str(e)}"
            }
