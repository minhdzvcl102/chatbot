
from fastmcp import FastMCP
from rag_mcp import rag_mcp
from sql_mcp import sql_mcp, close_connection

mcp = FastMCP("EmceeP")

mcp.mount("rag", rag_mcp)
mcp.mount("sql", sql_mcp)

if __name__ == "__main__":
    mcp.run(transport="stdio")
    close_connection()