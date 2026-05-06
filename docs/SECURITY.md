# Security Notes

This project is designed for a trusted home or lab network. Do not expose the web dashboard directly to the internet.

## Sensitive Data Policy

Do not commit:

- WiFi passwords.
- SSH passwords or private keys.
- API keys, tokens, certificates, or `.env` files.
- Local IP addresses from a real deployment.
- Logs, system dumps, package inventories, backup archives, virtualenvs, or APK builds.

The repository ignores these by default through `.gitignore`.

## Web Dashboard Access

The dashboard includes endpoints for WiFi management, reboot, shutdown, live camera stream, and alert acknowledgement. Keep the service reachable only on a trusted LAN or behind a private VPN.

Recommended protections for production-like use:

- Put the Pi on a private network segment.
- Use a firewall to allow only trusted clients.
- Add authentication or a reverse proxy before exposing the dashboard beyond a local LAN.
- Disable WiFi and power-management endpoints if they are not needed.

## Secret Scan Before Publishing

Run this before pushing:

```bash
rg -n "(api[_-]?key|token|secret|password|senha|passwd|sk-[A-Za-z0-9_-]+|AKIA[0-9A-Z]{16}|([0-9]{1,3}\\.){3}[0-9]{1,3})" \
  -g '!backups/**' -g '!venv/**' -g '!*.tar.gz' -S .
```

Matches that are code labels, placeholders, or documentation examples are acceptable. Real credentials are not.
