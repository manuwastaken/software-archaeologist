# Step 1 — LLM API Basics

Before writing any real code, you need to understand six foundational concepts.
These are not Archaeon-specific — they apply to **every** project that talks to an LLM.

---

## 1. API (Application Programming Interface)

### The idea

An API is a way for two programs to talk to each other over the internet.

You don't have the LLM running on your computer. It lives on Google's (or OpenAI's) servers.
Your Python code sends a **request** across the internet to those servers, and gets a **response** back.

### Analogy

Think of a restaurant.

- You are the customer (your Python code)
- The kitchen is the LLM (running on Google's servers)
- The waiter is the API (takes your order, brings back food)

You never go into the kitchen. You only talk to the waiter using a specific format:
> "I'd like the pasta, please."

The kitchen does the work. The waiter brings the result back.

### In your code

```python
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

interaction = client.interactions.create(
    model="gemini-3.6-flash",
    input="Explain what a compiler does?"
)
```

`client.interactions.create(...)` is the "waiter" — it sends your request to Google's servers
and brings back the response.

---

## 2. API Key

### The idea

When you call Google's API, Google needs to know:

- **Who** is making the request
- **Should** they be allowed to
- **How much** have they used (for billing)

An API key is a long unique string — essentially a password — that identifies you.

```
GEMINI_API_KEY="AIzaSyD3kf8..."
```

### Why it lives in `.env`

If you put the key directly in your Python file and pushed it to GitHub, anyone in the world
could use it and run up your bill.

Instead:

```
.env          <- contains the real key, never committed to Git
.env.example  <- committed to Git, shows others what variable to set
.gitignore    <- tells Git to ignore .env
```

Your code then reads it safely at runtime:

```python
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")  # reads from .env, not hardcoded
```

### Rule

> Never hardcode an API key. Never commit it to Git.

---

## 3. Model

### The idea

A "model" is the specific AI that processes your request.

One company (e.g. Google) can offer many different models, each with different:

- **Capability** — how intelligent the responses are
- **Speed** — faster models give quicker responses
- **Cost** — more capable models cost more per token
- **Context window** — how much text it can read at once

### Examples

| Model | Notes |
|---|---|
| `gemini-3.6-flash` | Fast, cheap, good for simple tasks |
| `gemini-2.5-pro` | Slower, more expensive, higher quality reasoning |
| `gpt-4o` | OpenAI's model, different provider |

### In your code

```python
interaction = client.interactions.create(
    model="gemini-3.6-flash",   # you pick which model to use
    input="Explain what a compiler does?"
)
```

You choose the model per request. Later in Archaeon, you might use a cheaper model for
simple lookups and a better model for final answer generation.

---

## 4. Prompt

### The idea

A prompt is the text you send to the model. It is the **input** — your question, instruction,
or context.

The quality of your output depends heavily on how you write the prompt.

### Types of prompts

**Simple question**
```
"Explain what a compiler does?"
```

**Instruction with context** (what Archaeon will do)
```
You are a software archaeology assistant.

Here is some source code from a repository:

    def connect(self, retries=3):
        for i in range(retries):
            try:
                return self.db.connect()
            except Exception:
                time.sleep(2 ** i)

Here is the commit that introduced it:

    Commit a83f21 — "Fix database connection failures under load"

Based on this evidence, explain why the retry logic exists.
```

The second version gives the model **actual evidence** to reason from.
This is the core idea behind RAG.

### System prompt vs user prompt

Most LLM APIs let you separate:

- **System prompt** — background instructions that set the model's behaviour
  > "You are a software archaeology assistant. Always cite evidence."

- **User prompt** — the actual question for this specific request
  > "Why does this function have three retries?"

---

## 5. Response

### The idea

The response is what the model sends back — a structured object, not just a raw string.

```python
interaction = client.interactions.create(
    model="gemini-3.6-flash",
    input="Explain what a compiler does?"
)

print(interaction.output_text)  # the actual answer text
```

### What a response typically contains

```
response
├── output_text       <- the answer as a string
├── usage_metadata    <- how many tokens were used
│   ├── prompt_tokens
│   ├── response_tokens
│   └── total_tokens
└── model             <- which model was used
```

You will use `usage_metadata` later in Archaeon to track cost per query.

### Responses are not always right

The model generates statistically likely text — it does not "know" things the way a
database does. This is why Archaeon feeds it **real evidence** from the codebase,
to ground its answers in facts rather than guesses.

---

## 6. Tokens

### The idea

LLMs break text into small pieces called **tokens** and convert each to a number.
A token is roughly one common word, part of a long word, or a punctuation mark.

### Approximate rules of thumb

```
1 token  ≈  4 characters of English text
100 tokens ≈ 75 words
1,000 tokens ≈ ~750 words ≈ ~1.5 pages
```

### Why tokens matter for Archaeon

**Cost** — you pay per token sent and received.

**Context window** — every model has a maximum number of tokens it can process in one
request (input + output combined).

```
gemini-3.6-flash context window: 1,000,000 tokens
```

**Chunking** — when Archaeon splits source code into pieces for the vector database,
it splits by token count, because that is how the model measures text size.

### Example tokenisation

```
"Why does this function retry three times?"
```

Tokenised roughly as:

```
["Why", " does", " this", " function", " retry", " three", " times", "?"]
```

8 tokens. The model receives numbers, processes them, and returns numbers that get decoded
back into text.

---

## Summary

| Concept | One-line definition |
|---|---|
| **API** | A way for your program to talk to a remote service over the internet |
| **API key** | A secret string that proves who you are to the API |
| **Model** | The specific AI that processes your request |
| **Prompt** | The text input you send to the model |
| **Response** | The structured object the model returns |
| **Tokens** | The units LLMs use to measure and process text |

---

## How they connect in your existing code

```python
load_dotenv(...)                          # load API KEY from .env
client = genai.Client(api_key=...)        # authenticate with the API using the key

interaction = client.interactions.create(
    model="gemini-3.6-flash",             # choose the MODEL
    input="Explain what a compiler does?" # write the PROMPT
)

print(interaction.output_text)            # read the RESPONSE
# tokens were counted behind the scenes for billing
```

This is the foundation. Everything in Archaeon — RAG, agents, evidence — is built on top
of this same loop.
