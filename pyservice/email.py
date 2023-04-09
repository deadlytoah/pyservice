
from dataclasses import dataclass
from typing import Dict, List, Union


class Headers(dict):
    def __init__(self, headers: List[Dict[str, str]]):
        super().__init__()
        for header in headers:
            self[header["name"]] = header["value"]


@dataclass
class MimeBody:
    content_type: str
    content: str


@dataclass
class Message:
    header: Headers
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
    id: int
    messages: List[Message]
