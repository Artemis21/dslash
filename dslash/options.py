"""Models to represent arguments to slash commands."""
import typing
from typing import Any, Optional, Type, Union

import nextcord
from nextcord.enums import Enum

Channel = nextcord.abc.GuildChannel
Mentionable = Union[nextcord.User, nextcord.Member, nextcord.Role]


class ApplicationCommandOptionType(Enum):
    """The type of an argument to a slash command."""

    sub_command = 1
    sub_command_group = 2
    string = 3
    integer = 4
    boolean = 5
    user = 6
    channel = 7
    role = 8
    mentionable = 9
    number = 10


class CommandOption:
    """An argument to a slash command."""

    def __init__(
        self,
        *,
        description: str,
        name: str,
        argument_name: str,
        type: Type,
        choices: Optional[dict[str, Union[str, int]]],
        required: bool,
    ):
        """Set up the command option."""
        self.description = description
        self.argument_name = argument_name
        self.name = name
        self.type = type
        self.choices = (
            [{"name": name, "value": value} for name, value in choices.items()] if choices else None
        )
        if choices and not issubclass(type, (int, str)):
            raise TypeError("Only int or str options may have choices.")
        if choices and not all(isinstance(value, type) for value in choices.values()):
            raise TypeError("All choice values must be of the option type.")
        self.required = required

    def dump(self) -> dict[str, Any]:
        """Get the JSON data for registering this option with the API."""
        return {
            "name": self.name,
            "description": self.description,
            "required": self.required,
            "type": self.type_value.value,
            "choices": self.choices,
        }

    @property
    def _is_user_type(self) -> bool:
        """Check if the option type is 'user'."""
        return (
            issubclass(self.type, (nextcord.User, nextcord.Member))
            or self.type is nextcord.abc.User
        )

    @property
    def _is_channel_type(self) -> bool:
        """Check if the option type is 'channel'."""
        return (
            issubclass(
                self.type,
                (nextcord.TextChannel, nextcord.VoiceChannel, nextcord.CategoryChannel),
            )
            or self.type is nextcord.abc.GuildChannel
        )

    @property
    def type_value(self) -> ApplicationCommandOptionType:
        """Get the Discord API code for the option's type."""
        if (not self.type) or issubclass(self.type, str):
            return ApplicationCommandOptionType.string
        if issubclass(self.type, bool):
            return ApplicationCommandOptionType.boolean
        if issubclass(self.type, int):
            return ApplicationCommandOptionType.integer
        if issubclass(self.type, float):
            return ApplicationCommandOptionType.number
        if self._is_user_type:
            return ApplicationCommandOptionType.user
        if self._is_channel_type:
            return ApplicationCommandOptionType.channel
        if issubclass(self.type, nextcord.Role):
            return ApplicationCommandOptionType.role
        if typing.get_origin(self.type) is typing.Union:
            if typing.get_args(self.type) == typing.get_args(Mentionable):
                return ApplicationCommandOptionType.mentionable
            raise TypeError("Union type not allowed for option type (except Mentionable).")
        raise TypeError(f"Unsupported option type {self.type!r}.")

    async def __call__(
        self, data: Optional[dict[str, Any]], guild: Optional[nextcord.Guild]
    ) -> Any:
        """Process option data from the API."""
        if (not data) or "value" not in data:
            return None
        value = data["value"]
        type = ApplicationCommandOptionType(data["type"])
        if type in (
            ApplicationCommandOptionType.string,
            ApplicationCommandOptionType.boolean,
            ApplicationCommandOptionType.integer,
            ApplicationCommandOptionType.number,
        ):
            return value
        value = int(value)
        if not guild:
            raise ValueError("User/role/channel option recieved without a guild.")
        if type == ApplicationCommandOptionType.mentionable:
            if role := guild.get_role(value):
                return role
        if type in (
            ApplicationCommandOptionType.user,
            ApplicationCommandOptionType.mentionable,
        ):
            if not (user := guild.get_member(value)):
                user = await guild.fetch_member(value)
            return user
        if type == ApplicationCommandOptionType.role:
            return guild.get_role(value)
        if type == ApplicationCommandOptionType.channel:
            return guild.get_channel(value)


class PartialCommandOption:
    """An argument to a slash command with some optional attributes."""

    def __init__(
        self,
        *,
        description: str,
        name: Optional[str],
        type: Optional[Type],
        choices: Optional[dict[str, Union[str, int]]],
        required: bool,
    ):
        """Set up the command option."""
        self.description = description
        self.name = name
        self.type = type
        self.choices = choices
        self.required = required

    def fallbacks(self, *, name: str, type: Optional[Type]) -> CommandOption:
        """Create an option with all attributes set."""
        return CommandOption(
            description=self.description,
            name=self.name or name,
            argument_name=name,
            type=self.type or type or str,
            choices=self.choices,
            required=self.required,
        )


def option(
    description: str,
    required: bool = False,
    choices: Optional[dict[str, Union[str, int]]] = None,
    *,
    name: Optional[str] = None,
    type: Optional[Type] = None,
) -> PartialCommandOption:
    """Label an option of a slash command."""
    return PartialCommandOption(
        description=description,
        name=name,
        type=type,
        choices=choices,
        required=required,
    )
