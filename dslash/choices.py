"""Interface for specifying option choices."""
from __future__ import annotations

import functools
from typing import Any, Generic, Optional, Type, TypeVar, Union

ChoiceType = Union[str, int, float]
CT = TypeVar("CT")


class Choice(Generic[CT]):
    """A single choice as part of an option's choices."""

    name: str
    value: CT

    def __init__(self, name: str, value: CT):
        """Store the choice attributes."""
        self.name = name
        self.value = value

    def __repr__(self) -> str:
        """Return the string representation of the choice."""
        return f"Choice(name={self.name!r}, value={self.value!r})"


class Choices(Generic[CT]):
    """A class containing each of the choices for some option.

    Example usage:

    ```python
    class IcecreamFlavors(Choices):
        vanilla = "Vanilla"
        chocolate = "Chocolate"
        strawberry = "Strawberry"
    ```

    Or for integer options:

    ```python
    class Rating(Choices):
        one = Choice("Very bad", 1)
        two = Choice("Bad", 2)
        three = Choice("OK", 3)
        four = Choice("Good", 4)
        five = Choice("Great", 5)
    ```
    """

    name: str
    value: CT

    @classmethod
    def _get_attr_choice(
        cls, name: str, value: Any
    ) -> Optional[tuple[Choice[ChoiceType], Type[ChoiceType]]]:
        """Convert an attribute to a choice."""
        if isinstance(value, str):
            # 'name' is the name of the Python attribute, which should be the
            # internally-used *value* for the choice, and 'value' is the value
            # of the Python attribute, which should be the user-displayed
            # *name* of the choice.
            return Choice(name=value, value=name), str
        elif isinstance(value, Choice):
            return value, type(value.value)
        return None

    @classmethod
    @functools.cache
    def _get_choices(cls) -> tuple[list[Choice[CT]], Type[CT]]:
        """Get the JSON data for registering these choices with the API."""
        choices = []
        choice_type = None
        for name, value in cls.__dict__.items():
            if name.startswith("_"):
                continue
            if not (choice_and_type := cls._get_attr_choice(name, value)):
                continue
            choice, this_type = choice_and_type
            if choice_type is None:
                choice_type = this_type
            elif choice_type != this_type:
                raise TypeError(
                    f"All choices must be of the same type, but {name} is "
                    f"{this_type} and previous choices were {choice_type}."
                )
            choices.append(choice)
        if choice_type is None:
            raise ValueError("There must be at least one choice.")
        return choices, choice_type  # type: ignore

    @classmethod
    @functools.cache
    def _find_choice(cls, value: CT) -> Choices[CT]:
        """Find the choice with the given value."""
        choices, _choice_type = cls._get_choices()
        for choice in choices:
            if choice.value == value:
                return cls(choice.name, choice.value)
        raise ValueError(f"Recieved {cls.__name__!r} choice with invalid value {value!r}.")

    def __init__(self, name: str, value: CT):
        """Store the attributes of a single choice."""
        self.name = name
        self.value = value

    def __repr__(self) -> str:
        """Return the string representation of the choice."""
        return f"{self.__class__.__name__}(name={self.name!r}, value={self.value!r})"
