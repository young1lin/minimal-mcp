"""MCP Tools - 提供文件操作、Shell 执行等工具

工具函数使用 @tool 装饰器定义，格式遵循 Google-style docstrings。
"""

import httpx
from markdownify import markdownify as md
import subprocess
import glob as glob_lib
from typing import Any, Union, get_type_hints, get_origin, get_args, Callable
import inspect
import re
from mcp_server import tool


# ============== Docstring 解析工具函数 ==============

def parse_google_docstring(docstring: str) -> dict[str, Any]:
    """
    解析 Google-style docstring，提取方法描述、参数和返回值信息

    Args:
        docstring: 函数的 docstring 字符串

    Returns:
        包含以下键的字典:
        - description: 方法的主要描述
        - args: 参数描述字典 {param_name: description}
        - returns: 返回值描述字符串
        - examples: 示例字符串（可选）
    """
    if not docstring:
        return {"description": "", "args": {}, "returns": "", "examples": ""}

    lines = docstring.strip().split("\n")
    result = {
        "description": "",
        "args": {},
        "returns": "",
        "examples": "",
    }

    current_section = "description"
    current_arg = None
    current_arg_lines = []

    for line in lines:
        stripped = line.strip()

        if stripped.lower().startswith("args:") or stripped.lower().startswith("parameters:"):
            if current_arg:
                result["args"][current_arg] = " ".join(current_arg_lines).strip()
            current_section = "args"
            current_arg = None
            current_arg_lines = []
            continue

        if stripped.lower().startswith("returns:"):
            if current_arg:
                result["args"][current_arg] = " ".join(current_arg_lines).strip()
                current_arg = None
                current_arg_lines = []
            current_section = "returns"
            continue

        if stripped.lower().startswith("examples:") or stripped.lower().startswith("example:"):
            current_section = "examples"
            continue

        if current_section == "description":
            if stripped:
                result["description"] += (stripped + " ").strip() + "\n"

        elif current_section == "args":
            arg_match = re.match(r"^(\w+)\s*\((\w+[\[\]]*)(?:,\s*(\w+))?\)\s*:?\s*(.*)$", stripped)
            if arg_match:
                if current_arg:
                    result["args"][current_arg] = " ".join(current_arg_lines).strip()
                current_arg = arg_match.group(1)
                description = arg_match.group(4).strip()
                current_arg_lines = [description] if description else []
            elif stripped and current_arg:
                current_arg_lines.append(stripped)
            elif stripped and not current_arg:
                simple_match = re.match(r"^(\w+)\s*:\s*(.*)$", stripped)
                if simple_match:
                    if current_arg:
                        result["args"][current_arg] = " ".join(current_arg_lines).strip()
                    current_arg = simple_match.group(1)
                    current_arg_lines = [simple_match.group(2).strip()]

        elif current_section == "returns":
            if stripped:
                result["returns"] += stripped + "\n"

        elif current_section == "examples":
            if stripped:
                result["examples"] += stripped + "\n"

    if current_arg:
        result["args"][current_arg] = " ".join(current_arg_lines).strip()

    result["description"] = result["description"].strip()
    result["returns"] = result["returns"].strip()
    result["examples"] = result["examples"].strip()

    return result


def get_python_type_string(type_hint) -> str:
    """将 Python 类型提示转换为 JSON Schema 类型字符串"""
    if type_hint is None:
        return "string"

    origin = get_origin(type_hint)
    args = get_args(type_hint)

    if origin is type(None):
        return "null"

    # 处理 Union 类型（包括 Python 3.10+ 的 X | Y 语法）
    # 检查是否是 Union 或 UnionType
    import types
    is_union = origin is Union or (hasattr(types, 'UnionType') and isinstance(type_hint, types.UnionType))

    if is_union:
        # 找到第一个非 None 的类型
        for arg in args:
            if arg is not type(None):
                return get_python_type_string(arg)
        return "string"

    if origin is list or (hasattr(type_hint, "__name__") and type_hint.__name__ == "list"):
        return "array"

    if hasattr(type_hint, "__name__"):
        type_name = type_hint.__name__
        type_map = {
            "str": "string", "int": "integer", "float": "number", "bool": "boolean",
            "list": "array", "dict": "object", "set": "array", "tuple": "array", "bytes": "string",
        }
        return type_map.get(type_name, "string")

    return "string"


def simple_tool_to_function_calling(
    simple_tool,
    server_name: str = "",
    include_examples: bool = True,
) -> dict:
    """
    将 SimpleTool 对象转换为 Claude Code Function Calling 格式

    直接使用 simple_tool.name 作为函数名（从 @tool(name="xxx") 获取）

    Args:
        simple_tool: SimpleTool 对象（有 func 属性）
        server_name: 服务器名称（用于前缀）
        include_examples: 是否包含示例

    Returns:
        符合 Claude Code Function Calling 格式的函数定义字典
    """
    func = simple_tool.func

    # 获取类型提示
    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}

    # 解析 docstring
    raw_docstring = inspect.getdoc(func) or ""
    docstring_info = parse_google_docstring(raw_docstring)

    # 构建描述
    description_parts = []
    if docstring_info["description"]:
        description_parts.append(docstring_info["description"])
    else:
        description_parts.append(simple_tool.description or "")

    if docstring_info["returns"]:
        description_parts.append(f"\nReturns: {docstring_info['returns']}")
    if include_examples and docstring_info["examples"]:
        description_parts.append(f"\nExamples:\n{docstring_info['examples']}")

    full_description = "\n".join(description_parts).strip()

    # 函数名：直接用 simple_tool.name，可选加 server 前缀
    safe_server_name = (server_name or "").replace("-", "_").replace(":", "_")
    if safe_server_name:
        function_name = f"{safe_server_name}__{simple_tool.name}"
    else:
        function_name = simple_tool.name

    # 构建参数
    properties = {}
    required_params = []
    arguments = getattr(simple_tool, 'arguments', {})
    required_arguments = getattr(simple_tool, 'required_arguments', [])

    for param_name, param_type in arguments.items():
        if param_name == "return":
            continue

        # 类型
        if param_name in hints:
            param_type_str = get_python_type_string(hints[param_name])
        else:
            param_type_str = get_python_type_string(param_type)

        # 描述
        description = docstring_info["args"].get(param_name, f"Parameter {param_name}")

        properties[param_name] = {
            "type": param_type_str,
            "description": description,
        }

        # 是否必需
        if param_name in required_arguments:
            required_params.append(param_name)

    return {
        "type": "function",
        "function": {
            "name": function_name,
            "description": full_description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required_params,
            },
        },
    }


def mcp_tool_to_function_calling(tool, server_name: str = "") -> dict:
    """
    将 MCP Server 的 ToolDefinition 转换为 Claude Code Function Calling 格式

    Args:
        tool: ToolDefinition 对象（来自 MCP Server，没有 func 属性）
        server_name: 服务器名称（用于前缀）

    Returns:
        符合 Claude Code Function Calling 格式的函数定义字典
    """
    # 函数名：server__tool_name
    safe_server_name = (server_name or "").replace("-", "_").replace(":", "_")
    if safe_server_name:
        function_name = f"{safe_server_name}__{tool.name}"
    else:
        function_name = tool.name

    # 描述
    description = tool.description or f"Tool from {server_name}"
    if server_name:
        description = f"[{server_name}] {description}"

    # 构建参数
    properties = {}
    required_params = []

    if tool.inputSchema and tool.inputSchema.properties:
        for param_name, param_prop in tool.inputSchema.properties.items():
            properties[param_name] = {
                "type": param_prop.type or "string",
                "description": param_prop.description or f"Parameter {param_name}",
            }

        if tool.inputSchema.required:
            required_params = tool.inputSchema.required

    return {
        "type": "function",
        "function": {
            "name": function_name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required_params,
            },
        },
    }


# ============== 工具函数定义 ==============


@tool(name="Fetch", required_arguments=["url"])
async def fetch_to_markdown(url: str) -> str:
    """获取网页内容并转换为 Markdown 格式

    Args:
        url: 要获取的网页 URL

    Returns:
        网页内容的 Markdown 格式字符串
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            response.raise_for_status()
            return md(response.text)
    except httpx.HTTPStatusError as e:
        return f"HTTP 错误: {e.response.status_code}"
    except Exception as e:
        return f"错误: {str(e)}"


@tool(name="Read", required_arguments=["path"])
async def read_file(path: str, offset: int = 1, limit: int | None = None) -> str:
    """读取文件内容

    Args:
        path: 要读取的文件路径
        offset: 从第几行开始读取（1-indexed，默认第1行）
        limit: 最多读取多少行（默认None表示读取全部）

    注意：
    - 读取前N行：offset=1, limit=N
    - 读取中间范围：offset=起始行, limit=结束行-起始行+1
    - 例如：读取前20行 -> Read(path, offset=1, limit=20)
    - 例如：读取10-30行 -> Read(path, offset=10, limit=21)

    Returns:
        带行号前缀的文件内容
    """
    with open(path, "r", encoding="utf-8") as file:
        lines = file.readlines()

    start = max(0, offset - 1)
    end = len(lines) if limit is None else start + limit

    result = []
    for i, line in enumerate(lines[start:end], start=offset):
        result.append(f"{i:>4} | {line.rstrip()}")

    return "\n".join(result)


@tool(name="Write", required_arguments=["path", "content"])
async def write_file(path: str, content: str) -> str:
    """写入文件内容

    Args:
        path: 要写入的文件路径
        content: 要写入的内容
    """
    with open(path, "w", encoding="utf-8") as file:
        file.write(content)
    return "文件写入成功"


@tool(name="Edit", required_arguments=["path", "offset", "limit", "content"])
async def edit_file(path: str, offset: int, limit: int, content: str) -> str:
    """编辑文件指定行的内容

    Args:
        path: 要编辑的文件路径
        offset: 从第几行开始编辑（1-indexed）
        limit: 连续编辑多少行
        content: 要替换成的新内容
    """
    with open(path, "r", encoding="utf-8") as file:
        lines = file.readlines()

    start = max(0, offset - 1)
    end = start + limit

    if start >= len(lines):
        return f"错误：起始行 {offset} 超出文件范围"

    new_lines = lines[:start] + [content + "\n"] + lines[end:]

    with open(path, "w", encoding="utf-8") as file:
        file.writelines(new_lines)

    return f"成功编辑第 {offset} 到 {offset + limit - 1} 行"


@tool(name="Glob", required_arguments=["pattern"])
async def glob_files(pattern: str = "*") -> str:
    """文件模式匹配

    Args:
        pattern: Glob 模式，例如 "**/*.py"、"*.txt"（必需参数）

    Returns:
        匹配到的文件路径列表
    """
    if not pattern:
        return "错误：Glob 需要提供 pattern 参数，例如 '*.py'、'src/**/*.txt'"
    files = glob_lib.glob(pattern, recursive=True)
    return "\n".join(files) if files else "未找到匹配的文件"


@tool(name="Shell", required_arguments=["command"])
async def run_shell(command: str, timeout: int = 30) -> str:
    """执行 Shell 命令

    Args:
        command: 要执行的命令
        timeout: 超时时间（秒）

    Returns:
        命令的标准输出
    """
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout,
        )
        output = result.stdout or result.stderr
        return output if output else "命令执行成功（无输出）"
    except subprocess.TimeoutExpired:
        return f"命令执行超时（超过{timeout}秒）"
    except Exception as e:
        return f"命令执行失败: {str(e)}"
