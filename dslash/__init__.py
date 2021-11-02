"""A library to supplement Discord.py by adding support for slash commands."""
from .choices import Choice, Choices
from .client import CommandClient
from .commands import SlashCommandInvokeError
from .groups import CommandGroup, CommandSubGroup, subcommand
from .options import Channel, Mentionable
from .permissions import (
    allow_roles,
    allow_users,
    disallow_roles,
    disallow_users,
    global_permissions,
    guild_permissions,
)

__version__ = "0.4.2"
__all__ = (
    "__version__",
    "CommandClient",
    "CommandGroup",
    "CommandSubGroup",
    "subcommand",
    "Channel",
    "Mentionable",
    "Choices",
    "Choice",
    "allow_roles",
    "allow_users",
    "disallow_roles",
    "disallow_users",
    "guild_permissions",
    "global_permissions",
    "SlashCommandInvokeError",
)
