import io
import unittest
from cxt import *
from pprint import pprint as pp
from collections import OrderedDict as odict

ACode = TAttrs(0); ACode.set_code()
ABold = TAttrs(0); ABold.set_b()
AItalic = TAttrs(0); AItalic.set_i()

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
    p = Parser(b'  some text here\n and here\n\n')
    _, st, para = p._parse(True, 1)
    assert st == True; assert para == 2
    assert not p.s.out
    expected = b'  some text here'
    assert p.body == expected

    _, st, para = p._parse(st, para)
    assert st == True; assert para == 2
    _, st, para = p._parse(st, para)
    expected += b' and here\n'
    assert p.body == expected
    assert p.i == len(p.buf)
    assert not p.s.out

  def testInline(self):
    p = Parser(b'  text `some code ` more text\n')
    _, st, para = p._parse(True, 1)
    assert st == True; assert para == 2
    assert p.body == b' more text'
    assert len(p.s.out) == 2
    assert p.s.out == [
      text(b'  text '),
      text(b'some code ', ACode),
    ]

  def testBold(self):
    p = Parser(b'plain [b]bolded [b] plain again')
    p._parse(True, 1)
    assert p.body == b' plain again'
    assert p.s.tAttrs == TAttrs(0)
    assert p.s.out == [
      text(b'plain '),
      text(b'bolded ', ABold),
    ]

  def testCode(self):
    p = Parser(b'plain [c]some code[c] plain again [## a=foo]more code[##]')
    p._parse(True, 1)
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
    assert o[3] == text(b'more bold', ABold)
    assert o[4] == text(b' some plain')

if __name__ == '__main__':
  unittest.main()

