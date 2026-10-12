# Framework, Not an LLM

Separate `GmailTechnicalStack` composition: 1920x1080, 60fps, 600 frames / 10 seconds. Graphics-only as explicitly selected by the user. Previous video outputs are unchanged.

## Edit Map

- 0-2.5s: Python + LangGraph + Gmail API + SQLite reveal one at a time.
- 2.5-4.5s: highlighted actual `langgraph==1.2.8` dependency in `pyproject.toml`, line 11. The source excerpt is generated directly from lines 9-15, not fabricated editor footage. Build asserts the dependency still matches.
- 4.5-7.65s: "No runtime LLM calls." Metadata fields travel along a simple Python-rules path into a read-only report illustration. It is explicitly not live execution and not a full architecture diagram.
- 7.65-10s: transition to Analyze / Identify / Suggest / Review / Organize. Review is amber and Organize remains inactive. No approval or cleanup is implied.

No presenter, chatbot, fabricated speech, synthetic data claims, full module tour or source modifications. Original background music is ducked for the LLM clarification and fades out at the end. See `STACK-AUDIO.md`.

## Build

```powershell
npm run prepare:stack
npm run audio:stack
npm run typecheck
npm run stills:stack
npm run render:stack
npm run finalize:stack
```

Delivery: `out/gmail-cleanup-agent-stack-10s-1080p.mp4`.
Verification: `out/stack-verification.json`.
