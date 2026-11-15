# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ElonGPT is a Python Discord bot (discord.py 2.7) that integrates with an OpenAI-compatible LLM provider (chat + image generation via the same key/base URL), CoinMarketCap, and DynamoDB for completion logging. Python 3.14 — not 3.12/3.13: those don't build against Homebrew's OpenSSL 4, and discord.py < 2.5 can't import on 3.13+ (`audioop` was removed; 2.5+ pulls in `audioop-lts`).

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

The three checks live in one reusable workflow, `.github/workflows/ci.yml` (`on: workflow_call`). `static-checks.yml` calls it on PRs and `build-and-deploy.yml` calls it before a release build — edit the steps there, not in either caller, so the two can't drift. Nothing lints `main` after merge by design; PR checks and the pre-release call are the gates.

### Dependencies

`requirements.txt` / `requirements-dev.txt` are **compiled lockfiles** — edit the `.in` files and recompile, never the `.txt` directly:

```bash
pip-compile --strip-extras requirements.in
pip-compile --strip-extras requirements-dev.in
```

`requirements-dev.in` starts with `-c requirements.txt` so dev tooling can't drag a shared dependency to a different version than the runtime image gets. Versions in the `.in` files are pinned deliberately, so recompiling prunes without silently upgrading the bot.

### Docker

```bash
docker build -t elongpt:tag .
ELONGPT_IMAGE=elongpt:dev docker compose up -d --build
```

`docker-compose.yml` requires `ELONGPT_IMAGE` (no default — CI pins it to the GHCR tag) and reads secrets from a `.env` file. The container runs read-only with `cap_drop: ALL`, so anything that needs to write must go under the `/tmp` tmpfs.

The image is a multi-stage build on **alpine** (~161MB; it was 335MB on `python:3.12-slim`). Both stages pin the same digest — a multi-arch index, so CI's amd64 and local arm64 both resolve. Three things in the Dockerfile are load-bearing:

- **Alpine means musl, so every dependency needs a musllinux wheel.** The install runs with `--only-binary=:all:` so a package without one fails the build instead of trying a source build the image has no toolchain for. If a new dependency breaks the build here, that's the cause — the fix is a different package or a `build-base` install confined to the builder stage, not dropping the flag.
- **`botocore/data` is pruned to `dynamodb` + `sts`** (~24MB of ~400 AWS service models otherwise). Calling a _different_ AWS service raises `UnknownServiceError` at runtime, not at build time — add its data directory to the `find` exclusions in the same commit.
- **The venv is built `--without-pip`** and populated by the builder's pip via `pip --python /opt/venv/bin/python install` (the `--python` flag must precede the subcommand). Nothing installs packages at runtime.

Bytecode is deliberately kept in the image: `--no-compile` would save ~28MB but doubles cold-start import (0.61s → 1.22s measured), and under `read_only: true` nothing can cache `.pyc` afterward, so that cost repeats on every restart.

## Architecture

**Entry points:** `main.py` (production) and `dev.py` (hot-reload wrapper). `main.py` starts the bot, registers an `on_ready` event with a status loop, and calls `bot.run()`. `dev.py` wraps `main.py` with watchdog for file-change auto-reload.

**All slash commands live in a single file:** `bot/commands.py`. This file creates the `commands.Bot` instance and defines all command handlers using `bot.tree.command()`. No Cogs or extension loading is used. Current commands: `/ask`, `/imagine`, `/price`, `/joke`, `/synccommands`.

**Module layout:**

- `bot/ai/openai_client.py` — the single module-level `AsyncOpenAI` client (`OPENAI_API_KEY` + optional `OPENAI_API_BASE_URL`, which lets the same code target OpenAI or any compatible provider). Chat, image generation, and web extraction all import this one `client`, so they share a connection pool. Don't reintroduce per-call `AsyncOpenAI()` construction — each one means a fresh pool and TLS handshake.
- `bot/ai/chat.py` — plain async functions, no classes. `get_chat_completion()` builds the whole message list per call and handles plain prompts, vision (base64 images, capped at `files[:5]` to match the five `/ask` attachment params), and tool-calling; it takes `tool_choice`, passed through only when `tools` is set, and returns the raw `message` object so the caller can inspect `.tool_calls`. The system prompt is sent with role **`developer`**, not `system`. Also holds the single-shot helper-model calls behind `WebFetch` and `ReadChannel` — `run_web_extraction()` and `run_transcript_extraction()`, both thin wrappers over `_run_extraction()`, which deliberately bypasses `DEFAULT_SYSTEM_PROMPT` so the model focuses on the material rather than the bot persona, and reuses `OPENAI_CHAT_MODEL`. `get_chat_context()` lives here too and is now only an orienting header (channel + topic, guild, online members, capped at `MAX_ONLINE_LISTED`) — it makes **no** history call. Conversation history moved behind the `ReadChannel` tool; see Key Patterns.
- `bot/ai/image.py` — `generate_image()`, one function: calls `client.images.generate` with `OPENAI_IMAGE_MODEL` at 1024x1024 with `moderation="low"`, and returns decoded PNG bytes (the API answers with base64, not a URL).
- `bot/ai/tools.py` — the tool registry (`TOOL_DEFINITIONS`, `TOOL_HANDLERS`, `execute_tool_call()`) plus the web tools themselves. Has `WebSearch` (DeutschlandGPT `/v2/search`, authenticated with `OPENAI_API_KEY` — always enabled), `WebFetch` (see below, always enabled), and `CreateScheduledEvent` for Discord server event creation. Tools use pydantic models validated via `openai.pydantic_function_tool()`, wrapped in `_tool_definition()` which **pops the `strict: true` key that helper stamps on** — `strict` is OpenAI-only, and a gateway forwarding to a non-OpenAI model translates the tool into that provider's shape and 400s on the extra key (`tools.0.custom.strict: Extra inputs are not permitted`), killing every `/ask` since tools are always sent. `execute_tool_call()` re-validates arguments with the same pydantic model, so nothing is lost. `CreateScheduledEvent` is omitted from `TOOL_DEFINITIONS` when `EVENTS_VOICE_CHANNEL_ID` is unset, so the model never sees a tool it can't fulfill. The Discord read tools are defined in `discord_tools.py` and folded in through `DISCORD_TOOL_HANDLERS` — add new ones there, not here.
- `bot/ai/tool_context.py` — the frozen `ToolContext` (guild, channel, invoking user) every handler receives as its second argument. It replaced a bare `guild`, which is why `CreateScheduledEvent` was for so long the only Discord tool: a guild-level create was the only thing reachable with what got passed.
- `bot/ai/discord_tools.py` — the tools that reach into the server. Reads: `ReadChannel`, `SearchMessages`, `GetMessage`, `ListEvents`, `GetMemberInfo`, `ServerSnapshot`. One write: `SendToChannel`, gated behind `DISCORD_SEND_TOOL_ENABLED`. Several things here are load-bearing:
  - **Every tool mirrors the invoking user's permissions, never the bot's**, through `_resolve_channel()` — it checks `permissions_for()` for the asker _and_ for `guild.me`, in that order. `_resolve_readable()` and `_resolve_writable()` are one-line wrappers over it, differing only in the permission tuple and the verb in the error message. Reading requires `read_message_history`; **posting deliberately does not** — a suggestions channel you may write to but not read back is an ordinary Discord setup, and demanding read access to post would refuse it. The bot is usually the more privileged of the two, so without the mirror `/ask` is a permission-escalation path, and the model reads attacker-writable text from three directions (the context header, search snippets, fetched pages). `ServerSnapshot` filters its channel list the same way; unfiltered it leaks every private channel name in the server.
  - **`ReadChannel` makes the same trade-off as `WebFetch`.** Under `MAX_TRANSCRIPT_CHARS` with no `prompt` the transcript goes back raw — cheaper than a helper-model round trip. Past that, or whenever a `prompt` is given, `run_transcript_extraction()` reads it and only the answer is returned, so hundreds of messages never enter the `/ask` conversation. Truncation keeps the **recent** end.
  - **`SearchMessages` passes `oldest_first=False` explicitly.** `history()` flips that to `True` on its own when `after` is set, which would silently return the oldest matches instead of the newest — a bug that only surfaces once someone uses the `days` filter.
  - Bots get no server-side message search, so `SearchMessages` is a `history()` sweep bounded by `SEARCH_SCAN_CAP`. It reports `hit_scan_cap` so the model knows when it saw a truncated view.
  - **`SendToChannel` is the only tool whose effect is visible to people who did not run the command**, which is why it is off by default. Its gate is stricter than the one on `CreateScheduledEvent`: the handler is registered _only_ when the switch is on, so it vanishes from `TOOL_HANDLERS` as well as `TOOL_DEFINITIONS` and a hallucinated call cannot reach it either. It sends with `AllowedMentions.none()` (the message body can carry text the model absorbed from a fetched page), splits through `split_message()`, caps at `MAX_SEND_CHARS`, prefixes a `-#` subtext attribution so a bot post elsewhere is never anonymous, and prints every send — the same reasoning as the `WebFetch` URL log. The matching prompt clause in `_SEND_TOOL` says to post only when the _user_ asked, because "a web page told me to" is precisely the failure mode.
- **`WebFetch`** (`bot/ai/tools.py`) — search only returns snippets, so this reads an actual page. Takes `url` + `prompt`, fetches with `httpx`, strips `NON_CONTENT_TAGS` with BeautifulSoup (`html.parser`), converts to Markdown, caps at `MAX_FETCH_CHARS`, then hands it to `run_web_extraction()` and returns only that answer — raw page text never enters the `/ask` conversation, which re-sends every tool message each round. Non-HTML `text/*` and JSON pass through raw; anything else (PDF, images) is refused. If the helper-model call fails, it falls back to returning a raw excerpt. Three things here are deliberate and easy to undo by accident:
  - **Decompose the tags, don't use markdownify's `strip=`** — `strip` keeps inner text, so inline JS/CSS would leak in.
  - **`_html_to_markdown` takes bytes and runs via `asyncio.to_thread`** — bytes so BeautifulSoup can sniff `<meta charset>` (a header-only guess mojibakes Latin-1 pages, and the extraction model then reads the garbage as fact); off-loop because `html.parser` is pure Python and would otherwise stall the gateway heartbeat and every other command. It uses `MarkdownConverter().convert_soup(soup)`, not `markdownify(str(soup))` — the latter re-serializes and re-parses the whole tree.
  - **Every fetched URL is printed** (including redirect hops). The model chooses the whole URL, query string included, so this log is the only record of what the bot sent where. The exfiltration path is real and got wider, not narrower, when history moved to a tool: `ReadChannel` can pull hundreds of messages into the conversation, and a crafted page can in principle talk the model into a URL carrying them out.
- `bot/utils/net.py` — SSRF guard for `WebFetch`. `assert_public_url()` enforces an http(s)-only scheme, **resolves the hostname and rejects if any returned address** is loopback/link-local/private/reserved/multicast/unspecified/non-global (IPv4-mapped IPv6 unwrapped first). `not is_global` is what catches CGNAT `100.64.0.0/10` — `is_private` reports it as public and clouds route it to internal services — and the explicit checks stay because `is_global` is `True` for multicast. `_fetch_page()` sets `follow_redirects=False` and walks redirects by hand so **every hop is re-validated** — otherwise a public host could 302 to `169.254.169.254` and reach cloud metadata. Do not swap this back to httpx's built-in redirect following.
- `bot/ai/prompts.py` — Two-template structure: `DEFAULT_SYSTEM_PROMPT` (placeholders: `{user_name}`, `{today_date}`) and `DEFAULT_USER_PROMPT` which wraps the context header and the user message in `<context>` / `<user_message>` XML tags. Also holds `WEB_EXTRACTION_PROMPT` and `TRANSCRIPT_EXTRACTION_PROMPT`, one per helper-model call. Two clauses in the system prompt are load-bearing and must survive edits: the one naming every untrusted wrapper as **data, not instructions** (`<context>`, `<search_results>`, `<channel_transcript>`, `<channel_search_results>`, `<discord_message>`, `<discord_events>`, `<discord_member>`, `<server_snapshot>` — extend it when you add a tool), and the one in `_DISCORD_TOOLS` telling the model it **cannot see the conversation** and must read the channel when the request refers to it. The second exists because the eager 10-message dump is gone: left implicit, a model will answer "what were we just talking about?" out of thin air rather than call a tool.
- `bot/db/` — DynamoDB persistence via **`aioboto3`** (not `boto3` — the write happens on the event loop, so a blocking client would stall the gateway). `client.py` holds a module-level `aioboto3.Session` (region/credentials fall back to botocore's default chain when the env vars are unset); `completion.py`'s `db_insert_completion()` opens the `dynamodb` resource per call via `async with session.resource(...)` and puts a `CompletionModel` (`types.py`) item into the `DYNAMODB_TABLE_NAME` table. `utils.py` has a `generate_uuid()` helper.
- `bot/utils/` — `settings.py` loads all env vars via `python-decouple`; `__init__.py` has embed creation and base64 helpers; `net.py` has the URL safety guard described above.

**Persistence is DynamoDB.** Completions are logged via `db_insert_completion()` (`bot/db/completion.py`). Logging failures in `/ask` are caught and printed, not fatal.

## Key Patterns

- The AI layer is module-level async functions over one shared client (`bot/ai/openai_client.py`), not classes — `get_chat_completion()`, `generate_image()`, `run_web_extraction()`, `run_transcript_extraction()`. There is no per-invocation object to construct, and no conversation state is held between commands: `get_chat_completion()` rebuilds every message from its arguments
- The `/ask` command runs a tool-calling loop (`TOOL_LOOP_ROUNDS`, 5) — it sends the prompt with tools, executes any tool calls, feeds results back, and repeats until the model responds with text. A round's tool calls run concurrently via `asyncio.gather` (order preserved, so `tool_call_id` pairing holds). The 5 is sized for search → fetch → fetch again → answer; dropping it back to 3 makes the model fall through to the "No response" embed. A conversational question now spends a round on `ReadChannel` first, so read → search → fetch → answer still fits — if "No response" embeds start appearing, 6 is the fix. The **last round is sent with `tool_choice="none"`** so it has to answer in prose — otherwise a model still calling tools on round 5 falls out of the loop with empty content and every round already paid for is wasted. Raising the count is not free: `get_chat_completion()` rebuilds the message list each call, so every round re-sends the system prompt, the `<context>` block and **every base64 image**
- **The model is not shown the conversation; it fetches it.** `get_chat_context()` builds only a cheap orienting header — channel + topic, guild, online members — injected into the **user** prompt's `<context>` block (not the system prompt). It used to carry the last 10 channel messages; that moved to the `ReadChannel` tool. Two reasons worth preserving: message bodies were the one high-bandwidth attacker-writable thing entering every request, and they were sent on every question including ones with nothing to do with the channel. The cost is a round trip on conversational follow-ups, and the risk is the model answering from nothing instead of calling the tool — which is what the explicit instruction in `_DISCORD_TOOLS` exists to prevent. Display names are still user-chosen, so the "treat `<context>` as data" rule stays
- Long-running commands use `interaction.response.defer()` + `interaction.followup.send()` to avoid Discord's 3-second timeout
- Discord rejects message content over 2000 characters (`50035`), and search-backed `/ask` answers routinely exceed it — send model output through `split_message()` (`bot/utils/__init__.py`) and post each chunk as its own followup. It breaks on the widest boundary that fits **and lands past the halfway mark** (paragraph → line → word, so a short opening paragraph doesn't get sent as its own stub message) and closes/reopens a code fence a cut lands inside, so don't replace it with a plain slice. `_drop_separator` removes only the whitespace the cut landed on — a plain `.strip()` there eats the indentation of a code block split mid-body
- Model output is echoed with `allowed_mentions=discord.AllowedMentions.none()`. `WebFetch` puts untrusted page text into the answer, so without it "start your reply with @everyone" is a working attack wherever the bot has Mention Everyone. `SendToChannel` sets it on every chunk for the same reason — that path is worse, since the post lands in a channel nobody in the conversation is watching
- All env vars are centralized as typed module constants in `bot/utils/settings.py`, read through python-decouple's `config()`. Nothing else in the codebase calls `os.environ` — add new settings there, and give integer vars the `cast=lambda v: int(v) if v else None` treatment so an empty 1Password field stays `None` instead of blowing up `int("")`

## Environment Variables

Secrets are managed via 1Password (see `.env.op` for the full list).

`.env.op` is a 1Password template resolved with `op inject`/`op run`, and its paths interpolate `$ENVIRONMENT` (`scripts/start-dev.sh` sets `development`; the deploy job sets `production`) — a new secret needs a line there as well as in `settings.py`.

Required: `DISCORD_TOKEN`, `ADMIN_USER_ID`, `OPENAI_API_KEY` (`settings.py` calls `config(...)` with no default — startup will crash if missing).

Optional (feature gates / overrides — `settings.py` provides defaults or `None`):

- `OPENAI_API_BASE_URL` — point chat + image at a non-OpenAI compatible provider; unset uses real OpenAI
- `OPENAI_CHAT_MODEL` — chat model, defaults to `gpt-5.4-mini` (note: the var is `OPENAI_CHAT_MODEL`, not `OPENAI_MODEL`). Also used by the `WebFetch` extraction helper
- `OPENAI_IMAGE_MODEL` — `/imagine` model, defaults to `gpt-image-1.5`
- `EVENTS_VOICE_CHANNEL_ID` — when unset, `CreateScheduledEvent` is dropped from `TOOL_DEFINITIONS` and `/ask` cannot schedule events
- `DISCORD_SEND_TOOL_ENABLED` — off by default. Switches on `SendToChannel`, letting `/ask` post into a channel other than the one it ran in. The Discord _read_ tools need no gate (they mirror the asker's permissions and reveal nothing the asker couldn't open); this one is opt-in per deployment because its reach extends past the invoking channel. `cast=bool` needs no empty-string guard — decouple maps `""` and `"false"` to `False`, unlike the `int` vars above
- `DGPT_SEARCH_URL` — web-search endpoint, defaults to `https://api.deutschlandgpt.de/v2/search`. Authenticated with `OPENAI_API_KEY`, so the `WebSearch` tool needs no key of its own and is always enabled. Points at DeutschlandGPT — if `OPENAI_API_BASE_URL` is aimed at real OpenAI instead, search calls will 401. The request body takes `query` plus an optional `count` (1–20, doesn't affect billing), which is why `WebSearch.count` is bounded `ge=1, le=20`.
- `CMC_PRO_API_KEY` — `/price` (short-circuits with a "not configured" embed when missing). Note: the Python constant is `CMC_API_KEY` but the env var is `CMC_PRO_API_KEY` — don't rename one without the other.
- `AWS_REGION` / `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` — DynamoDB credentials for completion logging; when unset, botocore falls back to its default credential chain (`~/.aws/`). Logging failures are caught and logged, not fatal.
- `DYNAMODB_TABLE_NAME` — completions table, defaults to `elongpt-completions`
- `IDLE_VOICE_TIMEOUT_SECONDS` / `IDLE_VOICE_TARGET_CHANNEL_ID` — idle-voice auto-mover (`bot/voice_idle.py`): a `tasks.loop` polls voice channels every 15s and moves self-deafened members who exceed the timeout to the target voice channel. Disabled unless **both** are set. `IDLE_VOICE_NOTIFY_CHANNEL_ID` (optional) is the text channel for the "moved" notice; when unset it falls back to the source voice channel's text chat. Requires the bot to have **Move Members**.

## Style

- Formatter: **black** (line length 88)
- Import sorting: **isort** (profile=black)
- Linter: **flake8** (max line length 120, ignores E203/W503)
- `env/` directory is excluded from all tools

## Deployment

Tags matching `*.*.*` trigger `build-and-deploy.yml`: `ci.yml` checks → Docker build → push to GHCR (`ghcr.io`) → SSH deploy. The deploy job renders `.env.op` into a real `.env` with `ENVIRONMENT=production op inject`, appends `ELONGPT_IMAGE` pinned to the just-built tag, scps `.env` + `docker-compose.yml` to the server, and runs `docker compose pull && up -d`. Nothing else is copied — the server runs the published image, so a file that isn't in the Docker build context never reaches production.

Two other workflows exist: `mirror-gitlab.yml` (pushes every branch/tag to a GitLab mirror) and `code-review.yml` (manual `workflow_dispatch` Claude review of a PR number).

## Development

You can always use the context7 mcp tools to search for library documentation when working with external libraries. Never guess APIs from memory.
