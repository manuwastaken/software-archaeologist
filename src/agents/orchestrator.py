import os
import re
from typing import Annotated, Sequence
from typing_extensions import TypedDict
from pathlib import Path
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from sqlalchemy.orm import Session
from src.agents.tools import build_archaeon_tools
from src.rag.embeddings import GeminiEmbeddingService
from src.rag.vector_store import ChromaVectorStore
from src.rate_limiter import gemini_rate_limiter  # RATE LIMIT: see src/rate_limiter.py to adjust or disable

DEFAULT_CHAT_MODEL = "gemini-3.6-flash"

ARCHAEON_SYSTEM_PROMPT = """You are Archaeon, an autonomous expert AI Software Archaeologist.
Your mission is to explore, analyze, and explain codebases with scientific rigor, precision, and historical context.
You do not merely describe what code does; you explain how components connect, why they were designed that way, and how the architecture functions.

### INVESTIGATION METHODOLOGY (ReAct):
1. **Always Verify Before Asserting**:
   - Never guess or extrapolate file paths, function implementations, or line numbers.
   - Always gather concrete evidence using your available tools before drawing conclusions.

2. **Tool Selection Strategy**:
   - **`symbol_lookup`**: Use this first when asked about a specific class, function, method, or symbol name (e.g., `SymbolVisitor`, `ChromaVectorStore`). It gives you exact line boundaries, docstrings, and parent classes from the AST index.
   - **`codebase_search`**: Use this for conceptual, semantic, or exploratory questions (e.g., "how is authentication handled?", "where are background jobs processed?").
   - **`file_read`**: Once you know a file path and relevant line numbers, use this tool to inspect the exact source code and implementation logic. Always specify bounded line ranges.

3. **Multi-Step Investigation**:
   - If an initial lookup or search gives partial clues, follow the trail! Inspect caller/callee relationships by reading relevant files or running targeted searches.
   - If a symbol lookup fails, try searching the codebase with `codebase_search`. If still not found, state honestly what you searched for and what was not located.

4. **Citation & Grounding Contract**:
   - Every claim about code structure, logic, or behavior MUST be grounded in facts discovered through your tools.
   - Always cite exact coordinates when referencing code using the format: `[file_path:start_line-end_line]`, for example: `[src/analysis/ast_parser.py:15-45]`.

5. **Investigation Efficiency**:
   - Be decisive and economical with tool calls. Avoid unnecessary intermediate searches.
   - Aim to complete your investigation in 1 to 2 tool execution steps to respect rate limits, then produce your final answer.

### COMMUNICATION STYLE:
- Be clear, structured, and pedagogical.
- Break complex explanations into logical sections (e.g., Architecture Overview, Implementation Details, Key Methods).
- Highlight trade-offs, design patterns, and potential edge cases like an experienced staff engineer.
"""


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def create_agent_graph(tools: list, model_name: str = DEFAULT_CHAT_MODEL, api_key: str | None = None):
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key or os.getenv("GEMINI_API_KEY"),
        temperature=0,
        max_retries=6,
    )
    model_with_tools = llm.bind_tools(tools)

    def call_model(state: AgentState):
        messages = state["messages"]
        # RATE LIMIT: Remove or adjust in src/rate_limiter.py
        # This is called on every ReAct loop iteration, so rate limiting here
        # prevents the agent from overwhelming the Gemini API across multiple steps.
        gemini_rate_limiter.wait_if_needed()
        response = model_with_tools.invoke(messages)
        return {"messages": [response]}

    tool_node = ToolNode(tools)

    workflow = StateGraph(AgentState)

    workflow.add_node("agent", call_model)
    workflow.add_node("tools", tool_node)

    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", tools_condition)
    workflow.add_edge("tools", "agent")

    return workflow.compile()

class ArchaeonAgentService:
    """
    Orchestration service for the Archaeon LangGraph agent.
    Coordinates repo-scoped tools, executes the ReAct graph,
    and formats citations and answers.
    """
    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = DEFAULT_CHAT_MODEL,
        vector_store: ChromaVectorStore | None = None,
        embedding_service: GeminiEmbeddingService | None = None,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name
        self.vector_store = vector_store or ChromaVectorStore()
        self.embedding_service = embedding_service or GeminiEmbeddingService(api_key=self.api_key)

    def _extract_citations(self, messages: list[BaseMessage]) -> list[dict]:
        """
        Inspects all intermediate tool calls in the state to build grounded line-level citations.
        """
        citations = []
        seen = set()
        for msg in messages:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for call in msg.tool_calls:
                    name = call.get("name")
                    args = call.get("args", {})
                    if name == "file_read":
                        fpath = args.get("file_path", "")
                        start = args.get("start_line", 0)
                        end = args.get("end_line", 0)
                        key = (fpath, start, end)
                        if key not in seen and fpath:
                            seen.add(key)
                            citations.append({
                                "file_path": fpath,
                                "symbol_name": None,
                                "start_line": start,
                                "end_line": end,
                                "similarity_score": 1.0,
                                "source": "file_read"
                            })
                    elif name == "symbol_lookup":
                        sname = args.get("name", "")
                        if sname and (sname not in seen):
                            seen.add(sname)
                            citations.append({
                                "file_path": "",
                                "symbol_name": sname,
                                "start_line": 0,
                                "end_line": 0,
                                "similarity_score": 1.0,
                                "source": "symbol_lookup"
                            })
        return citations

    def chat(
        self,
        repository_id: str,
        db: Session,
        clone_path: str,
        message: str,
        chat_history: Sequence[BaseMessage] | None = None,
        max_steps: int = 20,
    ) -> dict:
        """
        Executes an agentic investigation session:
        1. Factory-builds repo-scoped tools (codebase_search, symbol_lookup, file_read)
        2. Compiles a LangGraph ReAct agent
        3. Invokes the state machine with system instructions and chat history
        4. Returns the final answer and collected citations
        """
        # 1. Build repo-scoped tools
        tools = build_archaeon_tools(
            repository_id=repository_id,
            db=db,
            vector_store=self.vector_store,
            embedding_service=self.embedding_service,
            clone_path=clone_path,
        )
        # 2. Compile LangGraph workflow
        app = create_agent_graph(
            tools=tools,
            model_name=self.model_name,
            api_key=self.api_key,
        )
        # 3. Assemble initial message state (Way B: SystemMessage + History + User Message)
        initial_messages: list[BaseMessage] = [
            SystemMessage(content=ARCHAEON_SYSTEM_PROMPT)
        ]
        if chat_history:
            initial_messages.extend(chat_history)
        initial_messages.append(HumanMessage(content=message))
        # 4. Invoke graph with recursion limit protection
        final_state = app.invoke(
            {"messages": initial_messages},
            config={"recursion_limit": max_steps}
        )
        # 5. Extract final response
        messages = final_state.get("messages", [])
        final_message = messages[-1] if messages else AIMessage(content="No response generated.")
        content = final_message.content if hasattr(final_message, "content") else str(final_message)
        if isinstance(content, list):
            answer = "".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        else:
            answer = content
        # 6. Extract citations from tool invocations
        citations = self._extract_citations(messages)
        return {
            "answer": answer,
            "citations": citations,
            "total_messages": len(messages),
        }
