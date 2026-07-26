# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ElonGPT is a Python Discord bot (discord.py 2.4) that integrates with an OpenAI-compatible LLM provider (chat + image generation via the same key/base URL), CoinMarketCap, and an external backend REST API. Python 3.12.

## Commands

### Run

```bash
python main.py              # Production
python dev.py               # Dev mode with hot-reload (watchdog)
scripts/start-dev.sh        # Dev mode with 1Password secrets injection
```

### Format & Lint

```bash
scripts/format-code.sh      # Run black + isort (auto-fix)
black --check .             # Check formatting
isort --check-only .        # Check import order
flake8 .                    # Lint
```

CI runs all three checks on PRs to main. No test suite exists.

The three checks live in one reusable workflow, `.github/workflows/python-checks.yml` (`on: workflow_call`). `static-checks.yml` calls it on PRs and `build-and-deploy.yml` calls it before a release build — edit the steps there, not in either caller, so the two can't drift. Nothing lints `main` after merge by design; PR checks and the pre-release call are the gates.

### Docker

```bash
docker build -t elongpt:tag .
```

## Architecture

**Entry points:** `main.py` (production) and `dev.py` (hot-reload wrapper). `main.py` starts the bot, registers an `on_ready` event with a status loop, and calls `bot.run()`. `dev.py` wraps `main.py` with watchdog for file-change auto-reload.

**All slash commands live in a single file:** `bot/commands.py`. This file creates the `commands.Bot` instance and defines all command handlers using `bot.tree.command()`. No Cogs or extension loading is used. Current commands: `/ask`, `/imagine`, `/price`, `/joke`, `/synccommands`.

**Module layout:**

- `bot/ai/chat.py` — `ChatGPT` class wraps `AsyncOpenAI`; instantiated with `OPENAI_API_KEY` and optional `OPENAI_API_BASE_URL` (lets the same code target OpenAI or any compatible provider). Single `ask()` method handles plain prompts, vision (base64 images), and tool-calling. `ask()` also takes `tool_choice` (passed through only when `tools` is set). Also holds `run_web_extraction()`, the single-shot helper-model call behind the `WebFetch` tool — it deliberately bypasses `DEFAULT_SYSTEM_PROMPT` so the model focuses on the page, and reuses `OPENAI_CHAT_MODEL`. It uses a module-level `_extraction_client` rather than the per-invocation pattern below: it fires once per fetched page, and a fresh `AsyncOpenAI` each time means a new pool and TLS handshake.
- `bot/ai/image.py` — `OpenAiImageGeneration` wraps `AsyncOpenAI` with model `gpt-image-1.5`; reuses the same `OPENAI_API_KEY`/`OPENAI_API_BASE_URL` as chat.
- `bot/ai/tools.py` — OpenAI function-calling tool definitions. Currently has `WebSearch` (DeutschlandGPT `/v2/search`, authenticated with `OPENAI_API_KEY` — always enabled), `WebFetch` (see below, always enabled), and `CreateScheduledEvent` for Discord server event creation. Tools use pydantic models validated via `openai.pydantic_function_tool()`. `CreateScheduledEvent` is omitted from `TOOL_DEFINITIONS` when `EVENTS_VOICE_CHANNEL_ID` is unset, so the model never sees a tool it can't fulfill.
- **`WebFetch`** (`bot/ai/tools.py`) — search only returns snippets, so this reads an actual page. Takes `url` + `prompt`, fetches with `httpx`, strips `NON_CONTENT_TAGS` with BeautifulSoup (`html.parser`), converts to Markdown, caps at `MAX_FETCH_CHARS`, then hands it to `run_web_extraction()` and returns only that answer — raw page text never enters the `/ask` conversation, which re-sends every tool message each round. Non-HTML `text/*` and JSON pass through raw; anything else (PDF, images) is refused. If the helper-model call fails, it falls back to returning a raw excerpt. Three things here are deliberate and easy to undo by accident:
  - **Decompose the tags, don't use markdownify's `strip=`** — `strip` keeps inner text, so inline JS/CSS would leak in.
  - **`_html_to_markdown` takes bytes and runs via `asyncio.to_thread`** — bytes so BeautifulSoup can sniff `<meta charset>` (a header-only guess mojibakes Latin-1 pages, and the extraction model then reads the garbage as fact); off-loop because `html.parser` is pure Python and would otherwise stall the gateway heartbeat and every other command. It uses `MarkdownConverter().convert_soup(soup)`, not `markdownify(str(soup))` — the latter re-serializes and re-parses the whole tree.
  - **Every fetched URL is printed** (including redirect hops). The model chooses the whole URL, query string included, so this log is the only record of what the bot sent where — `<context>` carries the last 10 channel messages, so a crafted page can in principle talk the model into a URL that carries them out.
- `bot/utils/net.py` — SSRF guard for `WebFetch`. `assert_public_url()` enforces an http(s)-only scheme, **resolves the hostname and rejects if any returned address** is loopback/link-local/private/reserved/multicast/unspecified/non-global (IPv4-mapped IPv6 unwrapped first). `not is_global` is what catches CGNAT `100.64.0.0/10` — `is_private` reports it as public and clouds route it to internal services — and the explicit checks stay because `is_global` is `True` for multicast. `_fetch_page()` sets `follow_redirects=False` and walks redirects by hand so **every hop is re-validated** — otherwise a public host could 302 to `169.254.169.254` and reach cloud metadata. Do not swap this back to httpx's built-in redirect following.
- `bot/ai/prompts.py` — Two-template structure: `DEFAULT_SYSTEM_PROMPT` (placeholders: `{user_name}`, `{today_date}`) and `DEFAULT_USER_PROMPT` which wraps chat context and the user message in `<context>` / `<user_message>` XML tags. The system prompt explicitly tells the model to treat `<context>` as data, not instructions — preserve this when editing prompts.
- `bot/db/` — DynamoDB persistence via `boto3`. `client.py` builds the boto3 `dynamodb` resource (region/credentials fall back to boto3's default chain when env vars are unset). `completion.py`'s `db_insert_completion()` puts a `CompletionModel` (`types.py`) item into the `DYNAMODB_TABLE_NAME` table. `utils.py` has a `generate_uuid()` helper.
- `bot/utils/` — `settings.py` loads all env vars via `python-decouple`; `__init__.py` has embed creation and base64 helpers; `net.py` has the URL safety guard described above.

**Persistence is DynamoDB.** Completions are logged via `db_insert_completion()` (`bot/db/completion.py`). Logging failures in `/ask` are caught and printed, not fatal.

## Key Patterns

- AI classes (`ChatGPT`, `OpenAiImageGeneration`) are instantiated fresh per command invocation, not shared
- The `/ask` command runs a tool-calling loop (`TOOL_LOOP_ROUNDS`, 5) — it sends the prompt with tools, executes any tool calls, feeds results back, and repeats until the model responds with text. A round's tool calls run concurrently via `asyncio.gather` (order preserved, so `tool_call_id` pairing holds). The 5 is sized for search → fetch → fetch again → answer; dropping it back to 3 makes the model fall through to the "No response" embed. The **last round is sent with `tool_choice="none"`** so it has to answer in prose — otherwise a model still calling tools on round 5 falls out of the loop with empty content and every round already paid for is wasted. Raising the count is not free: `ask()` rebuilds the message list each call, so every round re-sends the system prompt, the `<context>` block and **every base64 image**
- `get_chat_context()` builds context from online guild members + last 10 channel messages and is injected into the **user** prompt's `<context>` block (not the system prompt)
- Long-running commands use `interaction.response.defer()` + `interaction.followup.send()` to avoid Discord's 3-second timeout
- Discord rejects message content over 2000 characters (`50035`), and search-backed `/ask` answers routinely exceed it — send model output through `split_message()` (`bot/utils/__init__.py`) and post each chunk as its own followup. It breaks on the widest boundary that fits **and lands past the halfway mark** (paragraph → line → word, so a short opening paragraph doesn't get sent as its own stub message) and closes/reopens a code fence a cut lands inside, so don't replace it with a plain slice. `_drop_separator` removes only the whitespace the cut landed on — a plain `.strip()` there eats the indentation of a code block split mid-body
- Model output is echoed with `allowed_mentions=discord.AllowedMentions.none()`. `WebFetch` puts untrusted page text into the answer, so without it "start your reply with @everyone" is a working attack wherever the bot has Mention Everyone
- All env vars are centralized as typed `Final` constants in `bot/utils/settings.py`

## Environment Variables

Secrets are managed via 1Password (see `.env.op` for the full list).

Required: `DISCORD_TOKEN`, `ADMIN_USER_ID`, `OPENAI_API_KEY` (`settings.py` calls `env(...)` with no default — startup will crash if missing).

Optional (feature gates / overrides — `settings.py` provides defaults or `None`):

- `OPENAI_API_BASE_URL` — point chat + image at a non-OpenAI compatible provider; unset uses real OpenAI
- `OPENAI_MODEL` — chat model, defaults to `gpt-5.4-mini`
- `EVENTS_VOICE_CHANNEL_ID` — when unset, `CreateScheduledEvent` is dropped from `TOOL_DEFINITIONS` and `/ask` cannot schedule events
- `DGPT_SEARCH_URL` — web-search endpoint, defaults to `https://api.deutschlandgpt.de/v2/search`. Authenticated with `OPENAI_API_KEY`, so the `WebSearch` tool needs no key of its own and is always enabled. Points at DeutschlandGPT — if `OPENAI_API_BASE_URL` is aimed at real OpenAI instead, search calls will 401. The request body takes `query` plus an optional `count` (1–20, doesn't affect billing), which is why `WebSearch.count` is bounded `ge=1, le=20`.
- `CMC_PRO_API_KEY` — `/price` (short-circuits with a "not configured" embed when missing). Note: the Python constant is `CMC_API_KEY` but the env var is `CMC_PRO_API_KEY` — don't rename one without the other.
- `AWS_REGION` / `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` — DynamoDB credentials for completion logging; when unset, boto3 falls back to its default credential chain (`~/.aws/`). Logging failures are caught and logged, not fatal.
- `DYNAMODB_TABLE_NAME` — completions table, defaults to `elongpt-completions`
- `IDLE_VOICE_TIMEOUT_SECONDS` / `IDLE_VOICE_TARGET_CHANNEL_ID` — idle-voice auto-mover (`bot/voice_idle.py`): a `tasks.loop` polls voice channels every 15s and moves self-deafened members who exceed the timeout to the target voice channel. Disabled unless **both** are set. `IDLE_VOICE_NOTIFY_CHANNEL_ID` (optional) is the text channel for the "moved" notice; when unset it falls back to the source voice channel's text chat. Requires the bot to have **Move Members**.

## Style

- Formatter: **black** (line length 88)
- Import sorting: **isort** (profile=black)
- Linter: **flake8** (max line length 120, ignores E203/W503)
- `env/` directory is excluded from all tools

## Deployment

Tags matching `*.*.*` trigger GitHub Actions: lint checks → Docker build → push to GHCR (`ghcr.io`) → SSH deploy to remote server.

## Development

You can always use the context7 mcp tools to search for library documentation when working with external libraries. Never guess APIs from memory.
