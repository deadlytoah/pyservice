import json
import subprocess
import sys
from typing import Callable, Dict, List, Union

import zmq
from zmq.asyncio import Context, Socket

from pyservice import (CommandInfo, ErrorCode, Metadata, State, StateException,
                       Timeout, UnknownCommandException)


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
                arguments='None',
                returns='The description of the service.',
                errors='None'
            ))
        self.register_command(
            'help',
            lambda args: self.help_screen(),
            Metadata(
                'help',
                'Describes available service commands.',
                Timeout.DEFAULT,
                'None',
                'A list of strings describing the available service commands.',
                '*RuntimeError* - metadata is missing or invalid.'))
        self.register_command(
            'metadata',
            lambda args: self.metadata(args),
            Metadata(
                'metadata',
                'Describes the given command.',
                Timeout.DEFAULT,
                'A list of commands to describe.',
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

    async def __error(self, code: ErrorCode, message: str) -> None:
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
                help_string += f'{metadata.arguments}\\\n\\\n'
                help_string += '**Returns**\\\n'
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
            raise UnknownCommandException(command)

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

    async def run(self) -> None:
        """
        Runs the service asynchronously.  The service will listen for
        requests on a random port, and will print the port number to
        stdout.  The port number will also be copied to the clipboard
        on macOS.
        """
        context = Context.instance()

        # Create a socket for the server
        socket: Socket = context.socket(zmq.REP)
        socket.bind("tcp://*:0")
        self.socket = socket

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
            except UnknownCommandException as e:
                error_response = str(e)
                if state == State.SENDING:
                    await self.__error(ErrorCode.UNKNOWN_COMMAND, "unknown command")
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
                    await self.__error(ErrorCode.UNCATEGORISED, error_response)
                    state = State.RECEIVING
                else:
                    print("Illegal state: ", state, file=sys.stderr)
                    print("While trying to respond with error message: ",
                          error_response, file=sys.stderr)