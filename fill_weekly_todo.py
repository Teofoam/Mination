#!/usr/bin/env python3
"""
Fill in auto-generated Weekly To-do List pages in Notion.

Division of labour
------------------
Notion's repeating database template creates the page every 6 days and keeps
the inline TIMELINE linked view (the Notion API cannot create linked data
source views). This script runs on a schedule, finds any page still carrying
the placeholder title, and writes the three things Notion can't compute:
the title, the Date Range, and the six day headings in the 2x3 grid.

The fiscal calendar
-------------------
Transcribed from Calendar.xlsx / Sheet1b. The year starts 1 July and is cut
into 61 consecutive 6-day blocks. Thirteen named "months" each occupy a whole
number of blocks, so no block ever straddles a month or a year boundary:

    61 blocks x 6 days = 366

A leap fiscal year (one containing a 29-day February) uses all 366. A common
year is one day short, and that day comes out of block 38 -- the last row of
Acid Lime, 8-12 February -- which runs 5 days instead of 6. Every other block
is always 6 days, and the year always closes on 30 June.

Environment
-----------
NOTION_TOKEN   internal integration token (required)
LOCAL_TZ       IANA tz used to interpret page creation times
DRY_RUN        "1" to print what would change without writing
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

# --------------------------------------------------------------------------
# Fiscal calendar  (from Calendar.xlsx / Sheet1b)
# --------------------------------------------------------------------------

FISCAL_START = (7, 1)   # 1 July
BLOCK_LEN = 6

# (fiscal month name, number of 6-day blocks it occupies)
MONTHS: list[tuple[str, int]] = [
    ("Galaxy Blue", 5),       # M1
    ("English Hyacinth", 4),  # M2
    ("Azure Blue", 5),        # M3
    ("Irish Green", 4),       # M4
    ("Amethyst Orchid", 5),   # M5
    ("Deep Mint", 5),         # M6
    ("Crystal Seas", 5),      # M7
    ("Acid Lime", 5),         # M8   <- contains the flex block
    ("Autumn Blaze", 5),      # M9
    ("Flame", 4),             # M10
    ("River Blue", 5),        # M11
    ("Blazing Yellow", 4),    # M12
    ("Atlantis", 5),          # M13
]

BLOCKS_PER_YEAR = sum(n for _, n in MONTHS)   # 61

# The block that absorbs the common-year shortfall: Acid Lime's last row,
# 8-12 February. 5 days in a common fiscal year, 6 in a leap one.
FLEX_BLOCK = 38

# --------------------------------------------------------------------------
# Naming
# --------------------------------------------------------------------------

# How the number after the dot is counted:
#   "year"   day within the fiscal year,  1..366  -> 2602.037 = 6 Aug
#   "month"  day within the fiscal month, 1..30   -> 2602.07  = 6 Aug
DAY_NUMBERING = "year"

# Width of the number after the dot. None picks it from DAY_NUMBERING:
# 3 digits for "year" (runs to 366), 2 for "month" (runs to 30).
DAY_DIGITS = None


def day_digits() -> int:
    if DAY_DIGITS is not None:
        return DAY_DIGITS
    return 2 if DAY_NUMBERING == "month" else 3

TITLE_SUFFIX = " Weekly To-do List"

# Rendered into each of the six column headings.
# Available: {label} {doy} {dom} {month_name} {month_no} and {d} (a date).
HEADING_FMT = "{label} | {d:%m-%d} {d:%a}"

# --------------------------------------------------------------------------
# Notion
# --------------------------------------------------------------------------

DATABASE_ID = "389ae5e7-2130-8003-806a-e59a4ed71cab"   # Weekly To-do Lists
# Optional. Leave empty to auto-resolve; set it only if the database ever grows
# a second data source and you need to pin a specific one.
DATA_SOURCE_ID = ""
TITLE_PROP = "Name"
DATE_PROP = "Date Range"
PLACEHOLDER_TITLE = "26PP.QQ - 26PP.RR Weekly To-do List"

LOCAL_TZ = ZoneInfo(os.environ.get("LOCAL_TZ", "Asia/Shanghai"))
DRY_RUN = os.environ.get("DRY_RUN") == "1"

# 2025-09-03 split every database into a container plus one or more "data
# sources". Querying moved from /v1/databases/{id}/query to
# /v1/data_sources/{id}/query; page and block writes are unaffected.
NOTION_VERSION = "2025-09-03"
API = "https://api.notion.com/v1"

DAY_MARKER = re.compile(r"\(J(?:\+(\d+))?\)")


# --------------------------------------------------------------------------
# Calendar maths
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Block:
    no: int             # 1..61 within the fiscal year
    start: date
    end: date
    month_no: int       # 1..13
    month_name: str
    month_start: date
    doy: int            # day of fiscal year of `start`
    fy_start: date      # 1 July of this fiscal year

    @property
    def length(self) -> int:
        return (self.end - self.start).days + 1

    @property
    def dom(self) -> int:
        """Day of fiscal month of `start`."""
        return (self.start - self.month_start).days + 1


def fiscal_year_start(d: date) -> date:
    year = d.year if (d.month, d.day) >= FISCAL_START else d.year - 1
    return date(year, *FISCAL_START)


def fiscal_year_length(fy_start: date) -> int:
    return (date(fy_start.year + 1, *FISCAL_START) - fy_start).days


def build_year(fy_start: date) -> list[Block]:
    """Every block of the fiscal year beginning at `fy_start`."""
    flex = BLOCK_LEN if fiscal_year_length(fy_start) == 366 else BLOCK_LEN - 1

    blocks: list[Block] = []
    cursor, doy, block_no = fy_start, 1, 1

    for month_no, (name, n_blocks) in enumerate(MONTHS, start=1):
        month_start = cursor
        for _ in range(n_blocks):
            length = flex if block_no == FLEX_BLOCK else BLOCK_LEN
            blocks.append(Block(
                no=block_no,
                start=cursor,
                end=cursor + timedelta(days=length - 1),
                month_no=month_no,
                month_name=name,
                month_start=month_start,
                doy=doy,
                fy_start=fy_start,
            ))
            cursor += timedelta(days=length)
            doy += length
            block_no += 1

    assert cursor == date(fy_start.year + 1, *FISCAL_START), \
        f"calendar does not close: {fy_start} -> {cursor}"
    return blocks


def block_containing(d: date) -> Block:
    for block in build_year(fiscal_year_start(d)):
        if block.start <= d <= block.end:
            return block
    raise AssertionError(f"no block contains {d}")


def day_number(block: Block, offset: int) -> int:
    """The number that goes after the dot, for day `offset` of `block`."""
    if DAY_NUMBERING == "month":
        return block.dom + offset
    return block.doy + offset


def label(block: Block, offset: int = 0) -> str:
    yy = block.fy_start.year % 100
    n = day_number(block, offset)
    return f"{yy:02d}{block.month_no:02d}.{n:0{day_digits()}d}"


def page_title(block: Block) -> str:
    return f"{label(block, 0)} - {label(block, block.length - 1)}{TITLE_SUFFIX}"


def heading_text(block: Block, offset: int) -> str:
    d = block.start + timedelta(days=offset)
    return HEADING_FMT.format(
        label=label(block, offset),
        doy=block.doy + offset,
        dom=block.dom + offset,
        month_name=block.month_name,
        month_no=block.month_no,
        d=d,
    )


# --------------------------------------------------------------------------
# Notion API
# --------------------------------------------------------------------------

class Notion:
    def __init__(self, token: str):
        self._ds: str | None = None
        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        })

    def _call(self, method: str, path: str, **kw):
        r = self.s.request(method, f"{API}{path}", timeout=30, **kw)
        if not r.ok:
            raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text}")
        return r.json()

    def data_source_id(self) -> str:
        """Resolve the database's data source. Since 2025-09-03 a database is a
        container for one or more data sources and queries target the source,
        not the database."""
        if self._ds is None:
            db = self._call("GET", f"/databases/{DATABASE_ID}")
            sources = db.get("data_sources") or []
            if not sources:
                raise RuntimeError(f"database {DATABASE_ID} reports no data sources")
            if len(sources) > 1:
                names = ", ".join(s.get("name", "?") for s in sources)
                print(f"note: database has {len(sources)} data sources ({names}); "
                      f"using the first. Set DATA_SOURCE_ID to pin one.")
            self._ds = DATA_SOURCE_ID or sources[0]["id"]
        return self._ds

    def query_placeholders(self) -> list[dict]:
        ds = self.data_source_id()
        pages, cursor = [], None
        while True:
            body = {
                "filter": {"property": TITLE_PROP,
                           "title": {"equals": PLACEHOLDER_TITLE}},
                "page_size": 100,
            }
            if cursor:
                body["start_cursor"] = cursor
            data = self._call("POST", f"/data_sources/{ds}/query", json=body)
            pages += data["results"]
            if not data.get("has_more"):
                return pages
            cursor = data["next_cursor"]

    def children(self, block_id: str) -> list[dict]:
        out, cursor = [], None
        while True:
            path = f"/blocks/{block_id}/children?page_size=100"
            if cursor:
                path += f"&start_cursor={cursor}"
            data = self._call("GET", path)
            out += data["results"]
            if not data.get("has_more"):
                return out
            cursor = data["next_cursor"]

    def walk_headings(self, block_id: str, depth: int = 0):
        """Every heading_1/2/3 under `block_id`, recursing into columns."""
        if depth > 4:
            return
        for blk in self.children(block_id):
            if blk["type"] in ("heading_1", "heading_2", "heading_3"):
                yield blk
            if blk.get("has_children"):
                yield from self.walk_headings(blk["id"], depth + 1)

    def set_heading(self, blk: dict, text: str):
        btype = blk["type"]
        self._call("PATCH", f"/blocks/{blk['id']}", json={
            btype: {"rich_text": [{"type": "text", "text": {"content": text}}]}
        })

    def set_page(self, page_id: str, title: str, start: date, end: date):
        self._call("PATCH", f"/pages/{page_id}", json={"properties": {
            TITLE_PROP: {"title": [{"type": "text", "text": {"content": title}}]},
            DATE_PROP: {"date": {"start": start.isoformat(), "end": end.isoformat()}},
        }})


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def plain_text(blk: dict) -> str:
    return "".join(rt.get("plain_text", "")
                   for rt in blk[blk["type"]].get("rich_text", []))


def fill(notion: Notion, page: dict) -> None:
    page_id = page["id"]
    created = (datetime.fromisoformat(page["created_time"].replace("Z", "+00:00"))
               .astimezone(LOCAL_TZ).date())
    block = block_containing(created)
    title = page_title(block)

    print(f"page {page_id}  created {created}")
    print(f"  block {block.no}/{BLOCKS_PER_YEAR}  "
          f"M{block.month_no} {block.month_name}  "
          f"{block.start}..{block.end} ({block.length}d)")
    print(f"  -> {title}")

    # Notion repeats strictly every 6 days, but block 38 is only 5 in a common
    # year, so pages start arriving one day into their block. Harmless for a
    # while (the date still lands in the right block) but it accumulates one
    # day per common year and eventually slips a whole block.
    drift = (created - block.start).days
    if drift:
        print(f"  ! page arrived {drift} day(s) into the block. "
              f"Re-anchor the template's repeat to {block.start}.")

    # Headings first: the title is the idempotency marker, so it goes last.
    # A run that dies halfway leaves the page eligible for the next run.
    for blk in notion.walk_headings(page_id):
        m = DAY_MARKER.search(plain_text(blk))
        if not m:
            continue
        offset = int(m.group(1) or 0)
        if offset >= block.length:
            print(f"  - leaving (J+{offset}) alone, block is only {block.length} days")
            continue
        text = heading_text(block, offset)
        print(f"  J+{offset} -> {text}")
        if not DRY_RUN:
            notion.set_heading(blk, text)

    if not DRY_RUN:
        notion.set_page(page_id, title, block.start, block.end)


def main() -> int:
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        print("NOTION_TOKEN is not set", file=sys.stderr)
        return 1

    notion = Notion(token)
    pages = notion.query_placeholders()
    if not pages:
        print("nothing to do")
        return 0
    for page in pages:
        fill(notion, page)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
