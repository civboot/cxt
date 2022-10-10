"""Civtext python module.

Parses a `.ct` file into python objects and provides mechanism to export as
HTML.
"""

import os
import re
from dataclasses import dataclass, field

import zoa
from zoa import BaseParser
from zoa import MapStrDyn

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

emptyAttrs = MapStrDyn()

def text(body, tAttrs=TAttrs(0), attrs=None):
  if not isinstance(body, str): body = body.decode('utf-8')
  if not attrs: attrs = emptyAttrs
  tAttrs = TAttrs(tAttrs.value) # copy
  return Text(body=body, tAttrs=tAttrs, attrs=attrs)

@dataclass
class Cmd:
  name: bytes
  tAttrs: TAttrs
  cAttrs: CAttrs
  attrs: MapStrDyn

  def updateAttr(self, attr, value):
    if isinstance(attr, bytearray): attr = bytes(attr)
    if attr == b'code': self.tAttrs.code = value
    else:               self.attrs[attr] = value


TOKEN_SPECIAL = {ord('['), ord(']'), ord('=')}
CMD_BOOLEANS = {b'b', b'i', b'~'}

RE_CODE = re.compile('#+')

@dataclass
class Parser:
  buf: bytearray
  mod: bytes = None
  i: int = 0
  line: int = 1
  body: bytearray = field(default_factory=bytearray)
  tAttrs = TAttrs(0)
  out: list = field(default_factory=list)

  # These are used by non-zoa parsers which depend on this to determine
  # whitespace behavior.
  skippedLines: int = 0
  skippedSpaces: int = 0

  def error(self, msg): raise zoa.ParseError(self.line, msg)
  def checkEof(self, cond, s: str):
    if not cond: self.error(f'unexpected EoF waiting for: {s}')

  def handleBody(self):
    if self.body:
      self.out.append(text(self.body, tAttrs=self.tAttrs))
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

  def cmdToken(self):
    token = bytearray()
    while self.i < len(self.buf):
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
    return Cmd(name, TAttrs(self.tAttrs.value), CAttrs(0), MapStrDyn())

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
    else:                end = b'[{}]'.format(cmd.name)
    code = self.until(end).decode('utf-8')
    self.out.append(text(body=code, tAttrs=cmd.tAttrs, attrs=cmd.attrs))

  def doCmd(self, cmd: Cmd):
    if cmd.name in (b'c', b'code') or RE_CODE.match(cmd.name):
      self.parseCode(cmd)
    elif cmd.name == b'`': self.body.extend(b'`')
    elif cmd.name in CMD_BOOLEANS:
      self.handleBody()
      if cmd.name == b'b':
        self.tAttrs.set_b(     not self.tAttrs.get_b())
      elif cmd.name == b'i':
        self.tAttrs.set_i(     not self.tAttrs.get_i())
      elif cmd.name == b'~':
        self.tAttrs.set_strike(not self.tAttrs.get_strike())
    else: self.error(f"Unknown cmd: {cmd}")

  def parseLine(self, started, paragraph):
    """Parse the remainder of a line.

    Params:
      started: whether text has started after header
      paragraph: 0=not pg, 1=in pg, 2=might be ending pg
    """
    while self.i < len(self.buf):
      c = self.buf[self.i]
      self.i += 1
      if c == ord('\n'):
        if not started: pass
        elif paragraph == 1: paragraph = 2 # could be ending paragraph
        elif paragraph == 2: paragraph = 0; self.body.extend(b'\n')
        else:                               self.body.extend(b'\n')
        return (started, paragraph)
      elif c == ord('`'): self.parseCode(self.newCmd(b'`'))
      elif c == ord('['):
        cmd = self.parseCmd()
        self.doCmd(cmd)
      elif c == ord(']'): self.parseCloseBracket()
      else:
        started = True
        paragraph = 1
        self.body.append(c)
    return started, paragraph

