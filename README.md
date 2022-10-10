# CivText: text markup for civilization

It should not take more than a few minutes to know how to read and write
documentation.

CivText is an ultra-simple markup language similar in spirit [BBCode], designed
to be as easy as possible to parse while delivering any features necessary to
the [Civboot] project.

CivText is designed to:
 * Make rendered document writing easy.
 * Make document reading of raw civdoc easy
 * Make parsing documents easy
 * Make consuming structured data from parsing CivText easy.

Because of the above there are only two special characters: brackets and
backticks.

CivText enables (for example) writing a command line utility's documentation as
a `.ct` file, parsing it and exporting it into a structed data format (aka json)
and injesting that to generate code for the args structure of a program.

**This repository is WIP**. Current progress:
  - [X] parsing text
  - [X] parsing code
  - [ ] parsing lists
  - [ ] export above to html
  - [ ] parsing tables

[BBCode]: https://en.wikipedia.org/wiki/BBCode
[Civboot]: https://civboot.org

## Example
```
This sentance has [b]bold[b] text, [i]italic[i] text, and
[b][i]bold italic[i][b] text.

[#]this is code[#], `this is also code`.

A url to [t ref=http://civboot.org]CivBoot[t], or displaying and linking the
full url: [url]http://civboot.org[url]

[t mark=myMark]
Creates a "local" mark so that this paragraph can be linked to.  How "local"
this is depends on the doc compiler, but typically it's within the same
directory.
[t]

A link to myMark would look like: [l]myMark[l]

Lists: [+]
 * bullet point
 * second bullet point
[/]

Numbered Lists: [+]
 1. first item
 2. second item
[/]

Indented lists [+]
 * Bullet point [+]
   * sub bullet point
 [/]
 * second bullet point
 * third bullet point
[/]

Checkboxes: [+]
 [X] done item
 [ ] undone item [+]
   [X] indended done item
   [ ] indended undone item
 [/]
[/]
```

## Special Character Escapes
```
This is a backtick: [`]

Doubling a bracket escapes it. [[ This is in literal brackets ]]
```

## Code Blocks
Code blocks use `[#...]`

```
[#]
This is a code
block.
   It can have multiple lines and whitespace.
[#]

[###]
This is a code block demonstrating
code blocks with custom ends.

It allows me to use [#] or even [##].

Three #'s in brackets end the code block, like this:
[###]
```

## Non-rendered blocks
```
[!]this is a comment and is not rendered[/]

Any block can end in ! and it will be "hidden"
so you can do:

[### myAttr=foo !]
this is a text block with myAttr=foo.
Code blocks are especially useful for this, since
they can contain configuration, code to run, etc.
[###]
```

## Full List of Brackets

Special characters
```
 [[   literal open bracket
 ]]   literal close bracket
 [`]  literal backtick
 `inline code` (same as markdown)
```

Other literals:
 * `[n]` literal newline `\n`
 * `[s]` literal space character, useful if spaces desired at beginning.

Text markup:
 * `[i]` italic
 * `[b]` bold
 * `[~]` strikethrough
 * `[u]` underline
 * `[:]` inline code, can use more than one `:` for open/close.
 * `[h1]` heading 1
 * `[h2]` heading 2
 * `[h3]` heading 3
 * `[!]` comment. Inner text not rendered.

Containers:

 * `[t]` starts a "text container" where attributes can be applied.
 * `[+]` starts a list. The first non-whitespace character determines the list
         type (`*`, `1.`, `[ ]`, `[X]`)
 * `[table]` starts a table.

Linking
 * `[... mark=markName]` creates a mark that can be linked to
 * `[l]` link to mark
 * `[url]` url with rendered link

Code Blocks
 * `[#]` code block, can use more than one `#` for open/close.

Attributes are added in `attr=foo` form:
 * `!` at end causes item to be "hidden"
 * mark: attribute which creates a mark that can be linked `[l]` to.
 * ref: using `ref=http://website.com` will cause the block to render a link.
 * title: adds title text.
 * l: link attribute, works same as `[l]` but adds to another block.
 * otherwise it is a "custom" attribute, some tools process these (i.e. `lang`
   for code, etc)

## Contributing

When opening a PR to submit code to this repository you must include the
following disclaimer in your first commit message:

```text
I <author> assent to license this and all future contributions to this project
under the dual licenses of the UNLICENSE or MIT license listed in the
`UNLICENSE` and `README.md` files of this repository.
```

## LICENSING

This work is part of the Civboot project and therefore primarily exists for
educational purposes. Attribution to the authors and project is appreciated but
not necessary.

Therefore this body of work is licensed using the [UNLICENSE](./UNLICENSE),
unless otherwise specified at the beginning of the source file.

If for any reason the UNLICENSE is not valid in your jurisdiction or project,
this work can be singly or dual licensed at your discression with the MIT
license below.

```text
Copyright 2021 Garrett Berg

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
