# Engine Template (Standalone)

This folder is a clean starter for a custom agent.
It is intentionally generic and independent from the helpdesk-specific flows.

## Files

- `generic_engine.py` - reusable 5-phase LangGraph engine
- `prompts_template.py` - replace with your domain prompt rules
- `tools_template.py` - replace read/write placeholders with real tools
- `graph_template.py` - specialization wiring example

## How to use

1. Copy this folder into your project (or keep it here).
2. Replace prompts in `prompts_template.py`.
3. Implement real tool functions in `tools_template.py` (e.g. Zendesk API).
4. Build your app endpoint and call `build_agent_graph(llm=...)`.
5. Enforce required-field validation in backend before write tool calls.

## Context for LLM

Give the model explicit runtime context on every turn to reduce hallucinations:

- `thread_id`: stable conversation identifier
- `known_fields`: dictionary of already collected fields
- `missing_fields`: required fields still missing
- `requester_profile`: normalized requester info (name/email/company)
- `business_rules`: hard constraints (when ticket can/cannot be opened)

Minimal example payload passed before the user message:

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

Recommended guardrails:

1. Ask only one missing field at a time.
2. Never invent IDs, emails, or ticket attributes.
3. Call write tools only when `missing_fields` is empty.
4. Re-validate required fields server-side before opening the ticket.

## Suggested flow for requester intake

1. Chat with requester
2. Fill required fields progressively
3. When complete, call write tool to open external ticket
4. Return final confirmation with external ticket ID

