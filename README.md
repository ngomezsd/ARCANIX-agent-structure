# ARCANIX — Investment Fund Multi-Agent System

A production-ready, Python-based multi-agent system for investment fund management.
Four autonomous AI agents collaborate to fetch market data, analyse trends, manage
portfolio allocations, assess risks, and generate comprehensive investment reports.

---

## Features

| Feature | Details |
|---------|---------|
| 🤖 Multi-Agent Workflow | Market Analyst, Portfolio Manager, Risk Analyst, Reporter |
| 📊 Real-time Market Data | Live data via `yfinance` |
| 📈 Technical Analysis | Moving averages (MA20/MA50), RSI, MACD |
| 💼 Portfolio Metrics | Sharpe ratio, VaR (95 %), diversification score |
| ⚠️ Risk Analysis | Concentration, volatility, compliance checks |
| 🧠 LLM-Powered | OpenAI GPT for intelligent, contextual analysis |
| 🔁 LangGraph Orchestration | Deterministic, stateful multi-step workflow |

---

## Architecture

```
                    ┌─────────────────────┐
                    │   main.py (entry)   │
                    └────────┬────────────┘
                             │
              ┌──────────────▼──────────────┐
              │  LangGraph Workflow          │
              │                             │
              │  1. fetch_market_data  ──►  utils/data_fetcher.py
              │  2. calculate_metrics  ──►  utils/portfolio_calculator.py
              │  3. market_analysis    ──►  agents/market_analyst.py
              │  4. risk_assessment    ──►  agents/risk_analyst.py
              │  5. recommendations    ──►  agents/portfolio_manager.py
              │  6. generate_report    ──►  agents/reporting.py
              └─────────────────────────────┘
```

---

## Directory Structure

```
ARCANIX-agent-structure/
├── README.md                   # This file
├── requirements.txt            # Python dependencies
├── .env.example                # Configuration template
├── config.py                   # Configuration & env management
├── main.py                     # Orchestration entry point
├── agents/
│   ├── __init__.py
│   ├── market_analyst.py       # Analyses trends & technical indicators
│   ├── portfolio_manager.py    # Makes allocation recommendations
│   ├── risk_analyst.py         # Assesses risk & compliance
│   └── reporting.py            # Generates investment reports
└── utils/
    ├── __init__.py
    ├── data_fetcher.py         # Fetches market data & computes technicals
    └── portfolio_calculator.py # Computes portfolio-level metrics
```

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/ngomezsd/ARCANIX-agent-structure.git
cd ARCANIX-agent-structure
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure your environment

```bash
cp .env.example .env
```

Open `.env` in your editor and add your OpenAI API key:

```env
OPENAI_API_KEY=sk-...your-key-here...
FUND_NAME=My Investment Fund
```

Get a key at: <https://platform.openai.com/api-keys>

### 4. Customise your portfolio

Edit the `portfolio` dictionary in `main.py`:

```python
portfolio: Dict[str, float] = {
    "AAPL": 10_000,   # $10,000 in Apple
    "MSFT": 15_000,   # $15,000 in Microsoft
    "GOOGL": 12_000,  # $12,000 in Google
    "TSLA":  8_000,   # $8,000  in Tesla
    # Add more tickers and amounts here …
}
```

### 5. Run the system

```bash
python main.py
```

---

## Example Output

```
============================================================
🏦  MY INVESTMENT FUND
    ARCANIX Multi-Agent Investment Analysis
============================================================

📊  Fetching market data ...
💼  Calculating portfolio metrics ...
🔍  Running market analysis ...
⚠️   Assessing portfolio risk ...
📈  Generating recommendations ...
📋  Generating investment report ...

============================================================
📊  FINAL INVESTMENT REPORT
============================================================
# Investment Report — My Investment Fund
...

✅  Report saved to investment_report.md

📌  Portfolio Snapshot
    Total Value  : $45,000.00
    Sharpe Ratio : 1.23
    Daily VaR 95%: $412.50
    Diversif. Score: 8.5/10
```

The full report is saved to **`investment_report.md`**.

---

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *(required)* | Your OpenAI API key |
| `FUND_NAME` | `My Investment Fund` | Name shown in reports |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model to use |
| `DATA_PERIOD` | `1y` | Historical data window (`1mo`, `3mo`, `6mo`, `1y`, `2y`) |
| `RISK_FREE_RATE` | `0.02` | Annual risk-free rate for Sharpe calculation |

---

## Multi-Agent System & REST API

The repository now ships a second, **OpenAI-free** autonomous agent layer built
on top of an event-driven architecture.  Agents run as background threads,
communicate through an in-process event bus, and expose a full REST API.

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        REST API (Flask)                          │
│  POST /api/agents/start   GET /api/agents/status                 │
│  POST /api/analysis/run   GET /api/analysis/results              │
│  GET  /api/portfolio/metrics  POST /api/portfolio/update         │
│  GET  /api/events         GET  /api/health                       │
└──────────────────────┬───────────────────────────────────────────┘
                       │ AgentCoordinator
         ┌─────────────┼──────────────────────────┐
         ▼             ▼              ▼            ▼
  ┌─────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
  │MarketMonitor│ │   Risk   │ │Portfolio │ │Opportunity│
  │  Agent      │ │ Manager  │ │Optimizer │ │  Scout   │
  └──────┬──────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
         │             │            │              │
         └─────────────▼────────────▼──────────────┘
                    EventBus (pub/sub)
                         │
                    ┌────▼────┐
                    │Reporter │
                    │ Agent   │
                    └─────────┘
                         │
               ┌─────────▼──────────┐
               │  SQLite Storage     │
               │ (portfolio, results,│
               │  agent_logs, events)│
               └────────────────────┘
```

### New Directory Structure

```
├── agents/
│   ├── base_agent.py          # Abstract base class
│   ├── market_monitor.py      # Fetches live market data
│   ├── risk_manager.py        # Rule-based risk assessment
│   ├── portfolio_optimizer.py # Rule-based allocation advice
│   ├── opportunity_scout.py   # Identifies buying opportunities
│   └── reporter.py            # Aggregates & reports
├── core/
│   ├── event_bus.py           # Pub/sub event bus singleton
│   ├── message_queue.py       # Underlying thread-safe queue
│   ├── agent_registry.py      # Runtime agent registry
│   ├── coordinator.py         # Orchestration & on-demand analysis
│   └── scheduler.py           # Periodic task scheduler
├── storage/
│   ├── database.py            # SQLite wrapper
│   ├── portfolio_store.py     # Portfolio persistence
│   └── results_store.py       # Analysis results persistence
├── api/
│   ├── app.py                 # Flask application factory
│   ├── routes.py              # Blueprint with all endpoints
│   ├── middleware.py          # Request logging, CORS, error handlers
│   └── models.py              # Response helpers
├── config/
│   ├── agent_config.json      # Per-agent settings
│   ├── api_config.json        # Flask server settings
│   └── task_config.json       # Scheduler task definitions
├── run_agents.py              # Start the agent system standalone
└── run_api.py                 # Start the REST API + agents
```

### How to Run

#### Run the agent system (no API)

```bash
python run_agents.py
```

All five agents start as background threads and process events continuously.
Press **Ctrl+C** for a graceful shutdown.

#### Run the REST API (includes agents)

```bash
python run_api.py
```

The Flask server starts on `http://0.0.0.0:5000` by default.  All agents run
in background threads alongside the API process.

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/agents/start` | Start one or all agents |
| `POST` | `/api/agents/stop` | Stop one or all agents |
| `GET`  | `/api/agents/status` | List all agent statuses |
| `GET`  | `/api/agents/<id>/logs` | Fetch agent log entries |
| `POST` | `/api/analysis/run` | Run a full analysis cycle |
| `GET`  | `/api/analysis/results` | Retrieve stored results |
| `GET`  | `/api/portfolio/metrics` | Current portfolio metrics |
| `POST` | `/api/portfolio/update` | Update portfolio positions |
| `GET`  | `/api/events` | Recent event-bus history |
| `GET`  | `/api/health` | System health check |

### Example API Calls

```bash
# Health check
curl http://localhost:5000/api/health

# Check all agent statuses
curl http://localhost:5000/api/agents/status

# Start a specific agent
curl -X POST http://localhost:5000/api/agents/start \
     -H "Content-Type: application/json" \
     -d '{"agent_name": "market_monitor"}'

# Start all agents
curl -X POST http://localhost:5000/api/agents/start \
     -H "Content-Type: application/json" \
     -d '{}'

# Update the portfolio
curl -X POST http://localhost:5000/api/portfolio/update \
     -H "Content-Type: application/json" \
     -d '{"portfolio": {"AAPL": 10000, "MSFT": 15000, "GOOGL": 12000}}'

# Run a full on-demand analysis
curl -X POST http://localhost:5000/api/analysis/run \
     -H "Content-Type: application/json" \
     -d '{"portfolio": {"AAPL": 10000, "MSFT": 15000}, "symbols": ["AAPL", "MSFT"]}'

# Get latest analysis results
curl "http://localhost:5000/api/analysis/results"

# Get recent events
curl "http://localhost:5000/api/events?limit=20"
```

---

## Extending the System

### Add a new agent

1. Create `agents/my_new_agent.py` following the same pattern as the existing agents.
2. Add a new node function in `main.py`.
3. Wire it into the LangGraph workflow with `graph.add_node` and `graph.add_edge`.

### Add more stocks

Simply extend the `portfolio` dict in `main.py` — any valid yfinance ticker works.

### Change the LLM model

Update `OPENAI_MODEL` in your `.env` file (e.g. `gpt-4o` for higher quality).

---

## Troubleshooting

| Problem | Solution |
|---------|---------|
| `EnvironmentError: OPENAI_API_KEY is not set` | Add your key to `.env` |
| `No market data returned` | Check ticker symbols and internet connection |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| Empty or garbled report | Try a more capable model (`OPENAI_MODEL=gpt-4o`) |

---

## Roadmap

- [ ] ESG analyst agent
- [ ] Backtesting module
- [ ] Broker API integration (Alpaca, Interactive Brokers)
- [ ] Automated daily scheduling (cron / GitHub Actions)
- [ ] Web dashboard (Streamlit)

---

## License

MIT
