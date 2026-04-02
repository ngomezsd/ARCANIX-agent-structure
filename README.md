# ARCANIX — Investment Fund Multi-Agent System

A production-ready, Python-based multi-agent system for investment fund management.
Specialized in discovering **small-cap and micro-cap** stock opportunities across **US and European markets**, with full portfolio management, risk assessment, and automated reporting.

---

## Features

| Feature | Details |
|---------|---------|
| 🤖 Multi-Agent Workflow | Market Analyst, Portfolio Manager, Risk Analyst, Reporter, SmallCap Scout |
| 📊 Real-time Market Data | Live data via `yfinance` for US and EU markets |
| 🔬 Small/Micro-Cap Discovery | Screen opportunities in NYSE, NASDAQ, LSE, Euronext, XETRA, and more |
| 📈 Technical Analysis | Moving averages (MA20/MA50), RSI, MACD |
| 💼 Portfolio Metrics | Sharpe ratio, VaR (95 %), diversification score |
| ⚠️ Risk Analysis | Concentration, volatility, compliance checks |
| 🏆 Opportunity Scoring | Composite 0–100 score across value, growth, momentum, and quality |
| 🧠 LLM-Powered | OpenAI GPT for intelligent, contextual analysis |
| 🔁 LangGraph Orchestration | Deterministic, stateful multi-step workflow |
| 💻 CLI Tool | Full command-line interface for daily portfolio work |

---

## Architecture

```
                    ┌─────────────────────────────────────────┐
                    │           ARCANIX CLI (cli.py)           │
                    └──────────┬──────────────────────────────┘
                               │
         ┌─────────────────────┼────────────────────────────┐
         │                     │                            │
         ▼                     ▼                            ▼
 Portfolio Commands    Opportunity Commands         Stock/Watchlist
         │                     │                            │
         ▼                     ▼                            ▼
agents/portfolio_manager  agents/smallcap_scout    utils/screener
agents/risk_analyst       utils/screener           utils/storage
utils/portfolio_calculator utils/data_fetcher

                    ┌─────────────────────┐
                    │   main.py (entry)   │  ← Full LangGraph workflow
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
├── main.py                     # LangGraph orchestration entry point
├── cli.py                      # ← NEW: Portfolio Manager CLI
├── agents/
│   ├── __init__.py
│   ├── market_analyst.py       # Analyses trends & technical indicators
│   ├── portfolio_manager.py    # Makes allocation recommendations
│   ├── risk_analyst.py         # Assesses risk & compliance
│   ├── reporting.py            # Generates investment reports
│   └── smallcap_scout.py       # ← NEW: Small/micro-cap opportunity discovery
├── utils/
│   ├── __init__.py
│   ├── data_fetcher.py         # Fetches market data & computes technicals
│   ├── portfolio_calculator.py # Computes portfolio-level metrics
│   ├── screener.py             # ← NEW: Stock screening & opportunity scoring
│   ├── storage.py              # ← NEW: Local JSON portfolio & watchlist storage
│   └── agent_utils.py          # Shared LLM response helpers
└── data/                       # ← Auto-created: local data storage
    ├── portfolio.json           # Your portfolio holdings
    ├── watchlist.json           # Stocks under monitoring
    └── *.md / *.json            # Generated reports
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

---

## CLI Usage — Portfolio Manager

### Portfolio Commands

```bash
# View current portfolio with live prices and metrics
python cli.py portfolio analyze

# Add a position (100 shares of AAPL at $150)
python cli.py portfolio add AAPL --quantity 100 --avg-cost 150.00

# Add a European stock (50 shares of BMW on XETRA)
python cli.py portfolio add BMW.DE --quantity 50 --avg-cost 95.00 --market DE

# Remove a position
python cli.py portfolio remove AAPL

# Get rebalancing suggestions
python cli.py portfolio rebalance --target-risk medium
```

### Opportunity Discovery

```bash
# Find US micro-cap tech stocks
python cli.py opportunities find --market US --cap micro --sector tech

# Find EU small-caps with 15%+ growth
python cli.py opportunities find --market EU --cap small --min-growth 15

# Find UK value plays
python cli.py opportunities find --market GB --cap small --strategy value

# Find German growth stocks and save reports
python cli.py opportunities find --market DE --cap small --strategy growth --json

# Show top 20 results
python cli.py opportunities find --market US --cap micro --top 20
```

**Supported markets:**
| Code | Exchange |
|------|----------|
| `US` | NYSE + NASDAQ |
| `EU` | All European markets combined |
| `GB` | London Stock Exchange |
| `DE` | Deutsche Börse / XETRA |
| `FR` | Euronext Paris |
| `NL` | Euronext Amsterdam |
| `IT` | Borsa Italiana |
| `ES` | BME (Madrid) |

**Cap types:** `micro` (< $300M) · `small` ($300M–$2B) · `mid` ($2B–$10B) · `all`

### Individual Stock Analysis

```bash
# Deep-dive on a single stock
python cli.py stock analyze MVIS

# Deep-dive on a European stock
python cli.py stock analyze BMW.DE

# Compare multiple stocks
python cli.py stock compare MVIS KOPN GFAI

# Save analysis as JSON + Markdown
python cli.py stock analyze MVIS --json
```

### Watchlist Management

```bash
# Add stocks to monitor
python cli.py watchlist add MVIS --market US --notes "nano-LIDAR play"
python cli.py watchlist add AML.L --market GB --target-price 4.50 --notes "Aston Martin recovery"

# View watchlist with live prices and upside to target
python cli.py watchlist show

# Run full opportunity analysis on all watchlist stocks
python cli.py watchlist report --json

# Remove from watchlist
python cli.py watchlist remove MVIS
```

---

## LangGraph Workflow (main.py)

For full multi-agent analysis of your portfolio:

### 1. Customise your portfolio in `main.py`

```python
portfolio: Dict[str, float] = {
    "AAPL": 10_000,   # $10,000 in Apple
    "MSFT": 15_000,   # $15,000 in Microsoft
    "GOOGL": 12_000,  # $12,000 in Google
    "TSLA":  8_000,   # $8,000  in Tesla
}
```

### 2. Run the full analysis

```bash
python main.py
```

---

## Opportunity Scoring

Each stock is scored 0–100 using a composite model:

| Component | Weight | Metrics |
|-----------|--------|---------|
| **Value** | 35% | P/E, PEG, Price/Book, EV/EBITDA |
| **Growth** | 35% | Revenue growth, Earnings growth, Profit margins |
| **Momentum** | 20% | Price vs 50-day MA, 52-week range position |
| **Quality** | 10% | Institutional ownership, analyst target upside |

**Score interpretation:**
- 70–100 → **BUY** (strong opportunity)
- 50–69 → **WATCH** (worth monitoring)
- 0–49 → **AVOID** (does not meet criteria)

---

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *(required for AI features)* | Your OpenAI API key |
| `FUND_NAME` | `My Investment Fund` | Name shown in reports |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model to use |
| `DATA_PERIOD` | `1y` | Historical data window (`1mo`, `3mo`, `6mo`, `1y`, `2y`) |
| `RISK_FREE_RATE` | `0.02` | Annual risk-free rate for Sharpe calculation |

---

## Troubleshooting

| Problem | Solution |
|---------|---------|
| `OPENAI_API_KEY is not set` | Add your key to `.env` |
| `No market data returned` | Check ticker symbols and internet connection |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| Empty or garbled report | Try a more capable model (`OPENAI_MODEL=gpt-4o`) |
| Slow screening | Reduce universe with `--sector` or `--min-growth` filters |

---

## Roadmap

- [ ] Broker API integration (Alpaca, Interactive Brokers)
- [ ] Automated daily scheduling (cron / GitHub Actions)
- [ ] Web dashboard (Streamlit)
- [ ] ESG analyst agent
- [ ] Backtesting module
- [ ] Custom stock universe import from CSV

---

## License

MIT
