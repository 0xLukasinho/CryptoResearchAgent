from dataclasses import dataclass


@dataclass(frozen=True)
class Article:
    title: str
    author: str
    date: str
    text: str
    url: str
