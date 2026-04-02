#!/usr/bin/env python3
"""ARCANIX Portfolio Manager CLI.

A command-line tool for portfolio management and small/micro-cap opportunity
discovery across US and European markets.

Usage examples:
    python cli.py portfolio analyze
    python cli.py portfolio add AAPL --quantity 100 --avg-cost 150.00
    python cli.py portfolio remove AAPL
    python cli.py portfolio rebalance --target-risk medium

    python cli.py opportunities find --market US --cap micro --sector tech
    python cli.py opportunities find --market EU --cap small --min-growth 15

    python cli.py stock analyze MVIS
    python cli.py stock compare MVIS KOPN GFAI

    python cli.py watchlist add MVIS --market US --notes "nano-LIDAR play"
    python cli.py watchlist remove MVIS
    python cli.py watchlist show
    python cli.py watchlist report
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Bootstrap — load .env before importing anything that touches config
# ---------------------------------------------------------------------------
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Optional pretty-print helpers (tabulate gracefully degrades if absent)
# ---------------------------------------------------------------------------
try:
    from tabulate import tabulate as _tabulate_impl

    def tabulate(rows: list, headers: list, **kwargs) -> str:  # type: ignore[misc]
        return _tabulate_impl(rows, headers=headers, **kwargs)

except ImportError:
    def tabulate(rows: list, headers: list, **kwargs) -> str:  # type: ignore[misc]
        """Minimal fallback formatter when tabulate is not installed."""
        col_widths = [len(str(h)) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))
        fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)
        lines = [fmt.format(*headers)]
        lines.append("  ".join("-" * w for w in col_widths))
        for row in rows:
            lines.append(fmt.format(*[str(c) for c in row]))
        return "\n".join(lines)


logger = logging.getLogger("arcanix.cli")

# ---------------------------------------------------------------------------
# Lazy imports — avoid loading heavy modules if --help is requested
# ---------------------------------------------------------------------------

def _load_modules():
    """Import application modules (deferred to avoid slow startup on --help)."""
    global storage, screener, SmallCapScoutAgent, PortfolioManagerAgent, \
           RiskAnalystAgent, calculate_portfolio_metrics, get_market_summary, \
           cfg

    from utils import storage as _storage
    from utils import screener as _screener
    from utils.portfolio_calculator import calculate_portfolio_metrics as _cpm
    from utils.data_fetcher import get_market_summary as _gms

    storage = _storage
    screener = _screener
    calculate_portfolio_metrics = _cpm
    get_market_summary = _gms

    # LLM-dependent modules — only imported when an AI key is available
    try:
        from agents.smallcap_scout import SmallCapScoutAgent as _SC
        from agents.portfolio_manager import PortfolioManagerAgent as _PM
        from agents.risk_analyst import RiskAnalystAgent as _RA
        import config as _cfg

        SmallCapScoutAgent = _SC
        PortfolioManagerAgent = _PM
        RiskAnalystAgent = _RA
        cfg = _cfg
    except ImportError:
        SmallCapScoutAgent = None  # type: ignore[assignment]
        PortfolioManagerAgent = None  # type: ignore[assignment]
        RiskAnalystAgent = None  # type: ignore[assignment]
        cfg = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_cap(cap: Optional[float]) -> str:
    if cap is None:
        return "N/A"
    if cap >= 1e9:
        return f"${cap/1e9:.2f}B"
    if cap >= 1e6:
        return f"${cap/1e6:.1f}M"
    return f"${cap:,.0f}"


def _fmt_pct(val: Optional[float]) -> str:
    if val is None:
        return "N/A"
    return f"{val*100:.1f}%"


def _fmt_float(val: Optional[float], decimals: int = 2) -> str:
    if val is None:
        return "N/A"
    return f"{val:.{decimals}f}"


def _save_report(data: Any, filename: str) -> None:
    """Save data as both JSON and Markdown to the data/ directory."""
    os.makedirs("data", exist_ok=True)

    json_path = os.path.join("data", filename + ".json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)
    print(f"  📄  JSON report saved → {json_path}")

    if isinstance(data, dict) and "ai_report" in data:
        md_path = os.path.join("data", filename + ".md")
        report = data.get("ai_report", {})
        lines = [
            f"# {report.get('title', 'Report')}",
            f"*Generated {date.today().isoformat()}*\n",
            "## Executive Summary",
            report.get("executive_summary", ""),
            "\n## Market Context",
            report.get("market_context", ""),
        ]
        if report.get("top_picks"):
            lines.append("\n## Top Picks")
            for pick in report["top_picks"]:
                lines.append(
                    f"\n### {pick.get('symbol')} — {pick.get('action', '')}\n"
                    f"**Thesis:** {pick.get('thesis', '')}\n\n"
                    f"**Catalyst:** {pick.get('key_catalyst', '')}\n\n"
                    f"**Risk:** {pick.get('risk', '')}"
                )
        if report.get("risk_warnings"):
            lines.append("\n## Risk Warnings")
            for rw in report["risk_warnings"]:
                lines.append(f"- {rw}")
        with open(md_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        print(f"  📄  Markdown report saved → {md_path}")


# ---------------------------------------------------------------------------
# Portfolio commands
# ---------------------------------------------------------------------------

def cmd_portfolio_analyze(args: argparse.Namespace) -> None:
    """Display a summary of the current portfolio."""
    portfolio = storage.load_portfolio()

    if not portfolio:
        print("⚠️  Portfolio is empty. Add positions with:\n"
              "    python cli.py portfolio add TICKER --quantity N --avg-cost P")
        return

    tickers = list(portfolio.keys())

    print(f"\n📊  Fetching market data for {len(tickers)} holdings …")
    try:
        market_data = get_market_summary(tickers, period="1y")
    except Exception as exc:
        print(f"⚠️  Could not fetch market data: {exc}")
        market_data = {}

    # Build dollar-value portfolio for metrics
    dollar_portfolio: Dict[str, float] = {}
    for ticker, pos in portfolio.items():
        price = (market_data.get(ticker) or {}).get("current_price") or pos.get("avg_cost", 0)
        dollar_portfolio[ticker] = price * pos.get("quantity", 0)

    metrics = calculate_portfolio_metrics(dollar_portfolio, market_data, risk_free_rate=0.02)

    print("\n" + "=" * 60)
    print("💼  PORTFOLIO OVERVIEW")
    print("=" * 60)

    rows = []
    for ticker, pos in portfolio.items():
        avg_cost = pos.get("avg_cost", 0)
        qty = pos.get("quantity", 0)
        mkt = market_data.get(ticker) or {}
        current_price = mkt.get("current_price") or avg_cost
        pnl_pct = (current_price - avg_cost) / avg_cost * 100 if avg_cost else 0
        value = current_price * qty
        rows.append([
            ticker,
            qty,
            f"${avg_cost:.2f}",
            f"${current_price:.2f}",
            f"{pnl_pct:+.1f}%",
            f"${value:,.0f}",
            pos.get("market", "US"),
        ])

    print(tabulate(
        rows,
        headers=["Ticker", "Qty", "Avg Cost", "Current", "P&L%", "Value", "Market"],
        tablefmt="rounded_outline",
    ))

    total = metrics.get("total_value", 0)
    print(f"\n  Total Value         : ${total:,.2f}")
    print(f"  Expected Return     : {_fmt_pct(metrics.get('expected_annual_return'))}")
    print(f"  Portfolio Volatility: {_fmt_pct(metrics.get('volatility'))}")
    print(f"  Sharpe Ratio        : {_fmt_float(metrics.get('sharpe_ratio'))}")
    print(f"  Daily VaR (95%)     : ${metrics.get('value_at_risk_95', 0):,.2f}")
    print(f"  Diversif. Score     : {metrics.get('diversification_score', 0):.1f}/10")

    if args.json:
        _save_report({"portfolio": portfolio, "metrics": metrics}, "portfolio_analysis")


def cmd_portfolio_add(args: argparse.Namespace) -> None:
    """Add or update a portfolio position."""
    storage.add_position(
        ticker=args.ticker,
        quantity=args.quantity,
        avg_cost=args.avg_cost,
        market=args.market,
        notes=args.notes or "",
    )
    print(f"✅  Added {args.ticker}: {args.quantity} shares @ ${args.avg_cost:.2f} ({args.market})")


def cmd_portfolio_remove(args: argparse.Namespace) -> None:
    """Remove a position from the portfolio."""
    removed = storage.remove_position(args.ticker)
    if removed:
        print(f"✅  Removed {args.ticker} from portfolio.")
    else:
        print(f"⚠️  {args.ticker} not found in portfolio.")


def cmd_portfolio_rebalance(args: argparse.Namespace) -> None:
    """Generate rebalancing recommendations."""
    portfolio = storage.load_portfolio()
    if not portfolio:
        print("⚠️  Portfolio is empty.")
        return

    tickers = list(portfolio.keys())
    print(f"\n⚖️  Generating rebalancing suggestions for {len(tickers)} holdings …")

    try:
        market_data = get_market_summary(tickers)
    except Exception as exc:
        print(f"⚠️  Could not fetch market data: {exc}")
        market_data = {}

    dollar_portfolio: Dict[str, float] = {
        t: (market_data.get(t) or {}).get("current_price", p.get("avg_cost", 0))
           * p.get("quantity", 0)
        for t, p in portfolio.items()
    }

    metrics = calculate_portfolio_metrics(dollar_portfolio, market_data)

    pm_agent = PortfolioManagerAgent()
    from agents.market_analyst import MarketAnalystAgent
    ma = MarketAnalystAgent()
    analysis = ma.analyze_market(market_data)
    recs = pm_agent.make_recommendations(analysis, metrics)

    print("\n" + "=" * 60)
    print("⚖️  REBALANCING RECOMMENDATIONS")
    print("=" * 60)
    print(f"  Action    : {recs.get('action', 'N/A').upper()}")
    print(f"  Rationale : {recs.get('rationale', 'N/A')}")
    print("\n  Suggested Allocations:")

    rows = []
    for sym, weight in (recs.get("allocations") or {}).items():
        current_w = metrics.get("weights", {}).get(sym, 0)
        rows.append([sym, f"{current_w*100:.1f}%", f"{weight*100:.1f}%",
                      f"{(weight-current_w)*100:+.1f}%"])
    if rows:
        print(tabulate(rows, headers=["Ticker", "Current", "Target", "Change"],
                       tablefmt="rounded_outline"))

    if recs.get("changes"):
        print("\n  Specific Actions:")
        for change in recs["changes"]:
            print(f"    • {change}")

    if args.json:
        _save_report({"metrics": metrics, "recommendations": recs}, "rebalance_suggestions")


# ---------------------------------------------------------------------------
# Opportunities commands
# ---------------------------------------------------------------------------

def cmd_opportunities_find(args: argparse.Namespace) -> None:
    """Screen the market for small/micro-cap opportunities."""
    min_growth = args.min_growth / 100 if args.min_growth else None

    print(f"\n🔍  Screening {args.cap}-cap stocks | market={args.market}"
          + (f" | sector={args.sector}" if args.sector else "")
          + (f" | min-growth={args.min_growth}%" if args.min_growth else "")
          + (f" | strategy={args.strategy}" if args.strategy else ""))
    print("    (This may take 1–2 minutes for large universes …)\n")

    scout = SmallCapScoutAgent()
    result = scout.find_opportunities(
        market=args.market,
        cap_type=args.cap,
        sector=args.sector,
        min_growth=min_growth,
        strategy=args.strategy,
        top_n=args.top_n,
    )

    opportunities = result.get("opportunities", [])
    if not opportunities:
        print("  No opportunities matched your criteria.")
        return

    print(f"  Screened {result.get('total_screened', 0)} stocks → {len(opportunities)} match(es)\n")
    print("=" * 70)
    print(f"🏆  TOP {len(opportunities)} OPPORTUNITIES — {args.market} {args.cap.upper()}-CAP")
    print("=" * 70)

    rows = []
    for o in opportunities:
        rows.append([
            o.get("symbol"),
            (o.get("name") or "")[:22],
            o.get("sector") or "N/A",
            _fmt_cap(o.get("market_cap")),
            _fmt_float(o.get("pe_ratio"), 1),
            _fmt_pct(o.get("revenue_growth")),
            f"{o.get('opportunity_score', 0):.0f}/100",
            o.get("recommendation_action", "?"),
        ])

    print(tabulate(
        rows,
        headers=["Ticker", "Name", "Sector", "Mkt Cap", "P/E", "Rev Growth", "Score", "Action"],
        tablefmt="rounded_outline",
    ))

    # LLM report summary
    ai = result.get("ai_report", {})
    if ai.get("executive_summary"):
        print(f"\n📝  Market Commentary:")
        print(f"    {ai['executive_summary']}")

    if args.json:
        fname = f"opportunities_{args.market}_{args.cap}_{date.today().isoformat()}"
        _save_report(result, fname)


# ---------------------------------------------------------------------------
# Stock commands
# ---------------------------------------------------------------------------

def cmd_stock_analyze(args: argparse.Namespace) -> None:
    """Deep-dive analysis on a single stock."""
    ticker = args.ticker.upper()
    print(f"\n🔬  Analysing {ticker} …")

    scout = SmallCapScoutAgent()
    result = scout.analyze_stock(ticker)

    if "error" in result:
        print(f"⚠️  Error fetching data for {ticker}: {result['error']}")
        return

    print("\n" + "=" * 60)
    print(f"📈  {ticker} — {result.get('name', 'Unknown')}")
    print("=" * 60)
    print(f"  Sector       : {result.get('sector', 'N/A')}")
    print(f"  Industry     : {result.get('industry', 'N/A')}")
    print(f"  Market Cap   : {_fmt_cap(result.get('market_cap'))}")
    print(f"  Current Price: {result.get('currency', '$')}{_fmt_float(result.get('current_price'))}")

    print("\n  📊  Valuation Metrics")
    val_rows = [
        ["P/E Ratio (TTM)", _fmt_float(result.get("pe_ratio"))],
        ["Forward P/E", _fmt_float(result.get("forward_pe"))],
        ["PEG Ratio", _fmt_float(result.get("peg_ratio"))],
        ["Price/Book", _fmt_float(result.get("price_to_book"))],
        ["EV/EBITDA", _fmt_float(result.get("ev_to_ebitda"))],
    ]
    print(tabulate(val_rows, headers=["Metric", "Value"], tablefmt="simple"))

    print("\n  📈  Growth Metrics")
    growth_rows = [
        ["Revenue Growth (YoY)", _fmt_pct(result.get("revenue_growth"))],
        ["Earnings Growth (YoY)", _fmt_pct(result.get("earnings_growth"))],
        ["Profit Margins", _fmt_pct(result.get("profit_margins"))],
        ["Return on Equity", _fmt_pct(result.get("return_on_equity"))],
    ]
    print(tabulate(growth_rows, headers=["Metric", "Value"], tablefmt="simple"))

    print("\n  🔍  Market Data")
    mkt_rows = [
        ["52-Week High", _fmt_float(result.get("fifty_two_week_high"))],
        ["52-Week Low", _fmt_float(result.get("fifty_two_week_low"))],
        ["50-Day Avg", _fmt_float(result.get("fifty_day_avg"))],
        ["Institutional Own.", _fmt_pct(result.get("inst_ownership"))],
        ["Short Ratio", _fmt_float(result.get("short_ratio"))],
        ["Analyst Target", _fmt_float(result.get("target_price"))],
    ]
    print(tabulate(mkt_rows, headers=["Metric", "Value"], tablefmt="simple"))

    score = result.get("opportunity_score", 0)
    action = result.get("recommendation_action", "?")
    print(f"\n  🏆  Opportunity Score : {score:.0f}/100  →  {action}")

    ai = result.get("ai_analysis", {})
    if ai.get("investment_thesis"):
        print(f"\n  💡  Investment Thesis:")
        for line in ai["investment_thesis"].split("\n"):
            print(f"     {line}")

    if ai.get("key_catalysts"):
        print("\n  🚀  Key Catalysts:")
        for c in ai["key_catalysts"]:
            print(f"     • {c}")

    if ai.get("key_risks"):
        print("\n  ⚠️  Key Risks:")
        for r in ai["key_risks"]:
            print(f"     • {r}")

    if ai.get("entry_strategy"):
        print(f"\n  📌  Entry Strategy: {ai['entry_strategy']}")

    if args.json:
        _save_report(result, f"stock_analysis_{ticker}_{date.today().isoformat()}")


def cmd_stock_compare(args: argparse.Namespace) -> None:
    """Compare multiple stocks side-by-side."""
    tickers = [t.upper() for t in args.tickers]
    print(f"\n⚖️  Comparing {', '.join(tickers)} …")

    scout = SmallCapScoutAgent()
    result = scout.compare_stocks(tickers)

    stocks = result.get("stocks", [])
    if not stocks:
        print("⚠️  Could not fetch data for any of the requested tickers.")
        return

    print("\n" + "=" * 70)
    print(f"⚖️  STOCK COMPARISON: {' vs '.join(tickers)}")
    print("=" * 70)

    rows = []
    for s in stocks:
        rows.append([
            s.get("symbol"),
            (s.get("name") or "")[:20],
            _fmt_cap(s.get("market_cap")),
            _fmt_float(s.get("pe_ratio"), 1),
            _fmt_pct(s.get("revenue_growth")),
            _fmt_pct(s.get("profit_margins")),
            f"{s.get('opportunity_score', 0):.0f}/100",
        ])

    print(tabulate(
        rows,
        headers=["Ticker", "Name", "Mkt Cap", "P/E", "Rev Growth", "Margin", "Score"],
        tablefmt="rounded_outline",
    ))

    comp = result.get("ai_comparison", {})
    if comp.get("comparative_analysis"):
        print(f"\n📝  Analysis: {comp['comparative_analysis']}")
    if comp.get("best_overall"):
        print(f"🏆  Best Overall: {comp.get('best_overall')}")

    if args.json:
        fname = f"compare_{'_'.join(tickers)}_{date.today().isoformat()}"
        _save_report(result, fname)


# ---------------------------------------------------------------------------
# Watchlist commands
# ---------------------------------------------------------------------------

def cmd_watchlist_add(args: argparse.Namespace) -> None:
    """Add a ticker to the watchlist."""
    storage.add_to_watchlist(
        ticker=args.ticker,
        market=args.market,
        target_price=args.target_price,
        notes=args.notes or "",
    )
    print(f"✅  {args.ticker.upper()} added to watchlist ({args.market}).")


def cmd_watchlist_remove(args: argparse.Namespace) -> None:
    """Remove a ticker from the watchlist."""
    removed = storage.remove_from_watchlist(args.ticker)
    if removed:
        print(f"✅  {args.ticker.upper()} removed from watchlist.")
    else:
        print(f"⚠️  {args.ticker.upper()} not found in watchlist.")


def cmd_watchlist_show(args: argparse.Namespace) -> None:
    """Display all watchlist entries with current prices."""
    watchlist = storage.load_watchlist()
    if not watchlist:
        print("⚠️  Watchlist is empty. Add stocks with:\n"
              "    python cli.py watchlist add TICKER")
        return

    tickers = list(watchlist.keys())
    print(f"\n👀  Fetching prices for {len(tickers)} watchlist items …")
    try:
        from utils.screener import fetch_fundamentals
        rows = []
        for ticker in tickers:
            fund = fetch_fundamentals(ticker)
            entry = watchlist[ticker]
            price = fund.get("current_price")
            target = entry.get("target_price")
            upside = ((target - price) / price * 100) if (price and target) else None
            rows.append([
                ticker,
                entry.get("market", "US"),
                _fmt_float(price),
                _fmt_float(target),
                f"{upside:+.1f}%" if upside is not None else "N/A",
                _fmt_cap(fund.get("market_cap")),
                entry.get("added_date", ""),
                (entry.get("notes") or "")[:30],
            ])
    except Exception as exc:
        print(f"⚠️  Could not fetch live data: {exc}")
        rows = [
            [t, w.get("market"), "N/A", _fmt_float(w.get("target_price")),
             "N/A", "N/A", w.get("added_date", ""), (w.get("notes") or "")[:30]]
            for t, w in watchlist.items()
        ]

    print(tabulate(
        rows,
        headers=["Ticker", "Market", "Price", "Target", "Upside", "Mkt Cap", "Added", "Notes"],
        tablefmt="rounded_outline",
    ))


def cmd_watchlist_report(args: argparse.Namespace) -> None:
    """Run the SmallCap Scout on all watchlist items and generate a report."""
    watchlist = storage.load_watchlist()
    if not watchlist:
        print("⚠️  Watchlist is empty.")
        return

    tickers = list(watchlist.keys())
    print(f"\n📊  Running opportunity analysis on {len(tickers)} watchlist items …")

    scout = SmallCapScoutAgent()
    result = scout.find_opportunities(
        market="US",
        cap_type="all",
        extra_tickers=tickers,
        top_n=len(tickers),
    )

    opportunities = result.get("opportunities", [])
    if not opportunities:
        print("  No data available for watchlist items.")
        return

    print("\n" + "=" * 70)
    print("📋  WATCHLIST OPPORTUNITY REPORT")
    print("=" * 70)

    rows = []
    for o in opportunities:
        rows.append([
            o.get("symbol"),
            _fmt_cap(o.get("market_cap")),
            _fmt_float(o.get("pe_ratio"), 1),
            _fmt_pct(o.get("revenue_growth")),
            f"{o.get('opportunity_score', 0):.0f}/100",
            o.get("recommendation_action", "?"),
        ])

    print(tabulate(
        rows,
        headers=["Ticker", "Mkt Cap", "P/E", "Rev Growth", "Score", "Action"],
        tablefmt="rounded_outline",
    ))

    ai = result.get("ai_report", {})
    if ai.get("executive_summary"):
        print(f"\n📝  {ai['executive_summary']}")

    if args.json:
        _save_report(result, f"watchlist_report_{date.today().isoformat()}")


# ---------------------------------------------------------------------------
# Commands that do NOT require an OpenAI API key (no LLM calls).
# Tag functions with `_no_llm_required = True` so the startup guard can
# discover them without a hard-coded list.
# ---------------------------------------------------------------------------
cmd_portfolio_analyze._no_llm_required = True  # type: ignore[attr-defined]
cmd_portfolio_add._no_llm_required = True       # type: ignore[attr-defined]
cmd_portfolio_remove._no_llm_required = True    # type: ignore[attr-defined]
cmd_watchlist_add._no_llm_required = True       # type: ignore[attr-defined]
cmd_watchlist_remove._no_llm_required = True    # type: ignore[attr-defined]
cmd_watchlist_show._no_llm_required = True      # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arcanix",
        description="ARCANIX Portfolio Manager — small/micro-cap opportunity discovery",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py portfolio analyze
  python cli.py portfolio add AAPL --quantity 100 --avg-cost 150
  python cli.py opportunities find --market US --cap micro --sector tech
  python cli.py opportunities find --market EU --cap small --min-growth 15
  python cli.py stock analyze MVIS
  python cli.py stock compare MVIS KOPN GFAI
  python cli.py watchlist add MVIS --market US --notes "nano-LIDAR play"
  python cli.py watchlist report
        """,
    )
    parser.add_argument("--json", action="store_true", help="Save output as JSON/Markdown reports")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    subs = parser.add_subparsers(dest="command", required=True)

    # --- portfolio ---
    port = subs.add_parser("portfolio", help="Portfolio management commands")
    port_subs = port.add_subparsers(dest="subcommand", required=True)

    pa = port_subs.add_parser("analyze", help="Analyse current portfolio")
    pa.set_defaults(func=cmd_portfolio_analyze)

    padd = port_subs.add_parser("add", help="Add/update a portfolio position")
    padd.add_argument("ticker", help="Ticker symbol")
    padd.add_argument("--quantity", type=float, required=True, help="Number of shares")
    padd.add_argument("--avg-cost", type=float, required=True, dest="avg_cost",
                      help="Average cost per share")
    padd.add_argument("--market", default="US", help="Market (US, GB, DE, …)")
    padd.add_argument("--notes", default="", help="Optional notes")
    padd.set_defaults(func=cmd_portfolio_add)

    prm = port_subs.add_parser("remove", help="Remove a portfolio position")
    prm.add_argument("ticker", help="Ticker symbol to remove")
    prm.set_defaults(func=cmd_portfolio_remove)

    preb = port_subs.add_parser("rebalance", help="Generate rebalancing suggestions")
    preb.add_argument("--target-risk", choices=["low", "medium", "high"], default="medium",
                      dest="target_risk")
    preb.set_defaults(func=cmd_portfolio_rebalance)

    # --- opportunities ---
    opp = subs.add_parser("opportunities", help="Opportunity discovery commands")
    opp_subs = opp.add_subparsers(dest="subcommand", required=True)

    ofind = opp_subs.add_parser("find", help="Screen for small/micro-cap opportunities")
    ofind.add_argument("--market", default="US",
                       help="Market: US, EU, GB, DE, FR, NL, IT, ES (default: US)")
    ofind.add_argument("--cap", default="small",
                       choices=["micro", "small", "mid", "all"],
                       help="Market cap tier (default: small)")
    ofind.add_argument("--sector", default=None, help="Filter by sector keyword")
    ofind.add_argument("--min-growth", type=float, default=None, dest="min_growth",
                       help="Minimum revenue growth in %% (e.g. 15 for 15%%)")
    ofind.add_argument("--strategy", choices=["value", "growth"], default=None,
                       help="Scoring strategy bias")
    ofind.add_argument("--top", type=int, default=10, dest="top_n",
                       help="Number of top results to display (default: 10)")
    ofind.set_defaults(func=cmd_opportunities_find)

    # --- stock ---
    stk = subs.add_parser("stock", help="Individual stock analysis")
    stk_subs = stk.add_subparsers(dest="subcommand", required=True)

    sana = stk_subs.add_parser("analyze", help="Deep-dive on a single stock")
    sana.add_argument("ticker", help="Ticker symbol")
    sana.set_defaults(func=cmd_stock_analyze)

    scmp = stk_subs.add_parser("compare", help="Compare multiple stocks")
    scmp.add_argument("tickers", nargs="+", help="Ticker symbols to compare")
    scmp.set_defaults(func=cmd_stock_compare)

    # --- watchlist ---
    wl = subs.add_parser("watchlist", help="Watchlist management")
    wl_subs = wl.add_subparsers(dest="subcommand", required=True)

    wladd = wl_subs.add_parser("add", help="Add a ticker to the watchlist")
    wladd.add_argument("ticker", help="Ticker symbol")
    wladd.add_argument("--market", default="US", help="Market identifier")
    wladd.add_argument("--target-price", type=float, default=None, dest="target_price",
                       help="Optional price target")
    wladd.add_argument("--notes", default="", help="Optional notes")
    wladd.set_defaults(func=cmd_watchlist_add)

    wlrm = wl_subs.add_parser("remove", help="Remove a ticker from the watchlist")
    wlrm.add_argument("ticker", help="Ticker symbol to remove")
    wlrm.set_defaults(func=cmd_watchlist_remove)

    wlshow = wl_subs.add_parser("show", help="Display watchlist with current prices")
    wlshow.set_defaults(func=cmd_watchlist_show)

    wlrep = wl_subs.add_parser("report", help="Run full analysis on watchlist")
    wlrep.set_defaults(func=cmd_watchlist_report)

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING,
                            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    # Check OPENAI_API_KEY before commands that use AI agents.
    # Commands tagged with `_no_llm_required = True` skip this check.
    func = getattr(args, "func", None)
    _needs_llm = func is not None and not getattr(func, "_no_llm_required", False)
    if _needs_llm and not os.getenv("OPENAI_API_KEY"):
        print("⚠️  OPENAI_API_KEY is not set.\n"
              "    Copy .env.example to .env and add your key, then retry.\n"
              "    (Simple watchlist/portfolio add/remove/show commands do not require it.)")
        sys.exit(1)

    _load_modules()

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    # Propagate top-level --json flag down if the subparser also defines it
    if not hasattr(args, "json"):
        args.json = False

    args.func(args)


if __name__ == "__main__":
    main()
