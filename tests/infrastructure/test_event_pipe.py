"""Characterization tests for the event-pipe infrastructure adapter."""

import queue
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from infrastructure import event_pipe


class FakeSocket:
    def __init__(self, recv_chunks=()):
        self.recv_chunks = list(recv_chunks)
        self.sent = []
        self.closed = False
        self.blocking = None
        self.bound = None
        self.listen_backlog = None
        self.accepted = None
        self.connected = None

    def bind(self, path):
        self.bound = path

    def listen(self, backlog):
        self.listen_backlog = backlog

    def setblocking(self, value):
        self.blocking = value

    def accept(self):
        return self.accepted, None

    def connect(self, path):
        self.connected = path

    def sendall(self, data):
        self.sent.append(data)

    def recv(self, _size):
        if not self.recv_chunks:
            return b""
        chunk = self.recv_chunks.pop(0)
        if isinstance(chunk, Exception):
            raise chunk
        return chunk

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def reset_event_pipe(monkeypatch):
    event_pipe.stop_writer_thread()
    monkeypatch.setattr(event_pipe, "_socket_server", None)
    monkeypatch.setattr(event_pipe, "_client_socket", None)
    monkeypatch.setattr(event_pipe, "_pipe_connected", False)
    monkeypatch.setattr(event_pipe, "_writer_thread", None)
    monkeypatch.setattr(event_pipe, "_writer_running", False)
    monkeypatch.setattr(event_pipe, "_web_broadcast_callback", None)
    monkeypatch.setattr(event_pipe, "_last_write_warning", 0.0)
    monkeypatch.setattr(event_pipe, "_consecutive_failures", 0)
    monkeypatch.setattr(event_pipe, "_reset_scheduled", False)
    monkeypatch.setattr(event_pipe, "_receive_buffer", "")
    monkeypatch.setattr(event_pipe, "_write_queue", queue.Queue(maxsize=1000))
    yield
    event_pipe.stop_writer_thread()


def test_print_viewer_logs_and_forwards_visible_levels(monkeypatch):
    sent = []
    monkeypatch.setattr(event_pipe, "send_log", lambda *args: sent.append(args))
    error = Mock()
    debug = Mock()
    monkeypatch.setattr(event_pipe.logging, "error", error)
    monkeypatch.setattr(event_pipe.logging, "debug", debug)

    event_pipe.print_viewer("ALT", "ERROR", "broken", "now")
    event_pipe.print_viewer("DBG", "DEBUG", "detail")

    error.assert_called_once_with("broken")
    debug.assert_called_once_with("detail")
    assert sent == [("ALT", "broken", "now")]


def test_send_log_broadcasts_even_when_pipe_is_disconnected():
    broadcasts = []
    event_pipe.set_web_broadcast_callback(
        lambda *args: broadcasts.append(args),
    )

    assert event_pipe.send_log("INFO", "hello", "10:00") is False
    assert broadcasts == [("INFO", "hello", "10:00")]


def test_send_log_ignores_broadcast_error_and_queues_message(monkeypatch):
    def fail_broadcast(*_args):
        raise RuntimeError("viewer gone")

    event_pipe.set_web_broadcast_callback(fail_broadcast)
    monkeypatch.setattr(event_pipe, "_pipe_connected", True)
    monkeypatch.setattr(event_pipe, "_client_socket", FakeSocket())

    assert event_pipe.send_log("INFO", "hello") is True
    assert event_pipe._write_queue.get_nowait() == ("INFO", "hello")


def test_send_log_drops_old_messages_when_queue_is_full(monkeypatch):
    small_queue = queue.Queue(maxsize=2)
    small_queue.put_nowait(("OLD", "one"))
    small_queue.put_nowait(("OLD", "two"))
    monkeypatch.setattr(event_pipe, "_write_queue", small_queue)
    monkeypatch.setattr(event_pipe, "_pipe_connected", True)
    monkeypatch.setattr(event_pipe, "_client_socket", FakeSocket())
    monkeypatch.setattr(event_pipe.time, "time", lambda: 10.0)

    assert event_pipe.send_log("NEW", "three") is True
    assert small_queue.get_nowait() == ("NEW", "three")
    assert event_pipe._last_write_warning == 10.0


def test_do_write_serializes_message(monkeypatch):
    client = FakeSocket()
    monkeypatch.setattr(event_pipe, "_pipe_connected", True)
    monkeypatch.setattr(event_pipe, "_client_socket", client)

    assert event_pipe._do_write("ODR", "체결") is True
    assert client.sent == ["ODR|체결\n".encode()]


def test_do_write_disconnects_and_schedules_reset_on_socket_error(monkeypatch):
    client = FakeSocket()
    client.sendall = Mock(side_effect=BrokenPipeError("closed"))
    reset = Mock()
    monkeypatch.setattr(event_pipe, "_pipe_connected", True)
    monkeypatch.setattr(event_pipe, "_client_socket", client)
    monkeypatch.setattr(event_pipe, "_schedule_pipe_reset", reset)

    assert event_pipe._do_write("INFO", "hello") is False
    assert event_pipe.is_connected() is False
    assert event_pipe._client_socket is None
    reset.assert_called_once_with()


def test_clear_queue_removes_every_pending_message(monkeypatch):
    pending = queue.Queue()
    pending.put(("A", "one"))
    pending.put(("B", "two"))
    monkeypatch.setattr(event_pipe, "_write_queue", pending)

    event_pipe._clear_queue()

    assert pending.empty()


def test_create_server_configures_nonblocking_unix_socket(monkeypatch):
    server = FakeSocket()
    monkeypatch.setattr(event_pipe.socket, "socket", lambda *_args: server)
    monkeypatch.setattr(event_pipe.os, "unlink", Mock(side_effect=FileNotFoundError))

    assert event_pipe.create_pipe_server() is True
    assert server.bound == event_pipe.SOCKET_PATH
    assert server.listen_backlog == 1
    assert server.blocking is False
    assert event_pipe.create_pipe_server() is True


def test_create_server_returns_false_when_socket_setup_fails(monkeypatch):
    monkeypatch.setattr(
        event_pipe.socket,
        "socket",
        Mock(side_effect=OSError("unavailable")),
    )

    assert event_pipe.create_pipe_server() is False


def test_wait_for_client_accepts_once(monkeypatch):
    client = FakeSocket()
    server = FakeSocket()
    server.accepted = client
    monkeypatch.setattr(event_pipe, "_socket_server", server)

    assert event_pipe.wait_for_client() is True
    assert event_pipe.wait_for_client() is True
    assert server.blocking is True
    assert event_pipe._client_socket is client
    assert event_pipe.is_connected() is True


def test_wait_for_client_requires_server_and_handles_accept_error(monkeypatch):
    assert event_pipe.wait_for_client() is False

    server = FakeSocket()
    server.accept = Mock(side_effect=OSError("failed"))
    monkeypatch.setattr(event_pipe, "_socket_server", server)
    assert event_pipe.wait_for_client() is False


def test_close_pipe_server_closes_sockets_and_unlinks_path(monkeypatch):
    server = FakeSocket()
    client = FakeSocket()
    unlink = Mock()
    monkeypatch.setattr(event_pipe, "_socket_server", server)
    monkeypatch.setattr(event_pipe, "_client_socket", client)
    monkeypatch.setattr(event_pipe, "_pipe_connected", True)
    monkeypatch.setattr(event_pipe.os, "unlink", unlink)

    event_pipe.close_pipe_server()

    assert server.closed is True
    assert client.closed is True
    assert event_pipe.is_connected() is False
    unlink.assert_called_once_with(event_pipe.SOCKET_PATH)


def test_connect_pipe_client_connects_and_handles_failure(monkeypatch):
    client = FakeSocket()
    socket_factory = Mock(return_value=client)
    monkeypatch.setattr(event_pipe.socket, "socket", socket_factory)

    assert event_pipe.connect_pipe_client() is client
    assert client.connected == event_pipe.SOCKET_PATH

    socket_factory.side_effect = OSError("missing")
    assert event_pipe.connect_pipe_client() is None


def test_receive_log_buffers_complete_and_partial_messages():
    handle = FakeSocket([b"first\nsecond\n", b"tail"])

    assert event_pipe.receive_log(handle) == "first"
    assert event_pipe.receive_log(handle) == "second"
    assert event_pipe.receive_log(handle) == "tail"
    assert event_pipe.receive_log(handle) is None


def test_receive_log_handles_decode_or_socket_failure():
    handle = FakeSocket([OSError("closed")])

    assert event_pipe.receive_log(handle) is None


def test_close_pipe_client_ignores_close_failure():
    handle = FakeSocket()
    handle.close = Mock(side_effect=OSError("already closed"))

    event_pipe.close_pipe_client(handle)
    event_pipe.close_pipe_client(None)


def test_reset_pipe_server_closes_existing_sockets_and_starts_waiter(
    monkeypatch,
):
    server = FakeSocket()
    client = FakeSocket()
    started = []

    class ImmediateThread:
        def __init__(self, target, **_kwargs):
            self.target = target

        def start(self):
            started.append(self.target)
            self.target()

    monkeypatch.setattr(event_pipe, "_socket_server", server)
    monkeypatch.setattr(event_pipe, "_client_socket", client)
    monkeypatch.setattr(event_pipe, "_pipe_connected", True)
    monkeypatch.setattr(event_pipe, "create_pipe_server", lambda: True)
    monkeypatch.setattr(event_pipe, "wait_for_client", lambda: True)
    start_writer = Mock()
    monkeypatch.setattr(event_pipe, "start_writer_thread", start_writer)
    monkeypatch.setattr(event_pipe.threading, "Thread", ImmediateThread)

    event_pipe.reset_pipe_server()

    assert server.closed is True
    assert client.closed is True
    assert event_pipe.is_connected() is False
    assert len(started) == 1
    start_writer.assert_called_once_with()
