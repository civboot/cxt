import io
import unittest
from cxt import *
from pprint import pprint as pp
from collections import OrderedDict as odict

ACode = TAttrs(0); ACode.set_code()
ABold = TAttrs(0); ABold.set_b()
AItalic = TAttrs(0); AItalic.set_i()

CList  = CAttrs(0); CList.set_list()
CLItem = CAttrs(0); CLItem.set_lItem()

def li(arr, cAttrs=CLItem, item = '*'):
  return Cont(arr, cAttrs, {'item': item})

def cList(arr, cAttrs=CList, attrs=None):
  attrs = attrs or {}
  return Cont(arr, cAttrs, attrs)

class TestParser(unittest.TestCase):
  def test_until(self):
    p = Parser(b'foo bar[c]')
    result = p.until(b'[c]')
    assert result == b'foo bar'

    p = Parser(b'a b [c d] e[c]')
    result = p.until(b'[c]')
    assert result == b'a b [c d] e'

  def testParseCmd(self):
    p = Parser(b'cmd   a   foo=bar]')
    cmd = p.parseCmd()
    assert cmd.name == b'cmd'
    assert cmd.tAttrs == TAttrs(0)
    assert cmd.cAttrs == CAttrs(0)
    assert cmd.attrs == {b'a': True, b'foo': b'bar'}

  def testParseLine(self):
    p = Parser(b'  some text here\nand here\n\n')
    _, pg = p.parseLine(NOT_PG)
    assert pg is END_PG_MAYBE
    assert not p.s.out
    expected = b'some text here'
    assert p.body == expected

    _, pg = p.parseLine(pg)
    assert pg is END_PG_MAYBE
    _, pg = p.parseLine(pg)
    expected += b' and here\n'
    assert p.body == expected
    assert p.i == len(p.buf)
    assert not p.s.out

  def testInline(self):
    p = Parser(b'  text `some code ` more text\n')
    _, pg = p.parseLine(IN_PG)
    assert pg is END_PG_MAYBE
    assert p.body == b' more text'
    assert len(p.s.out) == 2
    assert p.s.out == [
      text(b'  text '),
      text(b'some code ', ACode),
    ]

  def testBold(self):
    p = Parser(b'plain [b]bolded [b] plain again')
    p.parseLine(IN_PG)
    assert p.body == b' plain again'
    assert p.s.tAttrs == TAttrs(0)
    assert p.s.out == [
      text(b'plain '),
      text(b'bolded ', ABold),
    ]

  def testCode(self):
    p = Parser(b'plain [c]some code[c] plain again [## a=foo]more code[##]')
    p.parseLine(IN_PG)
    o = p.s.out; assert len(o) == 4
    assert o[0] == text(b'plain ')
    assert o[1] == text(b'some code', ACode)
    assert o[2] == text(b' plain again ')
    assert o[3] == text(b'more code', ACode, odict({b'a': b'foo'}))
    assert p.body == b''

  def testTextBlock(self):
    p = Parser(b'plain [b]bold [t a=foo]foo[/]\nmore bold[b] some plain')
    p.parse()
    o = p.s.out; assert len(o) == 5
    assert o[0] == text(b'plain ')
    assert o[1] == text(b'bold ', ABold)
    assert o[2] == text(b'foo', ABold, {b'a': b'foo'})
    assert o[3] == text(b' more bold', ABold)
    assert o[4] == text(b' some plain')

  def testList(self):
    p = Parser(
    b'''* item1
        * item2[/]''')
    p.parseList(Cmd(b'list', TAttrs(0), CAttrs(0), {}))
    o = p.s.out;
    assert len(o) == 1
    c = o[0]; assert c.cAttrs == CList; assert c.attrs == {}
    assert len(c.arr) == 2
    assert c.arr[0] == li([text(b'item1')])
    assert c.arr[1] == li([text(b'item2')])

  def testListNewline(self):
    p = Parser(
    b'''* item1
          continued.
        * item2

          multiline.
    [/]
    ''')
    p.parseList(Cmd(b'list', TAttrs(0), CAttrs(0), {}))
    o = p.s.out;
    assert len(o) == 1
    c = o[0]; assert c.cAttrs == CList; assert c.attrs == {}
    assert len(c.arr) == 2
    assert c.arr[0] == li([text(b'item1 continued.')])
    expected = li([text(b'item2\nmultiline.')])
    assert c.arr[1] == expected

if __name__ == '__main__':
  unittest.main()

