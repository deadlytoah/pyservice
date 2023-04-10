
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
