# Test Lessons

Durable, hard-won facts about this repo's tests and why they fail in non-obvious
ways. Read this when a failure is confusing. Append a new entry whenever a fix
turned on something you would not have guessed from the traceback.

Format: one short entry per lesson — what bit, and the rule that prevents it.

<!-- Example:
## pydantic: duplicate field silently shadows
A field declared twice in a model keeps only the last declaration. `TranscriptionResult`
must declare `provider`, `language`, and `segments` exactly once each.
-->
