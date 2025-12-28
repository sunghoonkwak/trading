"""
Named Pipe IPC module for WebSocket log communication between main process and viewer.
Works on Windows only using win32pipe.
"""
import win32pipe
import win32file
import pywintypes
import threading
import logging

PIPE_NAME = r'\\.\pipe\kis_websocket_log'
PIPE_BUFFER_SIZE = 65536

# Server side (main.py)
_pipe_handle = None
_pipe_connected = False
_pipe_lock = threading.Lock()


def create_pipe_server():
    """Create Named Pipe server. Call this from main.py at startup."""
    global _pipe_handle
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
    try:
        win32pipe.ConnectNamedPipe(_pipe_handle, None)
        _pipe_connected = True
        logging.info("[Pipe] Client connected")
        return True
    except pywintypes.error as e:
        logging.error(f"[Pipe] Client connection failed: {e}")
        return False


def send_log(message: str) -> bool:
    """Send log message through pipe. Non-blocking."""
    global _pipe_connected
    if not _pipe_connected or _pipe_handle is None:
        return False

    with _pipe_lock:
        try:
            data = (message + "\n").encode('utf-8')
            win32file.WriteFile(_pipe_handle, data)
            return True
        except pywintypes.error as e:
            logging.warning(f"[Pipe] Send failed: {e}")
            _pipe_connected = False
            return False


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


def receive_log(handle) -> str:
    """Receive log message from pipe. Blocking call."""
    try:
        result, data = win32file.ReadFile(handle, PIPE_BUFFER_SIZE)
        return data.decode('utf-8').strip()
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
