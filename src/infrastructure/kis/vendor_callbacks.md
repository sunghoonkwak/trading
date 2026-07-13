# KIS Vendor Callbacks

`vendor_callbacks.py` registers application-owned runtime collaborators with
the isolated KIS vendor API. The composition root supplies credential loading,
local alert publication, and WebSocket-state publication before KIS startup.

Notification, logging, and reconnect message formatting remain infrastructure
responsibilities. Alert and state publication are best-effort, so callback
delivery failures cannot disrupt KIS vendor processing.
