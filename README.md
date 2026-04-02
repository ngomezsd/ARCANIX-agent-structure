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
