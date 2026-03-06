# Using LLMs for entity linking

## Usage
### Requirements
1. You need an OpenRouter API key. Copy `env.example` to `.env` and edit it to add your key.
2. Install the python requirements after crating a virtual environment:
```bash
python3 -m venv .
pip install -r requirements.txt
```

### Setup
You want to adjust `get_text` to your needs. You might also want to edit the system prompty in `prompts.py` to describe your problem more specifically.


## Flow

```
  For each text:

  +-----------------------+     +-----------------------+
  |   summarize_text()    |     |  extract_entities()   |
  |                       |     |                       |
  |   LLM: "summarize     |     |   LLM: "extract all   |
  |    this letter"       |     |    named entities"    |
  +-----------+-----------+     +-----------+-----------+
              |                             |
              v                             v
           summary                  {persons: [...],
                                     places: [...], ...}
              |                             |
              +-------------+---------------+
                            |
                            v
               for each (entity, category):
                            |
  +-------------------------+--------------------------+
  |                                                    |
  |  link_entity(entity, context, tools, session)      |
  |  context = summary + category + ...                |
  |                                                    |
  |  +----------------------------------------------+  |
  |  |          AGENT LOOP (max N rounds)           |  |
  |  |                                              |  |
  |  |  "Entity: Galileo Galilei                    |  |
  |  |   Context: letter about astronomy            |  |
  |  |   Category: persons"                         |  |
  |  |                  |                           |  |
  |  |                  v                           |  |
  |  |           LLM (OpenRouter)                   |  |
  |  |                  |                           |  |
  |  |         +--------+--------+                  |  |
  |  |         |                 |                  |  |
  |  |    tool_calls        no tool_calls           |  |
  |  |         |                 |                  |  |
  |  |         v                 v                  |  |
  |  |  MCP: search_wikidata    return              |  |
  |  |    (in-memory session)   {candidates: [...]} |  |
  |  |         |                                    |  |
  |  |         v                                    |  |
  |  |  Wikidata API ----+                          |  |
  |  |         ^         |                          |  |
  |  |         +---------+                          |  |
  |  |     (loop until LLM stops                    |  |
  |  |      calling tools or max rounds)            |  |
  |  +---------------------------------------------+   |
  |                       |                            |
  |                       v                            |
  |  {candidates: [{qid: "Q307", confidence: "high"}]} |
  +----------------------------------------------------+
```
