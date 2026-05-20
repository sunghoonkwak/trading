"""
Unix domain socket IPC module for WebSocket log communication between main process and viewer.
Uses async write queue to prevent blocking when Event Viewer is unresponsive.
"""
import threading
import logging
import queue
import time
import os
import socket


# Linux Unix Domain Socket
SOCKET_PATH = '/tmp/kis_websocket_log.sock'

PIPE_BUFFER_SIZE = 65536
WRITE_QUEUE_SIZE = 1000  # Max queued messages before dropping
MAX_CONSECUTIVE_FAILURES = 10  # Reset pipe after this many consecutive write failures

# Server side (main.py)
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

# Web broadcast callback (for web_server.py)
_web_broadcast_callback = None


def set_web_broadcast_callback(callback):
    """Set callback function for web broadcast. Called by web_server.py."""
    global _web_broadcast_callback
    _web_broadcast_callback = callback
    logging.info("[Pipe] Web broadcast callback registered")


def print_viewer(msg_type, level, log, time_str=None):
    """Log to file and send to separate terminal viewer via pipe."""
    # Always log to file using standard logging
    if level == "ERROR":
        logging.error(log)
    else:
        # INFO and DEBUG map to logging.debug
        logging.debug(log)

    # Send to separate terminal viewer (only INFO/ERROR)
    if level in ["INFO", "ERROR"]:
        send_log(msg_type, log, time_str)


def create_pipe_server():
    """Create Unix Domain Socket server."""
    global _socket_server

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


def send_log(msg_type: str, message: str, time_str: str = None) -> bool:
    """Send log message through socket. Non-blocking via queue."""
    global _last_write_warning

    # Always try web broadcast first (works even without pipe connection)
    if _web_broadcast_callback:
        try:
            _web_broadcast_callback(msg_type, message, time_str)
        except Exception as e:
            logging.debug(f"[Pipe] Web broadcast failed: {e}")

    if not _pipe_connected:
        return False

    if _client_socket is None:
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
    """Actually write to socket."""
    global _pipe_connected, _client_socket

    if not _pipe_connected:
        return False

    with _pipe_lock:
        try:
            data = (msg_type + "|" + message + "\n").encode('utf-8')

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
    """Background thread to write messages to socket."""
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
    """Close and recreate socket server for new client connection."""
    global _pipe_connected, _socket_server, _client_socket
    logging.info("[Pipe] Resetting pipe server for reconnection...")

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
    """Close socket server."""
    global _pipe_connected, _socket_server, _client_socket

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
    """Connect to socket server. Call this from websocket_viewer.py."""
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
    """Receive log message from socket. Blocking call."""
    global _receive_buffer

    if "\n" in _receive_buffer:
        line, _receive_buffer = _receive_buffer.split("\n", 1)
        return line.strip()

    try:
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
    """Close socket client."""
    if handle:
        try:
            handle.close()
        except:
            pass
