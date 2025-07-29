# === /agent/agent_core.py ===
from langchain.chat_models import ChatOpenAI
from langchain.agents import initialize_agent, Tool
from langchain.agents.agent_types import AgentType
from agent.tools import get_available_items, get_cart_summary
from agent.prompt_templates import get_agent_prompt
import logging
import os

try:
    import openai
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        openai.api_key = key
    logging.info("✅ openai module imported: %s", openai.__file__)
    logging.info("✅ openai version: %s", openai.__version__)
except Exception as e:  # pragma: no cover - env issues
    logging.error("❌ Failed to import openai: %s", str(e))

llm = ChatOpenAI(temperature=0, model="gpt-4")  # or "gpt-3.5-turbo"

tools = [
    Tool(
        name="GetAvailableItems",
        func=get_available_items,
        description="Get available items for the user's society."
    ),
    Tool(
        name="GetCartSummary",
        func=get_cart_summary,
        description="Get a summary of items in the user's cart."
    )
]

agent = initialize_agent(
    tools,
    llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
)

def run_agent(query, user_info):
    """Execute the LangChain agent with provided query and user info."""
    if not getattr(openai, "api_key", None):
        raise RuntimeError("OpenAI API key not configured")
    try:
        prompt = get_agent_prompt(user_info)
        final_input = f"{prompt}\nUser: {query}"
        logging.debug("Final Agent Input: %s", final_input)
        response = agent.run(final_input)
        logging.info("✅ Agent Response: %s", response)
        return response, ["Would you like to add to cart?", "Do you want checkout link?"]
    except Exception as e:
        logging.error("❌ Agent Error: %s", str(e), exc_info=True)
        raise e  # Propagate to caller