"""A library to supplement Discord.py by adding support for slash commands."""
from .client import CommandClient
from .commands import SlashCommandInvokeError
from .options import Channel, Mentionable, option
from .permissions import (
    allow_roles,
    allow_users,
    disallow_roles,
    disallow_users,
    global_permissions,
    guild_permissions,
)

__version__ = "0.2.0"
__all__ = (
    "__version__",
    "CommandClient",
    "option",
    "Channel",
    "Mentionable",
    "allow_roles",
    "allow_users",
    "disallow_roles",
    "disallow_users",
    "guild_permissions",
    "global_permissions",
    "SlashCommandInvokeError",
)
