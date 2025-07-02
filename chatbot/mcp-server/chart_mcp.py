import os
import logging
import json
import matplotlib.pyplot as plt
import pandas as pd
import io # Vẫn cần cho các trường hợp khác hoặc có thể bỏ nếu chỉ muốn lưu file
import base64 # Không còn cần thiết nếu chỉ trả về link, nhưng vẫn giữ nếu có các chức năng khác dùng base64

from fastmcp import FastMCP
from typing import Annotated, Literal
from pydantic import Field

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

chart_mcp = FastMCP("CHART")

# Định nghĩa thư mục để lưu ảnh biểu đồ
# Đảm bảo thư mục này tồn tại hoặc tạo nó nếu cần.
# Ví dụ: 'charts_output' trong cùng thư mục với script
CHART_OUTPUT_DIR = "charts_output"
os.makedirs(CHART_OUTPUT_DIR, exist_ok=True) # Tạo thư mục nếu nó chưa tồn tại

@chart_mcp.tool()
def create_chart(
    data_json: Annotated[str, Field(description="JSON string of the data to plot. Expected format is a list of dictionaries, where each dictionary represents a row and keys are column names (e.g., [{'col1': 1, 'col2': 2}, {'col1': 3, 'col2': 4}]).")],
    chart_type: Annotated[Literal["line", "bar", "scatter"], Field(description="The type of chart to create (line, bar, or scatter).")],
    x_column: Annotated[str, Field(description="The name of the column to use for the X-axis.")],
    y_column: Annotated[str, Field(description="The name of the column to use for the Y-axis.")],
    title: Annotated[str, Field(description="The title of the chart.")],
    x_label: Annotated[str, Field(description="The label for the X-axis.", default="")],
    y_label: Annotated[str, Field(description="The label for the Y-axis.", default="")]
) -> dict:
    """
    Creates a chart (line, bar, or scatter) from provided data and saves it as a PNG image file.
    Returns the file path of the generated image.
    The data should be provided as a JSON string representing a list of dictionaries.
    """
    try:
        data = json.loads(data_json)
        df = pd.DataFrame(data)

        if x_column not in df.columns or y_column not in df.columns:
            return {"error": f"Columns '{x_column}' or '{y_column}' not found in data."}

        plt.figure(figsize=(10, 6))

        if chart_type == "line":
            plt.plot(df[x_column], df[y_column])
        elif chart_type == "bar":
            plt.bar(df[x_column], df[y_column])
        elif chart_type == "scatter":
            plt.scatter(df[x_column], df[y_column])
        else:
            return {"error": "Unsupported chart type. Choose from 'line', 'bar', 'scatter'."}

        plt.title(title)
        plt.xlabel(x_label if x_label else x_column)
        plt.ylabel(y_label if y_label else y_column)
        plt.grid(True)
        plt.tight_layout()

        # Tạo tên tệp duy nhất cho biểu đồ
        # Có thể dùng uuid.uuid4() để đảm bảo tên tệp là duy nhất hơn
        file_name = f"{title.replace(' ', '_').replace('/', '-')}_{chart_type}_{pd.Timestamp.now().strftime('%Y%m%d%H%M%S')}.png"
        file_path = os.path.join(CHART_OUTPUT_DIR, file_name)

        # Lưu biểu đồ vào tệp
        plt.savefig(file_path, format='png')
        plt.close() # Đóng biểu đồ để giải phóng bộ nhớ
        
        logger.info(f"Chart of type '{chart_type}' created successfully and saved to '{file_path}'.")

        # Trả về đường dẫn của tệp ảnh
        return {"chart_image_path": file_path, "message": "Chart successfully generated."}

    except json.JSONDecodeError:
        logger.error(f"Invalid JSON data provided: {data_json}")
        return {"error": "Invalid JSON data format."}
    except Exception as e:
        logger.error(f"Error creating chart: {str(e)}")
        return {"error": f"Failed to create chart: {str(e)}"}

