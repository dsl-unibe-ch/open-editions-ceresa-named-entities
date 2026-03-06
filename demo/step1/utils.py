import httpx

from config import OPENROUTER_API_KEY, OPENROUTER_URL, MODEL

async def get_tools(session) -> list[dict]:
    """
    Fetch the list of available tools from the MCP server and convert to
    OpenAI format.
    """

    tools_result = await session.list_tools()
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.inputSchema,
            },
        }
        for t in tools_result.tools
    ]

async def call_openrouter(
        messages: list,
        tools: list,
        temperature: float = 0.0,
        response_format: dict | None = None
) -> dict:
    json_body = {
        "model": MODEL,
        "messages": messages,
        "tools": tools,
        "temperature": temperature,
    }

    if response_format:
        json_body["response_format"] = response_format

    response = httpx.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json=json_body,
        timeout=30,
    )

    response.raise_for_status()
    return response.json()
