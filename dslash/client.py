"""Discord client type."""
import logging
import re
import traceback
import typing
from collections import defaultdict
from typing import Optional

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

logger = logging.getLogger("dslash")


class CommandClient(nextcord.Client):
    """Client capable of registering and responding to slash commands.

    This supports all the same parameters, methods and attributes as a
    `nextcord.Client`, plus a few more documented below.
    """

    application_id: int
    _commands: dict[Optional[int], dict[str, TopLevelCommand]]

    def __init__(self, guild_id: Optional[int] = None, **options: typing.Any):
        """Set up the client.

        - `guild_id` (`Optional[int]`)

          A guild ID to set by default for all commands. If this is passed, it
          will be set as the guild ID for every command unless a guild ID is set
          for that command specifically. This is useful during testing, because
          guild-specific commands update immediately, whereas global commands
          can be cached for up to an hour.
        """
        super().__init__(**options)
        self.guild_id = guild_id
        self._commands = defaultdict(dict)
        self._commands_by_id: dict[int, TopLevelCommand] = {}
        self._http: nextcord.http.HTTPClient = self._connection.http

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

    def command(
        self,
        *,
        guild_id: Optional[int] = None,
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
                channel: Channel = option(
                    'The channel to delete.', required=True)):
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
            guild_id=guild_id or self.guild_id,
            default_permission=default_permission,
            permissions=permissions,
        )

    def group(
        self,
        name: str,
        description: str,
        *,
        guild_id: Optional[int] = None,
        default_permission: bool = True,
        permissions: Permissions = None,
    ) -> SlashCommandGroup:
        """Create a new top-level command group.

        - `name` (`str`)

          The name of the command group.

        - `description` (`str`)

          A brief description of the command group.

        - `guild_id` (`Optional[int]`)

          The ID of a guild to limit the command to.

        - `default_permission` (default `True`)

          Whether or not this command should be usable for people where no
          relevant permissions have been set.

        - `permissions` (`Optional[Union[PermissionsSetter, list[PermissionsSetter]]`)

          Either a single permission or a list of permissions (or `None`, the default).

        Example usage:

        ```python
        client = CommandClient(guild_id=GUILD_ID)
        group = client.group(
            'users',
            'Commands to manage user profiles.',
            default_permission=False,
            permissions=allow_roles(ADMIN_ROLE_ID)
        )

        @group.subcommand()
        async def view(
                interaction: Interaction,
                user: User = option('The user to view.')):
            \"""View a user's profile.\"""
            ...

        @allow_roles(ADMIN_ROLE_ID)
        @group.subcommand(default_permission=False)
        async def clear(interaction: Interaction):
            \"""Clear all user profiles.\"""
            ...

        client.run(TOKEN)
        ```
        """
        return SlashCommandGroup(
            client=self,
            name=name,
            description=description,
            guild_id=guild_id or self.guild_id,
            default_permission=default_permission,
            permissions=permissions,
        )
