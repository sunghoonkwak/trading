"""
This module centralizes the main interactive menu logic.
It coordinates between the different handlers in the menu package and the display module.
"""
import os
import display
from display import render_ui, input_at, prepare_exit, PrintLevel, print_log
import kis_api.kis_auth as ka

# Centralized debug toggle for all menu handlers and KIS API interactions
MENU_DEBUG = False

def menu():
    """Main keyboard interaction loop."""
    # Lazy imports to avoid circular dependency with handlers importing MENU_DEBUG
    from .handle_account_info import handle_account_info
    from .handle_place_order import handle_place_order
    from .handle_manage_orders import handle_manage_orders

    os.system('cls' if os.name == 'nt' else 'clear')
    if MENU_DEBUG:
        ka._DEBUG = True
        print_log(PrintLevel.DEBUG, "[Menu] Debug mode (ka._DEBUG) enabled via MENU_DEBUG flag.")
    render_ui(full_refresh=True)

    while True:
        render_ui(full_refresh=True)
        choice = input_at(10, 2, "Enter Choice: ").strip()

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
            display.clear_order_logs()
        elif choice.lower() == 'q':
            prepare_exit()
            print("Exiting...")
            os._exit(0)
        else:
            pass
