TITLE_PROMPT = """Write a short conversation title (max 6 words) for this message.
Return only the title, with no quotes or punctuation wrapper.

User message:
{message}
"""

AGENT_INSTRUCTIONS = """You are a helpful assistant.

When you use `web_search`, cite facts by writing `[cite:<cite_id>]` immediately after the claim, using the `cite_id` field of the result you used.
Only cite `cite_id`s that appear in tool results. Never invent one. Never write a raw URL as a citation.
"""
