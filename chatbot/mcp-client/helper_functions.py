import json
def mcp_tools_to_tool_list(tool_list: list[dict]) -> list:
  """Convert MCP tool specifications to a list of tools following the structure of OpenAI SDK tool declaration."""

  res = []
  for tool in tool_list:
    tmp = {
      "type": "function",
      "function": {
        "name": tool["name"],
        "description": tool["description"],
      }
    }
    if len(tool["inputSchema"]["properties"].items()) == 0:
      res.append(tmp)
      continue
    tmp["function"]["parameters"] = {
      "type": "object",
      "properties": {},
      "required": tool["inputSchema"]["required"]
    }
    for key, value in tool["inputSchema"]["properties"].items():
      tmp["function"]["parameters"]["properties"][key] = {"type": value["type"], "description": value["description"]}
    res.append(tmp)
  return res

def mcp_resources_to_tool_list(resource_list: list[dict]) -> list:
  """Convert MCP resource specifications to list of tools following the structure of OpenAI"""
  res = []
  for resource in resource_list:
    tmp = {
      "type": "function",
      "function": {
        "name": resource["uri"],
        "description": resource["description"],
      }
    }
    res.append(tmp)
  return res

def mcp_resource_templates_to_tool_list(resource_template_list: list[dict]) -> list:
  """Convert MCP resource template specifications to list of tools following the structure of OpenAI"""
  res = []
  for resource_template in resource_template_list:
    des = resource_template["description"].split("|")[0]
    params = resource_template["description"].split("|")[1:]
    tmp = {
      "type": "function",
      "function": {
        "name": resource_template["uriTemplate"],
        "description": des,
      }
    }
    tmp["function"]["parameters"] = {
      "type": "object",
      "properties": {},
      "required": []
    }
    for param in params:
      param=param.split(":")
      t = param[1].split(",")
      tmp["function"]["parameters"]["properties"][param[0]] = {"type": t[1], "description": t[0]}
      tmp["function"]["parameters"]["required"].append(param[0])
    res.append(tmp)
  return res


TOOL_CODE_LOOKUP = {
  "sql+db://schema/{db_name*}": "001",
  "sql+db://list_tables/{db_name*}": "002",
  "sql+db://list_databases": "003",
  "rag_query": "004",
  "sql_query_db": "005",
  
}
def lookup_tool_code(name):
  return TOOL_CODE_LOOKUP[name];