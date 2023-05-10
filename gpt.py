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

from typing import Dict


class Message:
    """
    Represents a message in the chat.

    Use the `build_message` function to create a message of the
    appropriate role.

    :param role: The role of the message, which can be one of "system", "user", or "assistant".
    :type role: str
    :param text: The text content of the message.
    :type text: str
    """

    def __init__(self, role: str, text: str):
        self.role = role
        self.text = text

    def to_dictionary(self) -> Dict[str, str]:
        """
        Converts the message to a dictionary containing the message
        role and text content.

        Returns:
            A dictionary containing the message role and text content.
        """
        return {"role": self.role, "content": self.text}

    @staticmethod
    def from_dictionary(data: Dict[str, str]) -> 'Message':
        role = data['role']
        text = data['text']
        return Message(role=role, text=text)


class SystemMessage(Message):
    """Represents a system message."""

    def __init__(self, text: str):
        super().__init__("system", text)


class UserMessage(Message):
    """Represents a user message."""

    def __init__(self, text: str):
        super().__init__("user", text)


class AssistantMessage(Message):
    """Represents an assistant message."""

    def __init__(self, text: str):
        super().__init__("assistant", text)


def build_message(role: str, content: str) -> Message:
    """
    Returns a new instance of a message object that matches the given
    role and contains the provided content.

    Args:
        role (str): The role of the message, which can be 'system',
        'user', or 'assistant'.
        content (str): The content of the message.

    Returns:
        Message: A new instance of message with the given role that
        contains the provided content.

    Raises:
        ValueError: If the role provided is invalid.
    """
    if role == 'system':
        return SystemMessage(content)
    elif role == 'user':
        return UserMessage(content)
    elif role == 'assistant':
        return AssistantMessage(content)
    else:
        raise ValueError(f"Invalid role: {role}")
