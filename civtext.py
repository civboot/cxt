"""Civtext python module.

Parses a `.ct` file into python objects and provides mechanism to export as
HTML.
"""

import zoa
from dataclasses import dataclass, field

dictField = field(default_factory=dict)

@dataclass
class Text:
  body: str
