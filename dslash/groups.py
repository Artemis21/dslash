"""Definitions for the class-based command (sub)group system."""
from __future__ import annotations

import re
from typing import Any, Generic, Optional, TypeVar, Union

from .client import GUILD_ID_DEFAULT, GuildID
from .commands import (
    ChildSlashCommand,
    SlashCommandGroup,
    SlashCommandSubGroup,
    SlashSubCommand,
    SlashSubCommandConstructor,
)


def class_name_to_group_name(class_name: str) -> str:
    """Convert a class name to a group name."""
    return re.sub(r"([a-z])([A-Z0-9])", r"\1_\2", class_name).lower()


GT = TypeVar("GT", SlashCommandGroup, SlashCommandSubGroup)


class BaseCommandGroupMeta(type, Generic[GT]):
    """Base metaclass for class-nased command groups."""

    @classmethod
    def _construct_group(cls, name: str, description: str, **kwargs: Any) -> GT:
        """Construct a the actual group object."""
        raise NotImplementedError

    def __new__(
        cls,
        class_name: str,
        parents: tuple[type],
        attrs: dict[str, Any],
        name: Optional[str] = None,
        _base_class: bool = False,
        **kwargs: Any,
    ) -> Union[GT, type]:
        """Create a new command group class."""
        new_class = super().__new__(cls, class_name, parents, attrs)
        if _base_class:
            return new_class
        group = cls._construct_group(
            name=name or class_name_to_group_name(class_name),
            description=attrs["__doc__"] or "No description.",
            **kwargs,
        )
        # Command groups are singletons.
        instance = new_class()
        for attr in attrs.values():
            if isinstance(attr, SlashSubCommand):
                attr.prepend_params = (instance,)
            elif not isinstance(attr, ChildSlashCommand):
                continue
            group.subcommands[attr.name] = attr
        return group


class CommandGroupMeta(BaseCommandGroupMeta[SlashCommandGroup]):
    """Metaclass for class-based top-level command groups."""

    @classmethod
    def _construct_group(
        cls,
        name: str,
        description: str,
        guild_id: GuildID = GUILD_ID_DEFAULT,
        default_permission: bool = True,
    ) -> SlashCommandGroup:
        """Construct a the actual group object."""
        return SlashCommandGroup(
            # The client will replace the guild ID default when the group is registered.
            guild_id=guild_id,  # type: ignore
            name=name,
            description=description,
            default_permission=default_permission,
            permissions=None,
        )


class CommandSubGroupMeta(BaseCommandGroupMeta[SlashCommandSubGroup]):
    """Metaclass for class-based command subgroups."""

    @classmethod
    def _construct_group(cls, name: str, description: str) -> SlashCommandSubGroup:
        """Construct a the actual group object."""
        return SlashCommandSubGroup(name=name, description=description)


class CommandGroup(metaclass=CommandGroupMeta, _base_class=True):
    """Class to inherit to build command groups.

    See `CommandClient.group` for more information and examples.
    """


class CommandSubGroup(metaclass=CommandSubGroupMeta, _base_class=True):
    """Class to inherit to build command subgroups."""


def subcommand(
    name: Optional[str] = None, description: Optional[str] = None
) -> SlashSubCommandConstructor:
    """Build a subcommand for within a group."""
    return SlashSubCommandConstructor(
        parent=None,
        name=name,
        description=description,
    )
