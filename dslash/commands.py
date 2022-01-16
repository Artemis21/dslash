"""Models to represent slash commands and sub-commands."""
from __future__ import annotations

import collections.abc
import inspect
import typing
from typing import Any, Optional, Type, Union

import docstring_parser
import nextcord
from docstring_parser.common import DocstringParam
from nextcord.types.interactions import ApplicationCommandPermissions

from .options import ApplicationCommandOptionType, CommandOption

if typing.TYPE_CHECKING:
    from .client import CommandClient
    from .permissions import PermissionsSetter


CommandCallback = Any
Permissions = Optional[Union[list["PermissionsSetter"], "PermissionsSetter"]]


class SlashCommandInvokeError(Exception):
    """An error raised when a slash command callback throws an error."""

    def __init__(self, original: Exception):
        """Store a reference to the original exception."""
        self.original = original
        super().__init__(
            f"Slash Command raised an exception: " f"{original.__class__.__name__}: {original}"
        )


class BaseSlashCommand:
    """Base class for slash commands and slash sub-commands."""

    name: str
    description: str

    def __init__(self, *, name: str, description: str):
        """Set up a new slash command."""
        self.name = name
        self.description = description

    def dump(self) -> dict[str, Any]:
        """Get the data to create the command."""
        data = {"name": self.name, "description": self.description}
        self._add_dump_data(data)
        return data

    def _add_dump_data(self, data: dict[str, Any]):
        """Add values to the data to create the command."""
        pass

    async def __call__(
        self,
        interaction: nextcord.Interaction,
        options: Optional[list[dict[str, Any]]] = None,
    ):
        """Handle the command or a nested subcommand of it being invoked."""
        if options:
            full_options = options
        else:
            full_options = interaction.data.get("options", []) if interaction.data else []
        option_map = {option["name"]: option for option in full_options}
        await self._process_option_data(interaction, option_map)  # type: ignore

    async def _process_option_data(
        self, interaction: nextcord.Interaction, options: dict[str, dict[str, Any]]
    ):
        """Process and use option data passed when the command is invoked."""
        raise NotImplementedError


class CallableSlashCommand(BaseSlashCommand):
    """Base class for slash commands that do something (not just groups)."""

    def __init__(self, *, callback: CommandCallback, name: str, description: str):
        """Set up the slash command."""
        BaseSlashCommand.__init__(self, name=name, description=description)
        self.callback = callback
        self.options: dict[str, CommandOption] = {}
        # Params to pass to the callback before the interaction. Useful for
        # 'self' / 'cls' parameters.
        self.prepend_params: tuple[Any, ...] = ()

    def _process_callback(self):
        """Process the name, docstring and arguments of the callback."""
        self.name = self.name or self.callback.__name__
        docstring = docstring_parser.parse(self.callback.__doc__ or "")
        if not self.description:
            self.description = docstring.short_description or "No description."
        self._process_options(docstring.params)

    def _process_options(self, descriptions: list[DocstringParam]):
        """Get the options for this command from callback annotations."""
        description_map = {
            docstring_param.arg_name: docstring_param.description
            for docstring_param in descriptions
        }
        signature = inspect.signature(self.callback)
        # get_type_hints will parse string type hints, which inspect won't.
        annotations = typing.get_type_hints(self.callback)
        done_self = False
        for n, parameter in enumerate(signature.parameters.values()):
            if n == 0 and parameter.name == "self":
                done_self = True
                continue
            if n == 0 or (done_self and n == 1):
                # It's the first parameter, the interaction.
                continue
            description = description_map.get(parameter.name)
            self._process_option(parameter, annotations[parameter.name], description)

    def _process_option(
        self, parameter: inspect.Parameter, annotation: Type, description: Optional[str]
    ):
        """Process an option annotation."""
        self.options[parameter.name] = CommandOption(
            name=parameter.name, description=description or "No description.", type=annotation
        )

    def _add_dump_data(self, data: dict[str, Any]):
        """Add the command options to the dump data."""
        data["options"] = data.get("options", [])
        for option in self.options.values():
            data["options"].append(option.dump())

    async def _process_option_data(
        self, interaction: nextcord.Interaction, options: dict[str, dict[str, Any]]
    ):
        """Process and use option data passed when the command is invoked."""
        arguments = {}
        for option in self.options.values():
            data = options.get(option.name)
            arguments[option.name] = await option(data, interaction.guild)
        client: "CommandClient" = interaction._state._get_client()  # type: ignore
        try:
            if client.custom_interaction:
                interaction = client.custom_interaction(interaction)
            await self.callback(*self.prepend_params, interaction, **arguments)
        except Exception as exc:
            raise SlashCommandInvokeError(exc) from exc


class ContainerSlashCommand(BaseSlashCommand):
    """Base class for groups/commands which can have subcommands."""

    def __init__(self, name: str, description: str):
        """Set up the command group."""
        super().__init__(name=name, description=description)
        self.subcommands: dict[str, ChildSlashCommand] = {}

    def subcommand(
        self, name: Optional[str] = None, description: Optional[str] = None
    ) -> SlashSubCommandConstructor:
        """Create a decorator to register a new subcommand."""
        return SlashSubCommandConstructor(
            parent=self,
            name=name,
            description=description,
        )

    def _add_dump_data(self, data: dict[str, Any]):
        """Add the subcommands to the dump data."""
        data["options"] = data.get("options", [])
        for subcommand in self.subcommands.values():
            data["options"].append(subcommand.dump())

    async def _process_option_data(
        self, interaction: nextcord.Interaction, options: dict[str, dict[str, Any]]
    ):
        """Process and use option data passed when the command is invoked.

        Return value indicates whether the data was used.
        """
        for subcommand in self.subcommands.values():
            if subcommand.name in options:
                sub_options = options[subcommand.name].get("options", [])
                await subcommand(interaction, sub_options)
                return


class ChildSlashCommand(BaseSlashCommand):
    """Base class for groups/commands which must have parents."""


class TopLevelCommand(BaseSlashCommand):
    """Base class for groups/commands at the top level of the hierarchy.

    As far as the API is concerned this is all one type - application command,
    but the separation between a callable top level command and a container top
    level command helps for implementation.
    """

    def __init__(
        self,
        *,
        guild_id: Optional[int],
        default_permission: bool,
        permissions: Permissions,
    ):
        """Set up a new top-level slash command."""
        # We don't call the super constructor because this is a base class and
        # child classes will always have another parent with the same parent as
        # this class, which will call it instead.
        self.guild_id = guild_id
        self.default_permission = default_permission
        self.permissions: dict[int, list[ApplicationCommandPermissions]] = {}
        # A PermissionsSetter is primarily meant to be a wrapper, so we apply
        # its permissions by calling it on the command/group.
        if permissions:
            if isinstance(permissions, collections.abc.Iterable):
                for permission in permissions:
                    permission(self)
            else:
                permissions(self)
        self.id: Optional[int] = None

    def _add_dump_data(self, data: dict[str, Any]):
        """Add the default permissions to the dump data."""
        data["default_permission"] = self.default_permission


class SlashCommandGroup(TopLevelCommand, ContainerSlashCommand):
    """A top-level slash command that contains other commands."""

    def __init__(
        self,
        *,
        guild_id: Optional[int],
        default_permission: bool,
        permissions: Permissions,
        name: str,
        description: str,
    ):
        """Set up a new top-level slash command."""
        ContainerSlashCommand.__init__(self, name=name, description=description)
        TopLevelCommand.__init__(
            self,
            guild_id=guild_id,
            default_permission=default_permission,
            permissions=permissions,
        )

    def _add_dump_data(self, data: dict[str, Any]):
        """Add the default permissions to the dump data."""
        TopLevelCommand._add_dump_data(self, data)
        ContainerSlashCommand._add_dump_data(self, data)


class SlashCommand(CallableSlashCommand, TopLevelCommand):
    """A callable top-level slash command."""

    def __init__(
        self,
        *,
        guild_id: Optional[int],
        default_permission: bool,
        permissions: Permissions,
        callback: CommandCallback,
        name: str,
        description: str,
    ):
        """Set up a new top-level slash command."""
        CallableSlashCommand.__init__(self, callback=callback, name=name, description=description)
        self._process_callback()
        TopLevelCommand.__init__(
            self,
            guild_id=guild_id,
            default_permission=default_permission,
            permissions=permissions,
        )

    def _add_dump_data(self, data: dict[str, Any]):
        """Add the default permissions to the dump data."""
        CallableSlashCommand._add_dump_data(self, data)
        TopLevelCommand._add_dump_data(self, data)


class SlashCommandSubGroup(ChildSlashCommand, ContainerSlashCommand):
    """A sub-group of slash commands."""

    def __init__(self, name: str, description: str):
        """Set up the slash command group."""
        ContainerSlashCommand.__init__(self, name=name, description=description)

    def _add_dump_data(self, data: dict[str, Any]):
        """Add the option type to the dump data."""
        ContainerSlashCommand._add_dump_data(self, data)
        ChildSlashCommand._add_dump_data(self, data)
        data["type"] = ApplicationCommandOptionType.sub_command_group.value


class SlashSubCommand(ChildSlashCommand, CallableSlashCommand):
    """A subcommand of a slash command."""

    def __init__(self, callback: CommandCallback, name: str, description: str):
        """Set up a new subcommand."""
        CallableSlashCommand.__init__(self, callback=callback, name=name, description=description)
        self._process_callback()

    def _add_dump_data(self, data: dict[str, Any]):
        """Add the option type to the dump data."""
        CallableSlashCommand._add_dump_data(self, data)
        data["type"] = ApplicationCommandOptionType.sub_command.value


CT = typing.TypeVar("CT", bound=CallableSlashCommand)


class BaseSlashCommandConstructor(typing.Generic[CT]):
    """A class instances of which act as decorators to register commands."""

    command_class: Type[CT]

    def __init__(self, *, name: Optional[str], description: Optional[str]):
        """Set up the slash command constructor."""
        self.overwrites: dict[str, Any] = {"name": name, "description": description}

    def __call__(self, callback: CommandCallback) -> CT:
        """Construct an actual slash command."""
        command = self.command_class(callback=callback, **self.overwrites)
        self.register(command)
        return command

    def register(self, command: CT):
        """Register the created command."""
        raise NotImplementedError


class SlashCommandConstructor(BaseSlashCommandConstructor[SlashCommand]):
    """A class for decorating top-level commands."""

    command_class = SlashCommand

    def __init__(
        self,
        *,
        client: Optional["CommandClient"],
        guild_id: Optional[int],
        default_permission: bool,
        permissions: Permissions,
        name: Optional[str],
        description: Optional[str],
    ):
        """Set up the slash command constructor."""
        super().__init__(name=name, description=description)
        self.client = client
        self.overwrites["guild_id"] = guild_id
        self.overwrites["default_permission"] = default_permission
        self.overwrites["permissions"] = permissions

    def register(self, command: SlashCommand):
        """Register the created command."""
        if self.client:
            self.client._store_command(command)


class SlashSubCommandConstructor(BaseSlashCommandConstructor[SlashSubCommand]):
    """A class for decorating subcommands."""

    command_class = SlashSubCommand

    def __init__(
        self,
        *,
        parent: Optional[ContainerSlashCommand],
        name: Optional[str],
        description: Optional[str],
    ):
        """Set up the slash sub-command constructor."""
        super().__init__(name=name, description=description)
        self.parent = parent

    def register(self, command: SlashSubCommand):
        """Register the created subcommand."""
        if self.parent:
            self.parent.subcommands[command.name] = command
