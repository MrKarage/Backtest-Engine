import os
import matplotlib
matplotlib.use('Agg') # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timezone
from typing import List, Dict, Optional
from .models import BacktestResult, Candle, Trade, Side

class ReportGenerator:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.charts_dir = os.path.join(output_dir, "charts")
        os.makedirs(self.charts_dir, exist_ok=True)

    def generate(self, result: BacktestResult, candles: List[Candle]) -> Dict[str, str]:
        """
        Generates the full report (text + charts).
        Returns a dictionary with paths to the generated files.
        """
        # 1. Generate Text Report
        report_path = self._generate_text_report(result)

        # 2. Generate Daily Charts
        chart_paths = self._generate_daily_charts(result, candles)

        return {
            "report_path": report_path,
            "chart_paths": chart_paths
        }

    def _generate_text_report(self, result: BacktestResult) -> str:
        filepath = os.path.join(self.output_dir, "report.md")

        summary = result.summary

        with open(filepath, "w") as f:
            f.write(f"# Backtest Report: {result.backtest_id}\n\n")

            # Summary Section
            f.write("## Summary\n\n")
            f.write("| Metric | Value |\n")
            f.write("| :--- | :--- |\n")
            f.write(f"| Net Profit | {summary.net_profit:.2f} |\n")
            f.write(f"| Gross Profit | {summary.gross_profit:.2f} |\n")
            f.write(f"| Gross Loss | {summary.gross_loss:.2f} |\n")
            f.write(f"| Profit Factor | {summary.profit_factor:.2f} |\n")
            f.write(f"| Win Rate | {summary.win_rate * 100:.2f}% |\n")
            f.write(f"| Total Trades | {summary.total_trades} |\n")
            f.write(f"| Max Drawdown | {summary.max_drawdown:.2f} ({summary.max_drawdown_percent:.2f}%) |\n")
            f.write(f"| Avg Trade | {summary.avg_trade:.2f} |\n")
            f.write(f"| Avg Win | {summary.avg_win:.2f} |\n")
            f.write(f"| Avg Loss | {summary.avg_loss:.2f} |\n")
            f.write("\n")

            # Detail Section
            f.write("## Trade Detail\n\n")
            f.write("| ID | Symbol | Side | Entry Time | Entry Price | Exit Time | Exit Price | Lots | Net PnL |\n")
            f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")

            for trade in result.trades:
                entry_time = datetime.fromtimestamp(trade.entry_time, tz=timezone.utc).strftime('%Y-%m-%d %H:%M')
                exit_time = datetime.fromtimestamp(trade.exit_time, tz=timezone.utc).strftime('%Y-%m-%d %H:%M')
                f.write(f"| {trade.id[:8]} | {trade.symbol} | {trade.side} | {entry_time} | {trade.entry_price:.5f} | {exit_time} | {trade.exit_price:.5f} | {trade.lots} | {trade.net_pnl:.2f} |\n")

        return filepath

    def _generate_daily_charts(self, result: BacktestResult, candles: List[Candle]) -> List[str]:
        # Group candles by day (string YYYY-MM-DD)
        daily_candles: Dict[str, List[Candle]] = {}
        for c in candles:
            dt = datetime.fromtimestamp(c.time, tz=timezone.utc)
            date_str = dt.strftime('%Y-%m-%d')
            if date_str not in daily_candles:
                daily_candles[date_str] = []
            daily_candles[date_str].append(c)

        generated_files = []

        # Sort dates to process in order
        sorted_dates = sorted(daily_candles.keys())

        for date_str in sorted_dates:
            day_candles = daily_candles[date_str]
            if not day_candles:
                continue

            # Prepare Plot Data
            times = [datetime.fromtimestamp(c.time, tz=timezone.utc) for c in day_candles]
            opens = [c.open for c in day_candles]
            highs = [c.high for c in day_candles]
            lows = [c.low for c in day_candles]
            closes = [c.close for c in day_candles]

            # Plot
            fig, ax = plt.subplots(figsize=(12, 6))
            fig.suptitle(f"Chart - {date_str} ({len(day_candles)} candles)")

            # Draw Candles (Manual implementation for control)
            width = 0.6
            width2 = 0.1
            up_color = 'green'
            down_color = 'red'

            # Map time to integer index for plotting to avoid gaps
            indices = range(len(day_candles))

            for i in indices:
                open_p = opens[i]
                close_p = closes[i]
                high_p = highs[i]
                low_p = lows[i]

                color = up_color if close_p >= open_p else down_color

                # Wick
                ax.plot([i, i], [low_p, high_p], color='black', linewidth=1)
                # Body
                rect_height = abs(close_p - open_p)
                rect_bottom = min(open_p, close_p)
                # If doji (open==close), give it a small height so it's visible
                if rect_height == 0:
                    rect_height = (highs[i] - lows[i]) * 0.01 if (highs[i] - lows[i]) > 0 else 0.0001

                rect = plt.Rectangle((i - width/2, rect_bottom), width, rect_height, facecolor=color, edgecolor='black')
                ax.add_patch(rect)

            # --- Overlay Trades ---
            # We need to find trades that have an event (Entry or Exit) on this day.
            # And map their timestamps to the index 'i' (closest).

            day_start_ts = day_candles[0].time
            day_end_ts = day_candles[-1].time

            def get_index_for_time(ts: int) -> Optional[float]:
                # Binary search or simple loop? Simple loop is fine for 1440 candles max (1 min data)
                # We return float index. If exact match, return int. Else interpolate or closest.
                # Let's just find closest candle.
                if ts < day_start_ts or ts > day_end_ts:
                    return None

                # Find the candle with closest time
                closest_idx = 0
                min_diff = abs(ts - day_candles[0].time)

                for idx, c in enumerate(day_candles):
                    diff = abs(ts - c.time)
                    if diff < min_diff:
                        min_diff = diff
                        closest_idx = idx
                return closest_idx

            for trade in result.trades:
                entry_idx = get_index_for_time(trade.entry_time)
                exit_idx = get_index_for_time(trade.exit_time)

                # If entry happens today
                if entry_idx is not None:
                    # Plot Entry Marker
                    marker = '^' if trade.side == Side.BUY else 'v'
                    color = 'blue' if trade.side == Side.BUY else 'orange'
                    ax.scatter([entry_idx], [trade.entry_price], marker=marker, color=color, s=100, zorder=5, label='Entry' if 'Entry' not in ax.get_legend_handles_labels()[1] else "")

                # If exit happens today
                if exit_idx is not None:
                    # Plot Exit Marker
                    marker = 'X'
                    color = 'green' if trade.net_pnl > 0 else 'red'
                    ax.scatter([exit_idx], [trade.exit_price], marker=marker, color=color, s=100, zorder=5, label='Exit' if 'Exit' not in ax.get_legend_handles_labels()[1] else "")
                    # Annotate PnL
                    ax.text(exit_idx, trade.exit_price, f"{trade.net_pnl:.0f}", fontsize=8, verticalalignment='bottom')

                # Draw Line if both on this day
                if entry_idx is not None and exit_idx is not None:
                    ax.plot([entry_idx, exit_idx], [trade.entry_price, trade.exit_price], color='gray', linestyle='--', linewidth=1, alpha=0.7)

                # Draw Line if entry was before today but exit is today (Line coming from left)
                elif entry_idx is None and exit_idx is not None:
                     if trade.entry_time < day_start_ts:
                         # Draw from index 0 to exit
                         ax.plot([0, exit_idx], [trade.entry_price, trade.exit_price], color='gray', linestyle='--', linewidth=1, alpha=0.5)

                # Draw Line if entry is today but exit is later (Line going to right)
                elif entry_idx is not None and exit_idx is None:
                    if trade.exit_time > day_end_ts:
                        # Draw from entry to end
                        ax.plot([entry_idx, len(day_candles)-1], [trade.entry_price, trade.exit_price], color='gray', linestyle='--', linewidth=1, alpha=0.5)

            # Formatting
            ax.set_xlim(-1, len(day_candles))

            # Set X Ticks (every Nth candle to avoid crowding)
            step = max(1, len(day_candles) // 10)
            ax.set_xticks(range(0, len(day_candles), step))
            ax.set_xticklabels([times[i].strftime('%H:%M') for i in range(0, len(day_candles), step)], rotation=45)

            ax.grid(True, alpha=0.3)

            # Save
            filename = f"{date_str}.png"
            filepath = os.path.join(self.charts_dir, filename)
            plt.tight_layout()
            plt.savefig(filepath)
            plt.close(fig)

            generated_files.append(filepath)

        return generated_files
