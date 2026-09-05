# Security

Report vulnerabilities through GitHub's private vulnerability reporting if enabled. Otherwise open a minimal issue asking for a private contact, without exploit details or private captures.

The tool runs as your user and temporarily writes game config files. Its VConsole connection uses `127.0.0.1:29000`; do not expose that port through a firewall or tunnel. Automated sessions use local replays or bots with `-insecure`.

The CLI does not upload data. Report exports exclude raw logs, backups, profile contents and absolute replay paths, but include your labels and notes. Review those before sharing. Raw workspaces may contain account identifiers, local paths and personal configs.
