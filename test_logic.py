from datetime import date, timedelta
import fill_weekly_todo as F

# ---- structure -----------------------------------------------------------
assert F.BLOCKS_PER_YEAR == 61
assert 6 * 61 == 366

for fy in [2025, 2026, 2027, 2028, 2029, 2030, 2031]:
    blocks = F.build_year(date(fy, 7, 1))          # asserts the year closes
    assert len(blocks) == 61
    assert blocks[0].start == date(fy, 7, 1)
    assert blocks[-1].end == date(fy + 1, 6, 30)
    short = [b for b in blocks if b.length != 6]
    ln = F.fiscal_year_length(date(fy, 7, 1))
    assert (len(short) == 0) if ln == 366 else (len(short) == 1 and short[0].no == 38)
print("61 blocks close exactly on 6/30 for FY2025..FY2031")

# ---- every anchor visible in the two screenshots (FY2026) -----------------
SHEET = {   # block no -> (start date, day-of-fiscal-year, month no, month name)
    1:  (date(2026, 7, 1),   1,  1, "Galaxy Blue"),
    6:  (date(2026, 7, 31),  31, 2, "English Hyacinth"),
    7:  (date(2026, 8, 6),   37, 2, "English Hyacinth"),
    10: (date(2026, 8, 24),  55, 3, "Azure Blue"),
    15: (date(2026, 9, 23),  85, 4, "Irish Green"),
    19: (date(2026, 10, 17), 109, 5, "Amethyst Orchid"),
    24: (date(2026, 11, 16), 139, 6, "Deep Mint"),
    29: (date(2026, 12, 16), 169, 7, "Crystal Seas"),
    34: (date(2027, 1, 15),  199, 8, "Acid Lime"),
    38: (date(2027, 2, 8),   223, 8, "Acid Lime"),
    39: (date(2027, 2, 13),  228, 9, "Autumn Blaze"),
    44: (date(2027, 3, 15),  258, 10, "Flame"),
    48: (date(2027, 4, 8),   282, 11, "River Blue"),
    53: (date(2027, 5, 8),   312, 12, "Blazing Yellow"),
    57: (date(2027, 6, 1),   336, 13, "Atlantis"),
    61: (date(2027, 6, 25),  360, 13, "Atlantis"),
}
blocks = F.build_year(date(2026, 7, 1))
for no, (start, doy, mno, mname) in SHEET.items():
    b = blocks[no - 1]
    assert (b.start, b.doy, b.month_no, b.month_name) == (start, doy, mno, mname), \
        f"block {no}: {b.start} d{b.doy} M{b.month_no} {b.month_name}"
assert blocks[37].length == 5 and blocks[37].end == date(2027, 2, 12)
print(f"all {len(SHEET)} sheet anchors match, block 38 is 5 days (2/8-2/12)")

# ---- lookup by arbitrary date --------------------------------------------
assert F.block_containing(date(2026, 8, 9)).no == 7
assert F.block_containing(date(2027, 2, 12)).no == 38
assert F.block_containing(date(2027, 2, 13)).no == 39
assert F.block_containing(date(2027, 6, 30)).no == 61

# ---- his real Notion titles ----------------------------------------------
t1 = F.page_title(F.block_containing(date(2026, 7, 25)))
t2 = F.page_title(F.block_containing(date(2026, 7, 31)))
assert t1 == "2601.25 - 2601.30 Weekly To-do List", t1
assert t2 == "2602.01 - 2602.06 Weekly To-do List", t2
print("reproduces both real page titles:", t1, "/", t2)

# ---- leap fiscal year ----------------------------------------------------
lb = F.build_year(date(2027, 7, 1))               # contains Feb 2028
assert F.fiscal_year_length(date(2027, 7, 1)) == 366
assert lb[37].length == 6 and lb[37].end == date(2028, 2, 13)
assert lb[38].start == date(2028, 2, 14)
print("leap FY2027: block 38 runs 6 days (2/8-2/13), no shortfall")

print("\nsample titles (DAY_NUMBERING = %r):" % F.DAY_NUMBERING)
for no in (1, 6, 34, 38, 39, 61):
    b = blocks[no - 1]
    print(f"  block {no:>2}  {F.page_title(b)}")

print("\nheadings, block 7 (M2 English Hyacinth):")
b = blocks[6]
for o in range(b.length):
    print("  J+%d  %s" % (o, F.heading_text(b, o)))

print("\nheadings, block 38 (the short one):")
b = blocks[37]
for o in range(b.length):
    print("  J+%d  %s" % (o, F.heading_text(b, o)))

# ---- leap sheet (Sheet1a): FY2027, 2027-07-01 .. 2028-06-30 --------------
LEAP = {
    25: (date(2027,11,22), date(2027,11,27), 145,  6, "Deep Mint"),
    29: (date(2027,12,16), date(2027,12,21), 169,  7, "Crystal Seas"),
    34: (date(2028,1,15),  date(2028,1,20),  199,  8, "Acid Lime"),
    38: (date(2028,2,8),   date(2028,2,13),  223,  8, "Acid Lime"),
    39: (date(2028,2,14),  date(2028,2,19),  229,  9, "Autumn Blaze"),
    41: (date(2028,2,26),  date(2028,3,2),   241,  9, "Autumn Blaze"),
    44: (date(2028,3,15),  date(2028,3,20),  259, 10, "Flame"),
    48: (date(2028,4,8),   date(2028,4,13),  283, 11, "River Blue"),
    53: (date(2028,5,8),   date(2028,5,13),  313, 12, "Blazing Yellow"),
    57: (date(2028,6,1),   date(2028,6,6),   337, 13, "Atlantis"),
    61: (date(2028,6,25),  date(2028,6,30),  361, 13, "Atlantis"),
}
lb = F.build_year(date(2027, 7, 1))
for no, (st, en, doy, mno, mname) in LEAP.items():
    b = lb[no - 1]
    assert (b.start, b.end, b.doy, b.month_no, b.month_name) == (st, en, doy, mno, mname), \
        f"leap block {no}: {b.start}..{b.end} d{b.doy} M{b.month_no} {b.month_name}"
assert lb[37].length == 6
assert lb[-1].doy + lb[-1].length - 1 == 366
assert lb[40].start + timedelta(days=3) == date(2028, 2, 29)
print(f"all {len(LEAP)} leap-sheet anchors match; 2/29 sits in block 41 slot 4")

# Only M8 changes length; M9 shifts its start but still ends 3/14, so M10-M13
# fall on identical calendar dates in both kinds of year.
def month_spans(bs):
    out = {}
    for b in bs:
        out.setdefault(b.month_no, [b.month_start, None])
        out[b.month_no][1] = b.end
    return out
cs_, ls_ = month_spans(blocks), month_spans(lb)
differ = {m for m in range(1, 14)
          if (cs_[m][0].month, cs_[m][0].day, cs_[m][1].month, cs_[m][1].day)
          != (ls_[m][0].month, ls_[m][0].day, ls_[m][1].month, ls_[m][1].day)}
assert differ == {8, 9}, differ
assert (cs_[9][1].month, cs_[9][1].day) == (ls_[9][1].month, ls_[9][1].day) == (3, 14)
print("common vs leap: only M8 and M9 shift, and M9 re-converges on 3/14")

print("\nall assertions passed")
