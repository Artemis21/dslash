# DSlash

![Version: 0.5.1](https://img.shields.io/badge/Version-0.5.1-red?style=flat-square)
[![Code Style: black](https://img.shields.io/badge/Code%20Style-black-black?style=flat-square)](https://github.com/psf/black)
[![License: MIT](https://img.shields.io/badge/License-MIT-orange?style=flat-square)](./LICENSE)
[![PyPI: dslash](https://img.shields.io/badge/PyPI-dslash-green?style=flat-square)](https://pypi.org/project/dslash)
![Python: ^3.9](https://img.shields.io/badge/python-%5E3.9-blue?style=flat-square)

A library which supplements [Nextcord](https://github.com/nextcord/nextcord)
(a fork of Discord.py) by adding support for slash commands.

Documentation is still a work in progress, and the library should currently be
considered unstable.

You can install it using pip, eg. `pip install dslash`.

## Example

```python
import logging
import random
import typing

from dslash import Choices, CommandClient, CommandGroup, CommandSubGroup, allow_roles, subcommand
from nextcord import Embed, Interaction, Member, Role

GUILD_ID = ...
ADMIN_ROLE_ID = ...
TOKEN = ...

logging.basicConfig(level=logging.INFO)
client = CommandClient(guild_id=GUILD_ID)


@client.event
async def on_ready():
    print(f"Logged in as {client.user}.")


@client.command()
async def roll(interaction: Interaction, sides: typing.Optional[int]):
    """Roll a dice.

    :param sides: How many sides (default 6).
    """
    value = random.randint(1, sides or 6)
    await interaction.response.send_message(f"You got: {value}")


@client.group
class Images(CommandGroup):
    """Cute image commands."""

    @subcommand()
    async def cat(self, interaction: Interaction):
        """Get a cat image."""
        await interaction.response.send_message(
            embed=Embed().set_image(url="https://cataas.com/cat")
        )

    @subcommand()
    async def dog(self, interaction: Interaction):
        """Get a dog image."""
        await interaction.response.send_message(
            embed=Embed().set_image(url="https://placedog.net/500?random")
        )

    @subcommand(name="any")
    async def any_(self, interaction: Interaction):
        """Get any random image."""
        await interaction.response.send_message(
            embed=Embed().set_image(url="https://picsum.photos/600")
        )


@client.group
@allow_roles(ADMIN_ROLE_ID)
class Admin(CommandGroup, default_permissions=False):
    """Admin-only commands."""

    class Roles(CommandSubGroup):
        """Commands to manage roles."""

        @subcommand(name="del")
        async def del_(self, interaction: Interaction, role: Role):
            """Delete a role.

            :param role: The role to delete.
            """
            await role.delete()
            await interaction.response.send_message("Deleted the role.", ephemeral=True)


@allow_roles(ADMIN_ROLE_ID)
@client.command(default_permission=False)
async def ban(interaction: Interaction, user: Member):
    """Ban a user.

    :param user: The user to ban.
    """
    await user.ban()
    await interaction.response.send_message("Banned the user.", ephemeral=True)


class RPSChoices(Choices):
    rock = "Rock"
    paper = "Paper"
    scissors = "Scissors"
    gun = "Gun"


@client.command()
async def rps(interaction: Interaction, choice: RPSChoices):
    """Play rock, paper, scissors.

    :param choice: Your choice.
    """
    if choice == RPSChoices.gun:
        await interaction.response.send_message("That's cheating!")
    else:
        await interaction.response.send_message(f"You picked {choice.name}.")


client.run(TOKEN)
```

## Development

As well as Python 3.9+, this project requires Poetry for development.
[Click this link for installation instructions](https://python-poetry.org/docs/master/#installation),
or:

- #### \*nix (Linux/MacOS)

  `curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py | python -`

- #### Windows Powershell

  `(Invoke-WebRequest -Uri https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py -UseBasicParsing).Content | python -`

Once you have Poetry installed:

1. **Create a virtual environment:** `poetry shell`
2. **Install dependencies:** `poetry install`

The following commands are then available:

- `poe format` - Run auto-formatting and linting.

Prefix these with `poetry run` if outside of the Poetry shell.
