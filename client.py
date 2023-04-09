

import json
from typing import List
from .pyservice import ErrorCode, Metadata, ProtocolException, UnknownCommandException
import zmq


def call(endpoint: str, command: str, arguments: List[str] = []) -> List[str]:
    """
    Calls a service function.

    Args:
        endpoint: The endpoint to call.
        command: The name of the service function to call.
        arguments: The arguments to pass to the service function.

    Returns:
        The response from the service function.

    Raises:
        UnknownCommandException: The given command is invalid.
        ProtocolException: The response from the service function
        was invalid.
    """
    context = zmq.Context.instance()
    with context.socket(zmq.REQ) as socket:
        socket.linger = 0
        socket.connect(endpoint)

        socket.rcvtimeo = 300
        metadata = __metadata_impl(socket, command)
        socket.rcvtimeo = metadata.timeout.value

        return __call_impl(socket, command, arguments)


def __metadata_impl(socket: zmq.Socket, command: str) -> Metadata:
    response = __call_impl(socket, "metadata", [command])
    if len(response) > 0:
        return Metadata.from_dictionary(json.loads(response[1]))
    else:
        raise ProtocolException(
            f'invalid metadata response: {response}')


def __call_impl(socket: zmq.Socket, command: str, arguments: List[str]) -> List[str]:
    socket.send_multipart([command.encode()] + [arg.encode()
                          for arg in arguments])

    response = socket.recv_multipart()
    if len(response) > 0:
        if response[0] == b"OK":
            return [arg.decode() for arg in response[1:]]
        elif response[0] == b"ERROR":
            if len(response) == 3:
                error_code = response[1].decode()
                error_message = response[2].decode()
                if error_code == ErrorCode.UNKNOWN_COMMAND.value:
                    raise UnknownCommandException(command)
                else:
                    raise ProtocolException(
                        f'error {error_code}: {error_message}')
            else:
                raise ProtocolException(
                    f'invalid error response: {response}')
        else:
            raise ProtocolException(f'invalid response: {response}')
    else:
        raise ProtocolException(f'empty response')
