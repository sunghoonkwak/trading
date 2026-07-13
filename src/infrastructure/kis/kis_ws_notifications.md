# KIS WebSocket Notifications

`kis_ws_notifications.py` owns the KIS WebSocket reconnection notification
policy used by `vendor_callbacks.py`.

- A disconnect alone sends no Telegram notification.
- Reconnection failures notify after three consecutive failed attempts.
- A recovery notification is sent only after a reported outage.
- One or two transient failures remain visible through logs and UI state only.
