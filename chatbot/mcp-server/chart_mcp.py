import os
import logging
import json
import requests
import base64
import io
from PIL import Image
import asyncio
import aiohttp

from fastmcp import FastMCP
from typing import Annotated, Literal
from pydantic import Field

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

chart_mcp = FastMCP("CHART")

# Định nghĩa thư mục để lưu ảnh biểu đồ
CHART_OUTPUT_DIR = "charts_output"
os.makedirs(CHART_OUTPUT_DIR, exist_ok=True)

# Chart.js API endpoint (sử dụng QuickChart.io - free service)
QUICKCHART_API_URL = "https://quickchart.io/chart"

@chart_mcp.tool()
def create_chart(
    data_json: Annotated[str, Field(description="JSON string of the data to plot. Expected format is a list of dictionaries, where each dictionary represents a row and keys are column names (e.g., [{'col1': 1, 'col2': 2}, {'col1': 3, 'col2': 4}]).")],
    chart_type: Annotated[Literal["line", "bar", "scatter", "pie", "doughnut"], Field(description="The type of chart to create (line, bar, scatter, pie, or doughnut).")],
    x_column: Annotated[str, Field(description="The name of the column to use for the X-axis (not needed for pie/doughnut charts).")],
    y_column: Annotated[str, Field(description="The name of the column to use for the Y-axis (not needed for pie/doughnut charts).")],
    title: Annotated[str, Field(description="The title of the chart.")],
    x_label: Annotated[str, Field(description="The label for the X-axis.", default="")],
    y_label: Annotated[str, Field(description="The label for the Y-axis.", default="")],
    width: Annotated[int, Field(description="Width of the chart in pixels.", default=800)],
    height: Annotated[int, Field(description="Height of the chart in pixels.", default=600)]
) -> dict:
    """
    Creates a chart using Chart.js API (QuickChart.io) from provided data and saves it as a PNG image file.
    Returns both the file path and base64 encoded image data.
    The data should be provided as a JSON string representing a list of dictionaries.
    """
    try:
        # Parse input data
        data = json.loads(data_json)
        
        if not data:
            return {"error": "Empty data provided."}
        
        # Prepare Chart.js configuration
        chart_config = {
            "type": chart_type,
            "data": {},
            "options": {
                "responsive": True,
                "plugins": {
                    "title": {
                        "display": True,
                        "text": title
                    },
                    "legend": {
                        "display": True
                    }
                }
            }
        }
        
        # Configure chart based on type
        if chart_type in ["pie", "doughnut"]:
            # For pie/doughnut charts, we need labels and a single dataset
            if y_column not in data[0]:
                return {"error": f"Column '{y_column}' not found in data."}
            
            labels = [str(row.get(x_column, "")) for row in data]
            values = [row.get(y_column, 0) for row in data]
            
            chart_config["data"] = {
                "labels": labels,
                "datasets": [{
                    "data": values,
                    "backgroundColor": [
                        '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', 
                        '#9966FF', '#FF9F40', '#FF6384', '#C9CBCF'
                    ][:len(values)]
                }]
            }
        elif chart_type == "scatter":
            # For scatter charts, use {x, y} format
            if x_column not in data[0] or y_column not in data[0]:
                return {"error": f"Columns '{x_column}' or '{y_column}' not found in data."}
            
            chart_data = []
            for row in data:
                chart_data.append({
                    "x": row.get(x_column),
                    "y": row.get(y_column)
                })
            
            chart_config["data"] = {
                "datasets": [{
                    "label": y_label if y_label else y_column,
                    "data": chart_data,
                    "borderColor": '#36A2EB',
                    "backgroundColor": 'rgba(54, 162, 235, 0.6)',
                    "pointRadius": 5
                }]
            }
            
            # Add scales configuration for scatter
            chart_config["options"]["scales"] = {
                "x": {
                    "type": "linear",
                    "title": {
                        "display": True,
                        "text": x_label if x_label else x_column
                    }
                },
                "y": {
                    "title": {
                        "display": True,
                        "text": y_label if y_label else y_column
                    }
                }
            }
        else:
            # For line and bar charts, use labels and data arrays
            if x_column not in data[0] or y_column not in data[0]:
                return {"error": f"Columns '{x_column}' or '{y_column}' not found in data."}
            
            # Extract labels and values separately
            labels = [str(row.get(x_column, "")) for row in data]
            values = [row.get(y_column, 0) for row in data]
            
            chart_config["data"] = {
                "labels": labels,
                "datasets": [{
                    "label": y_label if y_label else y_column,
                    "data": values,
                    "borderColor": '#36A2EB',
                    "backgroundColor": 'rgba(54, 162, 235, 0.6)' if chart_type == 'bar' else 'rgba(54, 162, 235, 0.2)',
                    "fill": chart_type == 'line',
                    "tension": 0.1 if chart_type == 'line' else 0
                }]
            }
            
            # Add scales configuration for line and bar
            chart_config["options"]["scales"] = {
                "x": {
                    "title": {
                        "display": True,
                        "text": x_label if x_label else x_column
                    }
                },
                "y": {
                    "title": {
                        "display": True,
                        "text": y_label if y_label else y_column
                    },
                    "beginAtZero": True
                }
            }
        
        # Prepare API request
        api_payload = {
            "chart": chart_config,
            "width": width,
            "height": height,
            "format": "png"
        }
        
        # Log the chart configuration for debugging
        logger.info(f"Chart configuration: {json.dumps(chart_config, indent=2)}")
        
        # Make API request to QuickChart
        logger.info(f"Sending request to QuickChart API for {chart_type} chart")
        response = requests.post(
            QUICKCHART_API_URL,
            json=api_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"QuickChart API error: {response.status_code} - {response.text}")
            return {"error": f"Chart API error: {response.status_code}"}
        
        # Get image data
        image_data = response.content
        
        # Create unique filename
        import pandas as pd
        file_name = f"{title.replace(' ', '_').replace('/', '-')}_{chart_type}_{pd.Timestamp.now().strftime('%Y%m%d%H%M%S')}.png"
        file_path = os.path.join(CHART_OUTPUT_DIR, file_name)
        
        # Save image file
        with open(file_path, 'wb') as f:
            f.write(image_data)
        
        # Convert to base64
        img_base64 = base64.b64encode(image_data).decode('utf-8')
        
        logger.info(f"Chart of type '{chart_type}' created successfully using Chart.js API and saved to '{file_path}'.")
        
        return {
            "chart_image_path": file_path,
            "chart_image_base64": img_base64,
            "message": "Chart successfully generated using Chart.js API.",
            "chart_config": chart_config  # Include config for debugging
        }
        
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON data provided: {data_json}")
        return {"error": "Invalid JSON data format."}
    except requests.RequestException as e:
        logger.error(f"Error calling Chart.js API: {str(e)}")
        return {"error": f"Failed to call Chart.js API: {str(e)}"}
    except Exception as e:
        logger.error(f"Error creating chart: {str(e)}")
        return {"error": f"Failed to create chart: {str(e)}"}

@chart_mcp.tool()
async def create_chart_async(
    data_json: Annotated[str, Field(description="JSON string of the data to plot.")],
    chart_type: Annotated[Literal["line", "bar", "scatter", "pie", "doughnut"], Field(description="The type of chart to create.")],
    x_column: Annotated[str, Field(description="The name of the column to use for the X-axis.")],
    y_column: Annotated[str, Field(description="The name of the column to use for the Y-axis.")],
    title: Annotated[str, Field(description="The title of the chart.")],
    x_label: Annotated[str, Field(description="The label for the X-axis.", default="")],
    y_label: Annotated[str, Field(description="The label for the Y-axis.", default="")],
    width: Annotated[int, Field(description="Width of the chart in pixels.", default=800)],
    height: Annotated[int, Field(description="Height of the chart in pixels.", default=600)]
) -> dict:
    """
    Async version of create_chart using aiohttp for better performance.
    """
    try:
        # Parse input data
        data = json.loads(data_json)
        
        if not data:
            return {"error": "Empty data provided."}
        
        # Prepare Chart.js configuration (same logic as sync version)
        chart_config = {
            "type": chart_type,
            "data": {},
            "options": {
                "responsive": True,
                "plugins": {
                    "title": {
                        "display": True,
                        "text": title
                    },
                    "legend": {
                        "display": True
                    }
                }
            }
        }
        
        # Configure chart based on type
        if chart_type in ["pie", "doughnut"]:
            if y_column not in data[0]:
                return {"error": f"Column '{y_column}' not found in data."}
            
            labels = [str(row.get(x_column, "")) for row in data]
            values = [row.get(y_column, 0) for row in data]
            
            chart_config["data"] = {
                "labels": labels,
                "datasets": [{
                    "data": values,
                    "backgroundColor": [
                        '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', 
                        '#9966FF', '#FF9F40', '#FF6384', '#C9CBCF'
                    ][:len(values)]
                }]
            }
        elif chart_type == "scatter":
            if x_column not in data[0] or y_column not in data[0]:
                return {"error": f"Columns '{x_column}' or '{y_column}' not found in data."}
            
            chart_data = []
            for row in data:
                chart_data.append({
                    "x": row.get(x_column),
                    "y": row.get(y_column)
                })
            
            chart_config["data"] = {
                "datasets": [{
                    "label": y_label if y_label else y_column,
                    "data": chart_data,
                    "borderColor": '#36A2EB',
                    "backgroundColor": 'rgba(54, 162, 235, 0.6)',
                    "pointRadius": 5
                }]
            }
            
            chart_config["options"]["scales"] = {
                "x": {
                    "type": "linear",
                    "title": {
                        "display": True,
                        "text": x_label if x_label else x_column
                    }
                },
                "y": {
                    "title": {
                        "display": True,
                        "text": y_label if y_label else y_column
                    }
                }
            }
        else:
            # For line and bar charts
            if x_column not in data[0] or y_column not in data[0]:
                return {"error": f"Columns '{x_column}' or '{y_column}' not found in data."}
            
            labels = [str(row.get(x_column, "")) for row in data]
            values = [row.get(y_column, 0) for row in data]
            
            chart_config["data"] = {
                "labels": labels,
                "datasets": [{
                    "label": y_label if y_label else y_column,
                    "data": values,
                    "borderColor": '#36A2EB',
                    "backgroundColor": 'rgba(54, 162, 235, 0.6)' if chart_type == 'bar' else 'rgba(54, 162, 235, 0.2)',
                    "fill": chart_type == 'line',
                    "tension": 0.1 if chart_type == 'line' else 0
                }]
            }
            
            chart_config["options"]["scales"] = {
                "x": {
                    "title": {
                        "display": True,
                        "text": x_label if x_label else x_column
                    }
                },
                "y": {
                    "title": {
                        "display": True,
                        "text": y_label if y_label else y_column
                    },
                    "beginAtZero": True
                }
            }
        
        # Prepare API request
        api_payload = {
            "chart": chart_config,
            "width": width,
            "height": height,
            "format": "png"
        }
        
        # Make async API request
        logger.info(f"Sending async request to QuickChart API for {chart_type} chart")
        async with aiohttp.ClientSession() as session:
            async with session.post(
                QUICKCHART_API_URL,
                json=api_payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"QuickChart API error: {response.status} - {error_text}")
                    return {"error": f"Chart API error: {response.status}"}
                
                image_data = await response.read()
        
        # Create unique filename
        import pandas as pd
        file_name = f"{title.replace(' ', '_').replace('/', '-')}_{chart_type}_{pd.Timestamp.now().strftime('%Y%m%d%H%M%S')}.png"
        file_path = os.path.join(CHART_OUTPUT_DIR, file_name)
        
        # Save image file
        with open(file_path, 'wb') as f:
            f.write(image_data)
        
        # Convert to base64
        img_base64 = base64.b64encode(image_data).decode('utf-8')
        
        logger.info(f"Chart of type '{chart_type}' created successfully using async Chart.js API and saved to '{file_path}'.")
        
        return {
            "chart_image_path": file_path,
            "chart_image_base64": img_base64,
            "message": "Chart successfully generated using async Chart.js API.",
            "chart_config": chart_config
        }
        
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON data provided: {data_json}")
        return {"error": "Invalid JSON data format."}
    except aiohttp.ClientError as e:
        logger.error(f"Error calling Chart.js API: {str(e)}")
        return {"error": f"Failed to call Chart.js API: {str(e)}"}
    except Exception as e:
        logger.error(f"Error creating chart: {str(e)}")
        return {"error": f"Failed to create chart: {str(e)}"}

@chart_mcp.tool()
def create_custom_chart(
    chart_config_json: Annotated[str, Field(description="Complete Chart.js configuration as JSON string")],
    title: Annotated[str, Field(description="The title of the chart for filename.")],
    width: Annotated[int, Field(description="Width of the chart in pixels.", default=800)],
    height: Annotated[int, Field(description="Height of the chart in pixels.", default=600)]
) -> dict:
    """
    Creates a chart using custom Chart.js configuration.
    This allows for more advanced chart customization.
    """
    try:
        # Parse Chart.js configuration
        chart_config = json.loads(chart_config_json)
        
        # Prepare API request
        api_payload = {
            "chart": chart_config,
            "width": width,
            "height": height,
            "format": "png"
        }
        
        # Make API request
        logger.info(f"Sending custom chart request to QuickChart API")
        response = requests.post(
            QUICKCHART_API_URL,
            json=api_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"QuickChart API error: {response.status_code} - {response.text}")
            return {"error": f"Chart API error: {response.status_code}"}
        
        # Get image data
        image_data = response.content
        
        # Create unique filename
        import pandas as pd
        chart_type = chart_config.get("type", "custom")
        file_name = f"{title.replace(' ', '_').replace('/', '-')}_{chart_type}_{pd.Timestamp.now().strftime('%Y%m%d%H%M%S')}.png"
        file_path = os.path.join(CHART_OUTPUT_DIR, file_name)
        
        # Save image file
        with open(file_path, 'wb') as f:
            f.write(image_data)
        
        # Convert to base64
        img_base64 = base64.b64encode(image_data).decode('utf-8')
        
        logger.info(f"Custom chart created successfully using Chart.js API and saved to '{file_path}'.")
        
        return {
            "chart_image_path": file_path,
            "chart_image_base64": img_base64,
            "message": "Custom chart successfully generated using Chart.js API.",
            "chart_config": chart_config
        }
        
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON configuration provided: {chart_config_json}")
        return {"error": "Invalid JSON configuration format."}
    except requests.RequestException as e:
        logger.error(f"Error calling Chart.js API: {str(e)}")
        return {"error": f"Failed to call Chart.js API: {str(e)}"}
    except Exception as e:
        logger.error(f"Error creating custom chart: {str(e)}")
        return {"error": f"Failed to create custom chart: {str(e)}"}