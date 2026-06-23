import re


class _Data:
    def find(self, _path: str):
        raise LookupError


data = _Data()


def download(*_args, **_kwargs):
    return True


def sent_tokenize(text: str, language: str | None = None) -> list[str]:
    return [part for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part]
