import json
import re

def mcp_tools_to_tool_list(tool_list: list[dict]) -> list:
    """Convert MCP tool specifications to a list of tools following the structure of Bedrock/Claude API."""
    
    res = []
    for tool in tool_list:
        # Sanitize tool name to match Bedrock requirements
        sanitized_name = sanitize_tool_name(tool["name"])
        
        # Ensure description is not null
        description = tool.get("description", "")
        if description is None:
            description = f"Tool: {sanitized_name}"
        
        tmp = {
            "name": sanitized_name,
            "description": description,
            "input_schema": tool.get("inputSchema", {
                "type": "object",
                "properties": {},
                "required": []
            })
        }
        res.append(tmp)
    
    # Debug: Print the converted tools
    print("Converted tools structure:")
    for i, tool in enumerate(res):
        print(f"Tool {i}: name={tool['name']}, keys={list(tool.keys())}")
    
    return res

def mcp_resources_to_tool_list(resource_list: list[dict]) -> list:
    """Convert MCP resource specifications to list of tools following the structure of Bedrock/Claude API"""
    res = []
    for resource in resource_list:
        # Sanitize resource URI to create valid tool name
        sanitized_name = sanitize_tool_name(resource["uri"])
        
        # Ensure description is not null
        description = resource.get("description", "")
        if description is None:
            description = f"Resource: {sanitized_name}"
        
        tmp = {
            "name": sanitized_name,
            "description": description,
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
        res.append(tmp)
    return res

def mcp_resource_templates_to_tool_list(resource_template_list: list[dict]) -> list:
    """Convert MCP resource template specifications to list of tools following the structure of Bedrock/Claude API"""
    res = []
    for resource_template in resource_template_list:
        # Sanitize template URI to create valid tool name
        sanitized_name = sanitize_tool_name(resource_template["uriTemplate"])
        
        # Parse description
        description_parts = resource_template.get("description", "").split("|")
        des = description_parts[0] if description_parts else f"Resource template: {sanitized_name}"
        params = description_parts[1:] if len(description_parts) > 1 else []
        
        tmp = {
            "name": sanitized_name,
            "description": des,
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
        
        # Parse parameters from description
        for param in params:
            if ":" in param:
                param_parts = param.split(":")
                param_name = param_parts[0].strip()
                if len(param_parts) > 1 and "," in param_parts[1]:
                    param_info = param_parts[1].split(",")
                    param_desc = param_info[0].strip()
                    param_type = param_info[1].strip() if len(param_info) > 1 else "string"
                    
                    tmp["input_schema"]["properties"][param_name] = {
                        "type": param_type,
                        "description": param_desc
                    }
                    tmp["input_schema"]["required"].append(param_name)
        
        res.append(tmp)
    return res

def sanitize_tool_name(name: str) -> str:
    """
    Sanitize tool name to match AWS Bedrock requirements:
    - Only alphanumeric characters, hyphens, and underscores
    - Maximum 64 characters
    - Pattern: ^[a-zA-Z0-9_-]{1,64}$
    """
    # Create a mapping for common problematic names
    name_mapping = {
        "sql+db://sql/list_databases/{user_id*}": "list_databases",
        "sql+db://sql/schema/{db_name*}": "get_db_schema",
        "sql+db://sql/list_tables/{db_name*}": "list_tables",
        "rag_query": "rag_query",
        "rag_get_collection_info": "rag_get_collection_info",
        "sql_query_db": "sql_query_db",
        "chart_create_chart": "chart_create_chart"
    }
    
    # Check if we have a direct mapping
    if name in name_mapping:
        return name_mapping[name]
    
    # Generic sanitization
    # Replace problematic characters with underscores
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    
    # Remove multiple consecutive underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    
    # Ensure it's not empty
    if not sanitized:
        sanitized = "tool"
    
    # Truncate to 64 characters
    sanitized = sanitized[:64]
    
    # Ensure it matches the pattern
    if not re.match(r'^[a-zA-Z0-9_-]{1,64}$', sanitized):
        # If it still doesn't match, create a simple fallback
        sanitized = "tool_" + str(hash(name))[:10]
    
    return sanitized

def get_original_tool_name(sanitized_name: str) -> str:
    """
    Get the original tool name from the sanitized name
    """
    reverse_mapping = {
        "list_databases": "sql+db://sql/list_databases",
        "get_db_schema": "sql+db://sql/schema/{db_name*}",
        "list_tables": "sql+db://sql/list_tables/{db_name*}",
        "rag_query": "rag_query",
        "rag_get_collection_info": "rag_get_collection_info",
        "sql_query_db": "sql_query_db",
        "chart_create_chart": "chart_create_chart"
    }
    
    return reverse_mapping.get(sanitized_name, sanitized_name)

# Updated tool code lookup with sanitized names
TOOL_CODE_LOOKUP = {
    "get_db_schema": "001",
    "list_tables": "002", 
    "list_databases": "003",
    "rag_query": "004",
    "sql_query_db": "005",
}


def lookup_tool_code(name):
    return TOOL_CODE_LOOKUP.get(name, "999")  # Default code for unknown tools

