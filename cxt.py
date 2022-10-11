"""cxt python module.

Parses a `.cxt` file into python objects and provides mechanisms to export as
HTML and view in the terminal.
"""

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from enum import Enum

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

TOKEN_SPECIAL = {ord('['), ord(']'), ord('=')}
CMD_BOOLEANS = (b'b', b'i', b'~')

RE_CODE = re.compile(b'c|code|#+')
RE_H = re.compile(b'h[123]')

emptyAttrs = dict()

def isCode(name): return RE_CODE.match(name)
def isHdr(name):  return RE_H.match(name)
def isChng(name): return name in CMD_BOOLEANS

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

@dataclass
class ParserState:
  tAttrs: TAttrs = TAttrs(0)
  attrs: dict = field(default_factory=dict)
  out: list = field(default_factory=list)

class Pg(Enum):
  NOT_PG = 0
  IN_PG  = 1
  END_PG_MAYBE = 2
NOT_PG = Pg.NOT_PG; IN_PG = Pg.IN_PG; END_PG_MAYBE = Pg.END_PG_MAYBE

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
  def notEof(self): return self.i < len(self.buf)
  def checkEof(self, cond, s: str):
    if not cond: self.error(f'unexpected EoF waiting for: {s}')

  def expect(self, c):
    self.checkEof(self.notEof(), chr(c))
    found = self.buf[self.i]; self.i += 1
    if c != found: self.error(f'expected {chr(c)} found {chr(found)}.')

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

  def listNum(self, token):
    while self.notEof():
      c = self.buf[self.i]; self.i += 1
      if ord('0') <= c <= ord('9'):
        token.append(c)
      elif c == ord('.'):
        return token
      else:
       self.s.out.extend(token)
       self.s.out.append(c)
       return b''

  def listBox(self):
    c = self.buf[self.i]; self.i += 1
    if   c == ord('/'):             out = b'[/]'
    elif c == ord(' '):             out = b'[ ]'
    elif c in (ord('X'), ord('x')): out = b'[X]'
    else: self.i -= 2; return b''
    self.expect(ord(']'))
    return out

  def listToken(self):
    while True:
      self.checkEof(self.notEof(), '[/]')
      c = self.buf[self.i]; self.i += 1
      if c == ord(' '): pass  # skip spaces
      elif c == ord('*'):             return b'*'
      elif ord('0') <= c <= ord('9'): return numToken(bytearray([c]))
      elif c == ord('['):             return self.listBox()
      else: self.i -= 1; return b''

  def _checkCmdToken(self, t):
      if t == b'[': self.error("Did not expect: '['")
      if t == b'=': self.error("Did not expect: '='")
      if t == b']': self.error("Did not expect: ']'")

  def newCmd(self, name):
    return Cmd(name, TAttrs(self.s.tAttrs.value), CAttrs(0), dict())

  def parseCmd(self):
    name = self.cmdToken()
    if name == b']': return self.newCmd(b'')  # []
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

  def parseChng(self, cmd):
    self.handleBody()
    if   cmd.name == b'b': self.s.tAttrs.tog_b()
    elif cmd.name == b'i': self.s.tAttrs.tog_i()
    elif cmd.name == b'u': self.s.tAttrs.tog_u()
    elif cmd.name == b'~': self.s.tAttrs.tog_strike()

  def parseText(self, cmd):
    s = self.recurse(ParserState(
      out=self.s.out,
      tAttrs=cmd.tAttrs,
      attrs=dict(self.s.attrs)))
    self.s.attrs.update(cmd.attrs) # override attrs with cmd attrs
    self.parse()
    self.unrecurse(s)

  def startBullet(self, l, token):
    if not token: return
    self.handleBody()
    c = CAttrs(0)
    attrs = {}
    if token == b'*':   c.set_star()
    elif token == b'[ ]': c.set_nochk()
    elif token == b'[X]': c.set_chk()
    elif ord('0') <= token[0] <= ord('9'):
      c.set_num()
      attrs['value'] = token.decode('utf-8')
    else: assert False, f"unreachable: {token}"

    l.append(Cont(arr=self.s.out, cAttrs=c, attrs=attrs))
    self.s.out = []

  def parseList(self, cmd):
    prevS = self.recurse(ParserState(
      out=[],
      tAttrs=self.s.tAttrs,
      attrs=dict(self.s.attrs)))
    l = []
    pg = NOT_PG
    lastToken = None
    while self.notEof():
      t = self.listToken()
      if t == b'[/]': break # close
      if t:
        self.startBullet(l, lastToken)
        lastToken = t
        pg = NOT_PG
      close, pg = self.parseLine(pg)
      if close: break
    self.startBullet(l, lastToken)
    c = CAttrs(0); c.set_list()
    prevS.out.append(Cont(arr=l, cAttrs=c, attrs=cmd.attrs))
    self.unrecurse(prevS)

  def doCmd(self, cmd: Cmd) -> bool:
    if not cmd.name: return  # ignore []
    elif isCode(cmd.name): self.parseCode(cmd)
    elif cmd.name == b't': self.parseText(cmd)
    elif isChng(cmd.name): self.parseChng(cmd)
    elif cmd.name == b'+': self.parseList(cmd)
    elif isHdr(cmd.name):  pass # TODO
    elif cmd.name == b'n': self.body.extend(b'\n')
    elif cmd.name == b's': self.body.extend(b' ')
    elif cmd.name == b'`': self.body.extend(b'`')
    else: self.error(f"Unknown cmd: {cmd}")

  def parseLine(self, pg: Pg):
    """Parse the remainder of a line or until an `[/]`

    Returns: closed, pg
    """
    while self.notEof():
      c = self.buf[self.i]
      self.i += 1
      if c == ord(' ') and pg is NOT_PG: continue # skip spaces
      if c == ord('\n'):
        if   pg is NOT_PG: pass # ignore extra '\n'
        elif pg is IN_PG: pg = END_PG_MAYBE
        elif pg is END_PG_MAYBE:
          pg = NOT_PG; self.body.extend(b'\n')
        else: assert False, f"unreachable: {pg}"
        return (False, pg)
      elif pg is END_PG_MAYBE: # previous line was '\n'
        if c == ord(' '): continue # skip spaces
        self.body.extend(b' ')
      pg = IN_PG
      if c == ord('`'): self.parseCode(self.newCmd(b'`'))
      elif c == ord('['):
        cmd = self.parseCmd()
        if cmd.name == b'/':
          return (True, pg)
        self.doCmd(cmd)
      elif c == ord(']'): self.parseCloseBracket()
      else: self.body.append(c)
    return (False, pg)

  def parse(self, pg=IN_PG):
    while self.notEof():
      close, pg = self.parseLine(pg)
      if close: return
    self.handleBody()
    return self.s.out


def parse(b: bytes) -> list:
  p = Parser(b)
  out = p.parse()
  if out is None: p.error("Unexpected [/]")
  return out


def htmlText(t: Text) -> str:
  a = t.tAttrs
  start = []
  end = []
  if a.is_b():
    start.append('<b>'); end.append('</b>')
  if a.is_i():
    start.append('<i>'); end.append('</i>')
  if a.is_u():
    start.append('<u>'); end.append('</u>')
  if a.is_strike():
    start.append('<s>'); end.append('</s>')
  if a.is_code():
    start.append('<code>'); end.append('</code>')
  text = '<p>'.join(t.body.split('\n'))
  return ''.join(start) + text + ''.join(end)

def _htmlCont(cont: Cont):
  out = []
  for el in cont.arr:
    if isinstance(el, Text): out.append(htmlText(el))
    else                   : out.append(htmlCont(el))
  return '>' + ''.join(out)

def liIsOrdered(c: CAttrs):
  if c.is_star():    return False
  elif c.is_num():   return True
  elif c.is_nochk(): return False
  elif c.is_chk():   return False
  else: assert False, f'unexpected: {li}'

def htmlList(cont: Cont):
  out = []
  if not cont.arr: return
  ordered = liIsOrdered(cont.arr[0].cAttrs)
  if ordered: start = '<ol>'; end = '</ol>'
  else:       start = '<ul>'; end = '</ul>'

  for li in cont.arr:
    if liIsOrdered(li.cAttrs) != ordered:
      raise ValueError(f"change in ordering: {li}")
    if ordered: ls = f'<li value="{li.attrs["value"]}"'
    else:       ls = f'<li'
    out.append(ls + _htmlCont(li) + '</li>')
  return start + ''.join(out) + end

def htmlCont(cont: Cont) -> str:
  c = cont.cAttrs
  if c.is_t() : return '<span' + _htmlCont(cont) + '</span>'
  if c.is_h1(): return '<h1'  + _htmlCont(cont) + '</h1>'
  if c.is_h2(): return '<h2'  + _htmlCont(cont) + '</h2>'
  if c.is_h3(): return '<h3'  + _htmlCont(cont) + '</h3>'
  if c.is_list(): return htmlList(cont)


def html(els: list[El]):
  out = []
  for el in els:
    if isinstance(el, Text): out.append(htmlText(el))
    else:                    out.append(htmlCont(el))
  return out


argP = argparse.ArgumentParser(description='cxt documentation markup language.')
argP.add_argument('path', help="Path to file or directory.")
argP.add_argument('export', help="Path to export file.")

def syserr(msg):
  print("Error:", msg)
  sys.exit(1)

def cxtHtml(pth):
  if not pth.endswith('.cxt'): syserror("Can only process .cxt files")
  with open(pth, 'rb') as f: b = f.read()
  els = parse(b)
  return html(els)

def main(args):
  h = cxtHtml(args.path)
  print("Length:", len(h))
  with open(args.export, 'w') as f:
    f.write('<!DOCTYPE html>\n<html><body>\n')
    for l in h:
      f.write(l)
      f.write('\n')
    f.write('</body></html>\n')
    f.flush()
  print("Exported html at:", args.export)

if __name__ == '__main__':
  args = argP.parse_args()
  main(args)
