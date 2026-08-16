"""Optional email notifications via the local `mail` command.

Best-effort only: a missing/misconfigured MTA must never take down a
multi-day pipeline run over a notification. Disabled by default is not the
default here (matches the old pipeline's always-on behavior), but it's a
single config flag away — see config.NotificationConfig.
"""

from __future__ import annotations

import logging
import subprocess

from pipeline.config import NotificationConfig

logger = logging.getLogger("pipeline.notify")


def notify(subject: str, body: str, config: NotificationConfig) -> None:
    if not config.enabled:
        return
    try:
        subprocess.run(
            ["mail", "-s", subject, config.email],
            input=body,
            text=True,
            timeout=30,
            check=True,
            capture_output=True,
        )
    except Exception as exc:  # noqa: BLE001 - notification failures are non-fatal
        logger.warning("notification failed (subject=%r): %s", subject, exc)
