# -*- coding: utf-8 -*-
"""Email template generation for weekly ETF reports — cyberpunk dark edition."""
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EmailConfig:
    sender: str
    recipient: str
    smtp_server: str
    smtp_port: int
    username: str
    password: str


def format_email_html(etfs: list) -> str:
    """Generate cyberpunk-dark HTML email body with ETF performance."""

    start_date = etfs[0].start_date
    end_date   = etfs[0].end_date

    def pos_color(v: float) -> str:
        return "#00ff88" if v >= 0 else "#ff2d78"

    def pos_bg(v: float) -> str:
        return "#001a0f" if v >= 0 else "#1a0010"

    def pos_border(v: float) -> str:
        return "#00ff8855" if v >= 0 else "#ff2d7855"

    def pos_accent(v: float) -> str:
        return "#00ff88" if v >= 0 else "#ff2d78"

    def arrow(v: float) -> str:
        return "▲" if v >= 0 else "▼"

    # ── ETF rows ─────────────────────────────────────────────────────────────
    rows = ""
    for etf in etfs:
        wr   = etf.weekly_return * 100
        wt   = etf.weekly_trend  * 100
        c_w  = pos_color(wr)
        c_t  = pos_color(wt)
        a    = arrow(wr)
        row_bg = "#0a111e" if etfs.index(etf) % 2 == 0 else "#08111f"

        rows += f"""
          <tr style="border-bottom:1px solid #0f2040;background-color:{row_bg};">
            <td style="padding:14px 18px;font-family:'Courier New',Courier,monospace;
                       font-size:13px;color:#00d4ff;font-weight:700;letter-spacing:1px;">
              <span style="color:{c_w};margin-right:6px;">{a}</span>{etf.name}
            </td>
            <td style="padding:14px 16px;text-align:right;font-family:'Courier New',Courier,monospace;
                       font-size:13px;color:#5a7fa8;">€{etf.open_monday:.2f}</td>
            <td style="padding:14px 16px;text-align:right;font-family:'Courier New',Courier,monospace;
                       font-size:13px;color:#c0cce0;">€{etf.close_friday:.2f}</td>
            <td style="padding:14px 16px;text-align:right;font-family:'Courier New',Courier,monospace;
                       font-size:15px;font-weight:700;color:{c_w};">{wr:+.2f}%</td>
            <td style="padding:14px 16px;text-align:right;font-family:'Courier New',Courier,monospace;
                       font-size:12px;color:{c_t};">{wt:+.2f}%</td>
          </tr>"""

    # ── Best / worst ──────────────────────────────────────────────────────────
    best  = max(etfs, key=lambda x: x.weekly_return)
    worst = min(etfs, key=lambda x: x.weekly_return)

    best_label  = f"{best.name}&nbsp;&nbsp;{best.weekly_return*100:+.2f}%"  if best.weekly_return  > 0 else "N/A"
    worst_label = f"{worst.name}&nbsp;&nbsp;{worst.weekly_return*100:+.2f}%" if worst.weekly_return < 0 else "N/A"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>Weekly ETF Report</title>
</head>
<body style="margin:0;padding:0;background-color:#040810;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,sans-serif;">

<!-- ═══════ OUTER WRAPPER ═══════ -->
<table width="100%" cellpadding="0" cellspacing="0"
       style="background-color:#040810;padding:40px 16px;">
  <tr><td align="center">

    <!-- ═══════ CARD ═══════ -->
    <table width="600" cellpadding="0" cellspacing="0"
           style="max-width:600px;width:100%;
                  background-color:#08111f;
                  border:1px solid #0e2545;
                  border-radius:6px;overflow:hidden;">

      <!-- ── HEADER ─────────────────────────────────────── -->
      <tr>
        <td style="padding:0;">
          <!-- top accent line -->
          <div style="height:3px;background:linear-gradient(90deg,#00d4ff 0%,#7b2fff 50%,#ff2d78 100%);"></div>

          <div style="background:linear-gradient(160deg,#060e1d 0%,#0a1530 100%);
                      padding:36px 32px 30px;text-align:center;">

            <!-- badge -->
            <div style="display:inline-block;border:1px solid #00d4ff33;
                        background:#00d4ff0a;border-radius:3px;
                        padding:4px 14px;margin-bottom:16px;">
              <span style="font-family:'Courier New',Courier,monospace;
                           font-size:9px;color:#00d4ff;letter-spacing:4px;
                           text-transform:uppercase;">◈ AUTOMATED REPORT ◈</span>
            </div>

            <h1 style="margin:0;font-size:24px;font-weight:700;color:#e8f0ff;
                       letter-spacing:3px;text-transform:uppercase;
                       text-shadow:0 0 20px #00d4ff44;">
              Weekly ETF Tracker
            </h1>

            <p style="margin:12px 0 0;font-family:'Courier New',Courier,monospace;
                      font-size:12px;color:#00d4ff;letter-spacing:3px;">
              {start_date}&nbsp;&nbsp;→&nbsp;&nbsp;{end_date}
            </p>
          </div>
        </td>
      </tr>

      <!-- ── PERFORMANCE TABLE ───────────────────────────── -->
      <tr>
        <td style="padding:28px 24px 4px;">
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="border-collapse:collapse;border:1px solid #0f2040;border-radius:4px;overflow:hidden;">
            <!-- thead -->
            <tr style="background-color:#050e1a;border-bottom:1px solid #00d4ff33;">
              <th style="padding:10px 18px;text-align:left;font-family:'Courier New',Courier,monospace;
                         font-size:9px;color:#3a6090;letter-spacing:3px;
                         text-transform:uppercase;font-weight:400;">ETF</th>
              <th style="padding:10px 16px;text-align:right;font-family:'Courier New',Courier,monospace;
                         font-size:9px;color:#3a6090;letter-spacing:3px;
                         text-transform:uppercase;font-weight:400;">MON OPEN</th>
              <th style="padding:10px 16px;text-align:right;font-family:'Courier New',Courier,monospace;
                         font-size:9px;color:#3a6090;letter-spacing:3px;
                         text-transform:uppercase;font-weight:400;">FRI CLOSE</th>
              <th style="padding:10px 16px;text-align:right;font-family:'Courier New',Courier,monospace;
                         font-size:9px;color:#3a6090;letter-spacing:3px;
                         text-transform:uppercase;font-weight:400;">WEEKLY %%</th>
              <th style="padding:10px 16px;text-align:right;font-family:'Courier New',Courier,monospace;
                         font-size:9px;color:#3a6090;letter-spacing:3px;
                         text-transform:uppercase;font-weight:400;">TREND *</th>
            </tr>
            {rows}
          </table>
          <p style="margin:6px 0 0;text-align:right;font-family:'Courier New',Courier,monospace;
                    font-size:9px;color:#1e3555;letter-spacing:1px;">
            * TREND = Fri close vs. previous Fri close
          </p>
        </td>
      </tr>

      <!-- ── BEST / WORST ────────────────────────────────── -->
      <tr>
        <td style="padding:20px 24px 4px;">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <!-- Best -->
              <td width="48%"
                  style="background:#001a10;
                         border:1px solid #00ff8844;
                         border-left:3px solid #00ff88;
                         border-radius:4px;padding:14px 16px;">
                <p style="margin:0;font-family:'Courier New',Courier,monospace;
                           font-size:8px;color:#00ff88;letter-spacing:4px;
                           text-transform:uppercase;">▲ &nbsp;BEST PERFORMER</p>
                <p style="margin:8px 0 0;font-family:'Courier New',Courier,monospace;
                           font-size:13px;color:#e8f0ff;font-weight:700;">{best_label}</p>
              </td>
              <td width="4%"></td>
              <!-- Worst -->
              <td width="48%"
                  style="background:#1a0010;
                         border:1px solid #ff2d7844;
                         border-left:3px solid #ff2d78;
                         border-radius:4px;padding:14px 16px;">
                <p style="margin:0;font-family:'Courier New',Courier,monospace;
                           font-size:8px;color:#ff2d78;letter-spacing:4px;
                           text-transform:uppercase;">▼ &nbsp;UNDERPERFORMER</p>
                <p style="margin:8px 0 0;font-family:'Courier New',Courier,monospace;
                           font-size:13px;color:#e8f0ff;font-weight:700;">{worst_label}</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- ── CHART NOTE ──────────────────────────────────── -->
      <tr>
        <td style="padding:16px 24px 28px;">
          <div style="background:#060e1c;border:1px solid #0f2847;
                      border-left:3px solid #00d4ff;
                      border-radius:4px;padding:13px 16px;">
            <p style="margin:0;font-family:'Courier New',Courier,monospace;
                      font-size:11px;color:#3a6a90;">
              <span style="color:#00d4ff;letter-spacing:1px;">[ ATTACHMENT ]</span>
              &nbsp;&nbsp;Weekly price chart enclosed as PNG.
            </p>
          </div>
        </td>
      </tr>

      <!-- ── FOOTER ──────────────────────────────────────── -->
      <tr>
        <td style="border-top:1px solid #0a1e38;
                   background:#040810;padding:14px 24px;text-align:center;">
          <p style="margin:0;font-family:'Courier New',Courier,monospace;
                    font-size:9px;color:#1c3050;letter-spacing:2px;text-transform:uppercase;">
            SRC: YAHOO FINANCE &nbsp;|&nbsp; PIPELINE: AUTOMATED &nbsp;|&nbsp; {end_date}
          </p>
        </td>
      </tr>

      <!-- bottom accent line -->
      <tr>
        <td style="padding:0;">
          <div style="height:2px;background:linear-gradient(90deg,#ff2d78 0%,#7b2fff 50%,#00d4ff 100%);"></div>
        </td>
      </tr>

    </table>
  </td></tr>
</table>

</body>
</html>"""

    return html.strip()


def format_email_plain(etfs: list) -> str:
    """Plain-text fallback (email clients without HTML)."""

    start_date = etfs[0].start_date
    end_date   = etfs[0].end_date

    body = (
        f"WEEKLY ETF REPORT  |  {start_date} → {end_date}\n"
        f"{'═' * 72}\n\n"
    )

    body += f"{'ETF':<32} {'MON OPEN':>10} {'FRI CLOSE':>10} {'WEEKLY':>9} {'TREND':>9}\n"
    body += f"{'-' * 72}\n"

    for etf in etfs:
        a = "▲" if etf.weekly_return >= 0 else "▼"
        body += (
            f"{a} {etf.name:<30} "
            f"€{etf.open_monday:>9.2f} "
            f"€{etf.close_friday:>9.2f} "
            f"{etf.weekly_return*100:>+8.2f}% "
            f"{etf.weekly_trend*100:>+8.2f}%\n"
        )

    body += f"\n{'═' * 72}\n\n"

    best  = max(etfs, key=lambda x: x.weekly_return)
    worst = min(etfs, key=lambda x: x.weekly_return)

    body += f"  ★  BEST         {best.name}  ({best.weekly_return*100:+.2f}%)\n"
    body += f"  ⚠  UNDERPERFORM {worst.name}  ({worst.weekly_return*100:+.2f}%)\n\n"
    body += "  * Trend = Fri close vs. previous Fri close\n"
    body += "  Attachment: weekly_chart.png\n"

    return body