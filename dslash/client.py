"""Discord client type."""
import logging
import re
import traceback
import typing
from collections import defaultdict
from typing import Any, Callable, Coroutine, Literal, Optional, Type, Union, overload

import nextcord
import nextcord.http
from nextcord.types.interactions import ApplicationCommand, EditApplicationCommand

from .commands import (
    Permissions,
    SlashCommandConstructor,
    SlashCommandGroup,
    SlashCommandInvokeError,
    TopLevelCommand,
)

if typing.TYPE_CHECKING:
    from .groups import CommandGroup

logger = logging.getLogger("dslash")
AsyncFunc = Callable[..., Coroutine]
AsyncWrapper = Callable[[AsyncFunc], AsyncFunc]

GUILD_ID_DEFAULT = "default"
GuildID = Union[None, int, Literal["default"]]


class CommandClient(nextcord.Client):
    """Client capable of registering and responding to slash commands.

    This supports all the same parameters, methods and attributes as a
    `nextcord.Client`, plus a few more documented below.
    """

    application_id: int
    _commands: dict[Optional[int], dict[str, TopLevelCommand]]

    def __init__(
        self,
        guild_id: Optional[int] = None,
        *,
        custom_interaction: Optional[Callable[[nextcord.Interaction], typing.Any]] = None,
        **options: typing.Any,
    ):
        """Set up the client.

        - `guild_id` (`Optional[int]`)

          A guild ID to set by default for all commands. If this is passed, it
          will be set as the guild ID for every command unless a guild ID is set
          for that command specifically. This is useful during testing, because
          guild-specific commands update immediately, whereas global commands
          can be cached for up to an hour.

        - `custom_interaction` (`Optional[Callable[[nextcord.Interaction], Any]]`)

          A callable which transforms an interaction into a custom interaction
          type to be passed as the first argument to commands.
        """
        super().__init__(**options)
        self.guild_id = guild_id
        self.custom_interaction = custom_interaction
        self._commands = defaultdict(dict)
        self._commands_by_id: dict[int, TopLevelCommand] = {}
        self._http: nextcord.http.HTTPClient = self._connection.http
        self._event_handlers: dict[str, list[AsyncFunc]] = defaultdict(list)

    def dispatch(self, event_name: str, *args: Any, **kwargs: Any) -> None:
        """Dispatch an event and call additional handlers."""
        super().dispatch(event_name, *args, **kwargs)
        for handler in self._event_handlers[event_name]:
            self._schedule_event(handler, event_name, *args, **kwargs)

    @overload
    def listener(self, value: AsyncFunc) -> AsyncFunc:
        """Register an event listener for the event with the function's name.

        The function should be named "on_" followed by the event name, for example:

        ```python
        @client.listener
        async def on_message(message):
            ...
        ```

        This would register a handler for the "message" event.
        """
        ...

    @overload
    def listener(self, value: str) -> AsyncWrapper:
        """Register an event listener with the given name.

        For example:

        ```python
        @client.listener("message")
        async def my_message_handler(message):
            ...
        ```
        """
        ...

    def listener(self, value: Union[str, AsyncFunc]) -> Union[AsyncFunc, AsyncWrapper]:
        """Register an event listener."""
        if isinstance(value, str):

            def wrapper(handler: AsyncFunc) -> AsyncFunc:
                self.add_listener(value, handler)
                return handler

            return wrapper
        elif callable(value):
            self.add_listener(value.__name__.removeprefix("on_"), value)
            return value
        else:
            raise TypeError(
                "CommandClient.listener should be passed an event name or event handler."
            )

    def add_listener(self, event_name: str, handler: AsyncFunc):
        """Register a function as an event listener."""
        self._event_handlers[event_name].append(handler)

    async def on_interaction(self, interaction: nextcord.Interaction):
        """Handle a slash command interaction being sent.

        If you override this method, or regiser an `on_interaction` listener
        with `@client.event`, you must make sure to call this method, or
        slash commands will not work.
        """
        if interaction.type == nextcord.InteractionType.application_command:
            await self.wait_until_ready()
            if (not interaction.data) or ("id" not in interaction.data):
                return
            command_id = int(interaction.data["id"])  # type: ignore
            try:
                await self._commands_by_id[command_id](interaction)
            except SlashCommandInvokeError as exc:
                self.dispatch("slash_command_error", interaction, exc)

    async def on_slash_command_error(
        self, interaction: nextcord.Interaction, error: SlashCommandInvokeError
    ):
        """Handle an error while invoking a slash command.

        You can override this method, or register an `on_slash_command_error`
        listener with `@client.event` to handle errors yourself.
        """
        # Log the error:
        original = error.original
        message = "".join(
            traceback.format_exception(type(original), original, original.__traceback__)
        )
        logger.error(f"An error occured while handling a command:\n{message}")
        # Send an error message:
        await interaction.response.send_message(
            embed=nextcord.Embed(title="Command error!", description=str(error), color=0xFF0000),
            ephemeral=True,
        )

    async def login(self, token: str):
        """Log in with a token and register all commands.

        If you run the client with `client.start`, you do not need to call this
        yourself, it will be called automatically.
        """
        data = await self.http.static_login(token.strip())
        if not self._connection.application_id:
            self._connection.application_id = int(data["id"])
        logger.info("Syncing commands...")
        self._commands[None] = self._commands.get(None, {})
        for scope, commands in self._commands.items():
            await self._update_scope_commands(scope, commands)
        logger.info("Finished syncing commands.")

    async def _update_scope_commands(
        self, scope: typing.Optional[int], commands: dict[str, TopLevelCommand]
    ):
        """Update all commands for a scope and track permissions."""
        command_data = [command.dump() for command in commands.values()]
        try:
            created_commands = await self._register_scope_commands(
                scope, command_data  # type: ignore
            )
        except nextcord.HTTPException as error:
            self._handle_register_error(error, command_data)  # type: ignore
        permission_data = defaultdict(list)
        for command_data in created_commands:
            command = commands[command_data["name"]]
            command_id = int(command_data["id"])
            self._commands_by_id[command_id] = command
            command.id = command_id
            for guild_id, permissions in command.permissions.items():
                permission_data[guild_id].append({"id": command.id, "permissions": permissions})
        for guild_id, permissions in permission_data.items():
            if not permissions:
                continue
            await self._http.bulk_edit_guild_application_command_permissions(
                self.application_id, guild_id, permissions
            )

    async def _register_scope_commands(
        self, scope: typing.Optional[int], commands: list[EditApplicationCommand]
    ) -> list[ApplicationCommand]:
        """Register commands for a guild or globally."""
        if scope:
            logger.debug(f"Registering commands for guild {scope}.")
            return await self._http.bulk_upsert_guild_commands(
                self.application_id,
                scope,
                commands,
            )
        logger.debug("Registering global commands.")
        return await self._http.bulk_upsert_global_commands(
            self.application_id,
            commands,
        )

    def _handle_register_error(
        self, error: nextcord.HTTPException, commands: list[EditApplicationCommand]
    ):
        """Replace references to commands by index to references by name."""
        if error.status == 400:
            command_indices = set(re.findall(r"In\s(\d).", error.args[0]))
            error_string = error.args[0]
            for index in command_indices:
                error_command = commands[int(index)]
                error_string = error_string.replace(
                    f"In {index}",
                    "In {name}".format(**error_command),
                )
            error.args = (error_string, *error.args[1:])
        raise error

    def _store_command(self, command: TopLevelCommand):
        """Store a command to be registered on login."""
        self._commands[command.guild_id][command.name] = command

    def command(
        self,
        *,
        guild_id: GuildID = GUILD_ID_DEFAULT,
        default_permission: bool = True,
        name: Optional[str] = None,
        description: Optional[str] = None,
        permissions: Permissions = None,
    ) -> SlashCommandConstructor:
        """Register a new top-level slash command.

        - `guild_id` (`Optional[int]`)

          The ID of a guild to limit the command to.

        - `default_permission` (default `True`)

          Whether or not this command should be usable for people where no
          relevant permissions have been set.

        - `name` (`Optional[str]`)

          The name of the command. Defaults to the name of the function
          associated with it.

        - `description` (`Optional[str]`)

          A description of the command. Defaults to the first line of the
          docstring of the function associated with it.

        - `permissions`
          (`Optional[Union[PermissionsSetter, list[PermissionsSetter]]`)

          Either a single permission or a list of permissions (or `None`, the
          default). These can also be applied as decorators.

        This is intended to be used as a decorator. For example:

        ```python
        client = CommandClient()

        @client.command()
        async def flip(interaction: Interaction):
            \"""Flip a coin.\"""
            outcome = random.choice(['heads', 'tails'])
            await interaction.response.send_message(f'You got: {outcome}.')

        client.run(TOKEN)
        ```

        Example of setting more parameters:

        ```python
        @client.command(name='del', default_permission=False)
        @allow_roles(ADMIN_ROLE_ID, guild_id=GUILD_ID)
        async def del_(
                interaction: Interaction,
                channel: Channel = option('The channel to delete.')):
            \"""Delete a channel.\"""
            await channel.delete()
            await interaction.response.send_message(
                'Deleted that channel.',
                ephemeral=True
            )
        ```
        """
        return SlashCommandConstructor(
            client=self,
            name=name,
            description=description,
            guild_id=self.guild_id if guild_id == GUILD_ID_DEFAULT else guild_id,
            default_permission=default_permission,
            permissions=permissions,
        )

    def group(self, group: Union[SlashCommandGroup, Type["CommandGroup"]]) -> SlashCommandGroup:
        """Register a top-level command group.

        Example usage:

        ```python
        client = CommandClient(guild_id=GUILD_ID)

        @client.group
        @allow_roles(ADMIN_ROLE_ID)
        class Profiles(CommandGroup, default_permission=False):
            \"""Commands to manage user profiles.\"""

            @subcommand()
            async def create(self, interaction: Interaction, user: User, age: int):
                \"""Create a new profile for someone.

                :user: The user to create the profile for.
                :age: The age of the user, in years.
                \"""
                ...

            @subcommand()
            async def delete(self, interaction: Interaction, user: User):
                \"""Delete someone's profile.

                :user: The person who's profile you want to delete.
                \"""
                ...

        client.run(TOKEN)
        ```
        """
        # The metaclass of SlashCommandGroup means that the name type checkers
        # think points to the type itself will in fact point to an instance of
        # SlashCommandGroup.
        group_: SlashCommandGroup = group  # type: ignore
        if group_.guild_id == GUILD_ID_DEFAULT:
            group_.guild_id = self.guild_id
        self._store_command(group_)
        return group_
