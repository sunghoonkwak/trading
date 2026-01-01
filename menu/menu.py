"""
This module centralizes the main interactive menu logic.
It coordinates between the different handlers in the menu package and the display module.
"""
import os
import display
from display import render_ui, input_at, prepare_exit, PrintLevel, print_log, process_pending_alerts, start_alert_processor
import kis_api.kis_auth as ka

# Centralized debug toggle for all menu handlers and KIS API interactions
MENU_DEBUG = False

def menu():
    """Main keyboard interaction loop."""
    # Lazy imports to avoid circular dependency with handlers importing MENU_DEBUG
    from .handle_account_info import handle_account_info
    from .handle_place_order import handle_place_order
    from .handle_manage_orders import handle_manage_orders, sync_open_orders
    from .raoeo.raoeo import raoeo_menu
    import main  # For spawn_viewer

    os.system('cls' if os.name == 'nt' else 'clear')
    if MENU_DEBUG:
        ka._DEBUG = True
        print_log(PrintLevel.DEBUG, "[Menu] Debug mode (ka._DEBUG) enabled via MENU_DEBUG flag.")

    # Fetch initial orders on startup
    render_ui(full_refresh=True)
    sync_open_orders()
    render_ui(full_refresh=True)

    # Start background alert processor for real-time updates
    start_alert_processor()

    while True:
        process_pending_alerts()  # Handle alerts from background threads (e.g., Telegram)
        render_ui(full_refresh=True)
        choice = input_at(13, 2, "Enter Choice: ").strip()  # Row 13 between separators

        if choice == '1':
            handle_account_info()
        elif choice == '2':
            handle_place_order()
        elif choice == '3':
            handle_manage_orders()
        elif choice == '0':
            if display.print_log_level == PrintLevel.INFO:
                display.print_log_level = PrintLevel.DEBUG
            elif display.print_log_level == PrintLevel.DEBUG:
                display.print_log_level = PrintLevel.ERROR
            else:
                display.print_log_level = PrintLevel.INFO
            print_log(PrintLevel.ERROR, f"Log Level Changed to: {display.print_log_level.name}")
        elif choice.lower() == 'c':
            from .handle_manage_orders import sync_open_orders
            sync_open_orders()
        elif choice.lower() == 'v':
            from event_viewer import event_pipe
            if event_pipe.is_connected():
                display.add_alert("Viewer is already running!", "INFO")
            else:
                main.spawn_viewer()
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
            main.close_viewer()  # Close viewer terminal before exit
            shutdown_telegram()  # Send final notification
            prepare_exit()
            print("Exiting...")
            os._exit(0)
        else:
            pass
