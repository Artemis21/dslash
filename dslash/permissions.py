"""Tools for setting permissions on commands."""
from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .commands import TopLevelCommand

PermissionsSetter = Callable[["TopLevelCommand"], "TopLevelCommand"]


def warn_permissions_deprecation():
    """Warn about trying to configure permissions."""
    warnings.warn(
        "dslash: permissions configuration is deprecated and has no effect, as "
        "Discord no longer allows bots to configure permissions.",
        DeprecationWarning,
    )


def permissions_wrapper(*args: Any, **kwargs: Any) -> PermissionsSetter:
    """Make a no-op command wrapper."""
    warn_permissions_deprecation()
    return lambda command: command


global_permissions = guild_permissions = permissions_wrapper
allow_roles = disallow_roles = allow_users = disallow_users = permissions_wrapper
