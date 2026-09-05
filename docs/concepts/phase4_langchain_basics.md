# Phase 4 — LangChain & LCEL Conversational RAG Explained from Scratch

This guide explains **LangChain**, **LCEL (LangChain Expression Language)**, and **Conversational Memory** for developers who have never used LangChain before.

---

## 1. What Actually is LangChain? (Without Marketing Jargon)

When building an AI application, communicating with an LLM starts simple:
```python
# Raw API call:
response = client.models.generate_content("What is Python?")
```

### When Applications Grow, Raw API Calls Become Messy:
1. You have to format system instructions, past conversation messages, and new user inputs into strings manually.
2. You have to parse the response text out of JSON objects manually.
3. If you want to do a multi-step task:
   - *Step 1:* Take user question + chat history ➔ rephrase into a search query.
   - *Step 2:* Take search query ➔ fetch code from vector database.
   - *Step 3:* Take fetched code + original question ➔ generate an answer.
4. Writing 3 separate functions, formatting variables between them, handling errors, and tracking history by hand requires writing hundreds of lines of boilerplate code.

### LangChain is Just "Lego Bricks" for AI Workflows:
LangChain is a Python framework that gives you standardized, pluggable components to connect prompts, models, vector databases, and memory together like building blocks.

---

## 2. Understanding LCEL: The Pipe Operator (`|`)

In modern LangChain (v0.2 / v0.3+), workflows are written using **LCEL (LangChain Expression Language)** using the Unix pipe operator `|`.

### Think of Unix Pipes in Terminal:
In Linux or PowerShell, you pipe commands together:
```bash
cat server.log | grep "ERROR" | head -n 5
```
The output of `cat` flows into `grep`, and the output of `grep` flows into `head`.

### The Same Concept in Python with LCEL:
```python
chain = prompt | model | StrOutputParser()
```

When you call `chain.invoke({"question": "What is Python?"})`:
1. **`prompt`** takes the dictionary, formats the template string, and outputs a formatted message list.
2. **`|`** automatically pipes that list into **`model`** (Google Gemini).
3. **`model`** generates a response object (`AIMessage`).
4. **`|`** automatically pipes that response into **`StrOutputParser()`**.
5. **`StrOutputParser()`** strips away the API metadata and returns a clean Python string: `"Python is a programming language..."`.

You don't have to write glue code between the steps; the `|` operator connects them seamlessly!

---

## 3. The Core LangChain Primitives Explained Simply

Here are the 4 main building blocks used in `src/rag/conversational.py`:

### A. Message Objects (`HumanMessage` & `AIMessage`)
Instead of messy dictionaries like `{"role": "user", "content": "hello"}`, LangChain provides dedicated message classes:
- **`HumanMessage(content="...")`**: Represents what the user typed.
- **`AIMessage(content="...")`**: Represents what the assistant replied.

When messages are stored in SQLite, we convert them to these classes so LangChain understands who said what.

---

### B. `ChatPromptTemplate`
Instead of using Python f-strings (which are prone to formatting errors and injection vulnerabilities), LangChain uses `ChatPromptTemplate`:

```python
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert software engineer."),
    ("human", "{question}")
])
```
It accepts placeholders like `{question}` and replaces them when you call `.invoke({"question": "Explain AST"})`.

---

### C. `MessagesPlaceholder`
When you have an ongoing conversation, how do you inject the list of past messages into a prompt template?

You use `MessagesPlaceholder`:
```python
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert software engineer."),
    MessagesPlaceholder(variable_name="chat_history"),  # <-- Inserts the list of past messages here!
    ("human", "{question}")
])
```
When you pass a list of `[HumanMessage(...), AIMessage(...)]` into `"chat_history"`, LangChain slots them right into the conversation flow automatically!

---

### D. `StrOutputParser`
When Google Gemini returns a response, it comes back as a rich object containing token counts, safety ratings, and metadata:
```python
response = model.invoke(...)  # Returns an AIMessage(content="Hello", response_metadata={...})
```
By adding `| StrOutputParser()` to your chain, it automatically extracts just the `.content` text string for you:
```python
(prompt | model | StrOutputParser()).invoke(...)  # Returns "Hello" (clean string)
```

---

## 4. The Core Problem Phase 4 Solves: The Pronoun Trap

Imagine this conversation:
- **Turn 1:**
  - User: *"Where is the loss function defined in this project?"*
  - Assistant: *"In `model.py` lines 21-33 in `SkipGramModel.forward()`."*
- **Turn 2:**
  - User: *"Can you explain how it handles negative samples?"*

### Why Turn 2 Fails in Basic RAG:
In Phase 3, the user question is directly converted into a 3072-dimensional vector.
If we convert *"Can you explain how it handles negative samples?"* into a vector:
- What does **"it"** mean? The vector search engine has no idea!
- ChromaDB might match some random test file that mentions "sample". It will **not** match `model.py`.

---

## 5. The Solution: The Query Condenser Chain

To solve this, LangChain runs a fast, lightweight re-writing step before searching ChromaDB:

```text
Input:
- chat_history: [
    User: "Where is the loss function defined?",
    Assistant: "In model.py lines 21-33 in SkipGramModel.forward()."
  ]
- question: "Can you explain how it handles negative samples?"
                    │
                    ▼  (Rephrase Chain via Gemini)
Output:
"How does the SkipGramModel in model.py handle negative samples in its loss calculation?"
```

Now, that re-written question is passed to ChromaDB. ChromaDB retrieves the exact code from `model.py` with high similarity!

### In LCEL, that Rephrase Chain is just 2 lines:
```python
rephrase_prompt = ChatPromptTemplate.from_messages([
    ("system", "Given a chat history and the latest user question, formulate a standalone question. Do NOT answer it, just rephrase it."),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{question}"),
])

rephrase_chain = rephrase_prompt | self.llm | StrOutputParser()
```

---

## 6. How `src/rag/conversational.py` Works End-to-End

Here is the step-by-step lifecycle of a single user chat message:

```text
 1. User sends message to: POST /sessions/{id}/chat
                          │
                          ▼
 2. SQLite Database reads the last 6 messages for that session
    Converts them into: [HumanMessage(...), AIMessage(...)]
                          │
                          ▼
 3. ConversationalRAGService.chat() runs:
    ┌────────────────────────────────────────────────────────┐
    │ A. If chat_history exists:                             │
    │    rephrase_chain rewrites follow-up into standalone Q │
    │    Otherwise: uses question as-is                      │
    ├────────────────────────────────────────────────────────┤
    │ B. ChromaLangChainRetriever:                           │
    │    Embeds standalone query -> searches ChromaDB        │
    │    Returns Top-K code Documents with metadata          │
    ├────────────────────────────────────────────────────────┤
    │ C. QA Chain:                                           │
    │    Injects retrieved code chunks into {context}        │
    │    Injects chat_history into MessagesPlaceholder       │
    │    Gemini 3.6 Flash generates grounded answer          │
    └────────────────────────────────────────────────────────┘
                          │
                          ▼
 4. Save both new User message & Assistant message into SQLite
                          │
                          ▼
 5. Return clean JSON response with answer & citations to Swagger/User!
```

---

## 7. Why Keep `service.py` and `conversational.py` Separate?

| File | Class | Purpose | Architecture |
| :--- | :--- | :--- | :--- |
| `src/rag/service.py` | `RAGService` | Fast, single-turn question answering (`POST /repositories/{id}/query`). Zero memory, no history. | Direct Gemini API + ChromaDB |
| `src/rag/conversational.py` | `ConversationalRAGService` | Interactive multi-turn chat threads (`POST /sessions/{id}/chat`). Tracks history, resolves pronouns, supports sessions. | Modern LangChain LCEL |

Keeping them separate follows the **Single Responsibility Principle**:
- If you just want a quick, one-off question about a repo, `service.py` runs with minimal overhead.
- If you want an interactive pair-programming session with memory, `conversational.py` handles the dialogue flow.

---

## 8. Phase 4 Status: Implemented and Tested

This project has completed the Phase 4 conversational-memory layer in practice:
- SQLite-backed chat sessions and message persistence
- last-6-message sliding memory window for follow-up questions
- LangChain `HumanMessage` / `AIMessage` conversion
- query condensation for pronoun resolution
- session-based API endpoints for chat history and Q&A

The implementation is validated through real API tests using FastAPI `TestClient` in `tests/unit/test_api.py`, which exercise the actual route flow rather than mocked-only behavior.

