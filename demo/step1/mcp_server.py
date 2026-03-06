import httpx

from mcp.server.fastmcp import FastMCP

from config import (
    WIKIDATA_PAGE_SIZE,
    WIKIDATA_API,
    USER_AGENT,
)

mcp = FastMCP("ceresa_entity_linker", "0.1.0", json_response=True)

@mcp.tool(
    "search_wikidata",
    description=(
        "Search Wikidata by entity label (prefix match on labels and aliases). "
        "Use the full name as it would appear in an encyclopedia heading — "
        "never append descriptive or disambiguating words. "
        "Good: 'Leonardo da Vinci', 'Éditions Grasset', 'Mona Lisa'. "
        "Bad: 'Grasset publisher', 'Louvre Paris', 'Leonardo painter'. "
        "If no results, try: the name in another language, a shorter/longer form, or a known alias."
    ),
)
def search_wikidata(
    query: str,
    language: str = "en",
    page: int = 0,
) -> list[dict]:
    """
    Search Wikidata entities by label.

    Args:
        query: The entity name to search for (e.g. "Galileo Galilei").
        language: Language code for labels/descriptions (default: "en").
        page: Page number for pagination (0-indexed).
    """
    try:
        res = httpx.get(WIKIDATA_API, params={
            "action": "wbsearchentities",
            "search": query,
            "language": language,
            "format": "json",
            "limit": WIKIDATA_PAGE_SIZE,
            "continue": page * WIKIDATA_PAGE_SIZE,
        }, headers={"User-Agent": USER_AGENT})
        data = res.json()
    except Exception as e:
        return [{"error": str(e)}]

    return [
        {
            "id": item.get("id"),
            "label": item.get("label"),
            "description": item.get("description"),
        }
        for item in data.get("search", [])
    ]