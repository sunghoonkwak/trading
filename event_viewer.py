"""
Event Viewer - Real-time market data and order display using Textual TUI.
Runs in a separate terminal window with 3-panel layout:
- Top: Orders
- Middle: Latest quotes per ticker
- Bottom: Scrolling log dump (MKT only)
"""
import sys
import os
import time
import json
import subprocess
import logging
import threading
from collections import OrderedDict
from datetime import datetime

import win32event
import win32api
import pywintypes
import winerror

from textual.app import App, ComposeResult
from textual.containers import Vertical, ScrollableContainer
from textual.widgets import Static, RichLog
from textual.reactive import reactive

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kis.event_pipe as event_pipe

# Viewer process handle (used by spawn_viewer/close_viewer)
_viewer_process = None
_base_dir = os.path.dirname(os.path.abspath(__file__))
MUTEX_NAME = "StevenOpenAPITradingViewer"
_mutex_handle = None


def spawn_viewer():
    """Spawn the Event viewer in Windows Terminal."""
    global _viewer_process
    viewer_path = os.path.join(_base_dir, "event_viewer.py")
    try:
        _viewer_process = subprocess.Popen(
            ["wt", "-w", "0", "--size", "130,40", "nt", "--title", "Event Viewer",
             "python", viewer_path],
            cwd=_base_dir
        )
        logging.info("[System] Viewer terminal spawned")
        return True
    except Exception as e:
        logging.error(f"[System] Failed to spawn viewer: {e}")
        return False


def acquire_mutex():
    """Acquire named mutex to indicate viewer is running."""
    global _mutex_handle
    try:
        _mutex_handle = win32event.CreateMutex(None, True, MUTEX_NAME)
        if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
            pass
        return True
    except Exception as e:
        logging.error(f"[System] Failed to create mutex: {e}")
        return False


def is_running():
    """Check if viewer process is actually running using Mutex."""
    try:
        handle = win32event.OpenMutex(win32event.SYNCHRONIZE, False, MUTEX_NAME)
        if handle:
            win32api.CloseHandle(handle)
            return True
    except:
        pass
    return False


def close_viewer():
    """Close the viewer terminal if running."""
    global _viewer_process
    if _viewer_process is not None:
        try:
            _viewer_process.terminate()
            _viewer_process = None
            logging.info("[System] Viewer terminal closed")
        except:
            pass


def load_stock_config():
    """Load stock configuration for colorization."""
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_dir, "stock_configuration.json")
        if not os.path.exists(config_path):
            config_path = "stock_configuration.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


# Build ticker -> color lookup (loaded once)
_STOCK_CONFIG = load_stock_config()
_TICKER_COLORS = {}
for region in _STOCK_CONFIG.values():
    for stock in region:
        ticker = stock.get("ticker", "")
        color = stock.get("color", None)
        if ticker and color:
            _TICKER_COLORS[ticker] = color


def get_ticker_color(ticker: str) -> str:
    """Get Textual color markup for a ticker."""
    color = _TICKER_COLORS.get(ticker.strip())
    if color and len(color) == 3:
        r, g, b = color
        return f"rgb({r},{g},{b})"
    return None


class OrdersPanel(Static):
    """Panel displaying active orders."""

    orders_text = reactive("")

    def render(self) -> str:
        return self.orders_text or "[dim]No orders[/dim]"

    def watch_orders_text(self, new_value: str) -> None:
        """Called when orders_text changes - trigger refresh."""
        self.refresh(layout=True)


class QuotesPanel(Static):
    """Panel displaying latest quotes per ticker."""

    quotes_text = reactive("")

    def render(self) -> str:
        return self.quotes_text or "[dim]Waiting for quotes...[/dim]"

    def watch_quotes_text(self, new_value: str) -> None:
        """Called when quotes_text changes - trigger refresh."""
        self.refresh(layout=True)


class EventViewerApp(App):
    """Main Textual TUI application for Event Viewer."""

    BINDINGS = [("a", "toggle_auto_scroll", "Toggle Auto-Scroll")]

    CSS = """
    Screen {
        layout: vertical;
        background: $surface;
    }

    #orders-panel {
        height: auto;
        min-height: 3;
        max-height: 25;
        border: solid $primary;
        padding: 0 1;
    }

    #quotes-panel {
        height: auto;
        min-height: 3;
        max-height: 25;
        border: solid $secondary;
        padding: 0 1;
    }

    #log-panel {
        height: 1fr;
        border: solid $accent;
        padding: 0 1;
    }
    """

    def __init__(self):
        super().__init__()
        self.orders = OrderedDict()  # order_id -> order_info
        self.latest_quotes = OrderedDict()  # ticker -> quote_info
        self.pipe_handle = None
        self.running = True

    def compose(self) -> ComposeResult:
        yield OrdersPanel(id="orders-panel")
        yield QuotesPanel(id="quotes-panel")
        yield RichLog(id="log-panel", highlight=False, markup=True, auto_scroll=True, max_lines=1000)

    def action_toggle_auto_scroll(self) -> None:
        """Toggle auto-scroll for log panel."""
        log_panel = self.query_one("#log-panel", RichLog)
        log_panel.auto_scroll = not log_panel.auto_scroll

    def on_mount(self) -> None:
        """Start pipe connection when app mounts."""
        self.query_one("#log-panel", RichLog).write("[bold cyan]Event Viewer Started[/bold cyan]")
        self.query_one("#log-panel", RichLog).write(f"Connecting to pipe: {event_pipe.PIPE_NAME}")

        # Start pipe reading thread
        self.pipe_thread = threading.Thread(target=self._pipe_reader, daemon=True)
        self.pipe_thread.start()

    def _pipe_reader(self):
        """Background thread to read from pipe."""
        retry_count = 0
        max_retries = 30

        while self.pipe_handle is None and retry_count < max_retries and self.running:
            self.pipe_handle = event_pipe.connect_pipe_client()
            if self.pipe_handle is None:
                retry_count += 1
                self.call_from_thread(
                    self._log_message,
                    f"[yellow]Waiting for main.py... ({retry_count}/{max_retries})[/yellow]"
                )
                time.sleep(1)

        if self.pipe_handle is None:
            self.call_from_thread(
                self._log_message,
                "[red bold]Failed to connect to main.py. Exiting.[/red bold]"
            )
            return

        self.call_from_thread(self._log_message, "[green]Connected to main.py![/green]")

        while self.running:
            log = event_pipe.receive_log(self.pipe_handle)
            if log is None:
                self.call_from_thread(
                    self._log_message,
                    "[red]Main program closed. Exiting...[/red]"
                )
                self.call_from_thread(self.exit)
                break

            self.call_from_thread(self._process_message, log)

    def _log_message(self, message: str):
        """Add message to log panel."""
        log_panel = self.query_one("#log-panel", RichLog)
        log_panel.write(message)

    def _process_message(self, raw_message: str):
        """Process incoming pipe message and route to correct panel.

        Message formats:
        - MKT|{time}|MKT|{name}|{ticker}|Bid:...|Last:...|Diff:...|Ask:...
        - ODR|{ticker}|{name}|{side}|{qty}|{price}|{state}|{order_id}
        - CLR|ORDERS - clear all orders
        - SYS|{message} - system message
        """
        if "|" not in raw_message:
            self._log_message(raw_message)
            return

        # First part is the message type prefix added by event_pipe.send_log
        parts = raw_message.split("|", 1)
        msg_type = parts[0].strip()
        content = parts[1] if len(parts) > 1 else ""

        if msg_type == "ODR":
            self._handle_order_message(content)
            # Don't show ODR in log dump
        elif msg_type == "MKT":
            colored_content = self._handle_market_message(content)
            # Show MKT in log dump
            self._log_message(f"{colored_content}")
        elif msg_type == "SYS":
            # System messages (PINGPONG, errors, etc.) - show in red
            self._log_message(f"[red]{content}[/red]")
        elif msg_type == "CLR":
            # Clear orders
            if content.strip() == "ORDERS":
                self.orders.clear()
                self._update_orders_panel()
        else:
            # Unknown type
            self._log_message(f"[dim]{raw_message}[/dim]")

    def _handle_order_message(self, content: str):
        """Handle order status message.

        Format: ticker|name|side|qty|price|state|order_id
        Or for remove: REMOVED|order_id
        """
        parts = content.split("|")

        # Handle REMOVED message
        if len(parts) >= 2 and parts[0].strip() == "REMOVED":
            order_id = parts[1].strip()
            if order_id in self.orders:
                del self.orders[order_id]
                self._update_orders_panel()
            return

        # Normal order update: name|ticker|side|qty|price|state|order_id
        if len(parts) >= 6:
            name = parts[0].strip()
            ticker = parts[1].strip()
            side = parts[2].strip()
            qty = parts[3].strip()
            price = parts[4].strip()
            state = parts[5].strip()
            order_id = parts[6].strip() if len(parts) > 6 else f"{ticker}_{time.time()}"

            self.orders[order_id] = {
                "time": datetime.now().strftime("%H:%M:%S"),
                "ticker": ticker,
                "name": name,
                "side": side,
                "qty": qty,
                "price": price,
                "state": state,
            }
            # Keep only last 20 orders
            while len(self.orders) > 20:
                self.orders.popitem(last=False)

            self._update_orders_panel()

    def _handle_market_message(self, content: str) -> str:
        """Handle market data message.

        Format: {time} {name}|{ticker}|Bid:...|Last:...|Diff:...|Ask:...
        Returns: Colorized content string
        """
        parts = content.split("|")

        # New format: "time name|ticker|Bid:...|..."
        # parts[0] = "time name", parts[1] = ticker
        ticker = None
        if len(parts) >= 2:
            ticker = parts[1].strip()

        colored_content = content
        if ticker:
            # Clean up ticker prefix if needed
            if len(ticker) > 6 and ticker[:4] in ["DNAS", "DNYS", "DAMS"]:
                ticker = ticker[4:]

            # Apply color to ticker
            t_color = get_ticker_color(ticker)
            if t_color:
                parts[1] = f"[{t_color}]{parts[1]}[/{t_color}]"

            # Process other parts for coloring (Last, Diff)
            for i, part in enumerate(parts):
                stripped_part = part.lstrip()
                if stripped_part.startswith("Last:"):
                    try:
                        label, value = part.split(":", 1)
                        # User requested "bright color" matching input
                        parts[i] = f"{label}:[bold #ffff00]{value}[/bold #ffff00]"
                    except ValueError:
                        pass

                elif stripped_part.startswith("Diff:"):
                    try:
                        label, value = part.split(":", 1)
                        # Check for minus sign in the value part to determine color
                        if "-" in value:
                            color = "#ff0000" # Red
                        else:
                            color = "#00ffff" # Cyan
                        parts[i] = f"{label}:[{color}]{value}[/{color}]"
                    except ValueError:
                        pass

            colored_content = "|".join(parts)

            self.latest_quotes[ticker] = colored_content
            # Keep only last 20 tickers
            while len(self.latest_quotes) > 20:
                self.latest_quotes.popitem(last=False)

            self._update_quotes_panel()

        return colored_content


    def _update_orders_panel(self):
        """Update orders panel display."""
        lines = []
        for order_id, info in reversed(list(self.orders.items())):
            side_upper = info["side"].upper()
            if "BUY" in side_upper:
                side_color = "green"
            elif "SELL" in side_upper or "SEL" in side_upper:
                side_color = "red"
            else:
                side_color = "yellow"

            name = info.get("name", "")[:20]
            order_time = info.get("time", "")
            ticker = info['ticker']
            ticker_color = get_ticker_color(ticker)
            ticker_disp = f"{ticker:6}"
            if ticker_color:
                ticker_disp = f"[{ticker_color}]{ticker_disp}[/{ticker_color}]"

            lines.append(
                f"{order_time} {name:20}|{ticker_disp}| "
                f"[{side_color}]{info['side']:8}[/{side_color}] "
                f"prc: [cyan]{info['price']:>10}[/cyan] qty: [cyan]{info['qty']:>5}[/cyan]"
            )

        orders_panel = self.query_one("#orders-panel", OrdersPanel)
        orders_panel.orders_text = "\n".join(lines) if lines else ""

    def _update_quotes_panel(self):
        """Update quotes panel display."""
        lines = []
        for ticker, content in reversed(list(self.latest_quotes.items())):
            # Format: time|name|ticker|Bid:...|Last:...|Diff:...|Ask:...
            lines.append(f"{content}")

        quotes_panel = self.query_one("#quotes-panel", QuotesPanel)
        quotes_panel.quotes_text = "\n".join(lines) if lines else ""

    def on_unmount(self):
        """Cleanup on app exit."""
        self.running = False
        if self.pipe_handle:
            event_pipe.close_pipe_client(self.pipe_handle)


def main():
    """Main entry point for event viewer."""
    acquire_mutex()
    app = EventViewerApp()
    app.run()


if __name__ == "__main__":
    main()
