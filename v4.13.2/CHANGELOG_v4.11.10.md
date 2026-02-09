# Changelog — v4.11.10
- Added buffered emitter to coalesce quote/depth events and throttle depth updates.
- Added poison-pill protection in Open API message handler.
- Added best-effort auto reconnect with exponential backoff.
- Added SQLite maintenance runner (WAL checkpoint, VACUUM, ANALYZE).
