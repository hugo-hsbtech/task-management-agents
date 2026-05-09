# Prompts

Prompts are reusable message templates that clients can discover and render with arguments. They let you define structured interactions — system prompts, analysis workflows, multi-turn conversations — that LLM clients can invoke by name.

## Basic Prompt

```python
from fastmcp import FastMCP

mcp = FastMCP("MyServer")

@mcp.prompt
def review_code(code: str, language: str = "python") -> str:
    """Review code for best practices."""
    return f"Review this {language} code for best practices:\n\n```{language}\n{code}\n```"
```

The decorator infers the prompt name from the function name, the description from the docstring, and arguments from the function signature. Return a `str` and it becomes a single user message.

## Decorator Patterns

```python
# Bare decorator — name from function
@mcp.prompt
def analyze(topic: str) -> str: ...

# With parentheses — same as bare
@mcp.prompt()
def analyze(topic: str) -> str: ...

# Custom name
@mcp.prompt("code-review")
def review(code: str) -> str: ...

# All options
@mcp.prompt(
    name="code-review",
    description="Review code for issues",
    tags={"code", "review"},
)
def review(code: str) -> str: ...
```

## Return Types

Prompts support three return types with increasing control:

### String (simplest)

Returns a single user message.

```python
@mcp.prompt
def greet(name: str) -> str:
    return f"Hello, {name}!"
```

### List of Messages

Returns multiple messages with explicit roles. Useful for few-shot examples or multi-turn conversations.

```python
from fastmcp.prompts import Message

@mcp.prompt
def few_shot_classifier(text: str) -> list[Message]:
    return [
        Message("Classify the sentiment of the following text."),
        Message("The product is amazing!", role="user"),
        Message("Positive", role="assistant"),
        Message("I hate waiting in line.", role="user"),
        Message("Negative", role="assistant"),
        Message(text, role="user"),
    ]
```

### PromptResult (full control)

Returns messages with optional description and metadata.

```python
from fastmcp.prompts import PromptResult, Message

@mcp.prompt
def analysis(topic: str, depth: str = "brief") -> PromptResult:
    messages = [
        Message(f"You are an expert analyst. Provide a {depth} analysis."),
        Message(f"Analyze: {topic}", role="user"),
    ]
    return PromptResult(
        messages=messages,
        description=f"{depth.title()} analysis of {topic}",
    )
```

## Async Prompts

```python
@mcp.prompt
async def context_prompt(project_id: str) -> str:
    context = await fetch_project_context(project_id)
    return f"Given this project context:\n{context}\n\nHelp me with the next steps."
```

## Arguments

Arguments are inferred from function parameters. Required parameters become required arguments; parameters with defaults become optional.

```python
@mcp.prompt
def search_prompt(
    query: str,                          # required
    max_results: int = 10,               # optional, default 10
    include_archived: bool = False,      # optional, default False
) -> str:
    return f"Search for '{query}' (max {max_results}, archived={include_archived})"
```

**Important**: MCP passes all prompt arguments as strings. FastMCP auto-converts them to the declared types (int, bool, etc.) using Pydantic validation. If conversion fails, a `PromptError` is raised with a descriptive message.

## Non-String Argument Types

For complex types, FastMCP appends JSON schema info to the argument description so clients know the expected format:

```python
from pydantic import BaseModel

class SearchConfig(BaseModel):
    query: str
    filters: list[str] = []

@mcp.prompt
def structured_search(config: SearchConfig) -> str:
    """Search with structured config (pass as JSON string)."""
    return f"Search: {config.query}, filters: {config.filters}"
```

The client passes `config` as a JSON string like `'{"query": "solar", "filters": ["active"]}'`.

## Dependency Injection in Prompts

Prompts support `Depends()` and `Context` just like tools:

```python
from fastmcp import Context, Depends
from fastmcp.server.dependencies import get_access_token

@mcp.prompt
async def personalized_prompt(
    task: str,
    ctx: Context,
    token = Depends(get_access_token),
) -> str:
    user_id = token.client_id if token else "anonymous"
    ctx.info(f"Generating prompt for user {user_id}")
    return f"User {user_id} wants help with: {task}"
```

Injected parameters (`ctx`, `token`) are hidden from the prompt's argument list — clients only see `task`.

## Authorization

Gate prompts with auth checks, just like tools:

```python
from fastmcp.server.auth import require_scopes

@mcp.prompt(auth=require_scopes("prompts:read"))
def admin_prompt(query: str) -> str:
    return f"Admin query: {query}"
```

## Versioning

```python
@mcp.prompt(version="2")
def review_prompt(code: str) -> str:
    return f"Review this code (v2 template):\n{code}"
```

## Tags and Icons

```python
from mcp.types import Icon

@mcp.prompt(
    tags={"analysis", "research"},
    icons=[Icon(type="emoji", id="magnifying_glass")],
)
def research(topic: str) -> str:
    return f"Research {topic} thoroughly."
```

## Programmatic Registration

Register prompts without decorators using `add_prompt()`:

```python
from fastmcp.prompts.prompt import Prompt

# From a function
mcp.add_prompt(my_function)

# From a Prompt object
prompt = Prompt.from_function(
    my_function,
    name="custom-name",
    description="Custom description",
)
mcp.add_prompt(prompt)
```

## Client Usage

Clients discover and render prompts via the MCP protocol:

```python
from fastmcp.client import Client

async with Client(transport) as client:
    # List available prompts
    prompts = await client.list_prompts()
    for p in prompts:
        print(f"{p.name}: {p.description}")

    # Render a prompt with arguments
    result = await client.get_prompt("review_code", arguments={"code": "x = 1", "language": "python"})
    for msg in result.messages:
        print(f"[{msg.role}] {msg.content.text}")
```

## Message Helper

The `Message` class auto-serializes non-string content to JSON:

```python
from fastmcp.prompts import Message

Message("plain text")                    # TextContent, role="user"
Message("response", role="assistant")    # TextContent, role="assistant"
Message({"key": "value"})                # JSON-serialized TextContent
Message(["item1", "item2"])              # JSON-serialized TextContent
Message(my_pydantic_model)               # JSON-serialized TextContent
```

## Background Execution

Prompts support background execution via tasks (requires Docket/Redis):

```python
from fastmcp.server.tasks.config import TaskConfig

@mcp.prompt(task=TaskConfig(mode="supported"))
async def long_analysis(topic: str) -> str:
    data = await expensive_research(topic)
    return f"Analysis of {topic}:\n{data}"
```

When `task_meta` is provided by the client, the prompt runs in the background and returns a task ID for polling.

---

> Documentation Index: https://gofastmcp.com/llms.txt
