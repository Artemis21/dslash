"""Models to represent arguments to slash commands."""
import types
import typing
from typing import Any, Optional, Type, Union

import nextcord
from nextcord.enums import Enum

from .choices import Choices

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

    def __init__(self, *, name: str, description: str, type: Type):
        """Set up the command option."""
        self.description = description
        self.name = name
        self.type, self.choices, self.required = self._get_type_metadata(type)

    def _get_optional_type(self, param_type: Type) -> Optional[Type]:
        """Return the root type if 'type' is optional."""
        if typing.get_origin(param_type) in (typing.Union, types.UnionType):
            args = typing.get_args(param_type)
            if len(args) == 2 and isinstance(None, args[1]):
                return args[0]
        return None

    def _get_type_metadata(self, type: Type) -> tuple[Type, Optional[Type[Choices]], bool]:
        """Get the root type, associated choices, and whether it is required."""
        if root_type := self._get_optional_type(type):
            type = root_type
            required = False
        else:
            required = True
        if issubclass(type, Choices):
            _choices, choice_type = type._get_choices()
            choices = type
            type = choice_type
        else:
            choices = None
        return type, choices, required

    def dump(self) -> dict[str, Any]:
        """Get the JSON data for registering this option with the API."""
        if self.choices:
            choice_data, _choice_type = self.choices._get_choices()
            choice_dump = [{"name": choice.name, "value": choice.value} for choice in choice_data]
        else:
            choice_dump = None
        return {
            "name": self.name,
            "description": self.description,
            "required": self.required,
            "type": self.type_value.value,
            "choices": choice_dump,
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
        if typing.get_origin(self.type) is typing.Union:  # type: ignore
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
