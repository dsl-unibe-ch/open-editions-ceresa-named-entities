import json
import logging

from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import TextContent

from prompts import (
    ENTITY_CLASSES,
    ENTITY_SEARCH_SYSTEM_PROMPT,
    ENTITY_LINKING_SYSTEM_PROMPT,
    TEXT_SUMMARIZATION_SYSTEM_PROMPT,
)

from config import MAX_TOOL_ROUNDS


from utils import get_tools, call_openrouter
from mcp_server import mcp

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

def get_texts() -> list[str]:
    """Fetch the texts to process. In a real implementation, this might read from files, a database, or an API."""

    # some texts for testing
    from texts import TEXTS

    return TEXTS

async def summarize_text(text: str) -> str:
    """Summarize the text to provide it as context for entity linking."""

    system_message = {"role": "system", "content": TEXT_SUMMARIZATION_SYSTEM_PROMPT}
    user_message = {"role": "user", "content": text}

    response = await call_openrouter(messages=[system_message, user_message], tools=[], temperature=0.0)

    try:
        return response["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        # silent failure here, we might want to log this in a real implementation
        return ""

async def link_entity(entity: str, context: str, tools: list, session) -> dict:
    """Link an entity to a knowledge base (e.g. Wikidata).

    This function implements a tool-calling "agent" that interacts with the
    language model to iteratively call tools and refine its results. The agent
    can call tools up to MAX_TOOL_ROUNDS times, after which it must return
    whatever candidates it has found, even if they are not perfect.

    Args:
        entity: A string representing the entity to link.
        context: A string providing additional context for disambiguation
        (e.g. the summary of the text where the entity was found).
    Returns:
        A dictionary with a "candidates" key, which is a list of candidate
        matches. Each candidate is a dictionary with keys like "qid" and
        "confidence". If no candidates are found, the list will be empty.
    """

    user_message = f"Entity: {entity}\nContext: {context}"

    messages = [{
        "role": "system", "content": ENTITY_LINKING_SYSTEM_PROMPT
    }, {
        "role": "user", "content": user_message
    }]

    json_schema = {
        "name": "entity_linking",
        "schema": {
            "type": "object",
            "properties": {
                "candidates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "qid": {"type": "string"},
                            "confidence": {"type": "string", "enum": ["high", "medium", "low"]}
                        },
                        "required": ["qid", "confidence"],
                        "additionalProperties": False
                    }
                }
            },
            "required": ["candidates"],
            "additionalProperties": False
        }
    }

    for round in range(MAX_TOOL_ROUNDS):
        if round + 1 == MAX_TOOL_ROUNDS:
            messages.append({
                "role": "system",
                "content": "This is the final attempt. Return all "\
                            "probable candidates. Do not attempt to "\
                            "call tools anymore."
            })

        response = await call_openrouter(
            messages, tools,
            response_format={"type": "json_schema", "json_schema": json_schema}
        )

        message = response["choices"][0]["message"]
        messages.append(message)

        if not message.get("tool_calls"):
            return json.loads(message['content'])

        for tool_call in message["tool_calls"]:
            fn = tool_call["function"]
            tool_name = fn["name"]
            tool_args = json.loads(fn["arguments"])

            logging.info(f"  → Calling `{tool_name}` with {tool_args}")

            result = await session.call_tool(tool_name, tool_args)

            if result.content:
                match result.content[0]:
                    case TextContent():
                        tool_output = result.content[0].text
                    case _:
                        raise ValueError("Unexpected tool output format")
            else:
                tool_output = "[]"

            logging.info(f"  ← Result: {tool_output}")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": tool_output,
            })

    return {"candidates": []}

async def extract_entities(text: str, entity_classes: list[str]) -> dict[str, list[str]]:
    """Extract tags from text using a language model.

    Args:
        text: The input text to analyze.
        entity_classes: A list of entity categories to extract (e.g. ["persons", "places"]).
    Returns:
        A dictionary with keys corresponding to the entity classes. Each key maps to a list
        of strings representing the extracted entities or citations. If no entities are
        found for a category, the respective list will be empty.
    """

    json_schema = {
        "name": "entity_search",
        "schema": {
            "type": "object",
            "properties": {
                category: {
                    "type": "array",
                    "items": {"type": "string"}
                }
                for category in ENTITY_CLASSES
            },
            "required": list(ENTITY_CLASSES),
            "additionalProperties": False
        }
    }

    response = await call_openrouter(
        messages=[
            {"role": "system", "content": ENTITY_SEARCH_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        tools=[],
        response_format={"type": "json_schema", "json_schema": json_schema}
    )

    content = response["choices"][0]["message"]["content"]

    try:
        extracted = json.loads(content)

        return {category: extracted.get(category, []) for category in entity_classes}

    except json.JSONDecodeError:
        # If the response is not valid JSON, return empty lists for all categories
        return {category: [] for category in entity_classes}

async def main():
    texts = get_texts()

    async with create_connected_server_and_client_session(
        mcp._mcp_server
    ) as session:
        tools = await get_tools(session)

        for index, text in enumerate(texts):
            linked_entities = {}

            extracted_entities = await extract_entities(text, ENTITY_CLASSES)

            summary = await summarize_text(text)

            for category, entities in extracted_entities.items():
                linked_entities[category] = {}

                for entity in set(entities):
                    context = f"Summary of the source text: {summary}\n" +\
                        f"Entity category: {category}"

                    link_result = await link_entity(entity, context, tools, session)

                    logging.info(f"Entity: {entity} (Category: {category}) -> Link " +
                        f"candidates: {link_result['candidates']}\n\n")

                    linked_entities[category][entity] = link_result["candidates"]

            print(f"Final linked entities for text {index}:\n{json.dumps(linked_entities, indent=2)}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
