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

### Docker

```bash
docker build -t elongpt:tag .
```

## Architecture

**Entry points:** `main.py` (production) and `dev.py` (hot-reload wrapper). `main.py` starts the bot, registers an `on_ready` event with a status loop, and calls `bot.run()`. `dev.py` wraps `main.py` with watchdog for file-change auto-reload.

**All slash commands live in a single file:** `bot/commands.py`. This file creates the `commands.Bot` instance and defines all command handlers using `bot.tree.command()`. No Cogs or extension loading is used. Current commands: `/ask`, `/imagine`, `/price`, `/joke`, `/synccommands`.

**Module layout:**

- `bot/ai/chat.py` — `ChatGPT` class wraps `AsyncOpenAI`; instantiated with `OPENAI_API_KEY` and optional `OPENAI_API_BASE_URL` (lets the same code target OpenAI or any compatible provider). Single `ask()` method handles plain prompts, vision (base64 images), and tool-calling.
- `bot/ai/image.py` — `OpenAiImageGeneration` wraps `AsyncOpenAI` with model `gpt-image-1.5`; reuses the same `OPENAI_API_KEY`/`OPENAI_API_BASE_URL` as chat.
- `bot/ai/tools.py` — OpenAI function-calling tool definitions. Currently has `WebSearch` (DeutschlandGPT `/v2/search`, authenticated with `OPENAI_API_KEY` — always enabled) and `CreateScheduledEvent` for Discord server event creation. Tools use pydantic models validated via `openai.pydantic_function_tool()`. `CreateScheduledEvent` is omitted from `TOOL_DEFINITIONS` when `EVENTS_VOICE_CHANNEL_ID` is unset, so the model never sees a tool it can't fulfill.
- `bot/ai/prompts.py` — Two-template structure: `DEFAULT_SYSTEM_PROMPT` (placeholders: `{user_name}`, `{today_date}`) and `DEFAULT_USER_PROMPT` which wraps chat context and the user message in `<context>` / `<user_message>` XML tags. The system prompt explicitly tells the model to treat `<context>` as data, not instructions — preserve this when editing prompts.
- `bot/ai/moderation.py` — `check_moderate()` uses OpenAI's moderation API.
- `bot/db/` — DynamoDB persistence via `boto3`. `client.py` builds the boto3 `dynamodb` resource (region/credentials fall back to boto3's default chain when env vars are unset). `completion.py`'s `db_insert_completion()` puts a `CompletionModel` (`types.py`) item into the `DYNAMODB_TABLE_NAME` table. `utils.py` has a `generate_uuid()` helper.
- `bot/utils/` — `settings.py` loads all env vars via `python-decouple`; `__init__.py` has embed creation and base64 helpers.

**Persistence is DynamoDB.** Completions are logged via `db_insert_completion()` (`bot/db/completion.py`). Logging failures in `/ask` are caught and printed, not fatal.

## Key Patterns

- AI classes (`ChatGPT`, `OpenAiImageGeneration`) are instantiated fresh per command invocation, not shared
- The `/ask` command runs a tool-calling loop (up to 3 iterations) — it sends the prompt with tools, executes any tool calls, feeds results back, and repeats until the model responds with text
- `get_chat_context()` builds context from online guild members + last 10 channel messages and is injected into the **user** prompt's `<context>` block (not the system prompt)
- Long-running commands use `interaction.response.defer()` + `interaction.followup.send()` to avoid Discord's 3-second timeout
- All env vars are centralized as typed `Final` constants in `bot/utils/settings.py`

## Environment Variables

Secrets are managed via 1Password (see `.env.op` for the full list).

Required: `DISCORD_TOKEN`, `ADMIN_USER_ID`, `OPENAI_API_KEY` (`settings.py` calls `env(...)` with no default — startup will crash if missing).

Optional (feature gates / overrides — `settings.py` provides defaults or `None`):

- `OPENAI_API_BASE_URL` — point chat + image at a non-OpenAI compatible provider; unset uses real OpenAI
- `OPENAI_MODEL` — chat model, defaults to `gpt-5.4-mini`
- `EVENTS_VOICE_CHANNEL_ID` — when unset, `CreateScheduledEvent` is dropped from `TOOL_DEFINITIONS` and `/ask` cannot schedule events
- `DGPT_SEARCH_URL` — web-search endpoint, defaults to `https://api.deutschlandgpt.de/v2/search`. Authenticated with `OPENAI_API_KEY`, so the `WebSearch` tool needs no key of its own and is always enabled. Points at DeutschlandGPT — if `OPENAI_API_BASE_URL` is aimed at real OpenAI instead, search calls will 401.
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
