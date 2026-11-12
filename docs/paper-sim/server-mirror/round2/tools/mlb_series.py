import json

# NLCS: Milwaukee leads 1-0. 2-3-2: MIL hosts G1,G2,G6,G7; LAD hosts G3,G4,G5.
# Game-level: P(LAD win @MIL) = 0.557 (DK LAD -137 no-vig; PM 0.555 agrees)
# HFA sensitivity: P(LAD win @LAD) = 0.557 + hfa
print('NLCS: MIL leads 1-0; P(LAD@MIL)=0.557; market LAD pennant ask 0.48 / MIL ask 0.546')
print('%-6s %-10s %-10s %-10s' % ('hfa', 'P(LAD ser)', 'P(MIL ser)', 'LAD edge vs 0.48 ask'))
for hfa in (0.05, 0.075, 0.10):
    p_lad_at_mil = 0.557
    p_lad_at_lad = 0.557 + hfa
    # locations of remaining games G2..G7: MIL, LAD, LAD, LAD, MIL, MIL
    locs = ['MIL', 'LAD', 'LAD', 'LAD', 'MIL', 'MIL']
    # state (lad_wins_needed, mil_wins_needed) = (4,3) start; LAD needs 4 wins, MIL needs 3
    from functools import lru_cache
    @lru_cache(maxsize=None)
    def p(lad_need, mil_need, gi):
        if lad_need == 0: return 1.0
        if mil_need == 0: return 0.0
        pwin = p_lad_at_lad if locs[gi] == 'LAD' else p_lad_at_mil
        return pwin * p(lad_need - 1, mil_need, gi + 1) + (1 - pwin) * p(lad_need, mil_need - 1, gi + 1)
    r = p(4, 3, 0)
    print('%-6.3f %-10.3f %-10.3f %+10.1fc' % (hfa, r, 1 - r, (r - 0.48) * 100))

# ALCS: 0-0. 2-3-2: TB hosts G1,G2,G6,G7; CLE hosts G3,G4,G5.
# Game-level: P(TB win @TB) = 0.611 (DK TB -172 no-vig; PM 0.595 mid)
print()
print('ALCS: 0-0; P(TB@TB)=0.611; market TB pennant ask 0.637 / CLE ask 0.379')
print('%-6s %-10s %-10s %-10s %-10s' % ('hfa', 'P(TB ser)', 'P(CLE ser)', 'TB edge', 'CLE edge vs 0.379'))
for hfa in (0.05, 0.075, 0.10):
    p_tb_home = 0.611
    p_tb_away = 0.611 - hfa
    locs = ['TB', 'TB', 'CLE', 'CLE', 'CLE', 'TB', 'TB']
    from functools import lru_cache
    @lru_cache(maxsize=None)
    def p(tb_need, cle_need, gi):
        if tb_need == 0: return 1.0
        if cle_need == 0: return 0.0
        pwin = p_tb_home if locs[gi] == 'TB' else p_tb_away
        return pwin * p(tb_need - 1, cle_need, gi + 1) + (1 - pwin) * p(tb_need, cle_need - 1, gi + 1)
    r = p(4, 4, 0)
    print('%-6.3f %-10.3f %-10.3f %+10.1fc %+10.1fc' % (hfa, r, 1 - r, (r - 0.637) * 100, ((1 - r) - 0.379) * 100))

# sensitivity on the ALCS home game prob itself (PM game mid 0.595 vs DK no-vig 0.611)
print()
print('ALCS sensitivity on P(TB@TB): hfa=0.075')
for ph in (0.575, 0.595, 0.611, 0.63):
    p_tb_home = ph
    p_tb_away = ph - 0.075
    locs = ['TB', 'TB', 'CLE', 'CLE', 'CLE', 'TB', 'TB']
    from functools import lru_cache
    @lru_cache(maxsize=None)
    def p(tb_need, cle_need, gi):
        if tb_need == 0: return 1.0
        if cle_need == 0: return 0.0
        pwin = p_tb_home if locs[gi] == 'TB' else p_tb_away
        return pwin * p(tb_need - 1, cle_need, gi + 1) + (1 - pwin) * p(tb_need, cle_need - 1, gi + 1)
    r = p(4, 4, 0)
    print('P(TB@TB)=%.3f -> P(TB series)=%.3f (market ask 0.637)' % (ph, r))
