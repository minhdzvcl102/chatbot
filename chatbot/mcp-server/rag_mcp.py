import threading
import os
import time
import logging
import json
from fastmcp import FastMCP
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import chromadb.utils.embedding_functions as embedding_functions
import chromadb
from typing import Annotated
from dotenv import load_dotenv
from pydantic import Field
import boto3
import sqlite3
from botocore.exceptions import ClientError
from minio import Minio
from minio.error import S3Error
import tempfile
import shutil

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

# MinIO client setup
try:
    minio_client = Minio(
        os.getenv("MINIO_ENDPOINT"),
        access_key=os.getenv("MINIO_ACCESS_KEY"),
        secret_key=os.getenv("MINIO_SECRET_KEY"),
        secure=os.getenv("MINIO_SECURE", "false").lower() == "true"
    )
    logger.info(f"MinIO client initialized with endpoint: {os.getenv('MINIO_ENDPOINT')}")
except Exception as e:
    logger.error(f"Failed to initialize MinIO client: {str(e)}")
    minio_client = None

def get_file_from_minio(conversationId) -> str:
    """
    Download the most recent file from MinIO for a given conversationId and return local temp path.
    
    Args:
        conversationId: The ID of the conversation to query the file for.
    
    Returns:
        str: The local temporary path to the downloaded file.
    
    Raises:
        FileNotFoundError: If no file is found for the given conversationId.
        sqlite3.Error: If there's an issue with the database query.
        S3Error: If there's an issue downloading from MinIO.
    """
    try:
        # Validate conversationId
        if conversationId is None:
            raise ValueError("conversationId cannot be None")
        
        # Convert to string if it's an integer
        conversation_id_str = str(conversationId)
        logger.info(f"Looking for file with conversationId: {conversation_id_str}")
        
        # Validate MinIO client
        if minio_client is None:
            raise Exception("MinIO client is not initialized")
        
        # Validate database path
        db_path = os.getenv("SQLITE_DATABASE_PATH")
        if not db_path:
            raise ValueError("SQLITE_DATABASE_PATH environment variable is not set")
        
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database file not found at: {db_path}")
        
        # Connect to the SQLite database to get file name
        with sqlite3.connect(db_path) as sql_lite:
            cursor = sql_lite.cursor()
            sql = "SELECT fileName FROM uploaded_files WHERE conversationId = ? ORDER BY uploadedAt DESC LIMIT 1"
            cursor.execute(sql, (conversation_id_str,))
            result = cursor.fetchone()
            
            if result is None:
                # Try to list all conversationIds for debugging
                cursor.execute("SELECT DISTINCT conversationId FROM uploaded_files LIMIT 10")
                available_ids = cursor.fetchall()
                logger.warning(f"No file found for conversationId: {conversation_id_str}")
                logger.warning(f"Available conversationIds: {[row[0] for row in available_ids]}")
                raise FileNotFoundError(f"No file found for conversationId: {conversation_id_str}")
            
            file_name = result[0]
            logger.info(f"Found file: {file_name}")
            
            bucket_name = os.getenv("MINIO_BUCKET_NAME")
            if not bucket_name:
                raise ValueError("MINIO_BUCKET_NAME environment variable is not set")
            
            logger.info(f"Attempting to download {file_name} from bucket {bucket_name}")
            
            # Check if bucket exists and file exists
            try:
                # Check if object exists
                minio_client.stat_object(bucket_name, file_name)
                logger.info(f"File {file_name} exists in bucket {bucket_name}")
            except S3Error as stat_error:
                logger.error(f"File {file_name} not found in bucket {bucket_name}: {str(stat_error)}")
                raise Exception(f"File {file_name} not found in MinIO bucket {bucket_name}")
            
            # Create a temporary file
            temp_dir = tempfile.mkdtemp()
            local_file_path = os.path.join(temp_dir, file_name)
            
            # Download file from MinIO
            try:
                minio_client.fget_object(bucket_name, file_name, local_file_path)
                logger.info(f"Downloaded file {file_name} from MinIO to {local_file_path}")
                return local_file_path
            except S3Error as e:
                cleanup_temp_file(local_file_path)
                raise Exception(f"Error downloading file from MinIO: {str(e)}")
            except Exception as e:
                cleanup_temp_file(local_file_path)
                raise Exception(f"Error downloading file from MinIO: {str(e)}")
            
    except sqlite3.Error as e:
        raise Exception(f"Database error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in get_file_from_minio: {str(e)}")
        raise

def cleanup_temp_file(file_path: str):
    """Clean up temporary file and its directory"""
    try:
        if os.path.exists(file_path):
            temp_dir = os.path.dirname(file_path)
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temporary file: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to cleanup temp file {file_path}: {str(e)}")

rag_mcp = FastMCP("RAG")

client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)

class BedrockEmbeddingFunction(embedding_functions.EmbeddingFunction):
    def __init__(self, region_name: str = "us-east-1"):
        self.bedrock_client = boto3.client(
            service_name='bedrock-runtime',
            region_name=region_name
        )
        self.model_id = "amazon.titan-embed-text-v1"

    def __call__(self, input):
        try:
            embeddings = []
            for text in input:
                body = json.dumps({"inputText": text})
                response = self.bedrock_client.invoke_model(
                    body=body,
                    modelId=self.model_id,
                    accept="application/json",
                    contentType="application/json"
                )
                response_body = json.loads(response.get('body').read())
                embedding = response_body.get('embedding', [])
                embeddings.append(embedding)
            return embeddings
        except ClientError as e:
            logger.error(f"Bedrock embedding error: {e.response['Error']['Message']}")
            raise
        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            raise

bedrock_ef = BedrockEmbeddingFunction(region_name=os.getenv("AWS_REGION", "us-east-1"))

collection = client.get_or_create_collection("main", embedding_function=bedrock_ef)
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

PDF_FOLDER = os.path.join(os.path.dirname(__file__), "data")

MAX_BATCH_SIZE = 10
BATCH_DELAY_SECONDS = 0.25

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
                    loader = PyMuPDFLoader(filepath)
                    raw_docs = loader.load()
                    chunks = text_splitter.split_documents(raw_docs)

                    documents = []
                    ids = []

                    total_chunks = len(chunks)
                    for i, chunk in enumerate(chunks):
                        logger.info(f"Preparing chunk {i + 1}/{total_chunks} from file {filename}")
                        documents.append(chunk.page_content)
                        ids.append(f"{filename}_chunk_{i}")

                    for i in range(0, len(documents), MAX_BATCH_SIZE):
                        batch_docs = documents[i:i + MAX_BATCH_SIZE]
                        batch_ids = ids[i:i + MAX_BATCH_SIZE]
                        logger.info(f"Uploading batch {(i // MAX_BATCH_SIZE) + 1} with {len(batch_docs)} chunks")
                        collection.upsert(
                            documents=batch_docs,
                            ids=batch_ids
                        )
                        logger.info(f"Uploaded batch {(i // MAX_BATCH_SIZE) + 1}")
                        time.sleep(BATCH_DELAY_SECONDS)

                    logger.info(f"Processed file: {filename}, added {len(chunks)} chunks")
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

@rag_mcp.tool()
def query(
    query: Annotated[str, Field(description="Query to gather relevant context from uploaded files.")],
    n_results: Annotated[int, Field(description="Number of results to return", default=10)] = 10
) -> list:
    try:
        res = collection.query(query_texts=[query], n_results=n_results)
        logger.info(f"Query executed: {query}")

        if res["documents"] and len(res["documents"][0]) > 0:
            return [res["documents"][0][i] for i in range(len(res["documents"][0]))]
        else:
            return [{"message": "No relevant documents found"}]

    except Exception as e:
        logger.error(f"Error querying vector store: {str(e)}")
        return [{"error": str(e)}]

@rag_mcp.tool()
def summarize_pdf(conversationId: Annotated[int, Field(description="The conversation ID to retrieve the file path.")]) -> str:
    """
    Summarize a PDF file by downloading it from MinIO, extracting text content and creating a concise summary.
    """
    local_pdf_path = None
    try:
        logger.info(f"Starting summarize_pdf with conversationId: {conversationId}")
        
        # Validate input
        if conversationId is None:
            return "Error: conversationId is required"
        
        # Download file from MinIO to local temp location
        local_pdf_path = get_file_from_minio(conversationId)
        
        # Check if it's a PDF file
        if not local_pdf_path.lower().endswith('.pdf'):
            return "Error: File must be a PDF file"
        
        logger.info(f"Starting to summarize PDF: {local_pdf_path}")
        
        # Load the PDF document
        loader = PyMuPDFLoader(local_pdf_path)
        raw_docs = loader.load()
        
        if not raw_docs:
            return "Error: No content found in the PDF file"
        
        # Combine all pages content
        full_text = ""
        for doc in raw_docs:
            full_text += doc.page_content + "\n"
        
        # Basic text cleaning
        full_text = full_text.strip()
        
        if not full_text:
            return "Error: No readable text content found in the PDF"
        
        # Split into manageable chunks for processing
        chunks = text_splitter.split_text(full_text)
        
        # Create a summary based on the chunks
        # If document is short (< 2000 chars), return first portion as summary
        if len(full_text) < 2000:
            summary = full_text[:1000] + "..." if len(full_text) > 1000 else full_text
        else:
            # For longer documents, take key portions from different chunks
            summary_parts = []
            
            # Take beginning of document
            if chunks:
                summary_parts.append(chunks[0][:500])
            
            # Take middle sections if available
            if len(chunks) > 2:
                mid_chunk = chunks[len(chunks)//2]
                summary_parts.append(mid_chunk[:300])
            
            # Take end section if available
            if len(chunks) > 1:
                summary_parts.append(chunks[-1][:300])
            
            summary = "\n\n--- SECTION ---\n\n".join(summary_parts)
        
        # Get document metadata
        num_pages = len(raw_docs)
        word_count = len(full_text.split())
        char_count = len(full_text)
        
        # Format the final summary
        result = f"""
PDF SUMMARY
===========
File: {os.path.basename(local_pdf_path)}
Pages: {num_pages}
Words: {word_count:,}
Characters: {char_count:,}

CONTENT SUMMARY:
{summary}

---
Note: This is an automated extraction summary. For detailed analysis, use the query tool to search specific topics within the document.
        """.strip()
        
        logger.info(f"Successfully summarized PDF: {local_pdf_path}")
        return result
        
    except Exception as e:
        error_msg = f"Error summarizing PDF: {str(e)}"
        logger.error(f"Full error details: {type(e).__name__}: {str(e)}")
        logger.error(f"ConversationId received: {conversationId} (type: {type(conversationId)})")
        return error_msg
        
    finally:
        # Clean up temporary file
        if local_pdf_path:
            cleanup_temp_file(local_pdf_path)

@rag_mcp.tool()
def get_collection_info() -> dict:
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