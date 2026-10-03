# Linux production deployment

This directory contains the production contract for `eitaa.farhangimaz.ir`.
Runtime data and credentials are never included in a release artifact.  They
live under `/srv/projects/eitaa-bridge/shared` on the server.

The backend listens only on `127.0.0.1:8765`.  Nginx publishes the UI on the
domain and exposes a separate same-host integration gateway on
`127.0.0.1:8876` for a future application on the same server.

All server applications use the same publishing entry point:

```text
sudo publish-site list
sudo publish-site status eitaa-bridge
sudo publish-site deploy eitaa-bridge
```

Existing installations created before remote browser authentication was enabled
must run the versioned, rollback-safe migration after publishing the new code:

```text
sudo bash /srv/projects/eitaa-bridge/current/deploy/linux/enable-remote-messenger-auth
```

The migration accepts only the validated `web_reverse_proxy` profile, keeps a
restricted timestamped backup, validates the resulting config with the current
release and restores the backup if restart or readiness fails.

Each site has a root-owned handler in `/usr/local/lib/site-publisher`.  A failed
health check restores the previous `current` symlink and restarts the prior
release.  Releases are immutable; `shared` state is preserved across updates.
Publication normalizes group read/traverse permissions even when the caller has
`umask 077`, keeps all other-user permissions disabled, and verifies runtime
imports as the service user before changing the active symlink. The dependency
declarations include the HTTPX and Excel libraries required by the current code;
a regression check compares runtime imports with those declarations.

The symlink rollback restores code only. A release that has already migrated the
Coordinator database may make an older release reject it with
`coordinator_schema_newer`. Keep a restricted, consistent database backup before
upgrading, and verify compatibility before relying on code rollback. Restoring
operational data is a separate operation requiring the owner's current approval;
do not automatically restore or delete shared state after a failed startup.
For Eitaa Bridge, the publication gate checks both readiness and the unauthenticated
AppUser status response through the same-host gateway.  A `401` or malformed
status response fails the release and triggers the existing rollback path.

TLS is terminated at Nginx with an origin certificate.  The public certificate
is expected to be provided by the CDN.  Port 80 redirects to HTTPS.
