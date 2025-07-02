import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_chart_mcp():
    """Test function for chart_mcp functionality"""
    
    # Dữ liệu mẫu để test
    sample_data = [
        {"month": "Jan", "sales": 100, "profit": 20},
        {"month": "Feb", "sales": 150, "profit": 35},
        {"month": "Mar", "sales": 200, "profit": 50},
        {"month": "Apr", "sales": 180, "profit": 45},
        {"month": "May", "sales": 220, "profit": 60},
        {"month": "Jun", "sales": 250, "profit": 70}
    ]
    
    # Chuyển đổi dữ liệu thành JSON string
    data_json = json.dumps(sample_data)
    
    # Test cases
    test_cases = [
        {
            "name": "Line Chart - Sales Over Time",
            "params": {
                "data_json": data_json,
                "chart_type": "line",
                "x_column": "month",
                "y_column": "sales",
                "title": "Monthly Sales Trend",
                "x_label": "Month",
                "y_label": "Sales ($)"
            }
        },
        {
            "name": "Bar Chart - Profit by Month",
            "params": {
                "data_json": data_json,
                "chart_type": "bar",
                "x_column": "month",
                "y_column": "profit",
                "title": "Monthly Profit",
                "x_label": "Month",
                "y_label": "Profit ($)"
            }
        },
        {
            "name": "Scatter Plot - Sales vs Profit",
            "params": {
                "data_json": data_json,
                "chart_type": "scatter",
                "x_column": "sales",
                "y_column": "profit",
                "title": "Sales vs Profit Correlation",
                "x_label": "Sales ($)",
                "y_label": "Profit ($)"
            }
        }
    ]
    
    try:
        # Kết nối với MCP server thông qua stdio
        server_params = StdioServerParameters(
            command="python",
            args=["server.py"]
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize connection
                await session.initialize()
                
                print("=== TESTING CHART MCP ===\n")
                
                # Test từng trường hợp
                for i, test_case in enumerate(test_cases, 1):
                    print(f"Test {i}: {test_case['name']}")
                    print("-" * 50)
                    
                    try:
                        # Gọi tool create_chart
                        result = await session.call_tool(
                            "chart/create_chart",
                            test_case["params"]
                        )
                        
                        print(f"✅ Success: {result}")
                        
                    except Exception as e:
                        print(f"❌ Error: {str(e)}")
                    
                    print("\n")
                
                print("=== TEST COMPLETED ===")
                
    except Exception as e:
        print(f"❌ Connection Error: {str(e)}")
        print("Make sure the server is running with: python server.py")

# Test trực tiếp function (không qua MCP)
def test_direct_function():
    """Test trực tiếp function create_chart without MCP"""
    print("=== TESTING DIRECT FUNCTION ===\n")
    
    # Import và tạo function thực sự từ chart logic
    import os
    import matplotlib.pyplot as plt
    import pandas as pd
    
    def create_chart_direct(data_json, chart_type, x_column, y_column, title, x_label="", y_label=""):
        """Direct function implementation for testing"""
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

            # Tạo thư mục output nếu chưa có
            CHART_OUTPUT_DIR = "charts_output"
            os.makedirs(CHART_OUTPUT_DIR, exist_ok=True)
            
            # Tạo tên file
            file_name = f"{title.replace(' ', '_').replace('/', '-')}_{chart_type}_{pd.Timestamp.now().strftime('%Y%m%d%H%M%S')}.png"
            file_path = os.path.join(CHART_OUTPUT_DIR, file_name)

            # Lưu biểu đồ
            plt.savefig(file_path, format='png')
            plt.close()
            
            return {"chart_image_path": file_path, "message": "Chart successfully generated."}

        except json.JSONDecodeError:
            return {"error": "Invalid JSON data format."}
        except Exception as e:
            return {"error": f"Failed to create chart: {str(e)}"}
    
    # Dữ liệu mẫu
    sample_data = [
        {"x": 1, "y": 2},
        {"x": 2, "y": 4},
        {"x": 3, "y": 6},
        {"x": 4, "y": 8},
        {"x": 5, "y": 10}
    ]
    
    data_json = json.dumps(sample_data)
    
    # Test line chart
    print("Testing Line Chart...")
    result = create_chart_direct(
        data_json=data_json,
        chart_type="line",
        x_column="x",
        y_column="y",
        title="Simple Line Chart",
        x_label="X Values",
        y_label="Y Values"
    )
    print(f"Result: {result}\n")
    
    # Test bar chart
    print("Testing Bar Chart...")
    result = create_chart_direct(
        data_json=data_json,
        chart_type="bar",
        x_column="x",
        y_column="y",
        title="Simple Bar Chart",
        x_label="Categories",
        y_label="Values"
    )
    print(f"Result: {result}\n")
    
    # Test scatter plot
    print("Testing Scatter Plot...")
    result = create_chart_direct(
        data_json=data_json,
        chart_type="scatter",
        x_column="x",
        y_column="y",
        title="Simple Scatter Plot",
        x_label="X Values",
        y_label="Y Values"
    )
    print(f"Result: {result}\n")
    
    # Test với dữ liệu phức tạp hơn
    print("Testing Complex Data...")
    complex_data = [
        {"month": "Jan", "sales": 100, "profit": 20},
        {"month": "Feb", "sales": 150, "profit": 35},
        {"month": "Mar", "sales": 200, "profit": 50},
        {"month": "Apr", "sales": 180, "profit": 45}
    ]
    
    result = create_chart_direct(
        data_json=json.dumps(complex_data),
        chart_type="line",
        x_column="month",
        y_column="sales",
        title="Monthly Sales Trend",
        x_label="Month",
        y_label="Sales ($)"
    )
    print(f"Result: {result}\n")
    
    # Test với dữ liệu lỗi
    print("Testing Error Case...")
    result = create_chart_direct(
        data_json="invalid json",
        chart_type="line",
        x_column="x",
        y_column="y",
        title="Error Test",
        x_label="X",
        y_label="Y"
    )
    print(f"Result: {result}\n")

async def main():
    """Main function để chạy tất cả tests"""
    print("Choose test mode:")
    print("1. Test via MCP (requires server running)")
    print("2. Test direct function")
    print("3. Both")
    
    choice = input("Enter choice (1/2/3): ").strip()
    
    if choice in ["2", "3"]:
        test_direct_function()
    
    if choice in ["1", "3"]:
        await test_chart_mcp()

if __name__ == "__main__":
    # Uncomment dòng dưới nếu muốn chạy interactive
    # asyncio.run(main())
    
    # Hoặc chạy trực tiếp test function
    test_direct_function()