"""Shared OpenAI Responses API helper: forces a single named-function call
with strict JSON-schema output. Copied verbatim from
../uncharted_ice_proposal_maker/src/llm_client.py.

Tool dicts are kept in Anthropic shape ({name, description, input_schema}) at
each call site; this module converts to OpenAI's function-tool shape internally.
"""

import json

import openai

import config


def get_client() -> openai.OpenAI:
    return openai.OpenAI(api_key=config.OPENAI_API_KEY)


def _strictify(schema: dict) -> dict:
    """Recursively adds additionalProperties=False and lists every property in
    required, as OpenAI strict mode demands."""
    if schema.get("type") == "object" and "properties" in schema:
        schema = dict(schema)
        schema["properties"] = {k: _strictify(v) for k, v in schema["properties"].items()}
        schema["required"] = list(schema["properties"].keys())
        schema["additionalProperties"] = False
    elif schema.get("type") == "array" and "items" in schema:
        schema = dict(schema)
        schema["items"] = _strictify(schema["items"])
    return schema


def _to_function_tool(tool: dict) -> dict:
    return {
        "type": "function",
        "name": tool["name"],
        "description": tool["description"],
        "parameters": _strictify(tool["input_schema"]),
        "strict": True,
    }


def call_tool(content: list, tool: dict, model: str = None) -> dict:
    """Sends `content` (a Responses-API content-block list) with `tool` forced
    as the only callable function, and returns its parsed arguments."""
    client = get_client()
    response = client.responses.create(
        model=model or config.OPENAI_MODEL,
        input=[{"role": "user", "content": content}],
        tools=[_to_function_tool(tool)],
        tool_choice={"type": "function", "name": tool["name"]},
    )
    for item in response.output:
        if item.type == "function_call" and item.name == tool["name"]:
            return json.loads(item.arguments)
    raise RuntimeError(f'Model did not return the expected {tool["name"]} tool call')
