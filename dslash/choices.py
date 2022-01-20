"""Interface for specifying option choices."""
from __future__ import annotations

from typing import Any, Generic, Optional, Type, TypeVar, Union

ChoiceType = Union[str, int, float]
CT = TypeVar("CT")


class Choice(Generic[CT]):
    """A single choice as part of an option's choices."""

    def __init__(self, name: str, value: CT):
        """Store the choice attributes."""
        self.name = name
        self.value = value

    def __repr__(self) -> str:
        """Return the string representation of the choice."""
        return f"Choice(name={self.name!r}, value={self.value!r})"


class ChoicesMeta(type, Generic[CT]):
    """A metaclass for choices."""

    @classmethod
    def attribute_to_choice(
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
    def attributes_to_choices(
        cls,
        attrs: dict[str, Any],
    ) -> tuple[dict[str, Choice[CT]], Type[CT]]:
        """Get a mapping of attr name to chocie and the choice type for a choices class."""
        choices = {}
        choice_type = None
        for name, value in attrs.items():
            if name.startswith("_"):
                continue
            if not (choice_and_type := cls.attribute_to_choice(name, value)):
                continue
            choice, this_type = choice_and_type
            if choice_type is None:
                choice_type = this_type
            elif choice_type != this_type:
                raise TypeError(
                    f"All choices must be of the same type, but {name} is "
                    f"{this_type} and previous choices were {choice_type}."
                )
            choices[name] = choice
        if choice_type is None:
            raise ValueError("There must be at least one choice.")
        return choices, choice_type  # type: ignore

    def __new__(
        cls,
        class_name: str,
        parents: tuple[type],
        attrs: dict[str, Any],
        abstract: bool = False,
    ) -> type:
        """Create a new command group class."""
        if abstract:
            return super().__new__(cls, class_name, parents, attrs)
        attrs_to_choices, choice_type = cls.attributes_to_choices(attrs)
        for attr in attrs_to_choices:
            del attrs[attr]
        value_map = {}
        name_map = {}
        attrs["_value_map"] = value_map
        attrs["_name_map"] = name_map
        attrs["_choice_data"] = [
            {"name": choice.name, "value": choice.value} for choice in attrs_to_choices.values()
        ]
        attrs["_choice_type"] = choice_type
        new_cls = super().__new__(cls, class_name, parents, attrs)
        for name, choice_data in attrs_to_choices.items():
            choice = new_cls(choice_data.name, choice_data.value)
            value_map[choice_data.value] = choice
            name_map[name] = choice
        return new_cls

    def __getattr__(cls: Type[Choices[CT]], name: str) -> Choices[CT]:
        """Get a choice by name."""
        return cls._name_map[name]  # type: ignore


class Choices(Generic[CT], metaclass=ChoicesMeta, abstract=True):
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

    # Discord choice value -> choice instance (class attribute)
    _value_map: dict[CT, Choice[CT]]

    # Python choice name -> choice instance (class attribute)
    _name_map: dict[str, Choice[CT]]

    # Discord JSON choice data (class attribute)
    _choice_data: dict[str, dict[str, Union[str, CT]]]

    # Choice type (class attribute)
    _choice_type: Type[CT]

    # Discord choice name (instance attribute)
    name: str

    # Discord choice value (instance attribute)
    value: CT

    @classmethod
    def _get_by_value(cls, value: CT) -> Choice[CT]:
        """Get a choice by value."""
        return cls._value_map[value]

    def __init__(self, name: str, value: CT):
        """Store the attributes of a single choice."""
        self.name = name
        self.value = value

    def __repr__(self) -> str:
        """Return the string representation of the choice."""
        return f"{self.__class__.__name__}(name={self.name!r}, value={self.value!r})"
