import csv
import math

# ─────────────────────────────────────────────────────────────
# BACKTEST 1: Yearly Anchored VWAP
# ─────────────────────────────────────────────────────────────
print("=" * 60)
print("BACKTEST 1: Yearly Anchored VWAP")
print("=" * 60)

# Raw data rows (time, open, high, low, close, actual_vwap, actual_vah, actual_val)
rows = [
    (1745625600, 94638.68, 95199,     93870.69, 94628,    91754.22690829408, 99772.58298202748, 83735.87083456067),
    (1745712000, 94628,    95369,     93602.58, 93749.3,  91761.93963187031, 99769.00969685141, 83754.8695668892),
    (1745798400, 93749.29, 95630,     92800.01, 95011.18, 91780.58368319453, 99763.29013366211, 83797.87723272695),
    (1745884800, 95011.18, 95461.53,  93742.54, 94256.82, 91794.70383158672, 99758.97306349016, 83830.43459968329),
    (1745971200, 94256.82, 95228.45,  92910,    94172,    91807.13537359313, 99751.81780139201, 83862.45294579426),
    (1746057600, 94172,    97424.02,  94130.43, 96489.91, 91834.79705943356, 99760.68597946428, 83908.90813940285),
    (1746144000, 96489.9,  97895.68,  96350,    96887.14, 91861.27782256433, 99775.69523626287, 83946.86040886579),
    (1746230400, 96887.13, 96935.67,  95753.01, 95856.42, 91873.53573896138, 99780.08490798667, 83966.98656993608),
    (1746316800, 95856.42, 96304.48,  94151.38, 94277.62, 91884.07904256927, 99779.08936848592, 83989.06871665262),
    (1746403200, 94277.61, 95199,     93514.1,  94733.68, 91897.38664224106, 99774.47040758966, 84020.30287689247),
    (1746489600, 94733.68, 96920.65,  93377,    96834.02, 91916.96696724846, 99778.52843332474, 84055.40550117218),
    (1746576000, 96834.02, 97732,     95784.61, 97030.5,  91944.31412745177, 99792.61325325855, 84096.01500164499),
    (1746662400, 97030.5,  104145.76, 96876.29, 103261.6, 92047.59237039034, 99914.97806581657, 84180.20667496411),
    (1746748800, 103261.61,104361.3,  102315.14,102971.99,92131.81940926859,100028.82573802881, 84234.81308050836),
    (1746835200, 102971.99,104984.57, 102818.76,104809.53,92179.36561191312,100096.99640376434, 84261.7348200619),
    (1746921600, 104809.53,104972,    103345.06,104118,   92234.8357208786, 100175.79015105075, 84293.88129070646),
    (1747008000, 104118,   105819.45, 100718.37,102791.32,92331.17535114454,100302.32086011456, 84360.02984217452),
    (1747094400, 102791.32,104976.25, 101429.7, 104103.72,92400.03855057912,100394.58563169664, 84405.4914694616),
    (1747180800, 104103.72,104356.95, 102602.05,103507.82,92454.08997887965,100466.44498030294, 84441.73497745636),
    (1747267200, 103507.83,104192.7,  101383.07,103763.71,92511.84536168475,100540.68906222285, 84483.00166114666),
]

# We know this is cumulative from some earlier anchor date before row 0
# The VWAP at row 0 is 91754.22 while close is 94628 — so there's a LOT of
# prior history baked in. We need to figure out what the running sums were
# BEFORE this data starts, then test if our increment formula is correct.

# Strategy: Back-solve the prior accumulators from row 0 VWAP and SD,
# then simulate forward and compare.

# At row 0: vwap0 = 91754.22690829408, sd0 = 99772.58 - 91754.22 = 8018.36
# sd0 = VAH0 - VWAP0
sd0 = rows[0][6] - rows[0][5]  # VAH - VWAP
print(f"Row 0 SD: {sd0:.8f}")
print(f"Row 0 VAH-VWAP: {rows[0][6]-rows[0][5]:.8f}")
print(f"Row 0 VWAP-VAL: {rows[0][5]-rows[0][7]:.8f}")
print(f"SD symmetric: {abs((rows[0][6]-rows[0][5]) - (rows[0][5]-rows[0][7])) < 0.01}")

# We cannot replicate from scratch without volume data, but we CAN test
# whether the INCREMENTAL logic is correct by checking if going from
# row N to row N+1 produces the correct ratio of change.

print("\n--- Testing increment formula ---")
print("Checking if VWAP moves proportionally to TP vs prior VWAP")

# Test: does VWAP[i+1] = (VWAP[i]*cum_vol + tp[i+1]*vol[i+1]) / (cum_vol + vol[i+1])?
# Without actual volume, test with proxy volume = 1 (equal weighting)
# This tells us if the FORMULA is right even if magnitudes differ

# Formula check: ΔVWAP = (tp - VWAP) * (vol / (cum_vol + vol))
# If we assume equal volume per bar, the update should be smooth

for formula_name, tp_func in [
    ("(H+L+C)/3", lambda r: (r[2]+r[3]+r[4])/3),
    ("close",     lambda r: r[4]),
    ("(H+C)/2",   lambda r: (r[2]+r[4])/2),
    ("(O+H+L+C)/4", lambda r: (r[1]+r[2]+r[3]+r[4])/4),
]:
    tps = [tp_func(r) for r in rows]
    # Compute equal-weight average TP and check direction of VWAP movement
    actual_deltas = [rows[i+1][5] - rows[i][5] for i in range(len(rows)-1)]
    tp_vs_vwap = [tps[i] - rows[i][5] for i in range(len(rows)-1)]
    # Signs should match: when TP > VWAP, VWAP should increase
    matches = sum(1 for a, b in zip(actual_deltas, tp_vs_vwap) if (a > 0) == (b > 0))
    print(f"  {formula_name}: direction match {matches}/{len(actual_deltas)} = {100*matches/len(actual_deltas):.1f}%")

# Best formula identification
print("\n--- Correlation of |TP-VWAP| with |ΔVWAP| ---")
for formula_name, tp_func in [
    ("(H+L+C)/3", lambda r: (r[2]+r[3]+r[4])/3),
    ("close",     lambda r: r[4]),
    ("(O+H+L+C)/4", lambda r: (r[1]+r[2]+r[3]+r[4])/4),
]:
    tps = [tp_func(r) for r in rows]
    # The VWAP update is TP-weighted; directional check
    actual_dvwap = [rows[i+1][5] - rows[i][5] for i in range(len(rows)-1)]
    tp_diffs = [tps[i+1] - rows[i][5] for i in range(len(rows)-1)]
    # Normalize and compute correlation proxy
    n = len(actual_dvwap)
    mean_a = sum(actual_dvwap)/n
    mean_t = sum(tp_diffs)/n
    cov = sum((actual_dvwap[i]-mean_a)*(tp_diffs[i]-mean_t) for i in range(n))
    var_a = sum((x-mean_a)**2 for x in actual_dvwap)
    var_t = sum((x-mean_t)**2 for x in tp_diffs)
    corr = cov / math.sqrt(var_a * var_t) if var_a * var_t > 0 else 0
    print(f"  {formula_name}: Pearson r = {corr:.6f}")

# ─────────────────────────────────────────────────────────────
# BACKTEST 2: Year-reset VWAP simulation (new year rows)
# ─────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("BACKTEST 2: Year-reset verification (2026-01-01 rows)")
print("=" * 60)

# New year rows: 1767225600 = Jan 1 2026, 1767312000 = Jan 2, etc.
new_year_rows = [
    # time, open, high, low, close, actual_vwap, actual_vah, actual_val
    (1767225600, 87648.21, 88919.45, 87550.43, 88839.04, 88406.6131148795,  88406.6131148795,  88406.6131148795),
    (1767312000, 88839.05, 90961.81, 88379.88, 89995.13, 89421.47535983198, 90012.35796274587, 88830.5927569181),
    (1767398400, 89995.14, 90741.16, 89314.01, 90628.01, 89596.24593209707, 90214.58854462799, 88977.90331956615),
    (1767484800, 90628.01, 91810,    90628,    91529.73, 90008.37419019573, 90919.83935320504, 89096.90902718641),
    (1767571200, 91529.74, 94789.08, 91514.81, 93859.71, 91155.58070631041, 92918.36104738257, 89392.80036523826),
]

print("Row 0 (Jan 1): VWAP=VAH=VAL => SD=0 (first bar of year)")
r0 = new_year_rows[0]
print(f"  Actual: VWAP={r0[5]:.6f}, VAH={r0[6]:.6f}, VAL={r0[7]:.6f}")
print(f"  SD = {r0[6]-r0[5]:.10f} (should be 0)")

# Test different TP formulas against actual VWAP at bar 0
for formula_name, tp_func in [
    ("(H+L+C)/3", lambda r: (r[2]+r[3]+r[4])/3),
    ("close",     lambda r: r[4]),
    ("(O+H+L+C)/4", lambda r: (r[1]+r[2]+r[3]+r[4])/4),
    ("(H+L)/2",   lambda r: (r[2]+r[3])/2),
]:
    tp0 = tp_func(r0)
    err = abs(tp0 - r0[5])
    print(f"  {formula_name:20s}: TP={tp0:.6f}, error vs VWAP={err:.4f}")

print()

# Simulate 2-bar VWAP assuming equal volume=1 for new year
# With equal volume: VWAP[1] = (TP[0] + TP[1]) / 2
# With equal volume: Var[1] = ((TP[0]-VWAP[1])^2 + (TP[1]-VWAP[1])^2) / 2
# (population variance)

for formula_name, tp_func in [
    ("(H+L+C)/3", lambda r: (r[2]+r[3]+r[4])/3),
    ("close",     lambda r: r[4]),
    ("(O+H+L+C)/4", lambda r: (r[1]+r[2]+r[3]+r[4])/4),
]:
    r0, r1 = new_year_rows[0], new_year_rows[1]
    tp0 = tp_func(r0)
    tp1 = tp_func(r1)
    vwap1_calc = (tp0 + tp1) / 2
    var1_calc = ((tp0 - vwap1_calc)**2 + (tp1 - vwap1_calc)**2) / 2
    sd1_calc = math.sqrt(var1_calc)
    actual_vwap1 = r1[5]
    actual_sd1 = r1[6] - r1[5]
    err_vwap = abs(vwap1_calc - actual_vwap1)
    err_sd = abs(sd1_calc - actual_sd1)
    print(f"Bar 1 test ({formula_name}):")
    print(f"  Calc VWAP={vwap1_calc:.4f}, Actual={actual_vwap1:.4f}, Error={err_vwap:.4f}")
    print(f"  Calc SD  ={sd1_calc:.4f}, Actual={actual_sd1:.4f}, Error={err_sd:.4f}")
    print()

# ─────────────────────────────────────────────────────────────
# BACKTEST 3: CS9 Pattern Analysis
# ─────────────────────────────────────────────────────────────
print("=" * 60)
print("BACKTEST 3: CS9 - TD Sequential Analysis")
print("=" * 60)

cs9_rows = [
    # time, open, high, low, close, s0..s15
    (1745625600, 94638.68, 95199,     93870.69, 94628,    0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0),
    (1745712000, 94628,    95369,     93602.58, 93749.3,  0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0),
    (1745798400, 93749.29, 95630,     92800.01, 95011.18, 0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0),
    (1745884800, 95011.18, 95461.53,  93742.54, 94256.82, 0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0),
    (1745971200, 94256.82, 95228.45,  92910,    94172,    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0),
    (1746057600, 94172,    97424.02,  94130.43, 96489.91, 1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0),
    (1746144000, 96489.9,  97895.68,  96350,    96887.14, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0),
    (1746230400, 96887.13, 96935.67,  95753.01, 95856.42, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0),
    (1746316800, 95856.42, 96304.48,  94151.38, 94277.62, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0),
    (1746403200, 94277.61, 95199,     93514.1,  94733.68, 0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0),
    (1746489600, 94733.68, 96920.65,  93377,    96834.02, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0),
    (1746576000, 96834.02, 97732,     95784.61, 97030.5,  1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0),
    (1746662400, 97030.5,  104145.76, 96876.29, 103261.6, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0),
    (1746748800, 103261.61,104361.3,  102315.14,102971.99,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0),
    (1746835200, 102971.99,104984.57, 102818.76,104809.53,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0),
    (1746921600, 104809.53,104972,    103345.06,104118,   0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0),
    (1747008000, 104118,   105819.45, 100718.37,102791.32,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0),
    (1747094400, 102791.32,104976.25, 101429.7, 104103.72,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0),
    (1747180800, 104103.72,104356.95, 102602.05,103507.82,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0),
    (1747267200, 103507.83,104192.7,  101383.07,103763.71,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0),
    (1747353600, 103763.71,104550.33, 103100.49,103463.9, 1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0),
    (1747440000, 103463.9, 103709.86, 102612.5, 103126.65,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0),
    (1747526400, 103126.65,106660,    103105.09,106454.26,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0),
]

# Test TD Sequential with lookback=4: close < close[4] for buy (col8), close > close[4] for sell (col0)
print("Testing TD Sequential lookback=4:")
closes = [r[4] for r in cs9_rows]
shapes_col0 = [r[5] for r in cs9_rows]
shapes_col8 = [r[13] for r in cs9_rows]

lb = 4
buy_count = 0
sell_count = 0
results_col0 = []
results_col8 = []

# Simulate with available data (from bar 4 onward)
for i in range(len(closes)):
    if i >= lb:
        if closes[i] < closes[i - lb]:
            buy_count += 1
            sell_count = 0
        elif closes[i] > closes[i - lb]:
            sell_count += 1
            buy_count = 0
        else:
            buy_count = 0
            sell_count = 0
        if buy_count > 9: buy_count = 1
        if sell_count > 9: sell_count = 1
    results_col0.append(1 if sell_count == 9 else 0)
    results_col8.append(1 if buy_count == 9 else 0)

# Compare with actual (from bar 4+ only)
print(f"\n  Actual col0 (sell setup 9) fires: {[i for i,v in enumerate(shapes_col0) if v==1]}")
print(f"  Simul col0 (sell_count==9) fires: {[i for i,v in enumerate(results_col0) if v==1]}")
print(f"\n  Actual col8 (buy setup 9)  fires: {[i for i,v in enumerate(shapes_col8) if v==1]}")
print(f"  Simul col8 (buy_count==9)  fires: {[i for i,v in enumerate(results_col8) if v==1]}")

# Check if col0 fires when SELL setup = 9 or if logic is reversed
# (maybe col0 = buy setup and col8 = sell setup)
buy_count2, sell_count2 = 0, 0
results2_col0 = []
results2_col8 = []
for i in range(len(closes)):
    if i >= lb:
        if closes[i] > closes[i - lb]:
            buy_count2 += 1
            sell_count2 = 0
        elif closes[i] < closes[i - lb]:
            sell_count2 += 1
            buy_count2 = 0
        else:
            buy_count2 = 0
            sell_count2 = 0
        if buy_count2 > 9: buy_count2 = 1
        if sell_count2 > 9: sell_count2 = 1
    results2_col0.append(1 if buy_count2 == 9 else 0)
    results2_col8.append(1 if sell_count2 == 9 else 0)

print(f"\n  Reversed: col0 = buy_count==9:  {[i for i,v in enumerate(results2_col0) if v==1]}")
print(f"  Reversed: col8 = sell_count==9: {[i for i,v in enumerate(results2_col8) if v==1]}")

# Test different lookback values  
print("\n--- Testing different lookback values for col0 matches ---")
actual_col0_fire = set(i for i,v in enumerate(shapes_col0) if v==1)
actual_col8_fire = set(i for i,v in enumerate(shapes_col8) if v==1)

for lb_test in [1, 2, 3, 4, 5]:
    buy_c, sell_c = 0, 0
    fire0, fire8 = set(), set()
    for i in range(len(closes)):
        if i >= lb_test:
            if closes[i] > closes[i-lb_test]:
                buy_c += 1; sell_c = 0
            elif closes[i] < closes[i-lb_test]:
                sell_c += 1; buy_c = 0
            else:
                buy_c = 0; sell_c = 0
            if buy_c > 9: buy_c = 1
            if sell_c > 9: sell_c = 1
        if buy_c == 9: fire0.add(i)
        if sell_c == 9: fire8.add(i)
    
    hit0 = len(actual_col0_fire & fire0)
    hit8 = len(actual_col8_fire & fire8)
    # Also check swapped
    hit0s = len(actual_col0_fire & fire8)
    hit8s = len(actual_col8_fire & fire0)
    print(f"  lb={lb_test}: col0 hits={hit0}/{len(actual_col0_fire)}, col8 hits={hit8}/{len(actual_col8_fire)} | swapped: col0={hit0s}, col8={hit8s}")

# Check if it's actually counting something other than close vs close[n]
print("\n--- Checking if col0 fires based on close > close[1] run ---")
# Maybe it's just: N consecutive days up/down
for n in [3, 4, 5, 6, 7, 8, 9]:
    fire_up, fire_dn = set(), set()
    up_streak, dn_streak = 0, 0
    for i in range(1, len(closes)):
        if closes[i] > closes[i-1]:
            up_streak += 1; dn_streak = 0
        elif closes[i] < closes[i-1]:
            dn_streak += 1; up_streak = 0
        else:
            up_streak = 0; dn_streak = 0
        if up_streak == n: fire_up.add(i)
        if dn_streak == n: fire_dn.add(i)
    hit0 = len(actual_col0_fire & fire_up)
    hit8 = len(actual_col8_fire & fire_dn)
    hit0s = len(actual_col0_fire & fire_dn)
    hit8s = len(actual_col8_fire & fire_up)
    print(f"  n={n}-consecutive-up: col0 hits={hit0}/{len(actual_col0_fire)}, col8 hits={hit8}/{len(actual_col8_fire)} | swapped: col0={hit0s} col8={hit8s}")

print("\n--- FULL DIAGNOSIS DONE ---")
print("Check above outputs to identify correct formula.")

# ─────────────────────────────────────────────────────────────
# MANUAL CHECK 1: CS9 col0-firing bars with OHLC and close[4]
# ─────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("MANUAL CHECK 1: Bars where col0=1 fires — OHLC + close[4]")
print("=" * 60)

for i, r in enumerate(cs9_rows):
    if r[5] == 1:  # col0 fires
        close_4back = cs9_rows[i-4][4] if i >= 4 else None
        close_1back = cs9_rows[i-1][4] if i >= 1 else None
        print(f"  Bar {i:2d} | time={r[0]} | O={r[1]:.2f} H={r[2]:.2f} L={r[3]:.2f} C={r[4]:.2f}")
        print(f"         | close[1]={close_1back} | close[4]={close_4back}")
        print(f"         | C > C[4]: {r[4] > close_4back if close_4back else 'N/A'}")
        print(f"         | C > C[1]: {r[4] > close_1back if close_1back else 'N/A'}")
        print(f"         | shapes active: {[j for j in range(16) if r[5+j]==1]}")
        print()

print("\n--- Bars where col8=1 fires ---")
for i, r in enumerate(cs9_rows):
    if r[13] == 1:  # col8 fires (s8)
        close_4back = cs9_rows[i-4][4] if i >= 4 else None
        close_1back = cs9_rows[i-1][4] if i >= 1 else None
        print(f"  Bar {i:2d} | time={r[0]} | O={r[1]:.2f} H={r[2]:.2f} L={r[3]:.2f} C={r[4]:.2f}")
        print(f"         | close[1]={close_1back} | close[4]={close_4back}")
        print(f"         | C < C[4]: {r[4] < close_4back if close_4back else 'N/A'}")
        print(f"         | C < C[1]: {r[4] < close_1back if close_1back else 'N/A'}")
        print(f"         | shapes active: {[j for j in range(16) if r[5+j]==1]}")
        print()

# ─────────────────────────────────────────────────────────────
# MANUAL CHECK 2: New-year VWAP bar 1 TP formula comparison
# ─────────────────────────────────────────────────────────────
print("=" * 60)
print("MANUAL CHECK 2: New-year bar 1 TP formula closest to 89421.47")
print("=" * 60)

r0 = (1767225600, 87648.21, 88919.45, 87550.43, 88839.04, 88406.6131148795, 88406.6131148795, 88406.6131148795)
r1 = (1767312000, 88839.05, 90961.81, 88379.88, 89995.13, 89421.47535983198, 90012.35796274587, 88830.5927569181)

actual_vwap1 = r1[5]
actual_sd1   = r1[6] - r1[5]
print(f"Target VWAP bar1: {actual_vwap1:.8f}")
print(f"Target SD   bar1: {actual_sd1:.8f}")
print()

formulas = [
    ("(H+L+C)/3",    lambda r: (r[2]+r[3]+r[4])/3),
    ("close",        lambda r: r[4]),
    ("(O+H+L+C)/4",  lambda r: (r[1]+r[2]+r[3]+r[4])/4),
    ("(H+L)/2",      lambda r: (r[2]+r[3])/2),
    ("open",         lambda r: r[1]),
    ("(O+C)/2",      lambda r: (r[1]+r[4])/2),
    ("(H+L+2C)/4",   lambda r: (r[2]+r[3]+2*r[4])/4),
]

print(f"{'Formula':20s} {'TP0':>12s} {'TP1':>12s} {'VWAP_calc':>12s} {'Err_VWAP':>12s} {'SD_calc':>12s} {'Err_SD':>10s}")
print("-" * 100)
for formula_name, tp_func in formulas:
    tp0 = tp_func(r0)
    tp1 = tp_func(r1)
    vwap_calc = (tp0 + tp1) / 2
    var_calc = ((tp0 - vwap_calc)**2 + (tp1 - vwap_calc)**2) / 2
    sd_calc = math.sqrt(var_calc)
    err_v = abs(vwap_calc - actual_vwap1)
    err_s = abs(sd_calc - actual_sd1)
    print(f"{formula_name:20s} {tp0:12.4f} {tp1:12.4f} {vwap_calc:12.4f} {err_v:12.4f} {sd_calc:12.4f} {err_s:10.4f}")

# Also try: what if the SD uses sum-of-squared deviations / N (no sqrt of mean, but actual cumulative)
print()
print("--- Trying cumulative variance approach (TradingView uses sum(tp^2*vol) / sum(vol) - vwap^2) ---")
for formula_name, tp_func in formulas:
    tp0 = tp_func(r0)
    tp1 = tp_func(r1)
    # cumulative: sum_tpv = tp0+tp1, sum_tp2v = tp0^2+tp1^2, n=2
    sum_tpv  = tp0 + tp1
    sum_tp2v = tp0**2 + tp1**2
    n = 2
    vwap = sum_tpv / n
    variance = sum_tp2v / n - vwap**2
    sd = math.sqrt(abs(variance))
    err_v = abs(vwap - actual_vwap1)
    err_s = abs(sd - actual_sd1)
    print(f"{formula_name:20s} VWAP={vwap:.4f}(err={err_v:.4f})  SD={sd:.4f}(err={err_s:.4f})")

print()
print("--- All new_year_rows OHLC + TP candidates ---")
for i, r in enumerate(new_year_rows):
    tp_hlc3 = (r[2]+r[3]+r[4])/3
    tp_ohlc4 = (r[1]+r[2]+r[3]+r[4])/4
    tp_hlc3_2c = (r[2]+r[3]+2*r[4])/4
    print(f"  Bar {i} | O={r[1]:.2f} H={r[2]:.2f} L={r[3]:.2f} C={r[4]:.2f}")
    print(f"         | (H+L+C)/3={tp_hlc3:.4f} | (O+H+L+C)/4={tp_ohlc4:.4f} | (H+L+2C)/4={tp_hlc3_2c:.4f}")
    print(f"         | actual_VWAP={r[5]:.4f} actual_VAH={r[6]:.4f} actual_VAL={r[7]:.4f}")
    print()
