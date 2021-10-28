# DSlash

![Version: 0.3.2](https://img.shields.io/badge/Version-0.3.2-red?style=flat-square)
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
import random
import logging
import traceback
import typing

from nextcord import Embed, Interaction, Member, Role
from dslash import Choices, CommandClient, SlashCommandInvokeError, allow_roles, option


GUILD_ID = ...
ADMIN_ROLE_ID = ...
TOKEN = ...

logging.basicConfig(level=logging.INFO)
client = CommandClient(guild_id=GUILD_ID)


@client.event
async def on_ready():
    print(f'Logged in as {client.user}.')


@client.command()
async def roll(interaction: Interaction, sides: typing.Optional[int]):
    """Roll a dice.

    :param sides: How many sides (default 6).
    """
    value = random.randint(1, sides or 6)
    await interaction.response.send_message(f'You got: {value}')


images = client.group('images', 'Cute image commands.')


@images.subcommand()
async def cat(interaction: Interaction):
    """Get a cat image."""
    await interaction.response.send_message(
        embed=Embed().set_image(url='https://cataas.com/cat')
    )


@images.subcommand()
async def dog(interaction: Interaction):
    """Get a dog image."""
    await interaction.response.send_message(
        embed=Embed().set_image(url='https://placedog.net/500?random')
    )


@images.subcommand(name='any')
async def any_(interaction: Interaction):
    """Get any random image."""
    await interaction.response.send_message(
        embed=Embed().set_image(url='https://picsum.photos/600')
    )


admin = client.group(
    'admin',
    'Admin-only commands.',
    default_permission=False,
    permissions=allow_roles(ADMIN_ROLE_ID)
)
roles = admin.subgroup('roles', 'Commands to manage roles.')


@roles.subcommand(name='del')
async def del_(interaction: Interaction, role: Role):
    """Delete a role.

    :param role: The role to delete.
    """
    await role.delete()
    await interaction.response.send_message('Deleted the role.', ephemeral=True)


@allow_roles(ADMIN_ROLE_ID)
@client.command(default_permission=False)
async def ban(interaction: Interaction, user: Member):
    """Ban a user.

    :param user: The user to ban.
    """
    await user.ban()
    await interaction.response.send_message('Banned the user.', ephemeral=True)


class RPSChoices(Choices):
    rock = 'Rock'
    paper = 'Paper'
    scissors = 'Scissors'
    gun = 'Gun'


@client.command()
async def rps(interaction: Interaction, choice: RPSChoices):
    """Play rock, paper, scissors.

    :param choice: Your choice.
    """
    if choice == RPSChoices.gun:
        await interaction.response.send_message("That's cheating!")
    else:
        await interaction.response.send_message(f'You picked {choice.name}.')


client.run(TOKEN)
```

## Planned Features

- Class-based command groups, like `nextcord.ext.commands` cogs.

Compatibility with `nextcord.ext.commands` is not planned.

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
