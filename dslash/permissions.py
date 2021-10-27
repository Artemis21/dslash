"""Tools for setting permissions on commands."""
from typing import Any, Optional

from nextcord.enums import Enum

from .commands import SlashCommandSubGroup, SlashSubCommand, TopLevelCommand


class ApplicationCommandPermissionType(Enum):
    """Enum representing the permission type of an application command."""

    role = 1
    user = 2


UserPermissions = dict[int, bool]
# More accurately, list[nextcord.types.interactions.ApplicationCommandPermissions],
# but that just causes type checker errors.
ApiPermissions = list[dict[str, int]]


def _to_dict(ids: tuple[int, ...], value: bool) -> UserPermissions:
    """Create a dict with the same value for every key."""
    return {id: value for id in ids}


def _dump_permissions(
    *, roles: Optional[UserPermissions] = None, users: Optional[UserPermissions] = None
) -> ApiPermissions:
    """Dump permissions to the JSON structure accepted by the API."""
    return [
        *(
            {
                "id": role_id,
                "type": ApplicationCommandPermissionType.role.value,
                "permission": value,
            }
            for role_id, value in (roles or {}).items()
        ),
        *(
            {
                "id": user_id,
                "type": ApplicationCommandPermissionType.user.value,
                "permission": value,
            }
            for user_id, value in (users or {}).items()
        ),
    ]


def _update_permissions(dest: dict[int, ApiPermissions], source: dict[int, ApiPermissions]):
    """Update permissions for a command, extending rather than overwriting."""
    for guild_id, permissions in source.items():
        if guild_id in dest:
            dest[guild_id].extend(permissions)
        else:
            dest[guild_id] = permissions


class PermissionsSetter:
    """Decorator to set permissions on a command."""

    def __call__(self, command: TopLevelCommand) -> TopLevelCommand:
        """Set permissions on a command."""
        if not isinstance(command, TopLevelCommand):
            raise self._wrong_type(command)
        self._apply_permissions(command)
        return command

    def _wrong_type(self, command: Any) -> TypeError:
        """Construct an error when the given command is of the wrong type."""
        if isinstance(command, SlashCommandSubGroup):
            attempt = "subcommand group."
        elif isinstance(command, SlashSubCommand):
            attempt = "subcommand."
        elif callable(command):
            attempt = (
                "plain function. Make sure any permissions decorators are "
                "before the command decorator."
            )
        else:
            attempt = repr(type(command))
        return TypeError("Permissions can only be set on a top level command, not a " f"{attempt}")

    def _apply_permissions(self, command: TopLevelCommand):
        """Apply permissions to a command."""
        raise NotImplementedError


class AllPermissionsSetter(PermissionsSetter):
    """Decorator to set permissions on a command for all guilds."""

    def __init__(self, roles: dict[int, UserPermissions], users: dict[int, UserPermissions]):
        """Store the permissions."""
        self.permissions = {}
        _update_permissions(
            self.permissions,
            {
                guild_id: _dump_permissions(roles=role_permissions)
                for guild_id, role_permissions in roles.items()
            },
        )
        _update_permissions(
            self.permissions,
            {
                guild_id: _dump_permissions(users=user_permissions)
                for guild_id, user_permissions in users.items()
            },
        )

    def _apply_permissions(self, command: TopLevelCommand):
        """Set permissions on a command."""
        _update_permissions(command.permissions, self.permissions)  # type: ignore


class GuildPermissionsSetter(PermissionsSetter):
    """Decorator to set permissions on a command for one guild."""

    def __init__(self, roles: UserPermissions, users: UserPermissions, guild_id: Optional[int]):
        """Store the permissions."""
        self.permissions = _dump_permissions(roles=roles, users=users)
        self.guild_id = guild_id

    def _apply_permissions(self, command: TopLevelCommand):
        """Set permissions on a command."""
        guild_id = self.guild_id or command.guild_id
        if not guild_id:
            raise TypeError(
                f"Command {command.name!r} is not for a specific guild, so a "
                "guild ID must be set for permissions."
            )
        _update_permissions(command.permissions, {guild_id: self.permissions})  # type: ignore


def global_permissions(
    roles: dict[int, UserPermissions], users: dict[int, UserPermissions]
) -> AllPermissionsSetter:
    """Create a decorator to set permissions for multiple guilds."""
    return AllPermissionsSetter(roles, users)


def guild_permissions(
    roles: Optional[UserPermissions] = None,
    users: Optional[UserPermissions] = None,
    guild_id: Optional[int] = None,
) -> GuildPermissionsSetter:
    """Create a decorator to set permissions for a guild."""
    return GuildPermissionsSetter(roles or {}, users or {}, guild_id)


def allow_roles(*role_ids: int, guild_id: Optional[int] = None) -> GuildPermissionsSetter:
    """Allow certain roles to use a command in a guild."""
    return guild_permissions(roles=_to_dict(role_ids, True), guild_id=guild_id)


def disallow_roles(*role_ids: int, guild_id: Optional[int] = None) -> GuildPermissionsSetter:
    """Prevents certain roles from using a command in a guild."""
    return guild_permissions(roles=_to_dict(role_ids, False), guild_id=guild_id)


def allow_users(*user_ids: int, guild_id: Optional[int] = None) -> GuildPermissionsSetter:
    """Allow certain users to use a command in a guild."""
    return guild_permissions(users=_to_dict(user_ids, True), guild_id=guild_id)


def disallow_users(*user_ids: int, guild_id: Optional[int] = None) -> GuildPermissionsSetter:
    """Prevents certain users from using a command in a guild."""
    return guild_permissions(users=_to_dict(user_ids, False), guild_id=guild_id)
