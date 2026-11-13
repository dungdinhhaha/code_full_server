"""Session cookie / storage-secret hardening helpers (kept dependency-free for testing)."""
from __future__ import annotations

import logging
import secrets
from typing import Mapping


def is_production(env: Mapping[str, str]) -> bool:
    return str(env.get("APP_ENV", "development")).strip().lower() == "production"


def resolve_storage_secret(env: Mapping[str, str], logger: logging.Logger | None = None) -> str:
    """Return NICEGUI_STORAGE_SECRET, or a random per-process secret when it is missing.

    There is deliberately no fixed fallback key. A random secret invalidates every existing login
    session on each restart. The secret value is never logged.
    """
    value = str(env.get("NICEGUI_STORAGE_SECRET", "") or "").strip()
    if value:
        return value
    if logger is not None:
        logger.warning(
            "NICEGUI_STORAGE_SECRET chua duoc cau hinh: dung secret ngau nhien cho tien trinh nay, "
            "moi phien dang nhap se mat khi app restart. Hay dat NICEGUI_STORAGE_SECRET%s.",
            " (bat buoc trong production)" if is_production(env) else "",
        )
    return secrets.token_urlsafe(48)


def session_middleware_kwargs(env: Mapping[str, str]) -> dict:
    """Starlette SessionMiddleware kwargs: Secure cookie only in production (https)."""
    return {"https_only": True} if is_production(env) else {}
