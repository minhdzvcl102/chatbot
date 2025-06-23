import threading
import json
import os
import time
import logging
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
    api_key=os.getenv("ALIBABA_API_KEY"),
    api_base=os.getenv("BASE_API_URL"),
    model_name="text-embedding-v3"
)

collection = client.get_or_create_collection("main", embedding_function=openai_ef)
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

PDF_FOLDER = os.path.join(os.path.dirname(__file__), "data")

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
                        documents.append(chunk.page_content)
                        ids.append(f"{filename}_chunk_{i}")
                        metadatas.append({
                            **chunk.metadata,
                            "filename": filename,
                            "chunk_index": i
                        })
                    
                    # Upsert tất cả chunks cùng lúc (không cần embeddings parameter)
                    collection.upsert(
                        documents=documents,
                        ids=ids,
                        metadatas=metadatas
                        # Không cần embeddings parameter - ChromaDB sẽ tự tạo
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

# Thêm tool để kiểm tra trạng thái
@rag_mcp.tool()
def get_collection_info() -> dict:
    """Get information about the vector store collection."""
    try:
        count = collection.count()
        return {
            "total_documents": count,
            "collection_name": collection.name
        }
    except Exception as e:
        logger.error(f"Error getting collection info: {str(e)}")
        return {"error": str(e)}

if __name__ == "__main__":
    rag_mcp.run()