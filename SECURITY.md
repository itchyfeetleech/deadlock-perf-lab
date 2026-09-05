# Security and data handling

Deadlock Perf Lab runs as the current user. It needs write access only to its workspace and the game's config files it temporarily changes. It does not require root, collect analytics, contact a server, install drivers or upload captures.

The VConsole client connects only to `127.0.0.1:29000`. Do not expose the game's debug console through a firewall or tunnel. Automated sessions use local replays/bot scenarios and `-insecure`; inspect third-party GameInfo files before enabling experimental swaps.

Reports exclude backups, raw logs, profile contents and absolute replay paths. Freeform labels and notes are included; review them before sharing. Raw Steam/game logs can contain account identifiers and local paths and remain private by default.

Report a security issue through GitHub's private vulnerability reporting if it is enabled for this repository. Otherwise open a minimal issue asking for a private contact route, without posting exploit details, credentials or private captures. Do not post your full workspace.
