# Engine Template (Standalone)

This folder is a reusable starter to build a domain-specific agent.
It is intentionally generic and independent from the helpdesk flows.

Use it when you want to:
- clone a base agent quickly
- collect structured data via chat
- open tickets/tasks only when required data is complete
- keep domain logic in tools and prompts (not in graph wiring)

---

## What You Get

- `generic_engine.py`  
  Reusable LangGraph engine with 5 phases:
  1) mission
  2) scan
  3) think
  4) act
  5) learn (final user-facing reply)

- `prompts_template.py`  
  Replace with domain instructions, style, constraints, and policies.

- `tools_template.py`  
  Placeholder read/write tools. Replace with real API/DB integrations.

- `graph_template.py`  
  Shows how to wire prompts + tools into the generic engine.

---

## Architecture in 30 Seconds

The graph loops between model and tools:

1. **mission**: understand request
2. **scan**: call read tools if needed
3. **think**: decide what is missing
4. **act**: call write tools only when allowed
5. **learn**: produce final user-facing response

Routing rule:
- if model emits tool calls -> execute tools and loop back
- else move to next phase

This gives you predictable behavior while keeping the domain-specific logic outside the engine.

---

## Quick Start

1. Copy `starter/engine_template` into your project.
2. Install dependencies in your project:
   - `langgraph`
   - `langchain-core`
   - your LLM provider package (`langchain-openai`, `langchain-groq`, `langchain-ollama`, etc.)
3. Edit `prompts_template.py` with your domain.
4. Replace tools in `tools_template.py` with real implementations.
5. Build your app endpoint and invoke `build_agent_graph(llm=...)`.

---

## How to Specialize for Your Use Case

### 1) Prompts (`prompts_template.py`)

Define:
- what the agent is allowed to do
- what it must ask before action
- output style
- forbidden behaviors

Recommended rules:
- ask one missing field at a time
- never invent IDs/emails/attributes
- do not expose chain-of-thought
- open ticket only with complete required fields

### 2) Tools (`tools_template.py`)

Split tools into:
- **read tools**: fetch data/context/metadata
- **write tools**: create ticket, update status, send message, etc.

Always validate input in write tools, even if prompts already enforce constraints.

### 3) Graph (`graph_template.py`)

Keep this file thin:
- inject your LLM instance
- attach prompts and tools
- keep the generic engine unchanged unless truly necessary

---

## Context for LLM (Highly Recommended)

Pass explicit runtime context every turn to reduce hallucinations:

- `thread_id`: stable conversation identifier
- `known_fields`: already collected values
- `missing_fields`: still required values
- `requester_profile`: normalized user/contact info
- `business_rules`: hard constraints

Minimal example:

```json
{
  "thread_id": "abc-123",
  "known_fields": {
    "name": "Mario Rossi",
    "email": "mario@azienda.it"
  },
  "missing_fields": ["category", "priority", "description"],
  "business_rules": {
    "open_ticket_requires_all_required_fields": true
  }
}
```

---

## Example Pattern: Intake -> Ticket Creation

Use this deterministic pattern:

1. User message arrives
2. Extract/merge fields into state
3. Compute `missing_fields`
4. If missing:
   - ask one concise follow-up question
5. If complete:
   - call write tool (create ticket)
   - return confirmation with external ticket ID

Do not rely only on model decisions for gate checks.

---

## Minimal Endpoint Integration (Pseudo-flow)

1. Receive `{ message, thread_id? }`
2. Build `HumanMessage` with context + user text
3. Invoke graph with checkpointer config by `thread_id`
4. Return:
   - `reply`
   - `trace` (optional)
   - `ticket_id` (if created)

Persisted memory options:
- in-memory for local testing
- DB/Redis checkpointer for production-like behavior

---

## Guardrails Checklist

Before shipping, ensure:

- [ ] write tools re-validate mandatory fields server-side
- [ ] no ticket creation when required fields missing
- [ ] model cannot call non-registered tools
- [ ] sensitive data is masked in logs/traces
- [ ] retries/timeouts are configured for external APIs
- [ ] idempotency strategy exists for ticket creation
- [ ] user replies stay concise and domain-safe

---

## Troubleshooting

### Agent keeps asking the same question
- Ensure `known_fields` is persisted and re-injected each turn.
- Add dedup logic for repeated follow-ups.

### Agent opens ticket too early
- Add strict backend validation in write tool.
- Reinforce act-phase prompt with explicit gate.

### Hallucinated IDs/emails
- Provide stronger runtime context.
- Forbid synthetic identifiers in prompts.
- Reject invalid identifiers in tool layer.

### Tool call errors
- Confirm tool signatures match model arguments.
- Return structured, clear errors from tools.

---

## Suggested Next Step

Create a domain-specific copy:
- `my_prompts.py`
- `my_tools.py`
- `my_graph.py`

Keep `generic_engine.py` as shared core.

