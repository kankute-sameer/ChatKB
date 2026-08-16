FILE_SUMMARY_PROMPT = """Summarize this document in 2-3 sentences.
The summary will be used as this file's entry in a collection index.
Write a concise container summary that captures the topic, scope, and key contents.
Return only the summary.

Document:
{content}
"""

TABLE_SCHEMA_PROMPT = """Improve the YAML table description below.
Keep exactly these top-level fields: type, title, summary, resource, columns.
Keep every column name and inferred type unchanged. Replace generic column
descriptions with concise semantic descriptions inferred from the names and
sample context. Return only valid YAML-style text beginning with `type: table`.

Draft:
{schema}

Sample rows:
{sample}
"""
