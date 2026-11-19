# SupremeAI Gateway

The [Gateway Dockerfile](Dockerfile) runs `gateway.service.app:app`. Use the same app for local development and chat contract tests.

## Run locally

Before starting the app, set `SUPREMEAI_API_KEY` for client authentication and configure an approved provider credential (for example, `GROQ_API_KEY`) in the local environment. Keep both out of source control; clients only need the Gateway credential.

From the repository root:

```bash
python -m pip install -r gateway/requirements.txt
python -m uvicorn gateway.service.app:app --port 8787
```

| Route | What it proves |
| --- | --- |
| `GET /health` | The process is responding, not that a provider can answer. |
| `GET /readyz` | An eligible API slot or a configured, DNS-resolvable relay exists. It does not send an inference request. |
| `GET /release` | The running build identity, when a commit SHA was supplied. |
| `GET /v1/models` | Public model aliases, not a list of verified upstream models. |
| `POST /v1/chat/completions` | Authenticated OpenAI-compatible completion. Use `stream: true` for SSE. |
| `POST /api/v1/stream/chat` | Legacy SSE alias that delegates to the same chat handler. |

For streamed API-provider completions, the Gateway can try another model or slot **before** the first text or tool delta. After it starts sending output, a failed stream sends an error frame followed by `[DONE]`, without retrying or emitting a successful finish. `[DONE]` ends the transport; check the preceding frames for the result.

## API and relay lanes

A client key authenticates the caller. It does not approve a provider route or
act as a provider credential. Before enabling the API pool, configure and stage
[`SUPREMEAI_FREE_ROUTE_POLICY`](SECRETS_MODEL.md#gateway-free-api-route-approval).
Without a valid approval for a configured key and concrete model, the Gateway
does not send that provider any completions.

- `supremeai-api` (also `supremeai/api`) uses only approved API slots.
- `supremeai-web`, `supremeai/web`, `supremeai-webhook`, and the legacy relay
  aliases use only the configured relay. A relay error never tries API keys.
- Other text aliases prefer eligible API slots and can select the relay if the
  pool has no eligible slot at route selection. This is not an entitlement test
  for the relay or an automatic replay after a failed API attempt.
- Image input requires an explicitly approved vision model. It does not fall
  through to text-only models or to the relay. V0 UI generation likewise needs
  a separately approved V0 route.

The API skips a model after HTTP 402; 402 is a withdrawal signal, not a way to
test for free usage. No startup or request-error inference probes are sent. The
legacy shared Gateway response cache is not used for serving chat.

## Offline tests

With `pytest` and `pytest-asyncio` installed:

```bash
python -m pytest -q gateway/tests/test_docker_gateway_chat.py gateway/tests/test_stream_first_token_timeout.py gateway/tests/test_free_model_discovery.py
```

These tests use mock responses; they do not require provider credentials or a running server.

## Reference factory

[`gateway.main.create_app`](main.py) is a separate reference app for the [Gateway OpenAPI contract](../api-schemas/gateway.openapi.yaml) and [routing policy](routing_policy.json). Its runnable entrypoint is `gateway.serve:app`, which supports a test-only mock provider. See [the factory's tests](tests/test_streaming_gateway.py) for its route, scope and rate-limit contracts. They do not substitute for testing the Docker entrypoint.
