"""A library to supplement Discord.py by adding support for slash commands."""
import discord

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

__version__ = "0.1.2"
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

if discord.version_info.major != 2:
    raise RuntimeError(
        "This library requires Discord.py v2. Currently, this cannot be installed "
        "from PyPI, so you will have to install it from GitHub: \n"
        "    pip install git+https://github.com/Rapptz/discord.py"
    )
