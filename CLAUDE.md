# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ElonGPT is a Python Discord bot (discord.py 2.4) that integrates with OpenAI-compatible LLM providers, OpenAI image generation, CoinMarketCap, and an external backend REST API. Python 3.12.

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

- `bot/ai/chat.py` — `ChatGPT` class wraps AsyncOpenAI client; connects to a configurable provider via `DGPT_API_URL`/`DGPT_API_KEY` (not the OpenAI API directly). Has both `ask()` and `ask_with_tools()` methods.
- `bot/ai/image.py` — `OpenAiImageGeneration` class uses AsyncOpenAI with `gpt-image-1.5` model. This one uses `OPENAI_API_KEY` directly (not the DGPT provider).
- `bot/ai/tools.py` — OpenAI function-calling tool definitions. Currently has `CreateScheduledEvent` for Discord server event creation. Tools use pydantic models validated via `openai.pydantic_function_tool()`.
- `bot/ai/prompts.py` — System prompt template with `{user_name}`, `{context}`, `{today_date}` placeholders.
- `bot/ai/moderation.py` — `check_moderate()` uses OpenAI's moderation API.
- `bot/api/` — External backend HTTP calls via async `httpx` (`crud.py`) and URL/header helpers (`utils.py`)
- `bot/utils/` — `settings.py` loads all env vars via `python-decouple`; `__init__.py` has embed creation and base64 helpers

**No local database.** All persistence goes through `BACKEND_API_URL` (completions logging).

## Key Patterns

- AI classes (`ChatGPT`, `OpenAiImageGeneration`) are instantiated fresh per command invocation, not shared
- The `/ask` command runs a tool-calling loop (up to 3 iterations) — it sends the prompt with tools, executes any tool calls, feeds results back, and repeats until the model responds with text
- `get_chat_context()` builds context from online guild members + last 10 channel messages, passed to the LLM as part of the system prompt
- Long-running commands use `interaction.response.defer()` + `interaction.followup.send()` to avoid Discord's 3-second timeout
- Backend API calls use Bearer token auth (`BACKEND_API_KEY`)
- All env vars are centralized as typed `Final` constants in `bot/utils/settings.py`

## Environment Variables

Secrets are managed via 1Password (see `.env.op` for the full list). Key vars: `DISCORD_TOKEN`, `EVENTS_VOICE_CHANNEL_ID`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `CMC_PRO_API_KEY`, `BACKEND_API_URL`, `BACKEND_API_KEY`, `ADMIN_USER_ID`, `UTILS_API_URL`, `UTILS_API_KEY`, `DGPT_API_URL`, `DGPT_API_KEY`.

Note: `ChatGPT` (chat completions) uses `DGPT_API_URL`/`DGPT_API_KEY` while `OpenAiImageGeneration` uses `OPENAI_API_KEY` directly.

## Style

- Formatter: **black** (line length 88)
- Import sorting: **isort** (profile=black)
- Linter: **flake8** (max line length 120, ignores E203/W503)
- `env/` directory is excluded from all tools

## Deployment

Tags matching `*.*.*` trigger GitHub Actions: lint checks → Docker build → push to GHCR (`ghcr.io`) → SSH deploy to remote server.

## Development

You can always use the context7 mcp tools to search for library documentation when working with external libraries or in general.
