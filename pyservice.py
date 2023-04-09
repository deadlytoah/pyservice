import json
import subprocess
import sys
import zmq

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Union


class ProtocolException(Exception):
    """
    An exception that indicates unexpected data format in the external
    API request or response.

    Attributes:
        message (str): The error message associated with the
        exception.
    """

    def __init__(self, message: str):
        """
        Initializes a new instance of the ProtocolException class.

        Args:
            message (str): The error message associated with the
            exception.
        """
        super(ProtocolException, self).__init__(message)


class ErrorCode(Enum):
    UNKNOWN_COMMAND = "ERROR_UNKNOWN_COMMAND"
    UNCATEGORISED = "ERROR_UNCATEGORISED"


class State(Enum):
    SENDING = 0
    RECEIVING = 1


class StateException(Exception):
    def __init__(self, state):
        self.state = state


class UnknownCommandException(Exception):
    """
    Indicates the given command is invalid.
    """

    def __init__(self, command):
        super(UnknownCommandException, self).__init__(
            f'unknown command {command}')
        self.command = command


class Timeout(Enum):
    DEFAULT = 300
    LONG = 30000


@dataclass
class Metadata:
    name: str
    description: str
    timeout: Timeout
    arguments: str
    returns: str
    errors: str

    def to_dictionary(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'timeout': self.timeout.value,
            'arguments': self.arguments,
            'returns': self.returns,
            'errors': self.errors
        }


def ok(socket, array):
    socket.send_multipart([b"OK"] + [arg.encode() for arg in array])


def error(socket, code, message):
    socket.send_multipart([b"ERROR", code.value.encode(), message.encode()])


def list_commands(arguments: List[str]) -> List[str]:
    return list(command_map().keys())


def help_screen(arguments: List[str]) -> List[str]:
    response: List[str] = []
    for command, command_info in command_map().items():
        metadata = command_info.get('metadata')
        if metadata and isinstance(metadata, Metadata):
            help_string = f'**{command}**\\\n'
            help_string += f'{metadata.description}\\\n'
            if metadata.timeout.value > 300:
                help_string += 'Can take a long time to run.\\\n'
            help_string += '\\\n**Arguments**\\\n'
            help_string += f'{metadata.arguments}\\\n\\\n'
            help_string += '**Returns**\\\n'
            help_string += f'{metadata.returns}\\\n\\\n'
            help_string += '**Errors**\\\n'
            help_string += metadata.errors
            response.append(help_string)
        else:
            raise RuntimeError(f'metadata missing or invalid for {command}')
    return response


def metadata(arguments: List[str]) -> List[str]:
    """
    Retrieves metadata for specified service functions.

    Args:
        arguments: A list of names of the service functions to
        retrieve metadata for.

    Returns:
        A list of metadata for the specified service functions, as a
        JSON-encoded string.

    Raises:
        ValueError: arguments are empty.
        RuntimeError: metadata is missing.
    """
    if len(arguments) > 0:
        return [json.dumps(__metadata_impl(command).to_dictionary()) for command in arguments]
    else:
        raise ValueError("Expected one or more commands as arguments")


def __metadata_impl(function_name: str) -> Metadata:
    command = command_map().get(function_name)
    if command:
        metadata = command.get('metadata')
        if metadata and isinstance(metadata, Metadata):
            return metadata
        else:
            raise RuntimeError(f'metadata missing for {function_name}')
    else:
        raise UnknownCommandException(command)


__command_map: Dict[str, Dict[str, Union[Callable[[List[str]], List[str]], Metadata]]] = {
    "help": {
        'handler': help_screen,
        'metadata': Metadata('help',
                             'Describes available service commands.',
                             Timeout.DEFAULT,
                             'None',
                             'A list of strings describing the available service commands.',
                             '*RuntimeError* - metadata is missing or invalid.'),
    },
    "metadata": {
        'handler': metadata,
        'metadata': Metadata('metadata',
                             'Describes the given command.',
                             Timeout.DEFAULT,
                             'A list of commands to describe.',
                             'A list of metadata for the commmands in JSON',
                             '''*ValueError* - arguments are empty.\\
                                    *RuntimeError* - metadata is missing.'''),
    },
}


def command_map() -> Dict[str, Dict[str, Union[Callable[[List[str]], List[str]], Metadata]]]:
    return __command_map


def register(command: str, handler: Callable[[List[str]], List[str]], metadata: Metadata) -> None:
    __command_map[command] = {
        'handler': handler,
        'metadata': metadata
    }


def service_main() -> None:
    context = zmq.Context.instance()

    # Create a socket for the server
    socket: zmq.Socket = context.socket(zmq.REP)
    socket.bind("tcp://*:0")

    # Print the port number to stdout
    port_bytes = socket.getsockopt(zmq.LAST_ENDPOINT)
    assert (isinstance(port_bytes, bytes))
    port: str = port_bytes.decode().rsplit(":", 1)[-1]
    print(port)
    subprocess.call(f'/bin/echo -n {port} | pbcopy', shell=True)

    state: State = State.RECEIVING

    while True:
        try:
            # Wait for a request from a client
            if state == State.RECEIVING:
                message = socket.recv_multipart()
                state = State.SENDING
            else:
                raise StateException(state)

            command = message[0].decode()
            arguments = [arg.decode() for arg in message[1:]]

            print("received command", command, file=sys.stderr)

            # Process the request
            command_info = command_map().get(command)
            if command_info:
                handler = command_info.get('handler')
                if handler and callable(handler):
                    response = handler(arguments)

                    # Send the response back to the client
                    if state == State.SENDING:
                        ok(socket, response)
                        state = State.RECEIVING
                    else:
                        raise StateException(state)
                else:
                    raise RuntimeError(
                        f'handler missing or not valid for {command}')
            else:
                raise UnknownCommandException(f'unknown command {command}')

        except KeyboardInterrupt:
            break
        except StateException as e:
            print("Illegal state: ", e.state, file=sys.stderr)
            exit(1)
        except UnknownCommandException as e:
            error_response = str(e)
            if state == State.SENDING:
                error(socket, ErrorCode.UNKNOWN_COMMAND, "unknown command")
                state = State.RECEIVING
            else:
                print("Illegal state: ", state, file=sys.stderr)
                print("While trying to respond with error message: ",
                      error_response, file=sys.stderr)
        except Exception as e:
            # Handle any errors that occur during processing
            error_response = f'{type(Exception()).__module__}.{type(e).__name__}: {str(e)}'
            print(error_response, file=sys.stderr)
            if state == State.SENDING:
                error(socket, ErrorCode.UNCATEGORISED, error_response)
                state = State.RECEIVING
            else:
                print("Illegal state: ", state, file=sys.stderr)
                print("While trying to respond with error message: ",
                      error_response, file=sys.stderr)
