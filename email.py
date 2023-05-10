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

from dataclasses import dataclass
from typing import Dict, List, Union


class Headers(dict):
    @staticmethod
    def from_email_headers(headers: List[Dict[str, str]]) -> 'Headers':
        instance = Headers()
        for header in headers:
            instance[header["name"]] = header["value"]
        return instance

    @staticmethod
    def from_dictionary(headers: Dict[str, str]) -> 'Headers':
        instance = Headers()
        for key, value in headers.items():
            instance[key] = value
        return instance

    def __getitem__(self, key):
        return super().__getitem__(key.lower())

    def __setitem__(self, key, value):
        super().__setitem__(key.lower(), value)


@dataclass
class MimeBody:
    content_type: str
    content: str


@dataclass
class Message:
    headers: Headers
    body: Union[MimeBody, str]

    def get_body_str(self) -> str:
        if isinstance(self.body, str):
            return self.body
        else:
            raise ValueError('found unexpected a MIME message')

    def get_body_mime(self) -> MimeBody:
        if isinstance(self.body, MimeBody):
            return self.body
        else:
            raise ValueError('expected a MIME message')


@dataclass
class Thread:
    id: str
    messages: List[Message]
