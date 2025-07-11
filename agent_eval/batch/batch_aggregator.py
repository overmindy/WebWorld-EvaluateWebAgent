"""Batch Results Aggregator - Simplified and optimized."""

import json
import csv
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
from dataclasses import asdict
from loguru import logger

from .batch_config import BatchResults

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


class BatchResultsAggregator:
    """Aggregates and exports batch evaluation results."""

    def __init__(self, output_directory: Path):
        """Initialize results aggregator."""
        self.output_dir = Path(output_directory)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Results aggregator initialized: {self.output_dir}")
    
    async def save_batch_results(self, batch_results: BatchResults) -> None:
        """Save batch results to JSON file."""
        try:
            results_file = self.output_dir / f"{batch_results.batch_id}_results.json"
            results_dict = asdict(batch_results)

            # Handle datetime serialization
            if results_dict.get('start_time'):
                results_dict['start_time'] = batch_results.start_time.isoformat()
            if results_dict.get('end_time') and batch_results.end_time:
                results_dict['end_time'] = batch_results.end_time.isoformat()

            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(results_dict, f, indent=2, default=str)

            logger.info(f"Batch results saved: {results_file}")

        except Exception as e:
            logger.error(f"Failed to save batch results: {e}")
            raise
    
    async def export_results(self, batch_results: BatchResults, format_type: str) -> None:
        """Export results in specified format."""
        try:
            format_lower = format_type.lower()
            if format_lower == 'json':
                await self._export_json(batch_results)
            elif format_lower == 'csv':
                await self._export_csv(batch_results)
            elif format_lower == 'html':
                await self._export_html(batch_results)
            elif format_lower in ['excel', 'xlsx']:
                if HAS_PANDAS:
                    await self._export_excel(batch_results)
                else:
                    logger.warning("Excel export requires pandas and openpyxl. Skipping Excel export.")
            else:
                logger.warning(f"Unsupported export format: {format_type}")

        except Exception as e:
            logger.error(f"Failed to export results in {format_type} format: {e}")
            raise
    
    async def _export_json(self, batch_results: BatchResults) -> None:
        """Export results as JSON."""
        export_file = self.output_dir / f"{batch_results.batch_id}_export.json"
        
        export_data = {
            "batch_summary": {
                "batch_id": batch_results.batch_id,
                "batch_name": batch_results.batch_name,
                "start_time": batch_results.start_time.isoformat(),
                "end_time": batch_results.end_time.isoformat() if batch_results.end_time else None,
                "duration_seconds": batch_results.duration_seconds,
                "total_tasks": batch_results.total_tasks,
                "completed_tasks": batch_results.completed_tasks,
                "successful_tasks": batch_results.successful_tasks,
                "failed_tasks": batch_results.failed_tasks,
                "success_rate": batch_results.success_rate,
                "completion_rate": batch_results.completion_rate,
                "average_score": batch_results.average_score,
                "total_fields": batch_results.total_fields,
                "correct_fields": batch_results.correct_fields,
                "field_accuracy": batch_results.field_accuracy
            },
            "summary_statistics": batch_results.summary_stats,
            "individual_results": batch_results.individual_results,
            "errors": batch_results.errors,
            "metadata": batch_results.metadata
        }
        
        with open(export_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        logger.info(f"JSON export completed: {export_file}")
    
    async def _export_csv(self, batch_results: BatchResults) -> None:
        """Export results as CSV."""
        # Export summary CSV
        summary_file = self.output_dir / f"{batch_results.batch_id}_summary.csv"
        
        summary_data = [
            ["Metric", "Value"],
            ["Batch ID", batch_results.batch_id],
            ["Batch Name", batch_results.batch_name],
            ["Start Time", batch_results.start_time.isoformat()],
            ["End Time", batch_results.end_time.isoformat() if batch_results.end_time else ""],
            ["Duration (seconds)", batch_results.duration_seconds],
            ["Total Tasks", batch_results.total_tasks],
            ["Completed Tasks", batch_results.completed_tasks],
            ["Successful Tasks", batch_results.successful_tasks],
            ["Failed Tasks", batch_results.failed_tasks],
            ["Success Rate", f"{batch_results.success_rate:.2%}"],
            ["Completion Rate", f"{batch_results.completion_rate:.2%}"],
            ["Average Score", f"{batch_results.average_score:.3f}"],
            ["Total Fields", batch_results.total_fields],
            ["Correct Fields", batch_results.correct_fields],
            ["Field Accuracy", f"{batch_results.field_accuracy:.2%}"]
        ]
        
        with open(summary_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(summary_data)
        
        # Export detailed results CSV
        details_file = self.output_dir / f"{batch_results.batch_id}_details.csv"

        if batch_results.individual_results:
            # First, flatten all results to get the complete set of keys
            flattened_results = []
            all_keys = set()

            for result in batch_results.individual_results:
                flattened_result = self._flatten_dict(result)
                flattened_results.append(flattened_result)
                all_keys.update(flattened_result.keys())

            fieldnames = sorted(all_keys)

            with open(details_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for flattened_result in flattened_results:
                    writer.writerow(flattened_result)
        
        logger.info(f"CSV export completed: {summary_file}, {details_file}")
    
    async def _export_html(self, batch_results: BatchResults) -> None:
        """Export results as HTML report."""
        html_file = self.output_dir / f"{batch_results.batch_id}_report.html"
        
        html_content = self._generate_html_report(batch_results)
        
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"HTML export completed: {html_file}")
    
    async def _export_excel(self, batch_results: BatchResults) -> None:
        """Export results as Excel file (requires pandas and openpyxl)."""
        if not HAS_PANDAS:
            raise ImportError("Excel export requires pandas and openpyxl packages")

        try:
            excel_file = self.output_dir / f"{batch_results.batch_id}_results.xlsx"

            with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
                # Summary sheet
                summary_data = {
                    "Metric": ["Batch ID", "Batch Name", "Start Time", "End Time", "Duration (seconds)",
                              "Total Tasks", "Completed Tasks", "Successful Tasks", "Failed Tasks",
                              "Success Rate", "Completion Rate", "Average Score", "Total Fields",
                              "Correct Fields", "Field Accuracy"],
                    "Value": [
                        batch_results.batch_id,
                        batch_results.batch_name,
                        batch_results.start_time.isoformat(),
                        batch_results.end_time.isoformat() if batch_results.end_time else "",
                        batch_results.duration_seconds,
                        batch_results.total_tasks,
                        batch_results.completed_tasks,
                        batch_results.successful_tasks,
                        batch_results.failed_tasks,
                        f"{batch_results.success_rate:.2%}",
                        f"{batch_results.completion_rate:.2%}",
                        f"{batch_results.average_score:.3f}",
                        batch_results.total_fields,
                        batch_results.correct_fields,
                        f"{batch_results.field_accuracy:.2%}"
                    ]
                }
                
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
                
                # Individual results sheet
                if batch_results.individual_results:
                    # Flatten results for DataFrame
                    flattened_results = []
                    for result in batch_results.individual_results:
                        flattened_results.append(self._flatten_dict(result))
                    
                    results_df = pd.DataFrame(flattened_results)
                    results_df.to_excel(writer, sheet_name='Individual Results', index=False)
                
                # Statistics sheet
                if batch_results.summary_stats:
                    stats_data = []
                    for key, value in batch_results.summary_stats.items():
                        if isinstance(value, dict):
                            for sub_key, sub_value in value.items():
                                stats_data.append({"Category": key, "Metric": sub_key, "Value": sub_value})
                        else:
                            stats_data.append({"Category": "General", "Metric": key, "Value": value})
                    
                    if stats_data:
                        stats_df = pd.DataFrame(stats_data)
                        stats_df.to_excel(writer, sheet_name='Statistics', index=False)
            
            logger.info(f"Excel export completed: {excel_file}")
            
        except ImportError:
            logger.warning("pandas and openpyxl required for Excel export. Skipping Excel export.")
        except Exception as e:
            logger.error(f"Excel export failed: {e}")
    
    def _flatten_dict(self, d: Dict[str, Any], parent_key: str = '', sep: str = '_') -> Dict[str, Any]:
        """Flatten nested dictionary for CSV/Excel export."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                # Convert lists to string representation
                items.append((new_key, str(v)))
            else:
                items.append((new_key, v))
        return dict(items)

    def _generate_html_report(self, batch_results: BatchResults) -> str:
        """Generate HTML report content."""
        html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Batch Evaluation Report - {batch_results.batch_name}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .header {{
            text-align: center;
            color: #333;
            border-bottom: 2px solid #007bff;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .metric-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            border-left: 4px solid #007bff;
        }}
        .metric-value {{
            font-size: 2em;
            font-weight: bold;
            color: #007bff;
        }}
        .metric-label {{
            color: #666;
            margin-top: 5px;
        }}
        .success {{ color: #28a745; }}
        .warning {{ color: #ffc107; }}
        .danger {{ color: #dc3545; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #f8f9fa;
            font-weight: bold;
        }}
        .status-completed {{ background-color: #d4edda; color: #155724; }}
        .status-failed {{ background-color: #f8d7da; color: #721c24; }}
        .status-timeout {{ background-color: #fff3cd; color: #856404; }}
        .progress-bar {{
            width: 100%;
            height: 20px;
            background-color: #e9ecef;
            border-radius: 10px;
            overflow: hidden;
        }}
        .progress-fill {{
            height: 100%;
            background-color: #28a745;
            transition: width 0.3s ease;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Batch Evaluation Report</h1>
            <h2>{batch_results.batch_name}</h2>
            <p>Batch ID: {batch_results.batch_id}</p>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>

        <div class="summary-grid">
            <div class="metric-card">
                <div class="metric-value">{batch_results.total_tasks}</div>
                <div class="metric-label">Total Tasks</div>
            </div>
            <div class="metric-card">
                <div class="metric-value success">{batch_results.successful_tasks}</div>
                <div class="metric-label">Successful</div>
            </div>
            <div class="metric-card">
                <div class="metric-value danger">{batch_results.failed_tasks}</div>
                <div class="metric-label">Failed</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{batch_results.success_rate:.1%}</div>
                <div class="metric-label">Success Rate</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{batch_results.duration_seconds:.1f}s</div>
                <div class="metric-label">Duration</div>
            </div>
        </div>

        <div class="progress-bar">
            <div class="progress-fill" style="width: {batch_results.success_rate * 100}%"></div>
        </div>
        <p style="text-align: center; margin-top: 10px;">Overall Success Rate</p>
    </div>

    <div class="container">
        <h3>📊 Summary Statistics</h3>
        {self._generate_stats_html(batch_results.summary_stats)}
    </div>

    <div class="container">
        <h3>📝 Individual Results</h3>
        {self._generate_results_table_html(batch_results.individual_results)}
    </div>

    {self._generate_errors_html(batch_results.errors) if batch_results.errors else ""}
</body>
</html>
        """
        return html_template

    def _generate_stats_html(self, stats: Dict[str, Any]) -> str:
        """Generate HTML for statistics section."""
        if not stats:
            return "<p>No statistics available.</p>"

        html = "<table>"
        html += "<tr><th>Metric</th><th>Value</th></tr>"

        for key, value in stats.items():
            if isinstance(value, dict):
                html += f"<tr><td colspan='2'><strong>{key.replace('_', ' ').title()}</strong></td></tr>"
                for sub_key, sub_value in value.items():
                    formatted_value = f"{sub_value:.2%}" if 'rate' in sub_key.lower() else str(sub_value)
                    html += f"<tr><td>&nbsp;&nbsp;{sub_key.replace('_', ' ').title()}</td><td>{formatted_value}</td></tr>"
            else:
                formatted_value = f"{value:.2%}" if 'rate' in key.lower() else str(value)
                html += f"<tr><td>{key.replace('_', ' ').title()}</td><td>{formatted_value}</td></tr>"

        html += "</table>"
        return html

    def _generate_results_table_html(self, results: List[Dict[str, Any]]) -> str:
        """Generate HTML table for individual results."""
        if not results:
            return "<p>No individual results available.</p>"

        html = "<table>"
        html += "<tr><th>HTML File</th><th>Task</th><th>Status</th><th>Duration</th><th>Steps</th><th>Success Rate</th><th>Task Score</th><th>Field Accuracy</th></tr>"

        for result in results:
            status = result.get('status', 'unknown')
            status_class = f"status-{status}"

            duration = result.get('duration_seconds', 0)
            steps = result.get('total_steps', 0)
            success_rate = result.get('success_rate', 0)
            task_score = result.get('task_score', 0.0)

            # Calculate field accuracy for this task
            validation_result = result.get('final_validation_result', {})
            total_fields = validation_result.get('total_fields', 0)
            correct_fields = validation_result.get('correct_fields', 0)
            field_accuracy = correct_fields / total_fields if total_fields > 0 else 0.0

            html += f"""
            <tr>
                <td>{result.get('html_file_id', 'N/A')}</td>
                <td>{result.get('task_id', 'N/A')}</td>
                <td class="{status_class}">{status.title()}</td>
                <td>{duration:.1f}s</td>
                <td>{steps}</td>
                <td>{success_rate:.1%}</td>
                <td>{task_score:.3f}</td>
                <td>{field_accuracy:.1%}</td>
            </tr>
            """

        html += "</table>"
        return html

    def _generate_errors_html(self, errors: List[Dict[str, Any]]) -> str:
        """Generate HTML for errors section."""
        if not errors:
            return ""

        html = """
        <div class="container">
            <h3>⚠️ Errors</h3>
            <table>
                <tr><th>Timestamp</th><th>Type</th><th>Error</th></tr>
        """

        for error in errors:
            html += f"""
            <tr>
                <td>{error.get('timestamp', 'N/A')}</td>
                <td>{error.get('type', 'N/A')}</td>
                <td>{error.get('error', 'N/A')}</td>
            </tr>
            """

        html += "</table></div>"
        return html
