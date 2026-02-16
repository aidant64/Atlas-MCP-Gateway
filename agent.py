import os
import asyncio
from typing import List

from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

# Import tools from gateway to ensure governance logic is applied
# In a distributed system, this would be an MCP Client connecting to the Gateway Server.
# Here, we import the implementation directly which contains the Gatekeeper logic.
from gateway import check_payment_status_logic, request_payment_extension_logic, modify_welfare_record_logic

# --- wrapper tools for LangChain to inspect ---
# LangChain needs to know the schema. fastmcp tools are async.
# We wrap them to adapt to LangChain's expected format if needed, 
# or use LangChain's @tool decorator if we weren't using FastMCP's.
# Since we already defined them in gateway.py with @mcp.tool(), 
# we can wrap them in a simple callable for LangGraph or Use StructuredTool.

@tool
async def check_payment_status_tool(beneficiary_id: str):
    """Check the payment status for a beneficiary."""
    # Ensure awaitable calls correctly
    return await check_payment_status_logic(beneficiary_id)

@tool
async def request_payment_extension_tool(beneficiary_id: str, reason: str):
    """Request a payment extension for a beneficiary."""
    return await request_payment_extension_logic(beneficiary_id, reason)

@tool
async def modify_welfare_record_tool(beneficiary_id: str, changes: str):
    """Modify a welfare record. 'changes' should be a JSON string or dict description."""
    # Simulating dict parsing from string if necessary, or just passing it
    return await modify_welfare_record_logic(beneficiary_id, {"raw_changes": changes})


def create_atlas_agent():
    # Check for OPENAI_API_KEY
    if os.environ.get("OPENAI_API_KEY"):
        print("Using OpenAI GPT-4o...")
        llm = ChatOpenAI(model="gpt-4o", temperature=0)
    else:
        print("OPENAI_API_KEY not found. Using Local LLM (Ollama - mistral-nemo)...")
        # Ensure 'mistral-nemo' is pulled
        llm = ChatOllama(model="mistral-nemo", temperature=0)
    
    tools = [check_payment_status_tool, request_payment_extension_tool, modify_welfare_record_tool]
    
    system_prompt = (
        "You are the ATLAS Assistant for Alex. "
        "You have no final authority to change welfare status. "
        "You must request tools through the ATLAS Hub. "
        "If an action is paused for human review, inform Alex empathetically "
        "and explain that Sarah (Case Officer) is reviewing it per Article 14 of the EU AI Act."
    )
    
    # Create the ReAct agent using LangGraph
    # 'state_modifier' and 'messages_modifier' were incorrect. The signature shows 'prompt'.
    agent_graph = create_react_agent(llm, tools=tools, prompt=system_prompt)
    
    return agent_graph
