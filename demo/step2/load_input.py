# load_input.py
"""Utility to load the raw LLMEntityLinker output file.

Provides a simple function :func:`load_file` that reads the file and returns a list of
lines (stripped of trailing newlines). It also removes any leading/trailing empty
lines for convenience.
"""

from pathlib import Path
from typing import List


def load_file(path: str) -> List[str]:
    """Read *path* and return a list of its lines.

    Parameters
    ----------
    path: str
        Path to the text file produced by LLMEntityLinker.

    Returns
    -------
    List[str]
        The file lines with ``"\n"`` removed and stripped of surrounding whitespace.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Input file not found: {path}")
    # Read the file using UTF‑8 (the LLM output should be UTF‑8 encoded).
    lines = [line.rstrip("\n") for line in p.read_text(encoding="utf-8").splitlines()]
    # Remove leading/trailing blank lines but keep internal empty lines – they may be
    # useful for section separation.
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines
