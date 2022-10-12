import io
import unittest
from cxt import *
from pprint import pprint as pp
from collections import OrderedDict as odict

ACode = TAttrs(0); ACode.set_code()
ABold = TAttrs(0); ABold.set_b()
AItalic = TAttrs(0); AItalic.set_i()

CList  = CAttrs(0); CList.set_list()
CStar  = CAttrs(0); CStar.set_star()
CNum   = CAttrs(0); CNum.set_num()
CNochk = CAttrs(0); CNochk.set_nochk()
CChk   = CAttrs(0); CChk.set_chk()

def li(arr, cAttrs = CStar, attrs = None):
  attrs = attrs or {}
  return Cont(arr, cAttrs, attrs)

def cList(arr, cAttrs=CList, attrs=None):
  attrs = attrs or {}
  return Cont(arr, cAttrs, attrs)

class TestParser(unittest.TestCase):
  def testUntil(self):
    p = Parser('foo bar[c]')
    result = tx(p.until('[c]'))
    assert result == 'foo bar'

    p = Parser('a b [c d] e[c]')
    result = tx(p.until('[c]'))
    assert result == 'a b [c d] e'

  def testParseCmd(self):
    p = Parser('cmd   a   foo=bar]')
    cmd = p.parseCmd()
    assert cmd.name == 'cmd'
    assert cmd.tAttrs == TAttrs(0)
    assert cmd.cAttrs == CAttrs(0)
    # FIXME: text(True)
    assert cmd.attrs == {'a': None, 'foo': text('bar')}

  def testParseLine(self):
    p = Parser('  some text here\nand here\n\n')
    _, pg = p.parseLine(NOT_PG)
    assert pg is END_PG_MAYBE
    assert not p.s.out
    expected = 'some text here'
    assert tx(p.body) == expected

    _, pg = p.parseLine(pg)
    assert pg is END_PG_MAYBE
    _, pg = p.parseLine(pg)
    expected += ' and here\n'
    assert tx(p.body) == expected
    assert p.i == len(p.buf)
    assert not p.s.out

  def testInline(self):
    p = Parser('  text `some code ` more text\n')
    _, pg = p.parseLine(IN_PG)
    assert pg is END_PG_MAYBE
    assert tx(p.body) == ' more text'
    assert len(p.s.out) == 2
    assert p.s.out == [
      text('  text '),
      text('some code ', ACode),
    ]

  def testBold(self):
    p = Parser('plain [b]bolded [b] plain again')
    p.parseLine(IN_PG)
    assert tx(p.body) == ' plain again'
    assert p.s.tAttrs == TAttrs(0)
    assert p.s.out == [
      text('plain '),
      text('bolded ', ABold),
    ]

  def testCode(self):
    p = Parser('plain [c]some code[c] plain again [## a=foo]more code[##]')
    p.parseLine(IN_PG)
    o = p.s.out; assert len(o) == 4
    assert o[0] == text('plain ')
    assert o[1] == text('some code', ACode)
    assert o[2] == text(' plain again ')
    assert o[3] == text('more code', ACode, odict({'a': text('foo')}))
    assert p.body == []

  def testGet(self):
    o = parse('get @that variable')
    assert len(o) == 3
    assert o[0] == text('get ')
    assert o[1] == text('that', TGet)
    assert o[2] == text(' variable')

  def testGetAttr(self):
    o = parse('[t ref=@attr]some text[/]')
    assert len(o) == 1
    attrs = {'ref': text('attr', TGet)}
    expected = Cont([text('some text')], CText, attrs)
    assert o[0] == expected

  def testTextBlock(self):
    p = Parser('plain [b]bold [t a=foo]foo[/]\nmore bold[b] some plain')
    o = p.parse(); assert len(o) == 5
    assert o[0] == text('plain ')
    assert o[1] == text('bold ', ABold)
    assert o[2] == Cont([text('foo', ABold)], CText, {'a': text('foo')})
    assert o[3] == text(' more bold', ABold)
    assert o[4] == text(' some plain')

  def testRef(self):
    o = parse('[r]reference[/][t r=tref]text[/]'); assert len(o) == 2
    expected = Cont([text('reference')], CText, {'r': text('reference')})
    assert o[0] == expected
    expected = Cont([text('text')], CText, {'r': text('tref')})
    assert o[1] == expected

  def testList(self):
    p = Parser(
    '''* item1
        * item2[/]''')
    p.parseList(Cmd('list', TAttrs(0), CAttrs(0), {}))
    o = p.s.out;
    assert len(o) == 1
    c = o[0]; assert c.cAttrs == CList; assert c.attrs == {}
    assert len(c.arr) == 2
    assert c.arr[0] == li([text('item1')])
    assert c.arr[1] == li([text('item2')])

  def testQuote(self):
    o = parse('''["]This is a quote[/]''')
    assert len(o) == 1;
    expected = Cont([text("This is a quote")], CQuote, {})
    assert expected == o[0]

  def testListNewline(self):
    p = Parser(
    '''* item1
          continued.
        * item2

          multiline.
    [/]
    ''')
    p.parseList(Cmd('list', TAttrs(0), CAttrs(0), {}))
    o = p.s.out;
    assert len(o) == 1
    c = o[0]; assert c.cAttrs == CList; assert c.attrs == {}
    assert len(c.arr) == 2
    assert c.arr[0] == li([text('item1 continued.')])
    expected = li([text('item2\nmultiline.')])
    assert c.arr[1] == expected

class TestHtml(unittest.TestCase):
  def testText(self):
    p = Parser('plain `some code` [b]bold[b] plain [## a=foo]more code[##]')
    o = p.parse()
    result = ''.join(html(o))
    expected = 'plain <code>some code</code> <b>bold</b> plain <code>more code</code>'
    assert expected == result

  def testRef(self):
    o = parse('a url: [r]http://foo.txt[/]') # [t r=tref]text[/]')
    result = ''.join(html(o))
    expected = 'a url: <span><a href="http://foo.txt">http://foo.txt</a></span>'
    assert expected == result

    o = parse('[r]reference[/]') # [t r=tref]text[/]')

  def testH1(self):
    o = parse('[h1]header[/]\nsome text')
    result = ''.join(html(o))
    expected = '<h1>header</h1>some text'
    assert expected == result

  def testList(self):
    o = parse('''[+]
    * item1
    * item2[/]''')
    result = ''.join(html(o))
    expected = '<ul><li>item1</li><li>item2</li></ul>'
    assert expected == result

  def testQuote(self):
    o = parse('''["]This is a [b]quote[b][/]''')
    result = ''.join(html(o))
    expected = '<blockquote>This is a <b>quote</b></blockquote>'
    assert expected == result

  def testBlock(self):
    o = parse('code block:\n[###]\nA code\nblock\n[###]\n')
    result = ''.join(html(o))
    expected = 'code block: <pre>\nA code\nblock\n</pre>'
    assert expected == result

  def testSetGet(self):
    o = parse('[r set=goo]http://google.com[/]\n\nSearch at @goo.')
    result = ''.join(html(o))
    expected = (
      'Search at <span>'
        '<a href="http://google.com">http://google.com</a>'
      '</span>.'
    )
    assert expected == result

  def testGetAttr(self):
    o = parse(
        '[r set=url]http://google.com[/]\n'
        '[r set=foo]not rendered[/]\n\n'
        'You can find out at [t r=@url]the url[/].')
    result = ''.join(html(o))
    expected = (
      'You can find out at <span>'
        '<a href="http://google.com">the url</a>'
      '</span>.'
    )
    assert expected == result


if __name__ == '__main__':
  unittest.main()

