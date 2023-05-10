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
import os
import subprocess
import sys
from enum import Enum
from typing import Callable, Dict, List, Optional, Union

import zmq
from zmq.asyncio import Context, Socket

from pyservice import (CommandInfo, ErrorCode, FatalServiceError,
                       ServiceException, State, StateException,
                       UnknownCommandException)
from pyservice.metadata import (Argument, Arguments, Metadata, Timeout,
                                VariableLengthArguments)


class Service:
    """
    A base class for services.
    """

    def __init__(self: 'Service'):
        self.command_map: Dict[str, CommandInfo] = {}
        self.__register_common_commands()

    def __register_common_commands(self: 'Service') -> None:
        self.register_command(
            'describe',
            lambda args: self.describe(),
            Metadata(
                name='describe',
                description='Returns the description of the service.',
                timeout=Timeout.DEFAULT,
                arguments=Arguments.none(),
                returns='The description of the service.',
                errors='None'
            ))
        self.register_command(
            'list',
            lambda args: self.list(),
            Metadata(
                'list',
                'Lists the available service commands.',
                Timeout.DEFAULT,
                Arguments.none(),
                'A list of available service commands.',
                'None'))
        self.register_command(
            'help',
            lambda args: self.help_screen(),
            Metadata(
                'help',
                'Describes the available service commands.',
                Timeout.DEFAULT,
                Arguments.none(),
                'A list of strings describing the available service commands.',
                '*RuntimeError* - metadata is missing or invalid.'))
        self.register_command(
            'metadata',
            lambda args: self.metadata(args),
            Metadata(
                'metadata',
                'Returns metadata for the provided list of commands.',
                Timeout.DEFAULT,
                Arguments.variable_length(
                    Argument('command', 'The command to retrieve metadata for.')),
                'A list of metadata for the commmands in JSON',
                '''*ValueError* - arguments are empty.\\
                   *RuntimeError* - metadata is missing.'''))

    def __get_command_info(self, command: str) -> CommandInfo:
        try:
            return self.command_map[command]
        except KeyError:
            raise UnknownCommandException(command)

    async def __ok(self, array: List[str]) -> None:
        await self.socket.send_multipart([b"OK"] + [arg.encode() for arg in array])

    async def __error(self, code: Enum, message: str) -> None:
        await self.socket.send_multipart(
            [b"ERROR", code.value.encode(), message.encode()])

    def name(self) -> str:
        """
        Retrieves the name of the service.  Subclasses must override this
        method to provide a descriptive name for the service.
        """
        raise NotImplementedError()

    def description(self) -> str:
        """
        Retrieves the description of the service.  Subclasses must override
        this method to provide a description of the service.
        """
        raise NotImplementedError()

    def describe(self: 'Service') -> List[str]:
        """
        Describes the service.

        :return: A list of strings describing the service.  The first
                 string should be the name of the service, and the
                 second string should be the description of the service.
        :rtype: List[str]
        """
        return [
            self.name(),
            self.description(),
        ]

    def list(self: 'Service') -> List[str]:
        return list(self.command_map.keys())

    def help_screen(self: 'Service') -> List[str]:
        """
        Retrieves a help screen for the service.

        Returns:
            A list of strings describing the available service commands.

        Raises:
            RuntimeError: metadata is missing or invalid.
        """
        response: List[str] = []
        for command, command_info in self.command_map.items():
            metadata = command_info.get('metadata')
            if metadata and isinstance(metadata, Metadata):
                help_string = f'**{command}**\\\n'
                help_string += f'{metadata.description}\\\n'
                if metadata.timeout.value > 300:
                    help_string += 'Can take a long time to run.\\\n'
                help_string += '\\\n**Arguments**\\\n'
                match metadata.arguments.inner:
                    case None:
                        help_string += 'None\\\n'
                    case VariableLengthArguments(argument):
                        help_string += 'This function accepts one or more of the following argument:\\\n'
                        help_string += f'*{argument.name}* - {argument.description}\\\n'
                    case arguments:
                        for argument in arguments:
                            help_string += f'*{argument.name}* - {argument.description}\\\n'
                help_string += '\\\n**Returns**\\\n'
                help_string += f'{metadata.returns}\\\n\\\n'
                help_string += '**Errors**\\\n'
                help_string += metadata.errors
                response.append(help_string)
            else:
                raise RuntimeError(
                    f'metadata missing or invalid for {command}')
        return response

    def metadata(self: 'Service', arguments: List[str]) -> List[str]:
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
            return [json.dumps(self.__metadata_impl(command).to_dictionary()) for command in arguments]
        else:
            raise ValueError("Expected one or more commands as arguments")

    def __metadata_impl(self: 'Service', function_name: str) -> Metadata:
        command = self.command_map.get(function_name)
        if command:
            metadata = command.get('metadata')
            if metadata and isinstance(metadata, Metadata):
                return metadata
            else:
                raise RuntimeError(f'metadata missing for {function_name}')
        else:
            raise UnknownCommandException(function_name)

    def register_command(self, command: str, handler: Callable[[List[str]], List[str]], metadata: Metadata) -> None:
        """
        Registers a command with the service.  Replaces any existing
        command with the same name.

        Args:
            command: The name of the command.
            handler: The function to call when the command is received.
            metadata: The metadata for the command.
        """
        self.command_map[command] = {
            'handler': handler,
            'metadata': metadata
        }

    async def run(self, port: Optional[int] = None) -> None:
        """
        Runs the service asynchronously.  If port is None, the service
        will listen for requests on a random port, and will print the
        port number to stdout.  The port number will also be copied to
        the clipboard on macOS.

        :param port: The port to listen on.  If None, a random port
                     will be used.
        :type port: Optional[int]

        :return: None
        :rtype: None
        """
        context = Context.instance()

        # Create a socket for the server
        socket: Socket = context.socket(zmq.REP)
        if port is None:
            socket.bind("tcp://*:0")
            self.socket = socket

            # Print the port number to stdout
            port_bytes = socket.getsockopt(zmq.LAST_ENDPOINT)
            assert (isinstance(port_bytes, bytes))
            assigned_port: str = port_bytes.decode().rsplit(":", 1)[-1]
            print(assigned_port)
            subprocess.call(
                f'/bin/echo -n {assigned_port} | pbcopy', shell=True)
        else:
            socket.bind(f"tcp://*:{port}")
            self.socket = socket

        state: State = State.RECEIVING

        while True:
            try:
                # Wait for a request from a client
                if state == State.RECEIVING:
                    message = await socket.recv_multipart()
                    state = State.SENDING
                else:
                    raise StateException(state)

                command = message[0].decode()
                arguments = [arg.decode() for arg in message[1:]]

                print("received command", command, file=sys.stderr)

                # Process the request
                command_info = self.__get_command_info(command)
                handler = command_info.get('handler')
                if handler and callable(handler):
                    response = handler(arguments)

                    # Send the response back to the client
                    if state == State.SENDING:
                        await self.__ok(response)
                        state = State.RECEIVING
                    else:
                        raise StateException(state)
                else:
                    raise RuntimeError(
                        f'handler missing or not valid for {command}')

            except KeyboardInterrupt:
                break
            except StateException as e:
                print("Illegal state: ", e.state, file=sys.stderr)
                exit(1)
            except ServiceException as e:
                error_response = str(e)
                if state == State.SENDING:
                    await self.__error(e.error_code, e.args[0])
                    state = State.RECEIVING
                else:
                    print("Illegal state: ", state, file=sys.stderr)
                    print("While trying to respond with error message: ",
                          error_response, file=sys.stderr)
            except FatalServiceError as e:
                raise e
            except Exception as e:
                # Handle any other errors that occur during processing
                error_response = f'{type(Exception()).__module__}.{type(e).__name__}: {str(e)}'
                print(error_response, file=sys.stderr)
                if state == State.SENDING:
                    await self.__error(ErrorCode.UNCATEGORISED, error_response)
                    state = State.RECEIVING
                else:
                    print("Illegal state: ", state, file=sys.stderr)
                    print("While trying to respond with error message: ",
                          error_response, file=sys.stderr)
