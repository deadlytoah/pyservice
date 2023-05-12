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

from enum import Enum
from typing import Callable, Dict, List, Optional, Union

from pyservice.metadata import Metadata


class ServiceException(Exception):
    """
    An exception that indicates an error in the external API request
    or response.

    Attributes:
        message (str): The error message associated with the
        exception.
    """

    def __init__(self, error_code: Enum, message: str, context: Optional[str] = None):
        """
        Initializes a new instance of the ServiceException class.

        Args:
            message (str): The error message associated with the
            exception.
        """
        super(ServiceException, self).__init__(message)
        self.error_code = error_code
        self.context = context


class FatalServiceError(Exception):
    """
    An exception that indicates a fatal error that is difficult to
    recover from.  It should cause the service to abort.

    :param message: The error message associated with the exception.
    :type message: str
    """

    def __init__(self, message: str):
        super(FatalServiceError, self).__init__(message)


class ProtocolException(Exception):
    """
    An exception that indicates unexpected data format in the external
    API request or response.

    Attributes:
        message (str): The error message associated with the
        exception.
    """

    def __init__(self, message: str, context: Optional[str] = None):
        """
        Initializes a new instance of the ProtocolException class.

        Args:
            message (str): The error message associated with the
            exception.
        """
        super(ProtocolException, self).__init__(message, context)


class ErrorCode(Enum):
    UNKNOWN_COMMAND = "ERROR_UNKNOWN_COMMAND"
    UNCATEGORISED = "ERROR_UNCATEGORISED"


class State(Enum):
    SENDING = 0
    RECEIVING = 1


class StateException(Exception):
    def __init__(self, state):
        self.state = state


class UnknownCommandException(ServiceException):
    """
    Indicates the given command is invalid.
    """

    def __init__(self, command: str):
        super(UnknownCommandException, self).__init__(
            ErrorCode.UNKNOWN_COMMAND, command)


CommandInfo = Dict[str, Union[Callable[[List[str]], List[str]], Metadata]]
