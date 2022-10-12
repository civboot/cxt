"""cxt python module.

Parses a `.cxt` file into python objects and provides mechanisms to export as
HTML and view in the terminal.
"""

import copy
import argparse
import os
import re
import sys
import html as pyHtml
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

TOKEN_SPECIAL = {'[', ']', '='}
CMD_BOOLEANS = ('b', 'i', '~')

RE_CODE = re.compile('c|code|#+')
RE_H = re.compile('h[123]')
RE_ALNUM = re.compile('[0-9a-z_]', re.I)

emptyAttrs = dict()

TGet   = TAttrs(0); TGet.set_get()

CText  = CAttrs(0); CText.set_t()
CH1    = CAttrs(0); CH1.set_h1()
CH2    = CAttrs(0); CH2.set_h2()
CH3    = CAttrs(0); CH3.set_h3()
CQuote = CAttrs(0); CQuote.set_quote()

def isCode(name): return RE_CODE.match(name)
def isHdr(name):  return RE_H.match(name)
def isChng(name): return name in CMD_BOOLEANS

def text(body, tAttrs=TAttrs(0), attrs=None):
  if not isinstance(body, str): body = body
  if attrs is None: attrs = emptyAttrs
  else: attrs = dict(attrs) # copy
  tAttrs = TAttrs(tAttrs.value) # copy
  return Text(body=body, tAttrs=tAttrs, attrs=attrs)

def tx(text):
  if isinstance(text, str): return text
  if isinstance(text, bool): return text
  return ''.join(text)

@dataclass
class Cmd:
  name: str
  tAttrs: TAttrs
  cAttrs: CAttrs
  attrs: dict

  def updateAttr(self, attr, value):
    attr = tx(attr)
    self.attrs[attr] = value

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
  buf: str
  mod: str = None
  i: int = 0
  line: int = 1
  body: list = field(default_factory=list)
  recursion = 0
  s: ParserState = field(default_factory=ParserState)

  # These are used by non-zoa parsers which depend on this to determine
  # whitespace behavior.
  skippedLines: int = 0
  skippedSpaces: int = 0

  ####################
  # Helpers

  def error(self, msg): raise zoa.ParseError(self.line, msg)
  def notEof(self): return self.i < len(self.buf)
  def checkEof(self, cond, s: str):
    if not cond: self.error(f'unexpected EoF waiting for: {s}')

  def expect(self, c):
    self.checkEof(self.notEof(), c)
    found = self.buf[self.i]; self.i += 1
    if c != found: self.error(f'expected {chr(c)} found {chr(found)}.')

  def recurse(self, newState=None):
    if newState is None:
      newState = ParserState(
        out=[],
        tAttrs=self.s.tAttrs,
        attrs=self.s.attrs)

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
      self.s.out.append(text(
        tx(self.body), tAttrs=self.s.tAttrs, attrs=self.s.attrs))
      self.body.clear()

  def until(self, b: str):
    out = []
    i = 0
    while i < len(b):
      self.checkEof(self.notEof(), b)
      c = self.buf[self.i]
      if b[i] == c: i += 1;
      else:         i = 0;
      out.extend(c)
      self.i += 1
    return out[:-len(b)]

  def untilClose(self):
    while True:
      self.checkEof(self.notEof(), '[/]')
      if self.parse() is None:
        break

  def cmdToken(self, alnum=False):
    """Get a token inside of command blocks.

    - This is normally a string without whitespace: 'foo-bar'
    - TODO: It can also @get a value
    - TODO: It can also be `foo bar` or [#]foo bar[#]
    """
    token = []
    while self.notEof():
      c = self.buf[self.i]
      self.i += 1
      if len(token) == 0:
        if c <= ' ': continue # skip whitespace
        if c in TOKEN_SPECIAL:
          token.append(c)
          break
      if c <= ' ' or c in TOKEN_SPECIAL:
        self.i -= 1
        break
      if alnum and not RE_ALNUM.match(c):
        self.i -= 1
        break
      token.append(c)
    self.checkEof(token, ']')
    return tx(token)

  def newCmd(self, name):
    return Cmd(name, TAttrs(self.s.tAttrs.value), CAttrs(0), dict())

  def checkCmdToken(self, t):
      if t == '[': self.error("Did not expect: '['")
      if t == '=': self.error("Did not expect: '='")
      if t == ']': self.error("Did not expect: ']'")

  def parseCmd(self):
    name = self.cmdToken()
    if name == ']': return self.newCmd('')  # []
    self.checkCmdToken(name)

    cmd = self.newCmd(name)
    name = None
    while True:
      if not name:     name = self.cmdToken()
      if name == ']': break
      self.checkCmdToken(name)

      t = self.cmdToken()
      if t == ']': break
      if t == '=':
        self.checkEof(self.notEof(), '=')
        if self.buf[self.i] == '@':
          self.i += 1; tAttrs = TGet
        else:          tAttrs = TAttrs(0)
        value = self.cmdToken()
        self.checkCmdToken(value)
        cmd.updateAttr(name, text(value, tAttrs))
        name = None  # get a new token for next name
      else:
        cmd.updateAttr(name, None)
        name = t     # reuse t as next name
    return cmd

  ####################
  # Element Parsers

  def parseCode(self, cmd):
    self.handleBody()
    cmd.tAttrs.set_code()
    if cmd.name == '`': end = '`'
    else:                end = '[' + cmd.name + ']'
    code = tx(self.until(end))
    t = text(body=code, tAttrs=cmd.tAttrs, attrs=cmd.attrs)
    self.s.out.append(t)
    if 'set' in t.attrs: return NOT_PG

  def parseChng(self, cmd):
    self.handleBody()
    if   cmd.name == 'b': self.s.tAttrs.tog_b()
    elif cmd.name == 'i': self.s.tAttrs.tog_i()
    elif cmd.name == 'u': self.s.tAttrs.tog_u()
    elif cmd.name == '~': self.s.tAttrs.tog_strike()

  def parseGet(self, cmd):
    self.handleBody()
    name = self.cmdToken(alnum=True)
    self.s.out.append(text(name, TGet))

  def parseText(self, cmd):
    attrs = dict(self.s.attrs)
    attrs.update(cmd.attrs)
    prevS = self.recurse(ParserState(
      out=[],
      tAttrs=cmd.tAttrs,
      attrs={}))
    self.parse()
    t = Cont(self.s.out, CText, attrs)
    prevS.out.append(t)
    self.unrecurse(prevS)
    if 'set' in t.attrs: return NOT_PG

  def parseRef(self, cmd):
    self.handleBody()
    ref = tx(self.until('[/]'))
    a = dict(self.s.attrs)
    a.update(cmd.attrs)
    a['r'] = text(ref)
    c = Cont([text(ref)], CText, a)
    self.s.out.append(c)
    if 'set' in c.attrs: return NOT_PG

  def parseQuote(self, cmd):
    prevS = self.recurse(ParserState(
      out=[],
      tAttrs=self.s.tAttrs,
      attrs=self.s.attrs))
    self.untilClose()
    attrs = dict(self.s.attrs); attrs.update(cmd.attrs)
    prevS.out.append(Cont(arr=self.s.out, cAttrs=CQuote, attrs=attrs))
    self.unrecurse(prevS)

  def parseHdr(self, cmd):
    if   cmd.name == 'h1': c = CH1
    elif cmd.name == 'h2': c = CH2
    elif cmd.name == 'h3': c = CH3
    else: self.error(f"Unknown header: {cmd.name}")
    prevS = self.recurse(ParserState(
      out=[],
      tAttrs=self.s.tAttrs,
      attrs=self.s.attrs))
    self.untilClose()
    attrs = dict(self.s.attrs); attrs.update(cmd.attrs)
    prevS.out.append(Cont(arr=self.s.out, cAttrs=c, attrs=attrs))
    self.unrecurse(prevS)

  ####################
  # List

  def listNum(self, token):
    while self.notEof():
      c = self.buf[self.i]; self.i += 1
      if '0' <= c <= '9':
        token.append(c)
      elif c == '.':
        return token
      else:
       self.s.out.extend(token)
       self.s.out.append(c)
       return ''

  def listBox(self):
    c = self.buf[self.i]; self.i += 1
    if   c == '/':             out = '[/]'
    elif c == ' ':             out = '[ ]'
    elif c in ('X', 'x'): out = '[X]'
    else: self.i -= 2; return ''
    self.expect(']')
    return out

  def listToken(self):
    while True:
      self.checkEof(self.notEof(), '[/]')
      c = self.buf[self.i]; self.i += 1
      if c == ' ': pass  # skip spaces
      elif c == '*':        return '*'
      elif '0' <= c <= '9': return numToken([c])
      elif c == '[':        return self.listBox()
      else: self.i -= 1; return ''

  def startBullet(self, l, token):
    if not token: return
    self.handleBody()
    c = CAttrs(0)
    attrs = {}
    if token == '*':   c.set_star()
    elif token == '[ ]': c.set_nochk()
    elif token == '[X]': c.set_chk()
    elif '0' <= token[0] <= '9':
      c.set_num()
      attrs['value'] = text(token)
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
      if t == '[/]': break # close
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

  ####################
  # Top Level Parser

  def doCmd(self, cmd: Cmd) -> Pg:
    if not cmd.name: return  # ignore []
    elif isCode(cmd.name): return self.parseCode(cmd)
    elif cmd.name == 't':  return self.parseText(cmd)
    elif isChng(cmd.name): self.parseChng(cmd)
    elif cmd.name == '+':  self.parseList(cmd);  return NOT_PG
    elif cmd.name == '"':  self.parseQuote(cmd); return NOT_PG
    elif isHdr(cmd.name):  self.parseHdr(cmd);  return NOT_PG
    elif cmd.name == 'r':  return self.parseRef(cmd)
    elif cmd.name == 'n':  self.body.append('\n')
    elif cmd.name == 's':  self.body.append(' ')
    elif cmd.name == '`':  self.body.append('`')
    elif cmd.name == '@':  self.body.append('@')
    else: self.error(f"Unknown cmd: {cmd}")

  def parseCloseBracket(self):
    self.checkEof(self.i < len(self.buf))
    c = self.buf[self.i]
    if c == ']':
      self.body.append(c)
      self.i += 1
    else: self.error("expected ']'")

  def parseLine(self, pg: Pg):
    """Parse the remainder of a line or until an `[/]`

    Returns: closed, pg
    """
    while self.notEof():
      c = self.buf[self.i]
      self.i += 1
      if c == ' ' and pg is NOT_PG: continue # skip spaces
      if c == '\n':
        if   pg is NOT_PG: pass # ignore extra '\n'
        elif pg is IN_PG: pg = END_PG_MAYBE
        elif pg is END_PG_MAYBE:
          pg = NOT_PG; self.body.append('\n')
        else: assert False, f"unreachable: {pg}"
        return (False, pg)
      elif pg is END_PG_MAYBE: # previous line was '\n'
        if c == ' ': continue # skip spaces
        self.body.append(' ')
      pg = IN_PG
      if   c == '`': self.parseCode(self.newCmd('`'))
      elif c == '@': self.parseGet(self.newCmd('@'))
      elif c == '[':
        cmd = self.parseCmd()
        if cmd.name == '/':
          return (True, pg)
        newPg = self.doCmd(cmd)
        if newPg is not None: pg = newPg
      elif c == ']': self.parseCloseBracket()
      else: self.body.append(c)
    return (False, pg)

  def parse(self, pg=IN_PG):
    while self.notEof():
      close, pg = self.parseLine(pg)
      if close: return
    self.handleBody()
    return self.s.out


def parse(b: str) -> list:
  p = Parser(b)
  out = p.parse()
  if out is None: p.error("Unexpected [/]")
  return out

def htmlCode(start, end, el):
  if not el.tAttrs.is_code(): return False
  if '\n' in el.body:
    start.append('<pre>');  end.append('</pre>')
  else:
    start.append('<code>'); end.append('</code>')
  return True

def htmlRef(start, end, el):
  ref = el.attrs.get('r')
  if ref:
    start.append(f'<a href="{ref.body}">')
    end.append('</a>')

def htmlText(t: Text) -> str:
  a = t.tAttrs
  if a.is_get() or a.is_hide(): return ''
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
  htmlRef(start, end, t)
  if htmlCode(start, end, t):
    text = pyHtml.escape(t.body)
  else:
    text = '<p>'.join(pyHtml.escape(i) for i in t.body.split('\n'))
  return tx(start) + text + tx(end)

def _htmlCont(cont: Cont):
  start = []; end = []
  htmlRef(start, end, cont)
  out = []
  for el in cont.arr:
    if isinstance(el, Text): out.append(htmlText(el))
    else                   : out.append(htmlCont(el))

  return '>' + tx(start) + tx(out) + tx(end)

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
    if ordered: ls = f'<li value="{li.attrs["value"].body}"'
    else:       ls = f'<li'
    out.append(ls + _htmlCont(li) + '</li>')
  return start + tx(out) + end

def htmlCont(cont: Cont) -> str:
  c = cont.cAttrs
  if c.is_hide() or 'set' in cont.attrs: return ''
  if c.is_t() : return '<span' + _htmlCont(cont) + '</span>'
  if c.is_h1(): return '<h1'  + _htmlCont(cont) + '</h1>'
  if c.is_h2(): return '<h2'  + _htmlCont(cont) + '</h2>'
  if c.is_h3(): return '<h3'  + _htmlCont(cont) + '</h3>'
  if c.is_list(): return htmlList(cont)
  if c.is_quote(): return '<blockquote' + _htmlCont(cont) + '</blockquote>'

def htmlVars(els, vars=None):
  if vars is None: vars = {}
  for el in els:
    name = el.attrs.get('set')
    if name is not None:
      name = name.body
      if name in vars:
        raise ValueError(f"{name} is set more than once")
      el = copy.deepcopy(el)
      el.attrs.pop('set')
      vars[name] = el
    if isinstance(el, Cont): htmlVars(el.arr)
  return vars

def replaceVar(vars, el, requireStr=False, name=None):
  if requireStr and not isinstance(el, Text):
    raise ValueError(f"vars used as attr must be Text type: {name}")

  if isinstance(el, Text) and el.tAttrs.is_get():
    var = vars[el.body]
    if requireStr:
      if isinstance(var, Cont):
        if len(var.arr) != 1 or not isinstance(var.arr[0], Text):
          raise ValueError(f"vars used as attr must have single Text item: {name}")
      var = copy.deepcopy(var.arr[0])
    else: var = copy.deepcopy(var)
    el = var
  return el

def htmlReplace(els, vars):
  for i, el in enumerate(els):
    els[i] = replaceVar(vars, el)

    for aname, attr in el.attrs.items():
      el.attrs[aname] = replaceVar(vars, attr, requireStr=True, name=aname)

    if isinstance(el, Cont):
      htmlReplace(el.arr, vars)

def html(els: list[El]):
  vars = htmlVars(els)
  htmlReplace(els, vars)

  out = []
  for el in els:
    if isinstance(el, Text):   out.append(htmlText(el))
    elif isinstance(el, Cont): out.append(htmlCont(el))
    else: raise TypeError(el)

  return out


argP = argparse.ArgumentParser(description='cxt documentation markup language.')
argP.add_argument('path', help="Path to file or directory.")
argP.add_argument('export', help="Path to export file.")

def syserr(msg):
  print("Error:", msg)
  sys.exit(1)

def cxtHtml(pth):
  if not pth.endswith('.cxt'): syserror("Can only process .cxt files")
  with open(pth, 'r') as f: b = f.read()
  els = parse(b)
  return html(els)

def main(args):
  h = cxtHtml(args.path)
  end = []
  with open(args.export, 'w') as f:
    if args.export.endswith('.html'):
      f.write('<!DOCTYPE html>\n<html><body>\n')
      end.append('</body></html>\n')
    elif args.export.endswith('.md'):
      f.write('<div>\n'); end.append('</div>')
    else: syserror(f"Unknown file type. Supported are: .html, .md")

    f.write(f'<!-- Generated by cxt.py from {args.path} -->\n')
    for l in h:
      f.write(l); f.write('\n')
    for l in end:
      f.write(l); f.write('\n')
    f.flush()
  print("Exported to:", args.export)

if __name__ == '__main__':
  args = argP.parse_args()
  main(args)
