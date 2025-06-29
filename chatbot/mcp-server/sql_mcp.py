import mysql.connector
from mysql.connector import pooling
from fastmcp import FastMCP
from typing import Annotated
from pydantic import Field
from dotenv import load_dotenv
import os
import logging
import re
import time
import threading
from contextlib import contextmanager

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"))

# Connection pool configuration
POOL_CONFIG = {
    'pool_name': 'mysql_pool',
    'pool_size': 10,  # Increased pool size
    'pool_reset_session': True,
    'host': os.getenv("MYSQL_HOST", "localhost"),
    'user': os.getenv("MYSQL_USER", "root"),
    'password': os.getenv("MYSQL_PASSWORD", ""),
    'connection_timeout': 30,
    'autocommit': True,  # Enable autocommit for faster queries
    'use_unicode': True,
    'charset': 'utf8mb4'
}

# Initialize connection pool
try:
    connection_pool = mysql.connector.pooling.MySQLConnectionPool(**POOL_CONFIG)
    logger.info(f"Successfully created MySQL connection pool with {POOL_CONFIG['pool_size']} connections")
except mysql.connector.Error as e:
    logger.error(f"Failed to create MySQL connection pool: {str(e)}")
    raise Exception(f"MySQL connection pool creation failed: {str(e)}")

sql_mcp = FastMCP("SQL")

# Query cache for frequently accessed data
query_cache = {}
schema_cache = {}
CACHE_SIZE = 200
CACHE_TTL = 600  # 10 minutes for schema cache
QUERY_CACHE_TTL = 60  # 1 minute for query cache

# Thread lock for cache operations
cache_lock = threading.RLock()

def get_cache_key(query, params=None):
    """Generate cache key for query"""
    if params:
        return f"{query}_{str(params)}"
    return query

def is_cache_valid(timestamp, ttl):
    """Check if cache entry is still valid"""
    return time.time() - timestamp < ttl

def clean_expired_cache():
    """Remove expired cache entries"""
    current_time = time.time()
    with cache_lock:
        # Clean query cache
        expired_query_keys = [
            key for key, (_, timestamp) in query_cache.items() 
            if current_time - timestamp > QUERY_CACHE_TTL
        ]
        for key in expired_query_keys:
            del query_cache[key]
            
        # Clean schema cache
        expired_schema_keys = [
            key for key, (_, timestamp) in schema_cache.items() 
            if current_time - timestamp > CACHE_TTL
        ]
        for key in expired_schema_keys:
            del schema_cache[key]

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    connection = None
    try:
        connection = connection_pool.get_connection()
        yield connection
    except mysql.connector.Error as e:
        logger.error(f"Database connection error: {str(e)}")
        raise
    finally:
        if connection and connection.is_connected():
            connection.close()

def execute_query_optimized(query: str, params=None, use_cache=True) -> dict:
    """Optimized query execution with caching and connection pooling"""
    start_time = time.time()
    
    # Check cache first
    if use_cache:
        cache_key = get_cache_key(query, params)
        with cache_lock:
            if cache_key in query_cache:
                cached_result, timestamp = query_cache[cache_key]
                if is_cache_valid(timestamp, QUERY_CACHE_TTL):
                    logger.info(f"Cache hit for query in {time.time() - start_time:.3f}s")
                    return cached_result
    
    cursor = None
    try:
        with get_db_connection() as connection:
            cursor = connection.cursor(buffered=True)  # Use buffered cursor for better performance
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            rows = cursor.fetchall()
            
            if cursor.description is None:
                result = {"headers": [], "data": []}
            else:
                headers = [field_md[0] for field_md in cursor.description]
                result = {"headers": headers, "data": rows}
            
            execution_time = time.time() - start_time
            logger.info(f"Query executed in {execution_time:.3f}s")
            
            # Cache the result
            if use_cache and execution_time > 0.1:  # Only cache slow queries
                with cache_lock:
                    if len(query_cache) >= CACHE_SIZE:
                        # Remove oldest entry
                        oldest_key = min(query_cache.keys(), key=lambda k: query_cache[k][1])
                        del query_cache[oldest_key]
                    query_cache[cache_key] = (result, time.time())
            
            return result
            
    except mysql.connector.Error as e:
        logger.error(f"Error executing query '{query}': {str(e)}")
        return {"error": str(e)}
    finally:
        if cursor:
            cursor.close()

@sql_mcp.tool()
def query_db(query: Annotated[str, Field(description="The SQL query to be executed, remember to fetch the schema via the tool beforehand and connect to the database")]) -> dict:
    """Execute the SQL query and return results as a dictionary."""
    # Clean expired cache periodically
    clean_expired_cache()
    
    # Add query optimizations
    optimized_query = query.strip()
    
    # Add LIMIT if not present in SELECT queries to prevent massive result sets
    if (optimized_query.upper().startswith('SELECT') and 
        'LIMIT' not in optimized_query.upper() and 
        'COUNT(' not in optimized_query.upper()):
        optimized_query += ' LIMIT 1000'
        logger.info(f"Added LIMIT 1000 to query for safety")
    
    return execute_query_optimized(optimized_query, use_cache=True)

@sql_mcp.tool()
def query_db_no_limit(query: Annotated[str, Field(description="Execute SQL query without automatic LIMIT - use with caution for large datasets")]) -> dict:
    """Execute SQL query without automatic LIMIT - use with caution"""
    clean_expired_cache()
    return execute_query_optimized(query.strip(), use_cache=True)

@sql_mcp.resource(
    "sql+db://schema/{db_name*}",
    description="Returns a JSON describing the database schema, or None if not found|db_name:database name,string",
    mime_type="application/json"
)
def get_schema(db_name: Annotated[str, "Database name"]) -> dict:
    """Returns a JSON describing the database schema with caching."""
    start_time = time.time()
    
    # Sanitize db_name
    if not re.match(r'^[a-zA-Z0-9_]+$', db_name):
        logger.error(f"Invalid database name: {db_name}")
        return {"error": "Invalid database name"}
    
    # Check schema cache
    with cache_lock:
        if db_name in schema_cache:
            cached_result, timestamp = schema_cache[db_name]
            if is_cache_valid(timestamp, CACHE_TTL):
                logger.info(f"Schema cache hit for {db_name} in {time.time() - start_time:.3f}s")
                return cached_result
    
    try:
        # Optimized schema query
        query = """
        SELECT TABLE_NAME, COLUMN_NAME, COLUMN_DEFAULT, IS_NULLABLE, COLUMN_TYPE, 
               COLUMN_KEY, COLUMN_COMMENT
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s
        ORDER BY TABLE_NAME, ORDINAL_POSITION;
        """
        
        res = execute_query_optimized(query, (db_name,), use_cache=False)
        
        if "error" in res:
            logger.error(f"Failed to fetch schema for database '{db_name}': {res['error']}")
            return {"error": res["error"]}

        if not res["data"]:
            logger.info(f"No schema found for database '{db_name}'")
            return {"error": f"Database '{db_name}' not found or has no tables"}

        # Process schema data efficiently
        tables = {}
        primary_keys = {}
        
        for row in res["data"]:
            table_name, column_name, column_default, is_nullable, column_type, column_key, column_comment = row[:7]
            
            if table_name not in tables:
                tables[table_name] = {}
            
            # Build column description
            column_desc = f"type {column_type}"
            if is_nullable == "NO":
                column_desc += ", NOT NULL"
            if column_default is not None:
                column_desc += f", default {column_default}"
            if column_key == "UNI":
                column_desc += ", unique"
            if column_comment:
                column_desc += f", comment: {column_comment}"
            
            tables[table_name][column_name] = column_desc
            
            # Track primary keys
            if column_key == "PRI":
                if table_name not in primary_keys:
                    primary_keys[table_name] = []
                primary_keys[table_name].append(column_name)
        
        # Add primary key information
        for table_name, pk_columns in primary_keys.items():
            tables[table_name]["primary_key"] = ", ".join(pk_columns)
        
        result = {"database": db_name, "tables": tables}
        
        # Cache the schema
        with cache_lock:
            schema_cache[db_name] = (result, time.time())
        
        execution_time = time.time() - start_time
        logger.info(f"Schema retrieved for database '{db_name}' with {len(tables)} tables in {execution_time:.3f}s")
        return result
        
    except Exception as e:
        logger.error(f"Error retrieving schema for '{db_name}': {str(e)}")
        return {"error": str(e)}

@sql_mcp.resource(
    "sql+db://list_databases",
    description="Show available databases",
    mime_type="application/json"
)
def list_databases() -> dict:
    """Returns a list of available databases with caching."""
    cache_key = "list_databases"
    
    with cache_lock:
        if cache_key in query_cache:
            cached_result, timestamp = query_cache[cache_key]
            if is_cache_valid(timestamp, CACHE_TTL):
                logger.info("Database list cache hit")
                return cached_result
    
    try:
        res = execute_query_optimized(
            "SHOW DATABASES WHERE `Database` NOT IN ('mysql', 'performance_schema', 'sys', 'information_schema')",
            use_cache=False
        )
        
        if "error" in res:
            logger.error(f"Error listing databases: {res['error']}")
            return {"error": res["error"]}
        
        databases = [row[0] for row in res["data"]]
        result = {"databases": databases}
        
        # Cache the result
        with cache_lock:
            query_cache[cache_key] = (result, time.time())
        
        logger.info(f"Found {len(databases)} databases: {databases}")
        return result
        
    except Exception as e:
        logger.error(f"Error listing databases: {str(e)}")
        return {"error": str(e)}

@sql_mcp.resource(
    "sql+db://list_tables/{db_name*}",
    description="Show tables within a database|db_name:database name,string",
    mime_type="application/json"
)
def list_tables(db_name: Annotated[str, "Database name"]) -> dict:
    """Returns a list of tables in the specified database with caching."""
    if not re.match(r'^[a-zA-Z0-9_]+$', db_name):
        logger.error(f"Invalid database name: {db_name}")
        return {"error": "Invalid database name"}
    
    cache_key = f"list_tables_{db_name}"
    
    with cache_lock:
        if cache_key in query_cache:
            cached_result, timestamp = query_cache[cache_key]
            if is_cache_valid(timestamp, CACHE_TTL):
                logger.info(f"Table list cache hit for {db_name}")
                return cached_result
    
    try:
        res = execute_query_optimized(f"SHOW TABLES FROM `{db_name}`", use_cache=False)
        
        if "error" in res:
            logger.error(f"Error listing tables in '{db_name}': {res['error']}")
            return {"error": res["error"]}
        
        tables = [row[0] for row in res["data"]]
        result = {"database": db_name, "tables": tables}
        
        # Cache the result
        with cache_lock:
            query_cache[cache_key] = (result, time.time())
        
        logger.info(f"Found {len(tables)} tables in database '{db_name}': {tables}")
        return result
        
    except Exception as e:
        logger.error(f"Error listing tables in '{db_name}': {str(e)}")
        return {"error": str(e)}

@sql_mcp.tool()
def get_db_stats() -> dict:
    """Get database performance statistics"""
    try:
        stats = {
            "connection_pool_size": connection_pool.pool_size,
            "query_cache_size": len(query_cache),
            "schema_cache_size": len(schema_cache),
            "cache_hit_info": "Caching enabled for improved performance"
        }
        return stats
    except Exception as e:
        logger.error(f"Error getting database stats: {str(e)}")
        return {"error": str(e)}

def close_connection():
    """Close all connections in the pool and clear caches."""
    try:
        # Clear caches
        with cache_lock:
            query_cache.clear()
            schema_cache.clear()
        
        # Close connection pool - Note: mysql.connector pool doesn't have explicit close method
        # Connections will be closed automatically when the process ends
        logger.info("MySQL connection pool cleanup completed")
    except Exception as e:
        logger.error(f"Error closing MySQL connections: {str(e)}")

# Periodic cache cleanup
def periodic_cache_cleanup():
    """Background thread for periodic cache cleanup"""
    while True:
        try:
            time.sleep(300)  # Clean every 5 minutes
            clean_expired_cache()
            logger.debug("Periodic cache cleanup completed")
        except Exception as e:
            logger.error(f"Error in periodic cache cleanup: {str(e)}")

# Start background cache cleanup thread
cleanup_thread = threading.Thread(target=periodic_cache_cleanup, daemon=True)
cleanup_thread.start()