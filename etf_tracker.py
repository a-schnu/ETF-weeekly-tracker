"""
Multi-ETF Weekly Performance Tracker
====================================
Tracks VWCE.DE (All-World) and XDW0.DE (World Energy) in a single report.
"""

import os
import logging
import smtplib
import tempfile
from dotenv import load_dotenv
from datetime import datetime, timedelta
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from dataclasses import dataclass

import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf

# ══════════════════════════════════════════════════════════════════════
#                         CONFIGURATION
# ══════════════════════════════════════════════════════════════════════

TICKERS = {
    "VWCE.DE": "FTSE All-World",
    "XDW0.DE": "MSCI World Energy",
}

load_dotenv()

SMTP_SERVER = "smtp.mail.yahoo.com"
SMTP_PORT = 587
SMTP_USERNAME = os.getenv("EMAIL")
SMTP_PASSWORD = os.getenv("EMAIL_PSW")
EMAIL_SENDER = SMTP_USERNAME
EMAIL_RECIPIENT = SMTP_USERNAME

# ══════════════════════════════════════════════════════════════════════
#                         LOGGING
# ══════════════════════════════════════════════════════════════════════

LOG_FILE = Path(__file__).parent / "etf_tracker.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════
#                         DATA CLASS
# ══════════════════════════════════════════════════════════════════════

@dataclass
class ETFWeeklyData:
    """Container for weekly ETF data."""
    ticker: str
    name: str
    open_monday: float
    close_friday: float
    weekly_return: float
    start_date: str
    end_date: str
    week_data: pd.DataFrame

# ══════════════════════════════════════════════════════════════════════
#                         DATA FETCHING
# ══════════════════════════════════════════════════════════════════════

def fetch_price_data(ticker: str, days: int = 30) -> pd.DataFrame:
    """Fetch historical price data from Yahoo Finance."""
    logger.info(f"Fetching price data for {ticker}")

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    data = yf.download(
        ticker,
        start=start_date.strftime("%Y-%m-%d"),
        end=end_date.strftime("%Y-%m-%d"),
        progress=False,
    )

    if data.empty:
        raise ValueError(f"No data returned for ticker {ticker}")

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    logger.info(f"Fetched {len(data)} days of price data for {ticker}")
    return data


def extract_last_completed_week(data: pd.DataFrame) -> pd.DataFrame:
    """Extract the most recent completed trading week."""
    weekly = data["Close"].resample("W-FRI").last()

    if len(weekly) < 2:
        raise ValueError("Insufficient data to determine a completed week")

    today = datetime.now().date()
    last_friday = weekly.index[-1].date()

    week_end = weekly.index[-1] if today > last_friday else weekly.index[-2]
    week_start = week_end - timedelta(days=6)

    mask = (data.index >= week_start) & (data.index <= week_end)
    week_data = data.loc[mask].copy()

    if week_data.empty:
        raise ValueError("No trading data found for the last completed week")

    return week_data


def process_etf(ticker: str, name: str) -> ETFWeeklyData:
    """Fetch and process data for a single ETF."""
    logger.info(f"Processing {ticker} ({name})")
    
    price_data = fetch_price_data(ticker)
    week_data = extract_last_completed_week(price_data)
    
    open_monday = week_data["Open"].iloc[0]
    close_friday = week_data["Close"].iloc[-1]
    weekly_return = (close_friday / open_monday) - 1
    
    start_date = week_data.index[0].strftime("%Y-%m-%d")
    end_date = week_data.index[-1].strftime("%Y-%m-%d")
    
    logger.info(f"{ticker}: {weekly_return*100:+.2f}%")
    
    return ETFWeeklyData(
        ticker=ticker,
        name=name,
        open_monday=open_monday,
        close_friday=close_friday,
        weekly_return=weekly_return,
        start_date=start_date,
        end_date=end_date,
        week_data=week_data,
    )

# ══════════════════════════════════════════════════════════════════════
#                         CHART GENERATION
# ══════════════════════════════════════════════════════════════════════

def generate_combined_chart(etfs: list[ETFWeeklyData], output_path: Path) -> Path:
    """Generate side-by-side comparison chart with full styling."""
    logger.info("Generating combined weekly chart")
    
    plt.style.use('dark_background')
    fig, axes = plt.subplots(1, len(etfs), figsize=(10, 4.5))
    fig.patch.set_facecolor('#0d1117')
    
    # Se c'è solo un ETF, axes non è una lista
    if len(etfs) == 1:
        axes = [axes]

    for ax, etf in zip(axes, etfs):
        ax.set_facecolor('#0d1117')
        
        # Dati
        dates = etf.week_data.index
        closes = etf.week_data["Close"]
        open_monday = etf.open_monday
        close_friday = etf.close_friday
        
        # Calcolo performance
        weekly_return = (close_friday / open_monday - 1) * 100
        color_perf = '#00ff88' if weekly_return >= 0 else '#ff6b6b'

        # 1. Reference line Open Monday
        ax.axhline(y=open_monday, color='#ffa500', linestyle='--', 
                   linewidth=2, alpha=0.7, label=f'Open Mon: €{open_monday:.2f}')

        # 2. Main line with glow effect
        ax.plot(dates, closes, color='#00d4ff', linewidth=3, zorder=3)
        ax.plot(dates, closes, color='#00d4ff', linewidth=6, alpha=0.3, zorder=2)

        # 3. Fill green/red based on Open Monday
        ax.fill_between(dates, open_monday, closes, 
                        where=(closes >= open_monday),
                        alpha=0.2, color='#00ff88', interpolate=True)
        ax.fill_between(dates, open_monday, closes, 
                        where=(closes < open_monday),
                        alpha=0.2, color='#ff6b6b', interpolate=True)

        # 4. Data points with glow
        ax.scatter(dates, closes, color='#ffffff', s=80, zorder=5, 
                   edgecolors='#00d4ff', linewidths=2)

        # 5. Special markers
        ax.scatter(dates[0], open_monday, color='#ffa500', s=120, zorder=6,
                   marker='s', edgecolors='white', linewidths=2, label='Open Mon')
        ax.scatter(dates[-1], close_friday, color=color_perf, s=120, zorder=6,
                   marker='D', edgecolors='white', linewidths=2, label='Close Fri')

        # 6. Min/Max annotations
        min_price = closes.min()
        max_price = closes.max()
        min_date = closes.idxmin()
        max_date = closes.idxmax()
        
 
        # 7. Open Monday & Close Friday annotations
        ax.annotate(f'€{open_monday:.2f}', xy=(dates[0], open_monday),
                    xytext=(-20, 10), textcoords='offset points',
                    fontsize=8, color='#ffa500', fontweight='bold')
        ax.annotate(f'€{close_friday:.2f}\n({weekly_return:+.2f}%)', 
                    xy=(dates[-1], close_friday),
                    xytext=(8, 10), textcoords='offset points',
                    fontsize=9, color=color_perf, fontweight='bold')
                    
        # 9. Max annotation — SKIP se coincide con Close Friday
        if max_date != dates[-1]:
            ax.annotate(f'€{max_price:.2f}', xy=(max_date, max_price),
                        xytext=(8, 10), textcoords='offset points',
                        fontsize=9, color='#00ff88', fontweight='bold')

        # 10. Min annotation — SKIP se coincide con Close Friday o Open Monday
        if min_date != dates[-1] and min_date != dates[0]:
            ax.annotate(f'€{min_price:.2f}', xy=(min_date, min_price),
                        xytext=(8, -15), textcoords='offset points',
                        fontsize=9, color='#ff6b6b', fontweight='bold')
        elif min_date == dates[0] and min_price < open_monday:
            # Min è lunedì ma è il Close, non l'Open
            ax.annotate(f'€{min_price:.2f}', xy=(min_date, min_price),
                        xytext=(8, -15), textcoords='offset points',
                        fontsize=9, color='#ff6b6b', fontweight='bold')

        # 8. Styling
        ax.set_title(f"{etf.ticker} – {etf.name}\n{etf.start_date} to {etf.end_date}",
                     fontsize=14, fontweight='bold', color='#ffffff', pad=20)
        ax.set_xlabel("Date", fontsize=12, color='#888888')
        ax.set_ylabel("Close (EUR)", fontsize=12, color='#888888')
        ax.grid(True, alpha=0.15, color='#ffffff', linestyle='--')
        ax.tick_params(colors='#888888', rotation=45)

        # Spine styling
        for spine in ax.spines.values():
            spine.set_color('#333333')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, format="png", 
                facecolor='#0d1117', edgecolor='none')
    plt.close()
    plt.style.use('default')

    logger.info(f"Combined chart saved to {output_path}")
    return output_path

# ══════════════════════════════════════════════════════════════════════
#                         EMAIL
# ══════════════════════════════════════════════════════════════════════

def format_email_body(etfs: list[ETFWeeklyData]) -> str:
    """Format email body with comparison table."""
    
    body = (
        f"Hey Anto,\n\n"
        f"Here's your weekly ETF performance summary for "
        f"{etfs[0].start_date} to {etfs[0].end_date}.\n\n"
    )
    
    # Comparison table
    body += "═" * 47 + "\n"
    body += f"{'ETF':<40} {'Open Mon':>16} {'Close Fri':>12} {'Return':>8}\n"
    body += "─" * 47 + "\n"
    
    for etf in etfs:
        sign = "+" if etf.weekly_return >= 0 else ""
        emoji = "📈" if etf.weekly_return >= 0 else "📉"
        body += (
            f"{emoji} {etf.name:<28} "
            f"€{etf.open_monday:>12.2f} "
            f"€{etf.close_friday:>10.2f} "
            f"{sign}{etf.weekly_return*100:>6.2f}%\n"
        )
    
    body += "═" * 47 + "\n\n"
    
    # Winner/Loser
    best = max(etfs, key=lambda x: x.weekly_return)
    worst = min(etfs, key=lambda x: x.weekly_return)
    
    if best.weekly_return > 0:
        body += f"🏆 Best performer: {best.name} ({best.weekly_return*100:+.2f}%)\n"
    if worst.weekly_return < 0:
        body += f"⚠️ Underperformer: {worst.name} ({worst.weekly_return*100:+.2f}%)\n"
    
    body += "\nTschüss!"
    
    return body


def send_email(
    subject: str,
    body: str,
    chart_path: Path,
    sender: str,
    recipient: str,
    smtp_server: str,
    smtp_port: int,
    username: str,
    password: str,
) -> None:
    """Send email with chart attachment."""
    logger.info(f"Sending email to {recipient}")

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    with open(chart_path, "rb") as f:
        img = MIMEImage(f.read(), name=chart_path.name)
        img.add_header("Content-Disposition", "attachment", filename=chart_path.name)
        msg.attach(img)

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(username, password)
        server.send_message(msg)

    logger.info("Email sent successfully")

# ══════════════════════════════════════════════════════════════════════
#                         MAIN
# ══════════════════════════════════════════════════════════════════════

def main() -> None:
    """Main execution function."""
    logger.info("Starting Multi-ETF Weekly Tracker")
    logger.info(f"Tracking: {', '.join(TICKERS.keys())}")

    try:
        # Process all ETFs
        etfs = []
        for ticker, name in TICKERS.items():
            etf_data = process_etf(ticker, name)
            etfs.append(etf_data)

        # Week info (from first ETF)
        year = etfs[0].week_data.index[0].year
        week_num = etfs[0].week_data.index[0].isocalendar()[1]

        # Generate combined chart
        with tempfile.TemporaryDirectory() as tmp_dir:
            chart_path = Path(tmp_dir) / f"etf_weekly_{year}_W{week_num:02d}.png"
            generate_combined_chart(etfs, chart_path)

            # Format email
            subject = f"📊 Weekly ETF Report | {year}-W{week_num:02d} | VWCE & XDW0"
            body = format_email_body(etfs)

            # Send email
            send_email(
                subject=subject,
                body=body,
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