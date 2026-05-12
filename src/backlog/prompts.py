"""Prompts for the provider-agnostic backlog agent."""

BACKLOG_SYSTEM_PROMPT = """You are a backlog planning agent.

Transform product plans into implementation-ready backlog issues.

You must return a single JSON object and nothing else. No markdown fences.
The JSON must validate against the BacklogOutput schema provided by the caller.
"""

BACKLOG_USER_PROMPT_TEMPLATE = """{{
  "task": "Create platform-ready backlog issues from the product plan.",
  "output_contract": {{
    "type": "BacklogOutput",
    "json_schema": {output_schema},
    "required_shape": {{
      "platform": {platform},
      "issues": [
        {{
          "action": "create",
          "issue_type": "epic | user_story | task",
          "fields": {{
            "title": "short implementation-ready title",
            "description": "actionable description with traceability back to the plan",
            "priority": "0..4 where 0=none and 4=urgent",
            "parent_id": "optional parent issue id or null",
            "labels": ["optional", "labels"],
            "platform_fields": {platform_defaults}
          }},
          "depends_on": ["optional ids"],
          "relations": [
            {{
              "type": "blocks | blocked_by | relates_to | duplicate_of",
              "target_title": "exact title of the related issue in this output"
            }}
          ]
        }}
      ]
    }}
  }},
  "rules": [
    "Return only JSON matching output_contract.json_schema.",
    "Produce at least one issue.",
    "Use action='create' unless the plan explicitly asks to modify existing work.",
    "Use issue_type only as one of: epic, user_story, task.",
    "Every issue must include title and description.",
    "Preserve plan traceability inside each issue description.",
    "Copy platform_fields exactly from required_shape.issues[0].fields.platform_fields unless a tool result provides a more specific value.",
    "Do not invent platform identifiers.",
    "Use relations only when the plan explicitly states a blocking or dependency between issues.",
    "target_title in relations must match the title of another issue in this same output exactly.",
    "Omit relations array if there are no relations for an issue."
  ],
  "input": {{
    "plan_content": {plan_content},
    "stacks": {stacks},
    "platform_name": {platform_name},
    "platform": {platform},
    "platform_defaults": {platform_defaults},
    "context": {context}
  }}
}}"""
