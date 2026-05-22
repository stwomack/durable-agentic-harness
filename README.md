# Durable Agentic Harness — Self-Evolving Stock Agent

A demo proving Temporal is the production-grade harness for agentic AI. See [`AGENTS.md`](AGENTS.md) for the project bible and [`docs/superpowers/specs/`](docs/superpowers/specs/) for the locked design.

## Quick start

```bash
cp .env.example .env
# Edit .env: set OPENAI_API_KEY
docker compose build
docker compose up
```

Open:
- Demo UI: http://localhost:5173
- Temporal Web UI: http://localhost:8233
- FastAPI docs: http://localhost:8000/docs

## Stage demo

See [`docs/superpowers/specs/2026-05-21-self-evolving-stock-agent-design.md`](docs/superpowers/specs/2026-05-21-self-evolving-stock-agent-design.md) §9.
