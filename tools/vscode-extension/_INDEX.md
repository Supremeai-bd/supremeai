# tools/vscode-extension/ — File Index
> AI: Extension = 100% Thin Client। কোনো LLM logic এখানে থাকবে না।

## Key Files
| File | কী করে | Status |
|---|---|---|
| `src/services/SupremeAIService.ts` | Backend API communication layer | ⚠️ OpenRouter fallback আছে — REMOVE করতে হবে |
| `src/extension.ts` | Extension entry point, command registration | OK |
| `src/providers/SwarmPipelineProvider.ts` | `/api/chat/stream` SSE handler | OK |
| `package.json` | VS Code manifest, commands, settings | OK |

## Architecture Rule
```
User → Extension (Thin Client) → SupremeAI Backend → [LLM providers hidden]
                                      ↑
                          শুধু এখানেই সব intelligence
```

## Pending Work
- `SupremeAIService.ts` lines 350-424: OpenRouter fetch logic → **রিমুভ করতে হবে**
- Brand: GPT/OpenRouter/Groq নাম extension UI-তে দেখানো যাবে না
