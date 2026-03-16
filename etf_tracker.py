"""
Multi-ETF Weekly Performance Tracker
====================================
Tracks VWCE.DE (All-World) and XDW0.DE (World Energy) in a single report.
"""

import os
import logging
import smtplib
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

from email_template import format_email_html, format_email_plain

# ══════════════════════════════════════════════════════════════════════
#                         CONFIGURATION
# ══════════════════════════════════════════════════════════════════════

TICKERS = {
    "VWCE.DE": "FTSE All-World",
    "XDW0.DE": "MSCI World Energy",
}

load_dotenv()

SMTP_SERVER   = "smtp.mail.yahoo.com"
SMTP_PORT     = 587
SMTP_USERNAME = os.getenv("EMAIL")
SMTP_PASSWORD = os.getenv("EMAIL_PSW")
EMAIL_SENDER    = SMTP_USERNAME
EMAIL_RECIPIENT = SMTP_USERNAME

# ══════════════════════════════════════════════════════════════════════
#                         LOGGING
# ══════════════════════════════════════════════════════════════════════

LOG_FILE = Path(__file__).parent / "etf_tracker.log"

import sys

_fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

_file_handler   = logging.FileHandler(LOG_FILE, encoding="utf-8")
_file_handler.setFormatter(_fmt)

_stream_handler = logging.StreamHandler(stream=open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False))
_stream_handler.setFormatter(_fmt)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(_file_handler)
logger.addHandler(_stream_handler)
logger.propagate = False

# ══════════════════════════════════════════════════════════════════════
#                         DATA CLASS
# ══════════════════════════════════════════════════════════════════════

@dataclass
class ETFWeeklyData:
    ticker:          str
    name:            str
    open_monday:     float
    close_friday:    float
    prev_week_close: float
    weekly_return:   float   # Mon open → Fri close (intra-week)
    weekly_trend:    float   # prev Fri close → this Fri close (week-over-week)
    start_date:      str
    end_date:        str
    week_data:       pd.DataFrame

# ══════════════════════════════════════════════════════════════════════
#                         DATA FETCHING
# ══════════════════════════════════════════════════════════════════════

def fetch_price_data(ticker: str, days: int = 35) -> pd.DataFrame:
    """Fetch historical price data from Yahoo Finance (35 d to guarantee 2 full weeks)."""
    logger.info(f"Fetching price data for {ticker}")

    end_dt   = datetime.now()
    start_dt = end_dt - timedelta(days=days)

    data = yf.download(
        ticker,
        start=start_dt.strftime("%Y-%m-%d"),
        end=end_dt.strftime("%Y-%m-%d"),
        progress=False,
    )

    if data.empty:
        raise ValueError(f"No data returned for ticker {ticker}")

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    logger.info(f"Fetched {len(data)} trading days for {ticker}")
    return data


def extract_last_completed_week(data: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """
    Return (week_data, prev_friday_close) for the last COMPLETED Mon–Fri week.

    Logic:
    - Resample to weekly-ending-Friday to get a clean series of Friday closes.
    - If today > last Friday in the series  →  last completed week  = series[-1],
      prev_close = series[-2].
    - If today <= last Friday (still in current week, or it's Friday itself)
      →  last completed week  = series[-2],  prev_close = series[-3].
    - Trend  = (this_fri_close / prev_fri_close) - 1  (week-over-week).
    - Return = (fri_close / mon_open) - 1             (intra-week, computed in process_etf).
    """
    weekly = data["Close"].resample("W-FRI").last().dropna()

    if len(weekly) < 3:
        raise ValueError("Insufficient history: need ≥3 completed Friday closes (fetch more days).")

    today       = datetime.now().date()
    last_friday = weekly.index[-1].date()

    if today > last_friday:
        # We are past the last Friday → that week is complete
        week_end_ts   = weekly.index[-1]
        prev_fri_close = float(weekly.iloc[-2])
    else:
        # Today is Friday or earlier → last complete week is the one before
        week_end_ts   = weekly.index[-2]
        prev_fri_close = float(weekly.iloc[-3])

    week_start_ts = week_end_ts - timedelta(days=6)

    mask      = (data.index >= week_start_ts) & (data.index <= week_end_ts)
    week_data = data.loc[mask].copy()

    if week_data.empty:
        raise ValueError(f"No trading data found for week ending {week_end_ts.date()}")

    logger.info(
        f"Last completed week: {week_start_ts.date()} -> {week_end_ts.date()} "
        f"| prev Fri close: {prev_fri_close:.2f}"
    )
    return week_data, prev_fri_close


def process_etf(ticker: str, name: str) -> ETFWeeklyData:
    """Fetch and process a single ETF."""
    logger.info(f"Processing {ticker} ({name})")

    price_data              = fetch_price_data(ticker)
    week_data, prev_fri_close = extract_last_completed_week(price_data)

    open_monday  = float(week_data["Open"].iloc[0])
    close_friday = float(week_data["Close"].iloc[-1])

    weekly_return = (close_friday / open_monday)    - 1   # intra-week
    weekly_trend  = (close_friday / prev_fri_close) - 1   # week-over-week

    start_date = week_data.index[0].strftime("%Y-%m-%d")
    end_date   = week_data.index[-1].strftime("%Y-%m-%d")

    logger.info(
        f"{ticker}: return={weekly_return*100:+.2f}%  trend={weekly_trend*100:+.2f}%"
    )

    return ETFWeeklyData(
        ticker=ticker,
        name=name,
        open_monday=open_monday,
        close_friday=close_friday,
        prev_week_close=prev_fri_close,
        weekly_return=weekly_return,
        weekly_trend=weekly_trend,
        start_date=start_date,
        end_date=end_date,
        week_data=week_data,
    )

# ══════════════════════════════════════════════════════════════════════
#                         CHART
# ══════════════════════════════════════════════════════════════════════

def generate_combined_chart(etfs: list[ETFWeeklyData], output_path: Path) -> Path:
    """Generate side-by-side comparison chart — cyberpunk dark style."""
    logger.info("Generating combined weekly chart")

    plt.style.use("dark_background")
    fig, axes = plt.subplots(1, len(etfs), figsize=(10, 4.5))
    fig.patch.set_facecolor("#040810")

    if len(etfs) == 1:
        axes = [axes]

    for ax, etf in zip(axes, etfs):
        ax.set_facecolor("#08111f")

        dates        = etf.week_data.index
        closes       = etf.week_data["Close"]
        open_monday  = etf.open_monday
        close_friday = etf.close_friday
        trend_pct    = etf.weekly_trend * 100
        c_perf       = "#00ff88" if trend_pct >= 0 else "#ff2d78"

        # Reference line: Monday open
        ax.axhline(y=open_monday, color="#ffa500", linestyle="--",
                   linewidth=1.5, alpha=0.6, label=f"Mon Open €{open_monday:.2f}")

        # Price line (glow effect via layering)
        ax.plot(dates, closes, color="#00d4ff", linewidth=2.5, zorder=4)
        ax.plot(dates, closes, color="#00d4ff", linewidth=7, alpha=0.15, zorder=3)

        # Fill above/below Monday open
        ax.fill_between(dates, open_monday, closes,
                        where=(closes >= open_monday),
                        alpha=0.18, color="#00ff88", interpolate=True)
        ax.fill_between(dates, open_monday, closes,
                        where=(closes < open_monday),
                        alpha=0.18, color="#ff2d78", interpolate=True)

        # Data points
        ax.scatter(dates, closes, color="#ffffff", s=55, zorder=6,
                   edgecolors="#00d4ff", linewidths=1.5)

        # Open / close markers
        ax.scatter(dates[0],  open_monday,  color="#ffa500", s=100, zorder=7,
                   marker="s", edgecolors="#ffffff", linewidths=1.5)
        ax.scatter(dates[-1], close_friday, color=c_perf,    s=100, zorder=7,
                   marker="D", edgecolors="#ffffff", linewidths=1.5)

        # Annotations
        ax.annotate(f"€{open_monday:.2f}",
                    xy=(dates[0], open_monday),
                    xytext=(-18, 10), textcoords="offset points",
                    fontsize=8, color="#ffa500", fontweight="bold")
        ax.annotate(f"€{close_friday:.2f}\n({trend_pct:+.2f}%)",
                    xy=(dates[-1], close_friday),
                    xytext=(8, 10), textcoords="offset points",
                    fontsize=9, color=c_perf, fontweight="bold")

        min_price = closes.min()
        max_price = closes.max()
        min_date  = closes.idxmin()
        max_date  = closes.idxmax()

        if max_date != dates[-1]:
            ax.annotate(f"€{max_price:.2f}", xy=(max_date, max_price),
                        xytext=(8, 10), textcoords="offset points",
                        fontsize=9, color="#00ff88", fontweight="bold")

        if min_date not in (dates[-1], dates[0]):
            ax.annotate(f"€{min_price:.2f}", xy=(min_date, min_price),
                        xytext=(8, -15), textcoords="offset points",
                        fontsize=9, color="#ff2d78", fontweight="bold")
        elif min_date == dates[0] and min_price < open_monday:
            ax.annotate(f"€{min_price:.2f}", xy=(min_date, min_price),
                        xytext=(8, -15), textcoords="offset points",
                        fontsize=9, color="#ff2d78", fontweight="bold")

        ax.set_title(
            f"{etf.ticker} - {etf.name}\n{etf.start_date}  ->  {etf.end_date}",
            fontsize=13, fontweight="bold", color="#c8d8f0", pad=16,
        )
        ax.set_xlabel("Date",        fontsize=11, color="#3a6090")
        ax.set_ylabel("Close (EUR)", fontsize=11, color="#3a6090")
        ax.grid(True, alpha=0.10, color="#ffffff", linestyle="--")
        ax.tick_params(colors="#4a6a90", rotation=45)

        for spine in ax.spines.values():
            spine.set_color("#0f2847")

    plt.tight_layout(pad=2.0)
    plt.savefig(output_path, dpi=150, format="png",
                facecolor="#040810", edgecolor="none")
    plt.close()
    plt.style.use("default")

    logger.info(f"Combined chart saved to {output_path}")
    return output_path

# ══════════════════════════════════════════════════════════════════════
#                         EMAIL
# ══════════════════════════════════════════════════════════════════════

def send_email(
    subject:     str,
    html_body:   str,
    plain_body:  str,
    chart_path:  Path,
    sender:      str,
    recipient:   str,
    smtp_server: str,
    smtp_port:   int,
    username:    str,
    password:    str,
) -> None:
    logger.info(f"Sending email to {recipient}")

    # Correct MIME structure:
    #   mixed
    #   ├── alternative          ← plain + html as fallback pair (no duplication)
    #   │   ├── text/plain
    #   │   └── text/html
    #   └── image/png            ← chart attachment
    outer = MIMEMultipart("mixed")
    outer["From"]    = sender
    outer["To"]      = recipient
    outer["Subject"] = subject

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(plain_body, "plain", "utf-8"))
    alt.attach(MIMEText(html_body,  "html",  "utf-8"))
    outer.attach(alt)

    with open(chart_path, "rb") as f:
        img = MIMEImage(f.read(), name=chart_path.name)
        img.add_header("Content-Disposition", "attachment", filename=chart_path.name)
        outer.attach(img)

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(username, password)
        server.send_message(outer)

    logger.info("Email sent successfully")

# ══════════════════════════════════════════════════════════════════════
#                         MAIN
# ══════════════════════════════════════════════════════════════════════

def main() -> None:
    logger.info("Starting Multi-ETF Weekly Tracker")
    logger.info(f"Tracking: {', '.join(TICKERS.keys())}")

    try:
        etfs = [process_etf(t, n) for t, n in TICKERS.items()]

        year     = etfs[0].week_data.index[0].year
        week_num = etfs[0].week_data.index[0].isocalendar()[1]

        with tempfile.TemporaryDirectory() as tmp_dir:
            chart_path = Path(tmp_dir) / f"etf_weekly_{year}_W{week_num:02d}.png"
            generate_combined_chart(etfs, chart_path)

            subject    = f"📊 Weekly ETF Report | {year}-W{week_num:02d} | VWCE & XDW0"
            html_body  = format_email_html(etfs)
            plain_body = format_email_plain(etfs)

            send_email(
                subject=subject,
                html_body=html_body,
                plain_body=plain_body,
                chart_path=chart_path,
                sender=EMAIL_SENDER,
                recipient=EMAIL_RECIPIENT,
                smtp_server=SMTP_SERVER,
                smtp_port=SMTP_PORT,
                username=SMTP_USERNAME,
                password=SMTP_PASSWORD,
            )

        logger.info("Multi-ETF weekly tracker completed successfully")

    except Exception as e:
        logger.error(f"Error in ETF tracker: {e}")
        raise


if __name__ == "__main__":
    main()