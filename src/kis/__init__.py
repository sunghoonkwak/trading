# KIS module - expose thread helpers lazily to keep lightweight imports side-effect free.

_KIS_THREAD_EXPORTS = {
    "start_kis_thread",
    "stop_kis_thread",
    "is_kis_thread_running",
    "request_kis_auth",
    "request_kis_ws_auth",
    "request_portfolio",
    "wait_for_response",
    "initialize_websocket_and_pipe",
}

__all__ = sorted(_KIS_THREAD_EXPORTS)


def __getattr__(name):
    if name in _KIS_THREAD_EXPORTS:
        from . import kis_thread

        return getattr(kis_thread, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
