"""
This module centralizes the main interactive menu logic.
It coordinates between the different handlers in the menu package and the display module.
"""
import os
import display
from display import render_ui, input_at, prepare_exit, process_pending_alerts, start_alert_processor
from kis.event_pipe import PrintLevel
from kis.kis_api import kis_auth as ka

# Centralized debug toggle for all menu handlers and KIS API interactions
MENU_DEBUG = False

def menu():
    """Main keyboard interaction loop."""
    # Lazy imports to avoid circular dependency with handlers importing MENU_DEBUG
    from .handle_account_info import handle_account_info
    from .handle_place_order import handle_place_order
    from .handle_manage_orders import handle_manage_orders, sync_open_orders
    from .raoeo.raoeo import raoeo_menu
    from event_viewer import spawn_viewer, close_viewer

    os.system('cls' if os.name == 'nt' else 'clear')
    if MENU_DEBUG:
        ka._DEBUG = True
        display.add_alert("[Menu] Debug mode (ka._DEBUG) enabled via MENU_DEBUG flag.", "INFO")

    # Fetch initial orders on startup
    render_ui(full_refresh=True)
    sync_open_orders()
    render_ui(full_refresh=True)

    # Start background alert processor for real-time updates
    start_alert_processor()

    while True:
        process_pending_alerts()  # Handle alerts from background threads (e.g., Telegram)
        render_ui(full_refresh=True)
        choice = input_at(12, 2, "Enter Choice: ").strip()  # Row 12 between separators

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
            display.add_alert(f"Log Level Changed to: {event_pipe.print_log_level.name}", "INFO")
        elif choice.lower() == 'c':
            from .handle_manage_orders import sync_open_orders
            sync_open_orders()
        elif choice.lower() == 'v':
            from kis import event_pipe
            if event_pipe.is_connected():
                display.add_alert("Viewer is already running!", "INFO")
            else:
                spawn_viewer()
                display.add_alert("Viewer terminal launched!", "SUCCESS")
        elif choice.lower() == 'r':
            raoeo_menu()
        elif choice.lower() == 'p':
            from menu.portfolio import portfolio
            portfolio.portfolio_menu()
        elif choice.lower() == 'q':
            import trading_state
            from telegram_bot.telegram_bot import shutdown_telegram
            trading_state.stop_periodic_save()  # Save stock data before exit
            close_viewer()  # Close viewer terminal before exit
            shutdown_telegram()  # Send final notification
            prepare_exit()
            print("Exiting...")
            os._exit(0)
        else:
            pass
