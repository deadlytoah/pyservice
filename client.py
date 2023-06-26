#
# IPC Library using Python and ZMQ
# Copyright (C) 2023  Hee Shin
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

import json
from typing import List

import zmq
from zmq.asyncio import Context, Socket

from .pyservice import (ErrorCode, Metadata, ProtocolException,
                        UnknownCommandException)


class TimeoutException(Exception):
    pass


class ServiceException(Exception):
    """
    Represents an error that occurred during the execution of the service
    function.

    :param error_code: The predefined error code representing this error.
    :type error_code: str
    :param reason: A more descriptive reason for the error.
    :type reason: str
    """

    def __init__(self, error_code: str, reason: str):
        self.error_code = error_code
        self.reason = reason


async def call(endpoint: str, command: str, arguments: List[str] = []) -> List[str]:
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
        TimeoutException: The service function did not respond
                          within the timeout period.
    """
    context = Context.instance()
    with context.socket(zmq.REQ) as socket:
        socket.linger = 0
        socket.connect(endpoint)

        socket.rcvtimeo = 300
        metadata = await __metadata_impl(socket, command)
        socket.rcvtimeo = metadata.timeout.value

        return await __call_impl(socket, command, arguments)


async def __metadata_impl(socket: Socket, command: str) -> Metadata:
    response = await __call_impl(socket, "metadata", [command])
    try:
        return Metadata.from_dictionary(json.loads(response[0]))
    except IndexError:
        raise ProtocolException(
            f'invalid metadata response: {response}')


async def __call_impl(socket: Socket, command: str, arguments: List[str]) -> List[str]:
    await socket.send_multipart([command.encode()] + [arg.encode() for arg in arguments])

    try:
        response = await socket.recv_multipart()
    except zmq.error.Again:
        raise TimeoutException(
            f'no response from service after {int(socket.rcvtimeo)} ms')

    if len(response) > 0:
        if response[0] == b"OK":
            return [arg.decode() for arg in response[1:]]
        elif response[0] == b"ERROR":
            if len(response) == 3:
                error_code = response[1].decode()
                error_message = response[2].decode()
                if error_code == ErrorCode.UNKNOWN_COMMAND.value:
                    raise UnknownCommandException(error_message)
                else:
                    raise ServiceException(error_code, error_message)
            else:
                raise ProtocolException(
                    f'invalid error response: {response}')
        else:
            raise ProtocolException(f'invalid response: {response}')
    else:
        raise ProtocolException(f'empty response')
