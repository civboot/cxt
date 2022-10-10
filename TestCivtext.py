import io
import unittest
from civtext import *

tAttrsCode = TAttrs(0); tAttrsCode.set_code()

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
    st, para = p.parseLine(True, 1)
    assert st == True; assert para == 2
    assert not p.out
    expected = b'  some text here'
    print()
    print(expected)
    print(bytes(p.body))
    assert p.body == expected

    st, para = p.parseLine(st, para)
    assert st == True; assert para == 2
    st, para = p.parseLine(st, para)
    expected += b' and here\n'
    print(expected)
    print(bytes(p.body))
    assert p.body == expected
    assert p.i == len(p.buf)
    assert not p.out

  def testInline(self):
    p = Parser(b'  text `some code ` more text\n')
    st, para = p.parseLine(True, 1)
    assert st == True; assert para == 2
    assert p.body == b' more text'
    assert len(p.out) == 2
    assert p.out[0] == text(b'  text ')
    assert p.out[1] == text(b'some code ', tAttrsCode)

  def testBold(self):
    p = Parser(b'plain [b]bolded [b] plain again')



if __name__ == '__main__':
  unittest.main()

