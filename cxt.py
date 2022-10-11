"""cxt python module.

Parses a `.cxt` file into python objects and provides mechanisms to export as
HTML and view in the terminal.
"""

import os
import re
from dataclasses import dataclass, field

import zoa
from zoa import BaseParser
from zoa import MapStrStr

PWD = os.path.dirname(__file__)
with open(os.path.join(PWD, 'types.ty'), 'rb') as f:
  zparser = zoa.Parser(f.read())
zparser.parse()
tys = zparser.env.tys

TAttrs = tys[b'TAttrs']
CAttrs = tys[b'CAttrs']
Text   = tys[b'Text']
Cont   = tys[b'Cont']
El     = tys[b'El']

emptyAttrs = dict()

def text(body, tAttrs=TAttrs(0), attrs=None):
  if not isinstance(body, str): body = body.decode('utf-8')
  if attrs is None: attrs = emptyAttrs
  else: attrs = dict(attrs) # copy
  tAttrs = TAttrs(tAttrs.value) # copy
  return Text(body=body, tAttrs=tAttrs, attrs=attrs)

@dataclass
class Cmd:
  name: bytes
  tAttrs: TAttrs
  cAttrs: CAttrs
  attrs: dict

  def updateAttr(self, attr, value):
    if isinstance(attr, bytearray):  attr = bytes(attr)
    if isinstance(value, bytearray): value = bytes(value)
    if attr == b'code': self.tAttrs.code = value
    else:               self.attrs[attr] = value


TOKEN_SPECIAL = {ord('['), ord(']'), ord('=')}
CMD_BOOLEANS = (b'b', b'i', b'~')

RE_CODE = re.compile(b'#+')
RE_H = re.compile(b'h[123]')

@dataclass
class ParserState:
  tAttrs: TAttrs = TAttrs(0)
  attrs: dict = field(default_factory=dict)
  out: list = field(default_factory=list)

@dataclass
class Parser:
  buf: bytearray
  mod: bytes = None
  i: int = 0
  line: int = 1
  body: bytearray = field(default_factory=bytearray)
  recursion = 0
  s: ParserState = field(default_factory=ParserState)

  # These are used by non-zoa parsers which depend on this to determine
  # whitespace behavior.
  skippedLines: int = 0
  skippedSpaces: int = 0

  def error(self, msg): raise zoa.ParseError(self.line, msg)
  def checkEof(self, cond, s: str):
    if not cond: self.error(f'unexpected EoF waiting for: {s}')

  def recurse(self, newState):
    self.handleBody()
    self.recursion += 1
    prevState = self.s
    self.s = newState
    return prevState

  def unrecurse(self, oldState):
    if not self.recursion: self.error("Unclosed [/]")
    self.handleBody()
    self.recursion -= 1
    self.s = oldState

  def handleBody(self):
    if self.body:
      self.s.out.append(text(self.body, tAttrs=self.s.tAttrs, attrs=self.s.attrs))
      self.body.clear()

  def until(self, b: bytes):
    out = bytearray()
    i = 0
    while i < len(b):
      if self.i >= len(self.buf): self.eof(b)
      c = self.buf[self.i]
      if b[i] == c: i += 1;
      else:         i = 0;
      out.append(c)
      self.i += 1
    return out[:-len(b)]

  def notEof(self): return self.i < len(self.buf)

  def cmdToken(self):
    token = bytearray()
    while self.notEof():
      c = self.buf[self.i]
      self.i += 1
      if len(token) == 0:
        if c <= ord(' '): continue # skip whitespace
        if c in TOKEN_SPECIAL:
          token.append(c)
          break
      if c <= ord(' ') or c in TOKEN_SPECIAL:
        self.i -= 1
        break
      token.append(c)
    self.checkEof(token, ']')
    return token

  def _checkCmdToken(self, t):
      if t == b'[': self.error("Did not expect: '['")
      if t == b'=': self.error("Did not expect: '='")
      if t == b']': self.error("Did not expect: ']'")

  def newCmd(self, name):
    return Cmd(name, TAttrs(self.s.tAttrs.value), CAttrs(0), dict())

  def parseCmd(self):
    name = self.cmdToken()
    self._checkCmdToken(name)

    cmd = self.newCmd(name)
    name = None
    while True:
      if not name:     name = self.cmdToken()
      if name == b']': break
      self._checkCmdToken(name)

      t = self.cmdToken()
      if t == b']': break
      if t == b'=':
        value = self.cmdToken()
        self._checkCmdToken(value)
        cmd.updateAttr(name, value)
        name = None  # get a new token for next name
      else:
        cmd.updateAttr(name, True)
        name = t     # reuse t as next name
    return cmd

  def parseCloseBracket(self):
    self.checkEof(self.i < len(self.buf))
    c = self.buf[self.i]
    if c == ord(']'):
      self.body.append(c)
      self.i += 1
    else: self.error("expected ']'")

  def parseCode(self, cmd):
    self.handleBody()
    cmd.tAttrs.set_code()
    if cmd.name == b'`': end = b'`'
    else:                end = b'[' + cmd.name + b']'
    code = self.until(end).decode('utf-8')
    self.s.out.append(text(body=code, tAttrs=cmd.tAttrs, attrs=cmd.attrs))

  def parseText(self, cmd):
    s = self.recurse(ParserState(
      out=self.s.out,
      tAttrs=cmd.tAttrs,
      attrs=dict(self.s.attrs)))
    self.s.attrs.update(cmd.attrs) # override attrs with cmd attrs
    self.parse()
    self.unrecurse(s)

  def parseList(self, cmd):
    prevS = self.recurse(ParserState(
      out=[],
      tAttrs=self.s.tAttrs,
      attrs=dict(self.s.attrs)))

    # TODO: use cmd.attrs and cAttrs
    while self.notEof():
      self.parse(started=False, paragraph=0)
      if close: break

  def doCmd(self, cmd: Cmd) -> bool:
    if cmd.name in (b'c', b'code') or RE_CODE.match(cmd.name):
      self.parseCode(cmd)
    elif cmd.name == b'`': self.body.extend(b'`')
    elif cmd.name == b't': self.parseText(cmd)
    elif cmd.name in CMD_BOOLEANS:
      self.handleBody()
      if cmd.name == b'b':   self.s.tAttrs.tog_b()
      elif cmd.name == b'i': self.s.tAttrs.tog_i()
      elif cmd.name == b'~': self.s.tAttrs.tog_strike()
    elif RE_H.match(cmd.name):
      pass
    else: self.error(f"Unknown cmd: {cmd}")

  def _parse(self, started, paragraph):
    """Parse the remainder of a line or until an `[/]`

    Params:
      started: whether text has started after header
      paragraph: 0=not pg, 1=in pg, 2=might be ending pg

    Returns: close, started, paragraph
    """
    while self.notEof():
      c = self.buf[self.i]
      self.i += 1
      if c == ord('\n'):
        if not started: pass
        elif paragraph == 1: paragraph = 2 # could be ending paragraph
        elif paragraph == 2: paragraph = 0; self.body.extend(b'\n')
        else:                               self.body.extend(b'\n')
        return (False, started, paragraph)
      started = True
      if c == ord('`'): self.parseCode(self.newCmd(b'`'))
      elif c == ord('['):
        cmd = self.parseCmd()
        if cmd.name == b'/':
          return (True, started, paragraph)
        self.doCmd(cmd)
      elif c == ord(']'): self.parseCloseBracket()
      else:
        paragraph = 1
        self.body.append(c)
    return (False, started, paragraph)

  def parse(self, started=True, paragraph=1):
    while self.notEof():
      close, started, paragraph = self._parse(started, paragraph)
      if close: return
    self.handleBody()
