from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Union, assert_never


class Timeout(Enum):
    DEFAULT = 300
    LONG = 30000


@dataclass
class Argument:
    """
    Represents an argument to a service command.
    """

    name: str
    description: str

    def to_dictionary(self) -> Dict[str, Any]:
        """
        Converts the argument to a dictionary.
        """
        return {'name': self.name, 'description': self.description}

    @staticmethod
    def from_dictionary(dictionary: Dict[str, Any]) -> 'Argument':
        """
        Constructs an argument from a dictionary.
        """
        return Argument(dictionary['name'], dictionary['description'])


@dataclass
class VariableLengthArguments:
    """
    Represents arguments of variable length of the same type.
    """
    inner: Argument


@dataclass
class Arguments:
    """
    Represents the complete set of arguments to a service command.

    This can be either a list of arguments, an empty set or arguments of
    variable length of the same type.

    You can use the constructor to build the first two kinds.  The third kind
    is built using the static method `variable_length`.  The static method
    `none` is a convenience method for building an empty set of arguments.

    :param arguments: The arguments to the service command.
    :type arguments: List[Argument]
    """
    inner: None | List[Argument] | VariableLengthArguments

    def __init__(self, *arguments: Argument):
        if len(arguments) == 0:
            self.inner = None
        else:
            self.inner = list(arguments)

    @staticmethod
    def none() -> 'Arguments':
        """
        Returns an empty set of arguments.
        """
        return Arguments()

    @staticmethod
    def variable_length(argument: Argument) -> 'Arguments':
        """
        Constructs an instance of the class representing arguments of
        variable length of the same type.
        """
        instance = Arguments()
        instance.inner = VariableLengthArguments(argument)
        return instance

    def to_dictionary(self) -> Dict[str, Any]:
        """
        Converts the arguments represented by self to a dictionary.

        The dictionary has the following structure:

        .. code-block:: python

            {
                'type': 'none' | 'variable_length' | 'list',
                'value': None | Argument | List[Argument]
            }

        The value of the `type` key determines the type of the arguments.  If
        the type is `none`, then the value is `None`.  If the type is
        `variable_length`, then the value is a dictionary representing the
        argument of variable length.  If the type is `list`, then the value is
        a list of dictionaries representing the arguments.

        :return: The arguments as a dictionary.
        :rtype: Dict[str, Any]
        """
        match self.inner:
            case None:
                return {'type': 'none'}
            case VariableLengthArguments(inner):
                return {'type': 'variable_length', 'argument': inner.to_dictionary()}
            case list:
                return {'type': 'list', 'arguments': [item.to_dictionary() for item in list]}

    @staticmethod
    def from_dictionary(dictionary: Dict[str, Any]) -> 'Arguments':
        """
        Constructs an instance of the class from a dictionary.
        """
        match dictionary['type']:
            case 'none':
                return Arguments()
            case 'variable_length':
                return Arguments.variable_length(Argument.from_dictionary(dictionary['argument']))
            case 'list':
                list: List[dict[str, str]] = dictionary['arguments']
                return Arguments(*[Argument.from_dictionary(item) for item in list])
            case unreachable:
                assert_never(unreachable)


@dataclass
class Metadata:
    name: str
    description: str
    timeout: Timeout
    arguments: Arguments
    returns: str
    errors: str

    def to_dictionary(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'timeout': self.timeout.value,
            'arguments': self.arguments.to_dictionary(),
            'returns': self.returns,
            'errors': self.errors
        }

    @staticmethod
    def from_dictionary(dictionary: Dict[str, Any]) -> 'Metadata':
        return Metadata(
            name=dictionary['name'],
            description=dictionary['description'],
            timeout=Timeout(dictionary['timeout']),
            arguments=Arguments.from_dictionary(dictionary['arguments']),
            returns=dictionary['returns'],
            errors=dictionary['errors']
        )
