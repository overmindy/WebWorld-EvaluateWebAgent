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
            - is_valid: bool indicating if task was completed successfully (all fields correct)
            - actual_values: values returned by getSelectedValues()
            - expected_values: expected values from success_criteria
            - validation_details: detailed comparison results
            - error_message: error message if validation failed
            - task_score: float (0.0-1.0) representing partial credit score
            - total_fields: int total number of fields validated
            - correct_fields: int number of fields that matched expected values
            - field_validation_details: list of per-field validation results
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
                    "error_message": None,
                    "task_score": 1.0,
                    "total_fields": 0,
                    "correct_fields": 0,
                    "field_validation_details": []
                }

            # Get actual values from browser
            actual_values = await self._get_selected_values_from_browser()
            if actual_values is None:
                return {
                    "is_valid": False,
                    "actual_values": None,
                    "expected_values": success_criteria,
                    "validation_details": "Failed to retrieve values from browser",
                    "error_message": "Could not execute getSelectedValues() in browser",
                    "task_score": 0.0,
                    "total_fields": 0,
                    "correct_fields": 0,
                    "field_validation_details": []
                }

            # Validate the structure and values
            validation_result = self._compare_values(actual_values, success_criteria)

            return {
                "is_valid": validation_result["is_valid"],
                "actual_values": actual_values,
                "expected_values": success_criteria,
                "validation_details": validation_result["details"],
                "error_message": validation_result.get("error_message"),
                "task_score": validation_result.get("task_score", 0.0),
                "total_fields": validation_result.get("total_fields", 0),
                "correct_fields": validation_result.get("correct_fields", 0),
                "field_validation_details": validation_result.get("field_validation_details", [])
            }

        except Exception as e:
            logger.error(f"Task completion validation failed: {e}")
            return {
                "is_valid": False,
                "actual_values": None,
                "expected_values": success_criteria,
                "validation_details": f"Validation error: {str(e)}",
                "error_message": str(e),
                "task_score": 0.0,
                "total_fields": 0,
                "correct_fields": 0,
                "field_validation_details": []
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
            Dict with validation results including partial scoring
        """
        try:
            details = []
            total_fields = 0
            correct_fields = 0
            field_validation_details = []

            # Check type match
            actual_type = actual.get("type")
            expected_type = expected.get("type")

            if actual_type != expected_type:
                # Count this as one field check that failed
                total_fields = 1
                correct_fields = 0
                return {
                    "is_valid": False,
                    "details": f"Type mismatch: expected '{expected_type}', got '{actual_type}'",
                    "error_message": f"Selection type mismatch",
                    "total_fields": total_fields,
                    "correct_fields": correct_fields,
                    "task_score": 0.0,
                    "field_validation_details": [{"field": "type", "expected": expected_type, "actual": actual_type, "valid": False}]
                }

            details.append(f"Type match: {actual_type}")

            # Get values arrays
            actual_values = actual.get("values", [])
            expected_values = expected.get("values", [])

            # Check value count based on type
            if expected_type == "single":
                if len(actual_values) != 1:
                    total_fields = 1  # Count structure validation as one field
                    correct_fields = 0
                    return {
                        "is_valid": False,
                        "details": f"Single selection should have exactly 1 value, got {len(actual_values)}",
                        "error_message": "Invalid number of selected values for single selection",
                        "total_fields": total_fields,
                        "correct_fields": correct_fields,
                        "task_score": 0.0,
                        "field_validation_details": [{"field": "value_count", "expected": 1, "actual": len(actual_values), "valid": False}]
                    }
                if len(expected_values) != 1:
                    total_fields = 1
                    correct_fields = 0
                    return {
                        "is_valid": False,
                        "details": f"Expected single selection should have exactly 1 value, got {len(expected_values)}",
                        "error_message": "Invalid expected values configuration",
                        "total_fields": total_fields,
                        "correct_fields": correct_fields,
                        "task_score": 0.0,
                        "field_validation_details": [{"field": "expected_value_count", "expected": 1, "actual": len(expected_values), "valid": False}]
                    }
            elif expected_type == "range":
                if len(actual_values) != 2:
                    total_fields = 1
                    correct_fields = 0
                    return {
                        "is_valid": False,
                        "details": f"Range selection should have exactly 2 values, got {len(actual_values)}",
                        "error_message": "Invalid number of selected values for range selection",
                        "total_fields": total_fields,
                        "correct_fields": correct_fields,
                        "task_score": 0.0,
                        "field_validation_details": [{"field": "value_count", "expected": 2, "actual": len(actual_values), "valid": False}]
                    }
                if len(expected_values) != 2:
                    total_fields = 1
                    correct_fields = 0
                    return {
                        "is_valid": False,
                        "details": f"Expected range selection should have exactly 2 values, got {len(expected_values)}",
                        "error_message": "Invalid expected values configuration",
                        "total_fields": total_fields,
                        "correct_fields": correct_fields,
                        "task_score": 0.0,
                        "field_validation_details": [{"field": "expected_value_count", "expected": 2, "actual": len(expected_values), "valid": False}]
                    }
            elif expected_type == "multiple":
                if len(actual_values) < 1:
                    total_fields = 1
                    correct_fields = 0
                    return {
                        "is_valid": False,
                        "details": f"Multiple selection should have at least 1 value, got {len(actual_values)}",
                        "error_message": "No values selected for multiple selection",
                        "total_fields": total_fields,
                        "correct_fields": correct_fields,
                        "task_score": 0.0,
                        "field_validation_details": [{"field": "value_count", "expected": ">=1", "actual": len(actual_values), "valid": False}]
                    }
                if len(expected_values) < 1:
                    total_fields = 1
                    correct_fields = 0
                    return {
                        "is_valid": False,
                        "details": f"Expected multiple selection should have at least 1 value, got {len(expected_values)}",
                        "error_message": "Invalid expected values configuration",
                        "total_fields": total_fields,
                        "correct_fields": correct_fields,
                        "task_score": 0.0,
                        "field_validation_details": [{"field": "expected_value_count", "expected": ">=1", "actual": len(expected_values), "valid": False}]
                    }

            details.append(f"Value count check passed: {len(actual_values)} values")

            # Compare individual values and collect field validation results
            value_matches = []
            for i, (actual_val, expected_val) in enumerate(zip(actual_values, expected_values)):
                match_result = self._compare_single_value(actual_val, expected_val, i)
                value_matches.append(match_result)
                details.append(match_result["details"])

                # Accumulate field counts and details
                total_fields += match_result.get("total_fields", 0)
                correct_fields += match_result.get("correct_fields", 0)
                field_validation_details.extend(match_result.get("field_validation_details", []))

            # Calculate task score
            task_score = correct_fields / total_fields if total_fields > 0 else 0.0
            is_valid = task_score == 1.0  # Only fully correct tasks are considered valid

            return {
                "is_valid": is_valid,
                "details": "; ".join(details),
                "total_fields": total_fields,
                "correct_fields": correct_fields,
                "task_score": task_score,
                "field_validation_details": field_validation_details
            }

        except Exception as e:
            return {
                "is_valid": False,
                "details": f"Comparison failed: {str(e)}",
                "error_message": f"Value comparison error: {str(e)}",
                "total_fields": 0,
                "correct_fields": 0,
                "task_score": 0.0,
                "field_validation_details": []
            }

    def _compare_single_value(self, actual: Dict[str, Any], expected: Dict[str, Any], index: int) -> Dict[str, Any]:
        """
        Compare a single value object.

        Args:
            actual: Single actual value object
            expected: Single expected value object
            index: Index of the value being compared

        Returns:
            Dict with comparison results including field-level validation details
        """
        try:
            details = []
            total_fields = 0
            correct_fields = 0
            field_validation_details = []

            # Check each possible field
            fields_to_check = ["date", "time", "days", "hours", "minutes", "seconds"]

            for field in fields_to_check:
                expected_val = expected.get(field)
                actual_val = actual.get(field)

                # If expected field is specified, it must be validated
                if expected_val is not None:
                    total_fields += 1
                    field_detail = {
                        "field": f"value_{index}_{field}",
                        "expected": expected_val,
                        "actual": actual_val,
                        "valid": actual_val == expected_val
                    }
                    field_validation_details.append(field_detail)

                    if actual_val == expected_val:
                        correct_fields += 1
                        details.append(f"{field}={actual_val}")
                    else:
                        details.append(f"{field}={actual_val} (expected {expected_val})")

            # Calculate if this single value is completely valid
            is_valid = correct_fields == total_fields if total_fields > 0 else True

            return {
                "is_valid": is_valid,
                "details": f"Value {index}: {', '.join(details) if details else 'no fields to compare'}",
                "total_fields": total_fields,
                "correct_fields": correct_fields,
                "field_validation_details": field_validation_details,
                "error_message": None if is_valid else f"Value {index} has {total_fields - correct_fields} incorrect field(s)"
            }

        except Exception as e:
            return {
                "is_valid": False,
                "details": f"Value {index}: comparison failed - {str(e)}",
                "error_message": f"Single value comparison error: {str(e)}",
                "total_fields": 0,
                "correct_fields": 0,
                "field_validation_details": []
            }
