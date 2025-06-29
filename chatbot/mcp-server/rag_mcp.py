import threading
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
import asyncio
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"))

files_dir = os.path.join(os.path.dirname(__file__), "files")
if not os.path.exists(files_dir):
    os.makedirs(files_dir)
    logger.info(f"Created folder: {files_dir}")

VECTOR_STORE_PATH = os.path.join(files_dir, "chroma_db")
VECTOR_STORE_PATH = os.path.abspath(VECTOR_STORE_PATH)
logger.info(f"Vector store path: {VECTOR_STORE_PATH}")

rag_mcp = FastMCP("RAG")

# Connection pool for ChromaDB
client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)

# Optimized embedding function with retry and connection pooling
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key_env_var="ALIBABA_API_KEY",
    api_base=os.getenv("BASE_API_URL"),
    model_name="text-embedding-v3"
)

collection = client.get_or_create_collection("main", embedding_function=openai_ef)
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

PDF_FOLDER = os.path.join(os.path.dirname(__file__), "data")

# Optimized batch processing
MAX_BATCH_SIZE = 50  # Increased batch size
BATCH_DELAY_SECONDS = 0.1  # Reduced delay
THREAD_POOL_SIZE = 4  # Thread pool for concurrent processing

# Create thread pool executor for non-blocking operations
executor = ThreadPoolExecutor(max_workers=THREAD_POOL_SIZE)

def loadIntoVectorStoreThread():
    if not os.path.exists(PDF_FOLDER):
        os.makedirs(PDF_FOLDER)
        logger.info(f"Created PDF folder: {PDF_FOLDER}")

    processed_files = set()

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
                    # Process file with timeout
                    start_time = time.time()
                    
                    loader = PyMuPDFLoader(filepath)
                    raw_docs = loader.load()
                    chunks = text_splitter.split_documents(raw_docs)

                    documents = []
                    ids = []
                    metadatas = []  # Add metadata for better querying

                    total_chunks = len(chunks)
                    for i, chunk in enumerate(chunks):
                        documents.append(chunk.page_content)
                        ids.append(f"{filename}_chunk_{i}")
                        # Add metadata including filename and page number
                        metadatas.append({
                            "filename": filename,
                            "chunk_id": i,
                            "page": chunk.metadata.get("page", 0) if chunk.metadata else 0
                        })

                    # Optimized batch upload with larger batches
                    for i in range(0, len(documents), MAX_BATCH_SIZE):
                        batch_docs = documents[i:i + MAX_BATCH_SIZE]
                        batch_ids = ids[i:i + MAX_BATCH_SIZE]
                        batch_metadatas = metadatas[i:i + MAX_BATCH_SIZE]
                        
                        logger.info(f"Uploading batch {(i // MAX_BATCH_SIZE) + 1} with {len(batch_docs)} chunks")
                        
                        # Use upsert with metadata
                        collection.upsert(
                            documents=batch_docs,
                            ids=batch_ids,
                            metadatas=batch_metadatas
                        )
                        
                        logger.info(f"Uploaded batch {(i // MAX_BATCH_SIZE) + 1}")
                        time.sleep(BATCH_DELAY_SECONDS)

                    processing_time = time.time() - start_time
                    logger.info(f"Processed file: {filename}, added {len(chunks)} chunks in {processing_time:.2f}s")
                    processed_files.add(filename)
                    os.remove(filepath)
                    logger.info(f"Removed file: {filepath}")

                except Exception as e:
                    logger.error(f"Error processing file {filename}: {str(e)}")

            time.sleep(1)

        except Exception as e:
            logger.error(f"Error in vector store thread: {str(e)}")
            time.sleep(5)

t1 = threading.Thread(target=loadIntoVectorStoreThread)
t1.daemon = True
t1.start()

# Cache for recent queries
query_cache = {}
CACHE_SIZE = 100
CACHE_TTL = 300  # 5 minutes

def get_cache_key(query, n_results):
    """Generate cache key for query"""
    return f"{query}_{n_results}"

def is_cache_valid(timestamp):
    """Check if cache entry is still valid"""
    return time.time() - timestamp < CACHE_TTL

@rag_mcp.tool()
def query(
    query: Annotated[str, Field(description="Query to gather relevant context from uploaded files.")]
) -> list:
    try:
        start_time = time.time()
        
        # Check cache first
        cache_key = get_cache_key(query, 3)
        if cache_key in query_cache:
            cached_result, timestamp = query_cache[cache_key]
            if is_cache_valid(timestamp):
                logger.info(f"Cache hit for query: {query}")
                return cached_result
            else:
                # Remove expired cache entry
                del query_cache[cache_key]
        
        # Execute query with optimized parameters
        res = collection.query(
            query_texts=[query], 
            n_results=3,
            include=["documents", "metadatas", "distances"]  # Include metadata and distances
        )
        
        logger.info(f"Query executed: {query} in {time.time() - start_time:.2f}s")

        if res["documents"] and len(res["documents"][0]) > 0:
            # Enhanced result format with metadata
            results = []
            for i in range(len(res["documents"][0])):
                result = {
                    "content": res["documents"][0][i],
                    "metadata": res["metadatas"][0][i] if res.get("metadatas") else {},
                    "score": 1 - res["distances"][0][i] if res.get("distances") else 1.0  # Convert distance to similarity score
                }
                results.append(result)
            
            # Cache the result
            if len(query_cache) >= CACHE_SIZE:
                # Remove oldest cache entry
                oldest_key = min(query_cache.keys(), key=lambda k: query_cache[k][1])
                del query_cache[oldest_key]
            
            query_cache[cache_key] = (results, time.time())
            return results
        else:
            return [{"message": "No relevant documents found"}]

    except Exception as e:
        logger.error(f"Error querying vector store: {str(e)}")
        return [{"error": str(e)}]

@rag_mcp.tool()
def query_with_filter(
    query: Annotated[str, Field(description="Query to gather relevant context from uploaded files.")],
    filename: Annotated[str, Field(description="Filter by specific filename (optional)", default="")],
    n_results: Annotated[int, Field(description="Number of results to return", default=3)]
) -> list:
    """Enhanced query with filtering capabilities"""
    try:
        start_time = time.time()
        
        # Build where clause for filtering
        where_clause = None
        if filename:
            where_clause = {"filename": {"$eq": filename}}
        
        res = collection.query(
            query_texts=[query], 
            n_results=n_results,
            where=where_clause,
            include=["documents", "metadatas", "distances"]
        )
        
        logger.info(f"Filtered query executed: {query} in {time.time() - start_time:.2f}s")

        if res["documents"] and len(res["documents"][0]) > 0:
            results = []
            for i in range(len(res["documents"][0])):
                result = {
                    "content": res["documents"][0][i],
                    "metadata": res["metadatas"][0][i] if res.get("metadatas") else {},
                    "score": 1 - res["distances"][0][i] if res.get("distances") else 1.0
                }
                results.append(result)
            return results
        else:
            return [{"message": "No relevant documents found"}]

    except Exception as e:
        logger.error(f"Error querying vector store with filter: {str(e)}")
        return [{"error": str(e)}]

@rag_mcp.tool()
def get_collection_info() -> dict:
    try:
        start_time = time.time()
        count = collection.count()
        
        # Get sample of metadata to understand document structure
        sample_docs = collection.get(limit=5, include=["metadatas"])
        filenames = set()
        if sample_docs.get("metadatas"):
            for metadata in sample_docs["metadatas"]:
                if metadata and "filename" in metadata:
                    filenames.add(metadata["filename"])
        
        result = {
            "total_documents": count,
            "collection_name": collection.name,
            "available_files": list(filenames),
            "query_time": f"{time.time() - start_time:.2f}s"
        }
        
        logger.info(f"Collection info retrieved in {time.time() - start_time:.2f}s")
        return result
        
    except Exception as e:
        logger.error(f"Error getting collection info: {str(e)}")
        return {"error": str(e)}

# Cleanup function for graceful shutdown
def cleanup():
    """Cleanup resources on shutdown"""
    try:
        executor.shutdown(wait=True)
        query_cache.clear()
        logger.info("RAG MCP cleanup completed")
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")

if __name__ == "__main__":
    try:
        rag_mcp.run()
    finally:
        cleanup()