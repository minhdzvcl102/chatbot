import mysql.connector
from fastmcp import FastMCP
from typing import Annotated
from pydantic import Field
from dotenv import load_dotenv
import os
import logging
import re
import sqlite3

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"))

# Global connection variable
mydb = None
connection_error = None

def get_mysql_connection():
    """Get MySQL connection with better error handling"""
    global mydb, connection_error
    
    try:
        # Check if we already have a working connection
        if mydb and mydb.is_connected():
            return mydb
        
        # Try to establish new connection
        logger.info("Attempting to connect to MySQL database...")
        logger.info(f"MySQL Host: {os.getenv('MYSQL_HOST', 'localhost')}")
        logger.info(f"MySQL User: {os.getenv('MYSQL_USER', 'root')}")
        
        mydb = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "localhost"),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            connection_timeout=30,
            autocommit=True
        )
        
        logger.info("Successfully connected to MySQL database")
        connection_error = None
        return mydb
        
    except mysql.connector.Error as e:
        error_msg = f"MySQL connection failed: {str(e)}"
        logger.error(error_msg)
        connection_error = error_msg
        return None
    except Exception as e:
        error_msg = f"Unexpected error connecting to MySQL: {str(e)}"
        logger.error(error_msg)
        connection_error = error_msg
        return None

def check_mysql_connection():
    """Check if MySQL connection is available"""
    global connection_error
    connection = get_mysql_connection()
    if not connection:
        return False, connection_error or "MySQL Connection not available."
    return True, None

def get_database_name(user_id) -> list:
    """
    Get list of database names accessible by the user.
    """
    try:
        sqlite_path = os.getenv("SQLITE_DATABASE_PATH")
        if not sqlite_path:
            logger.error("SQLITE_DATABASE_PATH not configured")
            return []
            
        if not os.path.exists(sqlite_path):
            logger.error(f"SQLite database not found at: {sqlite_path}")
            return []
            
        logger.info(f"Connecting to SQLite database: {sqlite_path}")
        conn = sqlite3.connect(sqlite_path)
        
        query_db = """
            SELECT DISTINCT md.database_name 
            FROM user_database_permissions udp 
            JOIN mysql_databases md ON udp.database_id = md.id 
            WHERE udp.user_id = ? AND udp.is_active = 1 AND md.is_active = 1;
        """
        logger.info(f"Executing query: {query_db} with user_id: {user_id}")
        
        cursor = conn.cursor()
        cursor.execute(query_db, (user_id,))
        db_names = [row[0] for row in cursor.fetchall()]
        logger.info(f"Found {len(db_names)} databases for user {user_id}: {db_names}")
        return db_names
        
    except Exception as e:
        logger.error(f"Error fetching database names for user {user_id}: {str(e)}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()

sql_mcp = FastMCP("SQL")

def execute_multiple_queries(queries: list) -> dict:
    """Execute multiple SQL queries sequentially and return the result of the last SELECT query."""
    # Check MySQL connection first
    is_connected, error_msg = check_mysql_connection()
    if not is_connected:
        logger.error(f"MySQL connection not available: {error_msg}")
        return {"error": error_msg}
    
    cursor = None
    last_select_result = {"headers": [], "data": []}
    
    try:
        cursor = mydb.cursor()
        
        for i, query in enumerate(queries):
            query = query.strip()
            if not query:
                continue
                
            logger.info(f"Executing query {i+1}/{len(queries)}: {query}")
            cursor.execute(query)
            
            # If it's a SELECT query, capture the results
            if query.upper().strip().startswith('SELECT'):
                rows = cursor.fetchall()
                if cursor.description is not None:
                    headers = [field_md[0] for field_md in cursor.description]
                    last_select_result = {"headers": headers, "data": rows}
                    logger.info(f"SELECT query returned {len(rows)} rows")
                else:
                    logger.warning(f"SELECT query returned no metadata")
            else:
                # For non-SELECT queries (like USE), just consume any results
                if cursor.description is not None:
                    cursor.fetchall()
                logger.info(f"Non-SELECT query executed successfully")
        
        return last_select_result
        
    except mysql.connector.Error as e:
        logger.error(f"Error executing queries: {str(e)}")
        return {"error": str(e)}
    finally:
        if cursor:
            cursor.close()

@sql_mcp.tool()
def query_db(query: Annotated[str, Field(description="The SQL query to be executed, remember to fetch the schema via the tool beforehand and connect to the database")]) -> dict:
    """Execute the SQL query and return results as a dictionary."""
    
    # Split multiple queries by semicolon
    queries = [q.strip() for q in query.split(';') if q.strip()]
    
    if len(queries) > 1:
        # Multiple queries - use the special handler
        logger.info(f"Executing {len(queries)} queries: {queries}")
        return execute_multiple_queries(queries)
    else:
        # Single query - use original logic
        # Check MySQL connection first
        is_connected, error_msg = check_mysql_connection()
        if not is_connected:
            logger.error(f"MySQL connection not available: {error_msg}")
            return {"error": error_msg}
        
        cursor = None
        try:
            cursor = mydb.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            if cursor.description is None:
                logger.warning(f"Query '{query}' returned no metadata")
                return {"headers": [], "data": []}
            headers = [field_md[0] for field_md in cursor.description]
            logger.info(f"Query executed successfully: {query}")
            return {"headers": headers, "data": rows}
        except mysql.connector.Error as e:
            logger.error(f"Error executing query '{query}': {str(e)}")
            return {"error": str(e)}
        finally:
            if cursor:
                cursor.close()

def execute_query_with_params(query: str, params=None) -> dict:
    """Execute SQL query with optional parameters - internal helper function."""
    # Check MySQL connection first
    is_connected, error_msg = check_mysql_connection()
    if not is_connected:
        logger.error(f"MySQL connection not available: {error_msg}")
        return {"error": error_msg}
    
    cursor = None
    try:
        cursor = mydb.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        rows = cursor.fetchall()
        if cursor.description is None:
            logger.warning(f"Query '{query}' returned no metadata")
            return {"headers": [], "data": []}
        headers = [field_md[0] for field_md in cursor.description]
        logger.info(f"Query executed successfully: {query}")
        return {"headers": headers, "data": rows}
    except mysql.connector.Error as e:
        logger.error(f"Error executing query '{query}': {str(e)}")
        return {"error": str(e)}
    finally:
        if cursor:
            cursor.close()

@sql_mcp.resource(
    "sql+db://schema/{db_name*}",
    description="Returns a JSON describing the database schema, or None if not found|db_name:database name,string",
    mime_type="application/json"
)
def get_schema(db_name: Annotated[str, "Database name"]) -> dict:
    """Returns a JSON describing the database schema, or None if not found."""
    # Check MySQL connection first
    is_connected, error_msg = check_mysql_connection()
    if not is_connected:
        logger.error(f"MySQL connection not available: {error_msg}")
        return {"error": error_msg}
    
    # Sanitize db_name
    if not re.match(r'^[a-zA-Z0-9_]+$', db_name):
        logger.error(f"Invalid database name: {db_name}")
        return {"error": "Invalid database name"}
    try:
        # Use parameterized query for safety
        res = execute_query_with_params(
            """
            SELECT TABLE_NAME, COLUMN_NAME, COLUMN_DEFAULT, IS_NULLABLE, COLUMN_TYPE, 
                   NUMERIC_PRECISION, NUMERIC_SCALE, DATETIME_PRECISION, COLUMN_KEY, 
                   COLUMN_COMMENT, GENERATION_EXPRESSION
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s
            ORDER BY TABLE_NAME, ORDINAL_POSITION;
            """,
            (db_name,)
        )
        
        if "error" in res:
            logger.error(f"Failed to fetch schema for database '{db_name}': {res['error']}")
            return {"error": res["error"]}

        if not res["data"]:
            logger.info(f"No schema found for database '{db_name}'")
            return {"error": f"Database '{db_name}' not found or has no tables"}

        # Process schema data
        tables = {}
        primary_keys = {}
        foreign_keys = {}
        
        for row in res["data"]:
            table_name = row[0]
            column_name = row[1]
            column_default = row[2]
            is_nullable = row[3]
            column_type = row[4]
            column_key = row[8]
            column_comment = row[9]
            
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
        
        logger.info(f"Schema retrieved for database '{db_name}' with {len(tables)} tables")
        return {"database": db_name, "tables": tables}
        
    except Exception as e:
        logger.error(f"Error retrieving schema for '{db_name}': {str(e)}")
        return {"error": str(e)}

@sql_mcp.resource(
    "sql+db://list_databases/{user_id*}",
    description="Show available databases for a specific user",
    mime_type="application/json"
)
def list_databases(user_id) -> dict:
    """Returns a list of available databases for the user, excluding system databases."""
    logger.info(f"list_databases called with user_id: {user_id}")
    
    try:
        # Check MySQL connection first
        is_connected, error_msg = check_mysql_connection()
        if not is_connected:
            logger.error(f"MySQL connection not available for user {user_id}: {error_msg}")
            return {"error": error_msg}
        
        # Get allowed databases from get_database_name
        allowed_dbs = get_database_name(user_id)
        if not allowed_dbs:
            logger.warning(f"No databases found for user {user_id}")
            return {"databases": [], "message": f"No databases configured for user {user_id}"}
        
        logger.info(f"Allowed databases for user {user_id}: {allowed_dbs}")
        
        # Construct query to show only allowed databases
        placeholders = ','.join(['%s'] * len(allowed_dbs))
        query = f"SHOW DATABASES WHERE `Database` IN ({placeholders})"
        res = execute_query_with_params(query, allowed_dbs)
        
        if "error" in res:
            logger.error(f"Error listing databases for user {user_id}: {res['error']}")
            return {"error": res["error"]}
        
        # Extract database names from the result
        databases = [row[0] for row in res["data"]]
        logger.info(f"Found {len(databases)} accessible databases for user {user_id}: {databases}")
        return {"databases": databases, "user_id": user_id}
        
    except Exception as e:
        error_msg = f"Error listing databases for user {user_id}: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}

@sql_mcp.resource(
    "sql+db://list_tables/{db_name*}",
    description="Show tables within a database|db_name:database name,string",
    mime_type="application/json"
)
def list_tables(db_name: Annotated[str, "Database name"]) -> dict:
    """Returns a list of tables in the specified database."""
    # Check MySQL connection first
    is_connected, error_msg = check_mysql_connection()
    if not is_connected:
        logger.error(f"MySQL connection not available: {error_msg}")
        return {"error": error_msg}
    
    # Sanitize db_name
    if not re.match(r'^[a-zA-Z0-9_]+$', db_name):
        logger.error(f"Invalid database name: {db_name}")
        return {"error": "Invalid database name"}
    try:
        res = execute_query_with_params(f"SHOW TABLES FROM `{db_name}`")
        if "error" in res:
            logger.error(f"Error listing tables in '{db_name}': {res['error']}")
            return {"error": res["error"]}
        
        # Extract table names from the result
        tables = [row[0] for row in res["data"]]
        logger.info(f"Found {len(tables)} tables in database '{db_name}': {tables}")
        return {"database": db_name, "tables": tables}
        
    except Exception as e:
        logger.error(f"Error listing tables in '{db_name}': {str(e)}")
        return {"error": str(e)}

def close_connection():
    """Close the MySQL connection."""
    global mydb
    try:
        if mydb and mydb.is_connected():
            mydb.close()
            logger.info("MySQL connection closed")
    except Exception as e:
        logger.error(f"Error closing MySQL connection: {str(e)}")

# Initialize connection on import
logger.info("Initializing MySQL connection...")
get_mysql_connection()