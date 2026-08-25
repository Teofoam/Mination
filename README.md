# Weekly To-do auto-fill

Notion's repeating template generates the page every 6 days and keeps the
inline TIMELINE view. The Notion API can't create linked data-source views, so
the template stays — this script just fills in the three things Notion can't
compute: the title, the Date Range, and the six day headings in the 2×3 grid.

## Layout

```
your-repo/
├── fill_weekly_todo.py
├── test_logic.py
└── .github/
    └── workflows/
        └── notion-weekly.yml
```

## Setup

Notion renamed integrations to **connections** and moved the developer area,
so older guides (and the old `notion.so/my-integrations` link) are out of date.
The current flow:

1. **Turn on Developer Mode.** In Notion, left sidebar → `Settings` →
   `Connections`. Only a Workspace owner sees this tab. Enable Developer Mode
   there, then open *personal access tokens* from the developer section of the
   sidebar.

2. **Create the connection.** `+ New connection`. In the dialog:

   - **Authentication method: choose `Access token`, not `OAuth`.** OAuth is
     pre-selected but it's user-scoped and needs someone to click through an
     authorization flow — no good for an unattended Action. `Access token` is a
     workspace-scoped static token, which is what this script uses.
   - Picking `Access token` makes the **Redirect URIs** field disappear. It only
     exists for OAuth callbacks; you don't need to invent a placeholder URL.
   - Give it a name you'll recognise later in a page's Share menu.
   - It needs *Read content* and *Update content*.

   Then click the `•••` next to the new connection to copy the token (`ntn_…`).

   The **Personal access tokens** tab on the same page is a different thing —
   also user-scoped, also not what you want here.

3. **Share the database with it.** Open **Weekly To-do Lists** → `•••` →
   *Connections* → add your connection. Skip this and every call returns 404.

4. **Add the token as a repo secret**: Settings → Secrets and variables →
   Actions → New repository secret, named `NOTION_TOKEN`.

5. **Set your timezone** in `notion-weekly.yml` if `Asia/Shanghai` is wrong.
   It's used to turn each page's UTC creation timestamp into a local date, so
   getting it wrong can shift a block by one day.

6. **Dry run first.** Actions → *Fill Weekly To-do pages* → Run workflow →
   tick *dry_run*. It prints every change without writing anything.

Locally, on macOS/Linux:

```bash
pip install requests
NOTION_TOKEN=ntn_... DRY_RUN=1 python fill_weekly_todo.py
```

On Windows PowerShell — the `VAR=value command` prefix is bash syntax and won't
work; use `$env:` instead:

```powershell
pip install requests
$env:NOTION_TOKEN = Read-Host "Notion token"
$env:DRY_RUN = "1"
python fill_weekly_todo.py
```

`Read-Host` keeps the token out of PSReadLine's history file
(`$env:APPDATA\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt`),
which otherwise records every command you type in plain text. Clear the
variables when you're done:

```powershell
Remove-Item Env:NOTION_TOKEN, Env:DRY_RUN
```

They only live in the current window either way. Note that `DRY_RUN` is checked
for the exact string `1`, so unset it to write for real rather than setting it
to `0`.

## What it writes

For a page Notion created on 2026-08-06:

```
Name        2602.037 - 2602.042 Weekly To-do List
Date Range  2026-08-06 → 2026-08-11
headings    2602.037 | 08-06 Thu   … through …   2602.042 | 08-11 Tue
```

That's block 7 of 61 — the second row of M2, English Hyacinth.

Both numbering schemes are supported and covered by the tests; flipping
`DAY_NUMBERING` to `"month"` gives `2602.07 - 2602.12` for the same block, and
reproduces the titles of the pages that already exist.

Headings are matched by their `(J)` / `(J+3)` markers, so keep those markers in
the template. Everything else on the page is left alone.

Headings are written before the title on purpose: the title is what the script
filters on, so a run that dies halfway leaves the page eligible for the next run
rather than half-finished and invisible.

## API version

Pinned to `2025-09-03`. That release split every database into a container plus
one or more *data sources*, and moved querying from `/v1/databases/{id}/query`
to `/v1/data_sources/{id}/query`. The script resolves the data source at
startup via `GET /v1/databases/{id}` and caches it; page and block writes were
unaffected by the change.

`2022-06-28` still works for single-source databases and Notion hasn't
announced a cutoff, but an integration on the old version silently stops seeing
a database the moment anyone adds a second data source to it. Not worth the
trap for the sake of one extra GET.

## Knobs

All at the top of `fill_weekly_todo.py`:

| Constant | Default | Notes |
|---|---|---|
| `DAY_NUMBERING` | `"year"` | `"year"` → `2602.037 - 2602.042` for 8/6–8/11, i.e. day of the fiscal year, matching column A–F of the sheet. `"month"` → `2602.07 - 2602.12`, day within the fiscal month. |
| `DAY_DIGITS` | `None` | Width of the number after the dot. `None` derives it from `DAY_NUMBERING` — 3 for `"year"`, 2 for `"month"`. Set an integer to override. |
| `HEADING_FMT` | `{label} \| {d:%m-%d} {d:%a}` | Also available: `{doy}` `{dom}` `{month_name}` `{month_no}`, and `{d}` as a `datetime.date`. |
| `MONTHS` | 13 rows | Name + block count per fiscal month. |
| `FLEX_BLOCK` | `38` | The block that gives up a day in a common year. |
| `DATA_SOURCE_ID` | `""` | Empty auto-resolves. Pin one only if the database ever grows a second data source. |
| `FISCAL_START` | `(7, 1)` | |
| `BLOCK_LEN` | `6` | |

## The fiscal calendar

Transcribed from `Calendar.xlsx` / `Sheet1b` into the `MONTHS` table at the top
of the script. The year starts 1 July and is cut into **61 blocks of 6 days**;
thirteen named months each take a whole number of blocks, so a block never
straddles a month or a year boundary.

| # | Month | Blocks | Days | FY2026 |
|---|---|---|---|---|
| 1 | Galaxy Blue | 5 | 30 | 7/1 – 7/30 |
| 2 | English Hyacinth | 4 | 24 | 7/31 – 8/23 |
| 3 | Azure Blue | 5 | 30 | 8/24 – 9/22 |
| 4 | Irish Green | 4 | 24 | 9/23 – 10/16 |
| 5 | Amethyst Orchid | 5 | 30 | 10/17 – 11/15 |
| 6 | Deep Mint | 5 | 30 | 11/16 – 12/15 |
| 7 | Crystal Seas | 5 | 30 | 12/16 – 1/14 |
| 8 | Acid Lime | 5 | 29 or 30 | 1/15 – 2/12 |
| 9 | Autumn Blaze | 5 | 30 | 2/13 – 3/14 |
| 10 | Flame | 4 | 24 | 3/15 – 4/7 |
| 11 | River Blue | 5 | 30 | 4/8 – 5/7 |
| 12 | Blazing Yellow | 4 | 24 | 5/8 – 5/31 |
| 13 | Atlantis | 5 | 30 | 6/1 – 6/30 |

61 × 6 = 366. A leap fiscal year uses all of them. A common year is one day
short, and that day comes out of **block 38** — Acid Lime's last row — which
runs 5 days instead of 6. Everything else is fixed.

Both variants are in the workbook: `Sheet1b` is the common year, `Sheet1a` the
leap one. The difference is narrower than it looks:

| | Common (FY2026) | Leap (FY2027) |
|---|---|---|
| block 38 | 2/8 – 2/12, 5 days | 2/8 – 2/13, 6 days |
| M8 Acid Lime | 1/15 – 2/12, 29 days | 1/15 – 2/13, 30 days |
| M9 Autumn Blaze | 2/13 – 3/14, 30 days | 2/14 – 3/14, 30 days |
| M10 – M13 | identical | identical |

M9 starts a day later in a leap year but 29 February gets absorbed inside it, so
it still ends on 3/14 and everything downstream lands on the same calendar dates.
Only M8 changes length. The script derives all of this from `fiscal_year_length`,
so there's nothing to switch by hand.

## The once-a-year nudge

Notion's repeat is strictly every 6 days and doesn't know about block 38, so in
a common year pages start arriving one day into their block from mid-February
onward. Nothing breaks immediately — the creation date still falls inside the
right block, so the labels stay correct — but the offset accumulates a day per
common year and after about eight years it slips a whole block.

The script prints the drift and the date to re-anchor to whenever it sees a page
that didn't arrive on its block's first day. When that shows up, open the
template's repeat settings and set the start date to the date it names.
