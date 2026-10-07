# 2. Transcription on OpenAI, LLM on Azure OpenAI

Date: 2026-08-31
Status: Accepted

## Context

The user wants Azure OpenAI as the default LLM provider (notes + Q&A), inside
their Azure tenant. The design depends on speaker diarization so action items
have owners.

Azure OpenAI's speech-to-text (`gpt-4o-transcribe`, `whisper`) does **not**
return speaker diarization — no `diarized_json`. Azure's diarization offering is
Azure AI Speech, a separate service with a different SDK, auth, and output shape.
OpenAI's `gpt-4o-transcribe-diarize` is the only turnkey "transcribe + diarize in
one call" option among the providers already in play, and it is the only OpenAI
model that diarizes at all.

## Decision

Default v1 configuration: **transcription via OpenAI direct**
(`gpt-4o-transcribe-diarize`, `OPENAI_API_KEY`); **LLM via Azure OpenAI**
(`AZURE_OPENAI_*`). Two provider credentials.

Both sit behind their own seams — `TRANSCRIBER_PROVIDER` (`openai` |
`azure-openai`) and the LangChain `init_chat_model` factory — so either side can
be re-pointed by config.

## Consequences

- Two credentials to hold in `.env` instead of one. Startup validation lists any
  missing var for the selected providers.
- Diarization quality is not compromised for tenant tidiness.
- `azure-openai` transcription remains a selectable value but is not implemented
  in v1 (it would require the Azure AI Speech adapter, or Azure `gpt-4o-
  transcribe` + local `pyannote`). Deferred with local transcription.
- If diarization quality disappoints on real recordings, AssemblyAI or local
  `whisperX` + `pyannote` are the upgrade paths, added as new `Transcriber`
  adapters without touching downstream code.
