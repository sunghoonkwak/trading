"""
Named Pipe IPC module for WebSocket log communication between main process and viewer.
Works on Windows only using win32pipe.
"""
import win32pipe
import win32file
import pywintypes
import threading
import logging

from enum import IntEnum

class PrintLevel(IntEnum):
    ERROR = 0
    INFO = 1
    DEBUG = 2
    MAX = 3

print_log_level = PrintLevel.INFO

def get_log_level():
    return print_log_level

PIPE_NAME = r'\\.\pipe\kis_websocket_log'
PIPE_BUFFER_SIZE = 65536

# Server side (main.py)
_pipe_handle = None
_pipe_connected = False
_pipe_lock = threading.Lock()


def print_viewer(msg_type, level, log):
    """Log to file and send to separate terminal viewer via pipe."""
    # Always log to file using standard logging
    if level == PrintLevel.ERROR:
        logging.error(log)
    elif level == PrintLevel.INFO:
        logging.info(log)
    elif level == PrintLevel.DEBUG:
        logging.debug(log)

    # Send to separate terminal viewer
    if level <= print_log_level:
        send_log(msg_type, log)

def create_pipe_server():
    """Create Named Pipe server. Call this from main.py at startup."""
    global _pipe_handle
    if _pipe_handle is not None:
        return True

    try:
        _pipe_handle = win32pipe.CreateNamedPipe(
            PIPE_NAME,
            win32pipe.PIPE_ACCESS_OUTBOUND,
            win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_WAIT,
            1,  # Max instances
            PIPE_BUFFER_SIZE,
            PIPE_BUFFER_SIZE,
            0,  # Default timeout
            None  # Security attributes
        )
        logging.info(f"[Pipe] Server created: {PIPE_NAME}")
        return True
    except pywintypes.error as e:
        logging.error(f"[Pipe] Failed to create server: {e}")
        return False


def wait_for_client():
    """Wait for client to connect. Blocking call."""
    global _pipe_connected
    if _pipe_handle is None:
        return False

    if _pipe_connected:
        return True

    try:
        win32pipe.ConnectNamedPipe(_pipe_handle, None)
        _pipe_connected = True
        logging.info("[Pipe] Client connected")
        return True
    except pywintypes.error as e:
        if e.winerror == 535: # ERROR_PIPE_CONNECTED
            _pipe_connected = True
            return True
        logging.error(f"[Pipe] Client connection failed: {e}")
        return False


def send_log(msg_type: str, message: str) -> bool:
    """Send log message through pipe. Non-blocking.

    Args:
        msg_type: Message type prefix (MKT for market data, ODR for orders)
        message: Log message content
    """
    global _pipe_connected
    if not _pipe_connected or _pipe_handle is None:
        return False

    with _pipe_lock:
        try:
            data = (msg_type + "|" + message + "\n").encode('utf-8')
            win32file.WriteFile(_pipe_handle, data)
            return True
        except pywintypes.error as e:
            logging.warning(f"[Pipe] Send failed: {e}")
            _pipe_connected = False
            # Trigger pipe reset for reconnection
            _schedule_pipe_reset()
            return False


_reset_scheduled = False


def _schedule_pipe_reset():
    """Schedule pipe server reset in background thread."""
    global _reset_scheduled
    if _reset_scheduled:
        return
    _reset_scheduled = True

    def reset_worker():
        global _reset_scheduled
        import time
        time.sleep(0.5)  # Brief delay before reset
        reset_pipe_server()
        _reset_scheduled = False

    reset_thread = threading.Thread(target=reset_worker, daemon=True)
    reset_thread.start()


def reset_pipe_server():
    """Close and recreate pipe server for new client connection."""
    global _pipe_handle, _pipe_connected
    logging.info("[Pipe] Resetting pipe server for reconnection...")

    # Close existing pipe
    if _pipe_handle:
        try:
            win32pipe.DisconnectNamedPipe(_pipe_handle)
            win32file.CloseHandle(_pipe_handle)
        except:
            pass
        _pipe_handle = None
        _pipe_connected = False

    # Recreate pipe server
    if create_pipe_server():
        # Wait for new client in background
        def wait_reconnect():
            if wait_for_client():
                logging.info("[Pipe] New client reconnected")
        reconnect_thread = threading.Thread(target=wait_reconnect, daemon=True)
        reconnect_thread.start()


def close_pipe_server():
    """Close pipe server."""
    global _pipe_handle, _pipe_connected
    if _pipe_handle:
        try:
            win32file.CloseHandle(_pipe_handle)
        except:
            pass
        _pipe_handle = None
        _pipe_connected = False


def is_connected() -> bool:
    """Check if client is connected."""
    return _pipe_connected


# Client side (websocket_viewer.py)
def connect_pipe_client():
    """Connect to pipe server. Call this from websocket_viewer.py."""
    try:
        handle = win32file.CreateFile(
            PIPE_NAME,
            win32file.GENERIC_READ,
            0,  # No sharing
            None,  # Security
            win32file.OPEN_EXISTING,
            0,  # Flags
            None
        )
        logging.info("[Pipe] Connected to server")
        return handle
    except pywintypes.error as e:
        logging.error(f"[Pipe] Connection failed: {e}")
        return None


# Receive buffer for incomplete messages
_receive_buffer = ""

def receive_log(handle) -> str:
    """Receive log message from pipe. Blocking call.

    Returns one message at a time, buffering partial messages.
    """
    global _receive_buffer

    # If we have buffered messages, return the next one
    if "\n" in _receive_buffer:
        line, _receive_buffer = _receive_buffer.split("\n", 1)
        return line.strip()

    # Read more data from pipe
    try:
        result, data = win32file.ReadFile(handle, PIPE_BUFFER_SIZE)
        _receive_buffer += data.decode('utf-8')

        # Check if we have complete message(s)
        if "\n" in _receive_buffer:
            line, _receive_buffer = _receive_buffer.split("\n", 1)
            return line.strip()
        else:
            # Incomplete message, return what we have
            if _receive_buffer.strip():
                msg = _receive_buffer.strip()
                _receive_buffer = ""
                return msg
            return None
    except pywintypes.error as e:
        logging.error(f"[Pipe] Receive failed: {e}")
        return None


def close_pipe_client(handle):
    """Close pipe client."""
    if handle:
        try:
            win32file.CloseHandle(handle)
        except:
            pass
