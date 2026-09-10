from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from src.agents.orchestrator import (
    AgentState,
    ArchaeonAgentService,
    create_agent_graph,
    ARCHAEON_SYSTEM_PROMPT,
)
from src.agents.tools import build_archaeon_tools


def test_extract_citations():
    """Verify citation extraction from intermediate AIMessage tool calls."""
    service = ArchaeonAgentService(
        api_key="fake-key",
        vector_store=MagicMock(),
        embedding_service=MagicMock(),
    )

    messages = [
        SystemMessage(content=ARCHAEON_SYSTEM_PROMPT),
        HumanMessage(content="Where is the parser defined?"),
        AIMessage(
            content="",
            tool_calls=[
                {"name": "symbol_lookup", "args": {"name": "ASTParser"}, "id": "call_1"},
                {"name": "file_read", "args": {"file_path": "src/parser.py", "start_line": 10, "end_line": 35}, "id": "call_2"},
            ],
        ),
        ToolMessage(content="Symbol found", tool_call_id="call_1"),
        ToolMessage(content="Lines read", tool_call_id="call_2"),
        AIMessage(content="ASTParser is defined in src/parser.py."),
    ]

    citations = service._extract_citations(messages)

    assert len(citations) == 2
    # Verify file_read citation
    file_citation = next(c for c in citations if c["source"] == "file_read")
    assert file_citation["file_path"] == "src/parser.py"
    assert file_citation["start_line"] == 10
    assert file_citation["end_line"] == 35

    # Verify symbol_lookup citation
    sym_citation = next(c for c in citations if c["source"] == "symbol_lookup")
    assert sym_citation["symbol_name"] == "ASTParser"


def test_create_agent_graph_compiles():
    """Verify that create_agent_graph wires nodes and returns a compiled LangGraph app."""
    dummy_tools = build_archaeon_tools(
        repository_id="dummy-repo",
        db=MagicMock(),
        vector_store=MagicMock(),
        embedding_service=MagicMock(),
        clone_path="dummy/path",
    )

    with patch("src.agents.orchestrator.ChatGoogleGenerativeAI") as MockChat:
        mock_llm = MagicMock()
        MockChat.return_value = mock_llm
        mock_llm.bind_tools.return_value = MagicMock()

        app = create_agent_graph(tools=dummy_tools, api_key="fake-key")
        assert app is not None
        # Check that invoke is callable
        assert hasattr(app, "invoke")


def test_archaeon_agent_service_chat():
    """Verify that ArchaeonAgentService runs the graph and packages answers and citations."""
    service = ArchaeonAgentService(
        api_key="fake-key",
        vector_store=MagicMock(),
        embedding_service=MagicMock(),
    )

    mock_app = MagicMock()
    mock_app.invoke.return_value = {
        "messages": [
            SystemMessage(content=ARCHAEON_SYSTEM_PROMPT),
            HumanMessage(content="Explain the parser"),
            AIMessage(
                content="",
                tool_calls=[{"name": "file_read", "args": {"file_path": "src/parser.py", "start_line": 1, "end_line": 20}, "id": "call_1"}],
            ),
            ToolMessage(content="1: class Parser...", tool_call_id="call_1"),
            AIMessage(content="The parser processes tokens into AST nodes."),
        ]
    }

    with patch("src.agents.orchestrator.create_agent_graph", return_value=mock_app), \
         patch("src.agents.orchestrator.build_archaeon_tools", return_value=[]):
        
        result = service.chat(
            repository_id="repo-1",
            db=MagicMock(),
            clone_path="dummy/path",
            message="Explain the parser",
            chat_history=[],
            max_steps=10,
        )

        assert result["answer"] == "The parser processes tokens into AST nodes."
        assert len(result["citations"]) == 1
        assert result["citations"][0]["file_path"] == "src/parser.py"
        assert result["citations"][0]["start_line"] == 1
        assert result["total_messages"] == 5
