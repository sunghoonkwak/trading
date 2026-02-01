"""
Named Pipe IPC module for WebSocket log communication between main process and viewer.
Works on Windows (Named Pipes) and Linux (Unix Domain Sockets).
Uses async write queue to prevent blocking when Event Viewer is unresponsive.
"""
import sys
import threading
import logging
import queue
import time
import os

from enum import IntEnum

# Platform detection
IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import win32pipe
    import win32file
    import win32event
    import win32con
    import winerror
    import pywintypes
else:
    import socket

class PrintLevel(IntEnum):
    ERROR = 0
    INFO = 1
    DEBUG = 2
    MAX = 3

print_log_level = PrintLevel.INFO

def get_log_level():
    return print_log_level

# Windows Named Pipe
PIPE_NAME = r'\\.\pipe\kis_websocket_log'
# Linux Unix Domain Socket
SOCKET_PATH = '/tmp/kis_websocket_log.sock'

PIPE_BUFFER_SIZE = 65536
WRITE_QUEUE_SIZE = 1000  # Max queued messages before dropping
WRITE_TIMEOUT_MS = 500  # Milliseconds to wait for write before dropping
MAX_CONSECUTIVE_FAILURES = 10  # Reset pipe after this many consecutive write failures

# Server side (main.py)
_pipe_handle = None
_socket_server = None
_client_socket = None
_pipe_connected = False
_pipe_lock = threading.Lock()

# Async write queue
_write_queue = queue.Queue(maxsize=WRITE_QUEUE_SIZE)
_writer_thread = None
_writer_running = False
_last_write_warning = 0  # Timestamp of last warning to avoid spam
_consecutive_failures = 0  # Track consecutive write failures


def print_viewer(msg_type, level, log):
    """Log to file and send to separate terminal viewer via pipe."""
    # Always log to file using standard logging
    if level == PrintLevel.ERROR:
        logging.error(log)
    elif level == PrintLevel.INFO:
        logging.debug(log)
    elif level == PrintLevel.DEBUG:
        logging.debug(log)

    # Send to separate terminal viewer
    if level <= print_log_level:
        send_log(msg_type, log)


def create_pipe_server():
    """Create Named Pipe server (Windows) or Unix Domain Socket server (Linux)."""
    global _pipe_handle, _socket_server

    if IS_WINDOWS:
        if _pipe_handle is not None:
            return True
        try:
            _pipe_handle = win32pipe.CreateNamedPipe(
                PIPE_NAME,
                win32pipe.PIPE_ACCESS_OUTBOUND | win32file.FILE_FLAG_OVERLAPPED,
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
    else:
        # Linux: Unix Domain Socket
        if _socket_server is not None:
            return True
        try:
            # Remove existing socket file
            if os.path.exists(SOCKET_PATH):
                os.unlink(SOCKET_PATH)

            _socket_server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            _socket_server.bind(SOCKET_PATH)
            _socket_server.listen(1)
            _socket_server.setblocking(False)
            logging.info(f"[Pipe] Server created: {SOCKET_PATH}")
            return True
        except Exception as e:
            logging.error(f"[Pipe] Failed to create server: {e}")
            return False


def wait_for_client():
    """Wait for client to connect. Blocking call."""
    global _pipe_connected, _client_socket

    if IS_WINDOWS:
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
            if e.winerror == 535:  # ERROR_PIPE_CONNECTED
                _pipe_connected = True
                return True
            logging.error(f"[Pipe] Client connection failed: {e}")
            return False
    else:
        # Linux: Accept connection on Unix Domain Socket
        if _socket_server is None:
            return False
        if _pipe_connected and _client_socket:
            return True
        try:
            # Set blocking for accept
            _socket_server.setblocking(True)
            _client_socket, _ = _socket_server.accept()
            _pipe_connected = True
            logging.info("[Pipe] Client connected")
            return True
        except Exception as e:
            logging.error(f"[Pipe] Client connection failed: {e}")
            return False


def send_log(msg_type: str, message: str) -> bool:
    """Send log message through pipe. Non-blocking via queue."""
    global _last_write_warning
    if not _pipe_connected:
        return False

    if IS_WINDOWS and _pipe_handle is None:
        return False
    if not IS_WINDOWS and _client_socket is None:
        return False

    try:
        _write_queue.put_nowait((msg_type, message))
        return True
    except queue.Full:
        # Drop oldest messages to make room for new one
        dropped = 0
        while dropped < 100:
            try:
                _write_queue.get_nowait()
                dropped += 1
            except queue.Empty:
                break

        now = time.time()
        if now - _last_write_warning > 5.0:
            logging.warning(f"[Pipe] Queue full - dropped {dropped} old messages")
            _last_write_warning = now

        try:
            _write_queue.put_nowait((msg_type, message))
            return True
        except queue.Full:
            return False


def _do_write(msg_type: str, message: str) -> bool:
    """Actually write to pipe/socket."""
    global _pipe_connected, _client_socket

    if not _pipe_connected:
        return False

    with _pipe_lock:
        try:
            data = (msg_type + "|" + message + "\n").encode('utf-8')

            if IS_WINDOWS:
                if _pipe_handle is None:
                    return False
                overlapped = pywintypes.OVERLAPPED()
                overlapped.hEvent = win32event.CreateEvent(None, True, False, None)
                try:
                    err_code, _ = win32file.WriteFile(_pipe_handle, data, overlapped)
                    if err_code == 0:
                        win32file.CloseHandle(overlapped.hEvent)
                        return True
                    if err_code == winerror.ERROR_IO_PENDING:
                        result = win32event.WaitForSingleObject(overlapped.hEvent, WRITE_TIMEOUT_MS)
                        win32file.CloseHandle(overlapped.hEvent)
                        if result == win32event.WAIT_OBJECT_0:
                            return True
                        try:
                            win32file.CancelIo(_pipe_handle)
                        except:
                            pass
                        return False
                    win32file.CloseHandle(overlapped.hEvent)
                    return False
                except pywintypes.error as e:
                    try:
                        win32file.CloseHandle(overlapped.hEvent)
                    except:
                        pass
                    logging.warning(f"[Pipe] Write failed: {e}")
                    _pipe_connected = False
                    _schedule_pipe_reset()
                    return False
            else:
                # Linux: Write to Unix socket
                if _client_socket is None:
                    return False
                try:
                    _client_socket.sendall(data)
                    return True
                except (BrokenPipeError, ConnectionResetError, OSError) as e:
                    logging.warning(f"[Pipe] Write failed: {e}")
                    _pipe_connected = False
                    _client_socket = None
                    _schedule_pipe_reset()
                    return False
        except Exception as e:
            logging.error(f"[Pipe] Write error: {e}")
            return False


def _clear_queue():
    """Clear all pending messages from the write queue."""
    cleared = 0
    while True:
        try:
            _write_queue.get_nowait()
            cleared += 1
        except queue.Empty:
            break
    if cleared > 0:
        logging.info(f"[Pipe] Cleared {cleared} pending messages from queue")


def _writer_worker():
    """Background thread to write messages to pipe."""
    global _writer_running, _consecutive_failures
    while _writer_running:
        try:
            msg_type, message = _write_queue.get(timeout=0.5)
            success = _do_write(msg_type, message)

            if success:
                _consecutive_failures = 0
            else:
                _consecutive_failures += 1
                if _consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    logging.warning(
                        f"[Pipe] {_consecutive_failures} consecutive write failures, "
                        f"clearing queue ({_write_queue.qsize()} items) and resetting pipe"
                    )
                    _clear_queue()
                    _consecutive_failures = 0
                    _schedule_pipe_reset()
        except queue.Empty:
            continue
        except Exception as e:
            logging.error(f"[Pipe] Writer thread error: {e}")


def start_writer_thread():
    """Start the background writer thread."""
    global _writer_thread, _writer_running
    if _writer_thread is not None and _writer_thread.is_alive():
        return

    _writer_running = True
    _writer_thread = threading.Thread(target=_writer_worker, daemon=True, name="PipeWriter")
    _writer_thread.start()
    logging.info("[Pipe] Writer thread started")


def stop_writer_thread():
    """Stop the background writer thread."""
    global _writer_running
    _writer_running = False
    if _writer_thread is not None:
        _writer_thread.join(timeout=2.0)


_reset_scheduled = False


def _schedule_pipe_reset():
    """Schedule pipe server reset in background thread."""
    global _reset_scheduled
    if _reset_scheduled:
        return
    _reset_scheduled = True

    def reset_worker():
        global _reset_scheduled
        time.sleep(0.5)
        reset_pipe_server()
        _reset_scheduled = False

    reset_thread = threading.Thread(target=reset_worker, daemon=True)
    reset_thread.start()


def reset_pipe_server():
    """Close and recreate pipe server for new client connection."""
    global _pipe_handle, _pipe_connected, _socket_server, _client_socket
    logging.info("[Pipe] Resetting pipe server for reconnection...")

    if IS_WINDOWS:
        if _pipe_handle:
            try:
                win32pipe.DisconnectNamedPipe(_pipe_handle)
                win32file.CloseHandle(_pipe_handle)
            except:
                pass
            _pipe_handle = None
            _pipe_connected = False
    else:
        if _client_socket:
            try:
                _client_socket.close()
            except:
                pass
            _client_socket = None
        if _socket_server:
            try:
                _socket_server.close()
            except:
                pass
            _socket_server = None
        _pipe_connected = False

    if create_pipe_server():
        def wait_reconnect():
            if wait_for_client():
                logging.info("[Pipe] New client reconnected")
                start_writer_thread()
        reconnect_thread = threading.Thread(target=wait_reconnect, daemon=True)
        reconnect_thread.start()


def close_pipe_server():
    """Close pipe server."""
    global _pipe_handle, _pipe_connected, _socket_server, _client_socket

    if IS_WINDOWS:
        if _pipe_handle:
            try:
                win32file.CloseHandle(_pipe_handle)
            except:
                pass
            _pipe_handle = None
    else:
        if _client_socket:
            try:
                _client_socket.close()
            except:
                pass
            _client_socket = None
        if _socket_server:
            try:
                _socket_server.close()
            except:
                pass
            _socket_server = None
        if os.path.exists(SOCKET_PATH):
            try:
                os.unlink(SOCKET_PATH)
            except:
                pass
    _pipe_connected = False


def is_connected() -> bool:
    """Check if client is connected."""
    return _pipe_connected


# Client side (websocket_viewer.py)
def connect_pipe_client():
    """Connect to pipe server. Call this from websocket_viewer.py."""
    if IS_WINDOWS:
        try:
            handle = win32file.CreateFile(
                PIPE_NAME,
                win32file.GENERIC_READ,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None
            )
            logging.info("[Pipe] Connected to server")
            return handle
        except pywintypes.error as e:
            logging.error(f"[Pipe] Connection failed: {e}")
            return None
    else:
        try:
            client_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client_sock.connect(SOCKET_PATH)
            logging.info("[Pipe] Connected to server")
            return client_sock
        except Exception as e:
            logging.error(f"[Pipe] Connection failed: {e}")
            return None


# Receive buffer for incomplete messages
_receive_buffer = ""

def receive_log(handle) -> str:
    """Receive log message from pipe. Blocking call."""
    global _receive_buffer

    if "\n" in _receive_buffer:
        line, _receive_buffer = _receive_buffer.split("\n", 1)
        return line.strip()

    try:
        if IS_WINDOWS:
            result, data = win32file.ReadFile(handle, PIPE_BUFFER_SIZE)
            _receive_buffer += data.decode('utf-8')
        else:
            # Linux: Read from socket
            data = handle.recv(PIPE_BUFFER_SIZE)
            if not data:
                return None
            _receive_buffer += data.decode('utf-8')

        if "\n" in _receive_buffer:
            line, _receive_buffer = _receive_buffer.split("\n", 1)
            return line.strip()
        else:
            if _receive_buffer.strip():
                msg = _receive_buffer.strip()
                _receive_buffer = ""
                return msg
            return None
    except Exception as e:
        logging.error(f"[Pipe] Receive failed: {e}")
        return None


def close_pipe_client(handle):
    """Close pipe client."""
    if handle:
        try:
            if IS_WINDOWS:
                win32file.CloseHandle(handle)
            else:
                handle.close()
        except:
            pass
