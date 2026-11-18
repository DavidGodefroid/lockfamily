# Lock Family colour: coloured stock

The colour rules of every Lock Family site (lockfamily#72). A UX review
found the sites too dark and austere; this replaces the "paper and carbon,
no colour" rule of the identity. What stays: the ticket, the stamp, the
ledger rows, the three typefaces, the dark terminal.

**The idea in one line: the ticket is now printed on coloured stock.** Each
product has one accent. Its pale version is the paper of the hero and of
every second section; its saturated version is the ink of buttons, rules,
number tabs and the ticket's offset shadow. The dark theme is a dyed dark
stock, not black.

## Apply it to a product site

The same six steps in every Lock repo (lea, locksql, lockmq, lockfile,
lockhttp, locklog). Steps 1 to 3 are copies, byte for byte; nothing in them
is edited in the Lock repo.

1. **`site/assets/tokens.css`**: copy lockfamily `assets/tokens.css`.
2. **`site/assets/lock-site.css`**: copy lockfamily
   `site-kit/assets/lock-site.css`.
3. **`site/assets/logo.svg`**: copy lockfamily `assets/<lock>.svg` again
   (its dark fill follows the new `--card`).
4. **Every page** (`index.html`, the inner pages, `404.html`):
   - name the product on the root element,
     `<html lang="en" data-accent="locksql">` (as `site-kit/snippets/head.html`
     does from `{{LOCK}}`). This is the only place a site chooses its colour;
     without it a page gets the family's cobalt;
   - set both `theme-color` metas to the new `--paper`: `#fbf7ee` (light),
     `#1f1d26` (dark).
5. **`site/assets/og.png`** and **`apple-touch-icon.png`**: render them again
   from `site-kit/tools/og.html` (KIT.md step 9). The template takes the
   accent from `data-accent="{{LOCK}}"`; render with a light colour scheme.
6. **README banners** (`docs/assets/banner-light.svg`, `banner-dark.svg`):
   render them again with `site-kit/tools/banner_svg.py` (KIT.md, README).
   The tool takes the accent from `--name` (or `--accent`): the stub is the
   product's stock, the label its ink. Required: the old files carry the old
   beige and carbon.

Nothing else is required: the hero band, the tinted sections, the buttons,
the number tabs, the footer and the ticket's shadow come from the
stylesheet. Then look at every page in both schemes at 360, 768 and 1280 px
and fix what the site adds on top of the kit (its own CSS, inline styles,
images drawn for the old colours).

`data-accent` also works on any element: on the family page each Lock's row
carries its own (`<li data-accent="lockmq">`).

## Neutrals

| Token | Light | Dark | Use |
|---|---|---|---|
| `--paper` | `#fbf7ee` | `#1f1d26` | page background |
| `--paper-2` | `#f3ecdd` | `#282531` | neutral bands, inactive tabs |
| `--card` | `#fffcf5` | `#2f2c3a` | a ticket's face, panels, buttons |
| `--ink` | `#1d1b17` | `#ede6d6` | text, logos, strong rules |
| `--ink-2` | `#575146` | `#bdb5a3` | secondary text, control borders |
| `--rule` | `#b9af98` | `#5a546c` | ledger lines, perforations (decorative) |
| `--term-bg` | `#1a1814` | `#121017` | a terminal: dark in both themes |

The light paper is lighter than before (`#f4efe4`). The dark theme is no
longer near-black carbon (`#16140f`): it is a lifted aubergine grey with
the same warm cream ink, so coloured surfaces read as colour.

The status inks keep their meaning and their values: `--sign` (a human's
decision, the stamp), `--stamp` (denied), `--auto`, `--asked`, `--mask`,
`--agent`. They are for status words and the stamp only, never for
surfaces. Links and focus rings now use `--accent-ink`, not `--sign`.

## Accent tokens

Six tokens per product and per scheme, set by `data-accent`:

| Token | What it is | Where it goes |
|---|---|---|
| `--accent` | the saturated colour | fills: primary button, number tab, badge, 3-4px rules, the ticket's offset shadow |
| `--on-accent` | text on `--accent` (white in light, near-black in dark) | the label of anything filled with `--accent` |
| `--accent-ink` | the accent as text | links, the hero's key phrase, focus rings, step numbers |
| `--accent-tint` | a pale band (a deep one in dark) | every second section, the footer, notices, inline code, row hover |
| `--accent-stock` | the hero's coloured stock | the hero band, icon tiles |
| `--accent-stock-2` | the same stock, turned towards a neighbouring hue | the end of the hero's wash, nothing else |

| Product | `data-accent` | Scheme | `--accent` | `--on-accent` | `--accent-ink` | `--accent-tint` | `--accent-stock` | `--accent-stock-2` |
|---|---|---|---|---|---|---|---|---|
| lockfamily | `lockfamily` | light | `#2346d2` | `#ffffff` | `#2346d2` | `#ebeffc` | `#c8d1f7` | `#d4c8f7` |
| lockfamily | `lockfamily` | dark | `#889cf0` | `#14120e` | `#889cf0` | `#202548` | `#1d307c` | `#2b1763` |
| locksql | `locksql` | light | `#6d35d8` | `#ffffff` | `#6933cf` | `#f1ebfc` | `#d8c8f7` | `#efc8f7` |
| locksql | `locksql` | dark | `#ad8af0` | `#14120e` | `#ad8af0` | `#2f224a` | `#3e1d7c` | `#541660` |
| lockmq | `lockmq` | light | `#c9400a` | `#ffffff` | `#ad3709` | `#fcf0eb` | `#f7d5c8` | `#f7e6c8` |
| lockmq | `lockmq` | dark | `#ef9f80` | `#14120e` | `#ef9f80` | `#412420` | `#672f18` | `#42300f` |
| lockfile | `lockfile` | light | `#c21f6a` | `#ffffff` | `#af1c5f` | `#fcebf3` | `#f7c8dd` | `#f7c8f0` |
| lockfile | `lockfile` | dark | `#f18dbb` | `#14120e` | `#f18dbb` | `#401d34` | `#781c46` | `#5a1550` |
| lockhttp | `lockhttp` | light | `#0672a3` | `#ffffff` | `#066b99` | `#ebf7fc` | `#c8e8f7` | `#c8f7f1` |
| lockhttp | `lockhttp` | dark | `#80cdef` | `#14120e` | `#80cdef` | `#1a2e3f` | `#15455b` | `#0d3833` |
| locklog | `locklog` | light | `#1c7c3c` | `#ffffff` | `#1b7a3b` | `#ebfcf1` | `#c8f7d7` | `#d3f7c8` |
| locklog | `locklog` | dark | `#80efa5` | `#14120e` | `#80efa5` | `#1e302a` | `#114a24` | `#193b0e` |
| lockssh | `lockssh` | light | `#5d7500` | `#ffffff` | `#5b7300` | `#f8fceb` | `#edf7c8` | `#d5f7c8` |
| lockssh | `lockssh` | dark | `#d8ef80` | `#14120e` | `#d8ef80` | `#2b2f1e` | `#384210` | `#1b3b0e` |
| lea | `lea` | light | `#9a2bb3` | `#ffffff` | `#9128a8` | `#f9ebfc` | `#eec8f7` | `#f7c8e8` |
| lea | `lea` | dark | `#df8df1` | `#14120e` | `#df8df1` | `#382042` | `#671c78` | `#5d1646` |
| lockhub | `lockhub` | light | `#0b7a70` | `#ffffff` | `#0a7067` | `#ebfcfa` | `#c8f7f2` | `#c8e5f7` |
| lockhub | `lockhub` | dark | `#80efe5` | `#14120e` | `#80efe5` | `#1b3035` | `#104641` | `#12364c` |
| lockkit | `lockkit` | light | `#9a5f00` | `#ffffff` | `#885400` | `#fcf5eb` | `#f7e5c8` | `#f7d3c8` |
| lockkit | `lockkit` | dark | `#efc580` | `#14120e` | `#efc580` | `#382a1e` | `#533a13` | `#562514` |

`lockhub` and `lockkit` have no site today; their accents are for the
family page, the docs and the social cards.

Generated: `python3 site-kit/tools/accents.py` derives every value from one
base hue per product, refuses a set that fails a contrast rule below, and
rewrites the block in `assets/tokens.css` (`--check` in the tests,
`--table` prints the table above). To change or add an accent, edit
`ACCENTS` there; never edit the block by hand.

## Contrast rules (WCAG AA, checked by the generator and the tests)

- `--ink`, `--ink-2` and `--accent-ink` are at least 4.5:1 on `--paper`,
  `--paper-2`, `--card`, `--accent-tint`, `--accent-stock` and
  `--accent-stock-2`. Any of them may be body text on any of those grounds.
- `--on-accent` is at least 4.5:1 on `--accent`.
- `--accent` is at least 3:1 on the neutrals: enough for a rule, a border or
  a filled shape, **not** for text. Text in the accent is `--accent-ink`.
- The status inks are 4.5:1 on `--paper`, `--paper-2` and `--card` only.
  A status word on a tinted or stock ground sits on a `--card` chip or panel
  (the ticket does this).
- A wash sets `background-color` to its first stop as well as the gradient,
  so tools and tests read a real colour under the text.

## Where the colour goes

- **Hero**: a band of `--accent-stock`, edge to edge, washing to
  `--accent-stock-2`, ending on a scalloped perforation in `--paper`. Text
  is `--ink`; the key phrase is `--accent-ink`. The ticket sits on it with a
  hard offset shadow in `--accent`, like a second print pass out of register.
- **Sections**: each opens on a 3px `--accent` rule with its number in a
  filled tab. Every second section is a full-width `--accent-tint` band.
- **Buttons**: one primary per group, filled with `--accent`; the others on
  `--card` with an ink border. Hover never relies on colour alone.
- **Cards and rows**: lists stay ledgers. Colour comes from a 3px accent
  rule on top, an icon tile on `--accent-stock`, a row hover in
  `--accent-tint`; on the family page each Lock's row has a stub in that
  Lock's own stock.
- **Footer**: `--accent-tint` under a 4px `--accent` rule.
- **Header**: stays `--paper`, with a 4px `--accent` line on top and the
  current page underlined in `--accent`.

## What stays dark, what stays neutral

- Terminals, code blocks and the install box stay dark in both themes
  (`--term-bg`): `lox run` is a real terminal. Keep them to what a reader
  copies or needs to see; a page must not be mostly terminal.
- Body text stays `--ink` on a light or dyed ground. No white text on a
  saturated full-width fill, in either theme.
- The logos stay ink on card. They are not recoloured; they may sit on a
  stock tile.
- The ticket's face stays `--card` and its stamp stays `--sign`.

## Do

- Use the tokens by name; a site never writes an accent hex.
- Let one accent own a page. Another product's accent appears only where
  that product is listed (the family strip, the Locks rows).
- Put text on a tint or stock ground only in `--ink`, `--ink-2` or
  `--accent-ink`.
- Keep the wash to two neighbouring hues, large and slow; one wash per page.
- Check both schemes at 360, 768 and 1280 px, and run the site's contrast
  test.

## Do not

- No glows, blurs, glass panels, drop shadows with blur, or gradient text.
- No gradient outside the hero band (and the social card).
- No `--accent` as a text colour, no `--accent-stock` behind a status word.
- No near-black page: in the dark theme the ground is `--paper` or a dyed
  accent surface, never `#000` or the terminal's colour.
- No second accent to "liven up" a product page, and no accent on the logo.
- No motion added for colour's sake; what moves still stops under
  `prefers-reduced-motion`.
