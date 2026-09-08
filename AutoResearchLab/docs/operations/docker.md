# Docker operations

## Default local profile

The default Compose service runs the API as an unprivileged user with a
read-only application filesystem. SQLite state, research artifacts, logs, and
task sandboxes live in the `maars-data` named volume. Its optional RAG
dependency uses the CPU-only PyTorch wheel, preventing a web-service build from
pulling NVIDIA CUDA packages.

```bash
cp .env.example .env
docker compose up --build
curl http://localhost:3001/healthz
```

Use Mock mode from the UI for the first smoke test. It requires no model API
key. Real provider credentials belong in local `.env` or the deployment secret
manager, never in a committed Compose file.

## LLM API configuration

Do not put a key in the browser's **API Key** field: that setting is persisted
in SQLite. Instead, create the ignored `.env` file from `.env.example`.

For Gemini:

```dotenv
MAARS_LLM_PROVIDER=gemini
MAARS_API_KEY=your_Gemini_API_key
MAARS_MODEL=gemini-2.5-flash
```

For DeepSeek's OpenAI-compatible API:

```dotenv
MAARS_LLM_PROVIDER=deepseek
MAARS_API_KEY=your_DeepSeek_API_key
MAARS_API_BASE_URL=https://api.deepseek.com
MAARS_MODEL=deepseek-chat
```

Restart the service after changing `.env`:

```bash
docker compose up -d --build
```

Then open Settings (Alt+Shift+S on Windows/Linux), select **LLM** for the
agents you want to run, and save. Leave the browser API Key field empty. Agent
modes and preset selection are saved in SQLite, but `MAARS_API_KEY` from the
environment overrides UI credentials at runtime and is never persisted by the
application. DeepSeek supports the single-turn **LLM** mode; **Agent** mode
uses Google ADK and remains Gemini-only. Use **Mock** mode whenever you want
an offline, no-cost test.

Useful lifecycle commands:

```bash
docker compose logs -f maars-api
docker compose down
docker compose down --volumes  # removes all local MAARS runtime state
```

## Task Agent Docker mode

Task Agent Docker mode creates a container for each atomic task. Build its
scientific-computing image first:

```bash
docker compose --profile task-runtime build
```

The API needs Docker CLI plus access to a Docker daemon to manage those task
containers. This is a privileged capability: a process that controls Docker
can effectively control the host. Only on a trusted development machine, start
the opt-in profile with:

```bash
docker compose -f compose.yaml -f compose.task-agent.yaml up --build
```

Do not expose this profile to untrusted users or mount the production Docker
socket. For production, route task execution to a separate, policy-restricted
worker service with its own Docker/VM boundary.
