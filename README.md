# EVA - Phase 1

EVA is a modular Windows AI desktop assistant. Phase 1 provides the
foundation: configuration, structured logging, an event bus, a
provider-agnostic AI layer with a DeepSeek adapter, a text-only agent
loop, and a CLI.

This phase intentionally does **not** include tools, voice, memory,
networking, storage lifecycle, or GUI. Those arrive in later phases;
stubs and config keys are already in place so they can be added
without refactoring.

## Requirements

- Python 3.11+
- Windows 11 (or any OS capable of running Python 3.11)

## Installation

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Then edit `.env` and set at least:

```
DEEPSEEK_API_KEY=your_key_here
```

## Run

```bat
python -m app.main
```

or:

```bat
scripts\start_eva.bat
```

## Test

```bat
pytest
```

The suite is fully offline (no live API calls).

## Diagnostics

```bat
scripts\doctor.bat
```

## Configuration

- `config/config.yaml` - defaults (safe to commit)
- `config/user_config.yaml` - user overrides (safe to commit)
- `.env` - secrets (never commit)

## Architecture at a glance

```
CLI -> AgentLoop -> ProviderRegistry -> AIProvider -> DeepSeekProvider
                       |
                       +-- (future) OpenAI / Claude / Gemini / ...
```

## What's next

Phase 2 introduces the tool-calling framework and the first safe tool
(`open_application`).