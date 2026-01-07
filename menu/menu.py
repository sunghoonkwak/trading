"""
This module centralizes the main interactive menu logic.
Scroll-based terminal output version.
"""
import os
import display
from display import add_alert
from kis.event_pipe import PrintLevel
from kis.kis_api import kis_auth as ka

# Centralized debug toggle
MENU_DEBUG = False

# ANSI Color codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
CYAN = "\033[96m"

MENU_TEXT = """
============================================================
 KIS Real-time System - Trading Menu
============================================================
 1. Account Info (Balance & Portfolio)
 2. Place Order (Buy/Sell)
 3. Manage Open Orders (Correct/Cancel)
 r. RAOEO Strategy
 p. Portfolio
------------------------------------------------------------
 0. Toggle Log Level    v. Open Event Viewer
 c. Clear & Sync        q. Back to Super Menu
"""


def menu():
    """Main keyboard interaction loop."""
    from .handle_account_info import handle_account_info
    from .handle_place_order import handle_place_order
    from .handle_manage_orders import handle_manage_orders, sync_open_orders
    from .raoeo.raoeo import raoeo_menu
    from event_viewer import spawn_viewer, close_viewer, is_running

    if MENU_DEBUG:
        ka._DEBUG = True
        add_alert("[Menu] Debug mode enabled", "INFO")

    # Fetch initial orders on startup
    sync_open_orders()

    while True:
        print(MENU_TEXT)

        try:
            choice = input("Enter Choice: ").strip()
        except KeyboardInterrupt:
            add_alert("[Menu] Keyboard interrupt", "INFO")
            break
        except EOFError:
            break

        if choice == '1':
            handle_account_info()
        elif choice == '2':
            handle_place_order()
        elif choice == '3':
            handle_manage_orders()
        elif choice == '0':
            from kis import event_pipe
            if event_pipe.print_log_level == PrintLevel.INFO:
                event_pipe.print_log_level = PrintLevel.DEBUG
            elif event_pipe.print_log_level == PrintLevel.DEBUG:
                event_pipe.print_log_level = PrintLevel.ERROR
            else:
                event_pipe.print_log_level = PrintLevel.INFO
            add_alert(f"Log Level Changed to: {event_pipe.print_log_level.name}", "INFO")
        elif choice.lower() == 'c':
            from display import clear_quotes
            clear_quotes()
            sync_open_orders()
        elif choice.lower() == 'v':
            from kis import event_pipe

            if is_running():
                add_alert("[SYS] Viewer is already running!", "INFO")
            else:
                if event_pipe.is_connected():
                    event_pipe.reset_pipe_server()
                spawn_viewer()
                add_alert("[SYS] Viewer terminal launched!", "SUCCESS")
        elif choice.lower() == 'r':
            raoeo_menu()
        elif choice.lower() == 'p':
            from menu.portfolio import portfolio
            portfolio.portfolio_menu()
        elif choice.lower() == 'q':
            # Return to super menu instead of exit
            add_alert("[Menu] Returning to Super Menu...", "INFO")
            break
        else:
            pass


if __name__ == "__main__":
    menu()
