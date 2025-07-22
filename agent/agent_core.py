# === /agent/agent_core.py ===
from langchain.chat_models import ChatOpenAI
from langchain.agents import initialize_agent, Tool
from langchain.agents.agent_types import AgentType
from agent.tools import get_available_items, get_cart_summary
from agent.prompt_templates import get_agent_prompt

try:
    import openai
    print("✅ openai module imported:", openai.__file__)
    print("✅ openai version:", openai.__version__)
except Exception as e:
    print("❌ Failed to import openai:", str(e))

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
    try:
        prompt = get_agent_prompt(user_info)
        final_input = f"{prompt}\nUser: {query}"
        print("🔍 Final Agent Input:", final_input)
        response = agent.run(final_input)
        print("✅ Agent Response:", response)
        return response, ["Would you like to add to cart?", "Do you want checkout link?"]
    except Exception as e:
        print("❌ Agent Error:", str(e))
        raise e  # Let the API return it as part of 500 handler