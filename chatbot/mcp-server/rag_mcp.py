import threading
import json
import os
import time
import logging
import re
from datetime import datetime
from fastmcp import FastMCP
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import chromadb.utils.embedding_functions as embedding_functions
import chromadb
from typing import Annotated
from dotenv import load_dotenv
from pydantic import Field

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"))

# Tạo thư mục files đồng cấp với file code nếu chưa tồn tại
files_dir = os.path.join(os.path.dirname(__file__), "files")
if not os.path.exists(files_dir):
    os.makedirs(files_dir)
    logger.info(f"Created folder: {files_dir}")

VECTOR_STORE_PATH = os.path.join(files_dir, "chroma_db")
VECTOR_STORE_PATH = os.path.abspath(VECTOR_STORE_PATH)
logger.info(f"Vector store path: {VECTOR_STORE_PATH}")

rag_mcp = FastMCP("RAG")

# Khởi tạo client ChromaDB với persistent storage
client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)

openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key_env_var="ALIBABA_API_KEY",
    api_base=os.getenv("BASE_API_URL"),
    model_name="text-embedding-v3"
)

collection = client.get_or_create_collection("main", embedding_function=openai_ef)
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

PDF_FOLDER = os.path.join(os.path.dirname(__file__), "data")

# ========== CHART METADATA FUNCTIONS ==========

def extract_financial_data(text):
    """Trích xuất dữ liệu tài chính từ text để hỗ trợ vẽ biểu đồ"""
    financial_data = {
        "numbers": [],
        "years": [],
        "quarters": [],
        "currencies": [],
        "metrics": [],
        "trends": [],
        "comparisons": []
    }
    
    # Trích xuất số tiền (tỷ đồng, triệu USD, etc.)
    money_patterns = [
        r'(\d+(?:,\d+)*(?:\.\d+)?)\s*(tỷ|nghìn tỷ|triệu|tỷ đồng|triệu đồng|USD|VND)',
        r'(\d+(?:,\d+)*(?:\.\d+)?)\s*(billion|million|thousand)'
    ]
    
    for pattern in money_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for amount, unit in matches:
            financial_data["numbers"].append({
                "value": amount.replace(",", ""),
                "unit": unit,
                "context": "revenue" if any(keyword in text.lower() for keyword in ["doanh thu", "revenue"]) else "unknown"
            })
    
    # Trích xuất năm
    year_pattern = r'\b(20\d{2})\b'
    years = re.findall(year_pattern, text)
    financial_data["years"] = list(set(years))
    
    # Trích xuất quý
    quarter_patterns = [
        r'quý\s*(\d)',
        r'Q(\d)',
        r'quarter\s*(\d)'
    ]
    for pattern in quarter_patterns:
        quarters = re.findall(pattern, text, re.IGNORECASE)
        financial_data["quarters"].extend(quarters)
    
    # Trích xuất các chỉ số tài chính
    metrics_keywords = [
        "doanh thu", "revenue", "lợi nhuận", "profit", "tăng trưởng", "growth",
        "biên lãi", "margin", "EBITDA", "ROE", "ROA", "nợ", "debt",
        "tài sản", "assets", "vốn chủ sở hữu", "equity"
    ]
    
    for metric in metrics_keywords:
        if metric.lower() in text.lower():
            financial_data["metrics"].append(metric)
    
    # Trích xuất xu hướng (tăng/giảm)
    trend_patterns = [
        r'(tăng|giảm|tăng trưởng|suy giảm)\s*(\d+(?:\.\d+)?)\s*%',
        r'(increase|decrease|growth|decline)\s*(\d+(?:\.\d+)?)\s*%'
    ]
    
    for pattern in trend_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for direction, percentage in matches:
            financial_data["trends"].append({
                "direction": direction,
                "percentage": float(percentage),
                "type": "percentage_change"
            })
    
    # Trích xuất so sánh (so với năm trước, cùng kỳ, etc.)
    comparison_patterns = [
        r'so với\s*(năm trước|cùng kỳ|quý trước)',
        r'compared to\s*(last year|same period|previous quarter)'
    ]
    
    for pattern in comparison_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        financial_data["comparisons"].extend(matches)
    
    return financial_data

def detect_chart_type(text):
    """Phát hiện loại biểu đồ phù hợp dựa vào nội dung"""
    text_lower = text.lower()
    
    # Biểu đồ đường - cho xu hướng theo thời gian
    if any(keyword in text_lower for keyword in ['xu hướng', 'trend', 'theo thời gian', 'qua các năm', 'over time']):
        return 'line_chart'
    
    # Biểu đồ cột - cho so sánh
    elif any(keyword in text_lower for keyword in ['so sánh', 'compare', 'đối chiếu', 'phân khúc']):
        return 'bar_chart'
    
    # Biểu đồ tròn - cho tỷ lệ/cơ cấu
    elif any(keyword in text_lower for keyword in ['tỷ lệ', 'cơ cấu', 'proportion', 'structure', 'phân bổ']):
        return 'pie_chart'
    
    # Biểu đồ kết hợp - cho dữ liệu phức tạp
    elif any(keyword in text_lower for keyword in ['tổng hợp', 'phân tích tổng thể', 'comprehensive']):
        return 'combo_chart'
    
    # Default
    else:
        return 'bar_chart'

def create_chart_metadata(text, base_metadata):
    """Tạo metadata đặc biệt cho việc vẽ biểu đồ"""
    financial_data = extract_financial_data(text)
    chart_type = detect_chart_type(text)
    
    chart_metadata = {
        # Metadata gốc
        **base_metadata,
        
        # Metadata cho biểu đồ
        "chart_suitable": True if financial_data["numbers"] or financial_data["trends"] else False,
        "suggested_chart_type": chart_type,
        "data_points": len(financial_data["numbers"]),
        "time_series": bool(financial_data["years"] or financial_data["quarters"]),
        
        # Dữ liệu tài chính
        "financial_data": financial_data,
        
        # Gợi ý trục biểu đồ
        "x_axis_suggestions": financial_data["years"] + [f"Q{q}" for q in financial_data["quarters"]],
        "y_axis_suggestions": [item["context"] for item in financial_data["numbers"]],
        
        # Màu sắc gợi ý dựa trên trend
        "color_scheme": "green" if any(trend["direction"].lower() in ["tăng", "increase", "growth"] 
                                     for trend in financial_data["trends"]) else 
                       "red" if any(trend["direction"].lower() in ["giảm", "decrease", "decline"] 
                                   for trend in financial_data["trends"]) else "blue",
        
        # Độ ưu tiên hiển thị (cao hơn = quan trọng hơn)
        "chart_priority": (
            len(financial_data["numbers"]) * 2 +  # Số liệu càng nhiều càng quan trọng
            len(financial_data["trends"]) * 3 +   # Xu hướng rất quan trọng
            len(financial_data["years"]) * 1.5    # Dữ liệu theo năm cũng quan trọng
        ),
        
        # Template gợi ý cho prompt vẽ biểu đồ
        "chart_prompt_template": f"Vẽ {chart_type} cho dữ liệu về {', '.join(financial_data['metrics'])} "
                               f"với {len(financial_data['numbers'])} điểm dữ liệu từ {base_metadata.get('filename', '')}"
    }
    
    return chart_metadata

# ========== UPDATED PROCESSING FUNCTION ==========

def loadIntoVectorStoreThread():
    if not os.path.exists(PDF_FOLDER):
        os.makedirs(PDF_FOLDER)
        logger.info(f"Created PDF folder: {PDF_FOLDER}")
    
    processed_files = set()  # Theo dõi các file đã xử lý
    
    while True:
        try:
            files = [f for f in os.listdir(PDF_FOLDER) if f.lower().endswith(".pdf")]
            if not files:
                time.sleep(5)
                continue
            
            for filename in files:
                if filename in processed_files:
                    continue
                    
                filepath = os.path.join(PDF_FOLDER, filename)
                logger.info(f"Processing file: {filepath}")
                
                try:
                    loader = PyMuPDFLoader(filepath)
                    raw_docs = loader.load()
                    chunks = text_splitter.split_documents(raw_docs)
                    
                    # Chuẩn bị dữ liệu cho batch upsert
                    documents = []
                    ids = []
                    metadatas = []
                    
                    for i, chunk in enumerate(chunks):
                        # Metadata cơ bản
                        base_metadata = {
                            **chunk.metadata,
                            "filename": filename,
                            "chunk_index": i
                        }
                        
                        # Kiểm tra và tạo chart metadata nếu phù hợp
                        if any(keyword in chunk.page_content.lower() for keyword in 
                               ['doanh thu', 'lợi nhuận', 'tăng trưởng', 'biểu đồ', 'bảng', 'số liệu',
                                'revenue', 'profit', 'growth', 'chart', 'table', 'data']):
                            metadata = create_chart_metadata(chunk.page_content, base_metadata)
                            logger.info(f"Created chart metadata for chunk {i} in {filename}")
                        else:
                            metadata = base_metadata
                        
                        documents.append(chunk.page_content)
                        ids.append(f"{filename}_chunk_{i}")
                        metadatas.append(metadata)
                    
                    # Upsert tất cả chunks cùng lúc
                    collection.upsert(
                        documents=documents,
                        ids=ids,
                        metadatas=metadatas
                    )
                    
                    logger.info(f"Processed file: {filename}, added {len(chunks)} chunks")
                    processed_files.add(filename)
                    
                    # Xóa file sau khi xử lý thành công
                    os.remove(filepath)
                    logger.info(f"Removed file: {filepath}")
                    
                except Exception as e:
                    logger.error(f"Error processing file {filename}: {str(e)}")
                    # Không xóa file nếu xử lý thất bại
            
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Error in vector store thread: {str(e)}")
            time.sleep(5)

# ========== ORIGINAL TOOLS ==========

t1 = threading.Thread(target=loadIntoVectorStoreThread)
t1.daemon = True
t1.start()

@rag_mcp.tool()
def query(
    query: Annotated[str, Field(description="Query to gather relevant context from uploaded files.")]
) -> list:
    """Queries the vector store for relevant context."""
    try:
        res = collection.query(query_texts=[query], n_results=3)
        logger.info(f"Query executed: {query}")
        
        # Kiểm tra nếu có kết quả
        if res["documents"] and len(res["documents"]) > 0 and len(res["documents"][0]) > 0:
            return [
                {
                    "data": res["documents"][0][i], 
                    "metadata": res["metadatas"][0][i],
                    "distance": res["distances"][0][i] if "distances" in res else None
                } 
                for i in range(len(res["documents"][0]))
            ]
        else:
            return [{"message": "No relevant documents found"}]
            
    except Exception as e:
        logger.error(f"Error querying vector store: {str(e)}")
        return [{"error": str(e)}]

# ========== NEW CHART-SPECIFIC TOOLS ==========

@rag_mcp.tool()
def query_for_chart(
    query: Annotated[str, Field(description="Query để tìm dữ liệu phù hợp vẽ biểu đồ")],
    chart_type: Annotated[str, Field(description="Loại biểu đồ mong muốn: line_chart, bar_chart, pie_chart")] = None
) -> list:
    """Query chuyên biệt cho việc tìm dữ liệu vẽ biểu đồ"""
    try:
        # Tìm chunks có khả năng vẽ biểu đồ cao
        where_clause = {"chart_suitable": True}
        
        if chart_type:
            where_clause["suggested_chart_type"] = chart_type
        
        res = collection.query(
            query_texts=[query],
            n_results=5,
            where=where_clause
        )
        
        if res["documents"] and res["documents"][0]:
            results = []
            for i in range(len(res["documents"][0])):
                metadata = res["metadatas"][0][i]
                
                result = {
                    "content": res["documents"][0][i],
                    "metadata": metadata,
                    "chart_data": {
                        "type": metadata.get("suggested_chart_type"),
                        "financial_data": metadata.get("financial_data", {}),
                        "x_axis": metadata.get("x_axis_suggestions", []),
                        "y_axis": metadata.get("y_axis_suggestions", []),
                        "color_scheme": metadata.get("color_scheme", "blue"),
                        "priority": metadata.get("chart_priority", 0)
                    },
                    "chart_prompt": metadata.get("chart_prompt_template", ""),
                    "similarity_score": 1 - res["distances"][0][i] if "distances" in res else None
                }
                results.append(result)
            
            # Sắp xếp theo độ ưu tiên biểu đồ
            results.sort(key=lambda x: x["chart_data"]["priority"], reverse=True)
            return results
        
        return [{"message": "Không tìm thấy dữ liệu phù hợp để vẽ biểu đồ"}]
        
    except Exception as e:
        logger.error(f"Error in chart query: {str(e)}")
        return [{"error": str(e)}]

@rag_mcp.tool()
def get_collection_info() -> dict:
    """Get information about the vector store collection."""
    try:
        count = collection.count()
        
        # Thống kê các chunks có khả năng vẽ biểu đồ
        chart_suitable_count = collection.count(where={"chart_suitable": True})
        
        return {
            "total_documents": count,
            "chart_suitable_documents": chart_suitable_count,
            "collection_name": collection.name,
            "chart_capability_ratio": f"{chart_suitable_count}/{count}" if count > 0 else "0/0"
        }
    except Exception as e:
        logger.error(f"Error getting collection info: {str(e)}")
        return {"error": str(e)}

if __name__ == "__main__":
    rag_mcp.run()