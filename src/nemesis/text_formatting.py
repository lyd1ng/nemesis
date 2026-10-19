"""
A simple text formatter to allow an easy and hopefully uniform
way of presenting data

Date:   20261017
Author: Lyding Anrie Brumm.
"""

from datetime import datetime

WHITE_SPACE = "  "


class TextFormatter(object):
    """
    For now three levels of indentation are naively supported.
    """

    def __init__(self):
        self.current_level: int = 0
        self.underlines: list[str] = ["=", "~", "-", ".", ".", "."]
        self.padding: list[int] = []

    def start_block(
        self,
        heading: str,
        padding: int = 0,
        prepend_newline: bool = True,
    ):
        """
        Start a new indented block
        """
        if prepend_newline:
            print()
        self._heading(heading)
        self.padding.append(padding)
        self.current_level += 1
        return self

    def end_block(self):
        """
        End a new indented block
        """
        self.current_level -= 1
        _ = self.padding.pop()

    def print(self, s: str) -> None:
        """
        Print a string with the right level of indentation
        """
        print(WHITE_SPACE * self.current_level + s)

    def print_multiline(self, s: str) -> None:
        """
        Print a multi-line string with the right level of indentation.
        """
        new_s = s.replace("\n", "\n" + WHITE_SPACE * self.current_level)
        print(WHITE_SPACE * self.current_level + new_s)

    def print_var(self, name: str, value: object) -> None:
        """
        Print a string with the right level of indentation
        """
        diff = self.padding[-1] - len(name) if self.padding[-1] > 0 else 0
        if diff < 0:
            raise RuntimeError(f"Value name {name} longer than padding")
        print(
            WHITE_SPACE * self.current_level
            + name
            + ":"
            + " " * diff
            + WHITE_SPACE
            + str(value)
        )

    def date(self, time: float) -> str:
        """
        Converts a float time into a human readable date string
        """
        return datetime.fromtimestamp(time).strftime("%Y-%m-%d %H:%M:%S")

    def _heading(self, heading: str):
        """
        Print a heading
        """
        underline: str = self.underlines[self.current_level]
        praefix: str = WHITE_SPACE * self.current_level
        print(praefix + heading + ":")
        print(praefix + underline * (len(heading) + 1))

    def __enter__(self):
        # That surely looks a little bit weird,
        # but the __enter__ function can remain empty
        # because the add_heading function does the trick
        # and the with block is merely used a way to represent
        # the indentation in the python code as well
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_block()
