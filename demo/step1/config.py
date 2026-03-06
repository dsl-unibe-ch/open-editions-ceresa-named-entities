import os
import dotenv

dotenv.load_dotenv()

WIKIDATA_PAGE_SIZE = 5
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
USER_AGENT = "DHEntityLinker/0.1 (https://www.dh.unibe.ch/index_eng.html; david.herrmann@unibe.ch)"
MAX_TOOL_ROUNDS = 5

OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-3-flash-preview"

