
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
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

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

@sql_mcp.resource(
    "db://schema/{db_name*}",
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
        res = query_db(
            f"""
            SELECT TABLE_NAME, COLUMN_NAME, COLUMN_DEFAULT, IS_NULLABLE, COLUMN_TYPE, 
                   NUMERIC_PRECISION, NUMERIC_SCALE, DATETIME_PRECISION, COLUMN_KEY, 
                   COLUMN_COMMENT, GENERATION_EXPRESSION
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s;
            """,
            (db_name,)
        )
        if "error" in res:
            logger.error(f"Failed to fetch schema for database '{db_name}': {res['error']}")
            return None

        res = [res["headers"]] + res["data"]
        if len(res) == 1:
            logger.info(f"No schema found for database '{db_name}'")
            return None

        d = {}
        p = {}
        k = {}
        for r in res:
            if r != res[0]:
                d[r[0]] = {}
            if r[8] == 'PRI':
                p[r[1]] = r[0]
                k[r[0]] = k.get(r[0], "") + ", " + r[1] if r[0] in k else r[1]

        for r in res[1:]:
            des = f"type {r[4]}"
            if r[8] == "UNI":
                des += ", unique"
            if r[1] in p and p[r[1]] != r[0]:
                des += f", reference table '{p[r[1]]}' column '{r[1]}'"
            d[r[0]][r[1]] = des
        for table, columns in k.items():
            d[table]["primary key"] = columns
        logger.info(f"Schema retrieved for database '{db_name}'")
        return d
    except Exception as e:
        logger.error(f"Error retrieving schema for '{db_name}': {str(e)}")
        return None

@sql_mcp.resource(
    "db://list_databases",
    description="Show available databases",
    mime_type="application/json"
)
def list_databases() -> dict:
    """Returns a list of available databases, excluding system databases."""
    try:
        res = query_db("SHOW DATABASES WHERE `Database` NOT IN ('mysql', 'performance_schema', 'sys', 'information_schema')")
        if "error" in res:
            logger.error(f"Error listing databases: {res['error']}")
            return {"error": res["error"]}
        logger.info("Databases listed successfully")
        return {res["headers"][0]: res["data"]}
    except Exception as e:
        logger.error(f"Error listing databases: {str(e)}")
        return {"error": str(e)}

@sql_mcp.resource(
    "db://list_tables/{db_name*}",
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
        res = query_db(f"SHOW TABLES FROM `{db_name}`")
        if "error" in res:
            logger.error(f"Error listing tables in '{db_name}': {res['error']}")
            return {"error": res["error"]}
        logger.info(f"Tables listed for database '{db_name}'")
        return {res["headers"][0]: res["data"]}
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
