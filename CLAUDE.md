# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ElonGPT is a Python Discord bot (discord.py 2.4) that integrates with OpenAI (ChatGPT, DALL-E 3), Ollama (local LLMs), CoinMarketCap, and an external backend REST API. Python 3.12.

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

**Entry points:** `main.py` (production) and `dev.py` (hot-reload wrapper).

**All slash commands live in a single file:** `bot/commands.py`. This file creates the `commands.Bot` instance and defines all command handlers using `bot.tree.command()`. No Cogs or extension loading is used.

**Module layout:**

- `bot/ai/` — AI provider wrappers: `ChatGPT` (AsyncOpenAI), `Ollama` (sync client), `ImageDallE` (DALL-E 3), plus `moderation.py` and `prompts.py`
- `bot/api/` — External backend HTTP calls via async `httpx` (`crud.py`) and URL/header helpers (`utils.py`)
- `bot/utils/` — `settings.py` loads all env vars via `python-decouple`; `__init__.py` has embed creation and base64 helpers

**No local database.** All persistence goes through `BACKEND_API_URL` (recipes, completions, images) and `UTILS_API_URL` (Barcelona matches).

## Key Patterns

- AI classes (`ChatGPT`, `Ollama`, `ImageDallE`) are instantiated fresh per command invocation, not shared
- Long-running commands use `interaction.response.defer()` + `interaction.followup.send()` to avoid Discord's 3-second timeout
- Content moderation via OpenAI's moderation API gates `/ollama` and `/tts` commands
- Backend API calls use Bearer token auth (`BACKEND_API_KEY`)
- All env vars are centralized as typed `Final` constants in `bot/utils/settings.py`

## Environment Variables

Secrets are managed via 1Password (see `.env.op` for the full list). Key vars: `DISCORD_TOKEN`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `CMC_PRO_API_KEY`, `OLLAMA_SERVER`, `OLLAMA_MODEL`, `BACKEND_API_URL`, `BACKEND_API_KEY`, `ADMIN_USER_ID`, `UTILS_API_URL`, `UTILS_API_KEY`.

## Style

- Formatter: **black** (line length 88)
- Import sorting: **isort** (profile=black)
- Linter: **flake8** (max line length 120, ignores E203/W503)
- `env/` directory is excluded from all tools

## Deployment

Tags matching `1.*.*` trigger GitHub Actions: lint checks → Docker build → push to GHCR (`ghcr.io`) → SSH deploy to remote server.

## Development

You can always use the context7 mcp tools to search for library documentation when working with external libraries or in general.
