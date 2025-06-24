import mysql.connector
from fastmcp import FastMCP
from typing import Annotated
from pydantic import Field
from dotenv import load_dotenv
import os
import logging
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"))

# Initialize MySQL connection
try:
    mydb = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        connection_timeout=30
    )
    logger.info("Successfully connected to MySQL database")
except mysql.connector.Error as e:
    logger.error(f"Failed to connect to MySQL: {str(e)}")
    raise Exception(f"MySQL connection failed: {str(e)}")

sql_mcp = FastMCP("SQL")

@sql_mcp.tool()
def query_db(query: Annotated[str, Field(description="The SQL query to be executed, remember to fetch the schema via the tool beforehand and connect to the database")]) -> dict:
    """Execute the SQL query and return results as a dictionary."""
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
    "sql+db://list_databases",
    description="Show available databases",
    mime_type="application/json"
)
def list_databases() -> dict:
    """Returns a list of available databases, excluding system databases."""
    try:
        res = execute_query_with_params(
            "SHOW DATABASES WHERE `Database` NOT IN ('mysql', 'performance_schema', 'sys', 'information_schema')"
        )
        if "error" in res:
            logger.error(f"Error listing databases: {res['error']}")
            return {"error": res["error"]}
        
        # Extract database names from the result
        databases = [row[0] for row in res["data"]]
        logger.info(f"Found {len(databases)} databases: {databases}")
        return {"databases": databases}
        
    except Exception as e:
        logger.error(f"Error listing databases: {str(e)}")
        return {"error": str(e)}

@sql_mcp.resource(
    "sql+db://list_tables/{db_name*}",
    description="Show tables within a database|db_name:database name,string",
    mime_type="application/json"
)
def list_tables(db_name: Annotated[str, "Database name"]) -> dict:
    """Returns a list of tables in the specified database."""
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
    try:
        if mydb.is_connected():
            mydb.close()
            logger.info("MySQL connection closed")
    except Exception as e:
        logger.error(f"Error closing MySQL connection: {str(e)}")