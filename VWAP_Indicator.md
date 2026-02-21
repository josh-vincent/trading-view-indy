# Multi-Timeframe Anchored VWAP Indicator

Pine Script v6 indicator for TradingView.

## Features

- **Timeframe Modes**: Yearly, Quarterly, Monthly, Weekly, or Auto
- **Auto Timeframe Logic**:
  - Daily and above → Yearly value area
  - Above 4H up to Daily → Quarterly value area
  - 1H to 4H → Monthly value area
  - Below 1H → Weekly value area
- **Value Area Shading** with configurable colours for developing and previous periods
- **RHS Extension Lines**: Dashed lines extend the developing VWAP/VAH/VAL to the right edge; reset when the next period begins
- **Labels**: VWAP, DVAH, DVAL, PVWAP, PVAH, PVAL — each with live price — positioned 30% in from the right side of the visible screen
- **Optional bands**: ±2 SD and ±3 SD
- **Colour pickers** for every line and label element
- **Alerts**: Price crossing VWAP, VAH, VAL, and Previous VWAP

## How to Add to TradingView

1. Open TradingView and navigate to the chart
2. Click **Pine Editor** at the bottom of the screen
3. Delete all existing code in the editor
4. Paste the full script below
5. Click **Add to chart**

---

## Pine Script

```pine
// =============================================================================
// Multi-Timeframe Anchored VWAP with Value Areas
// Pine Script v6
//
// Features:
//   - Yearly / Quarterly / Monthly / Weekly value areas
//   - Auto timeframe: Daily+ → Yearly | >4H → Quarterly | 1H-4H → Monthly | <1H → Weekly
//   - Value area shading with configurable colours
//   - RHS extension lines (dashed) for developing period
//   - Labels: VWAP, DVAH, DVAL, PVWAP, PVAH, PVAL with live price at 30% from RHS
//   - ±2 SD and ±3 SD optional bands
//   - Previous period VWAP / VAH / VAL
//   - Alerts for price crossing VWAP, VAH, VAL and Prev VWAP
// =============================================================================

//@version=6
indicator("Multi-TF Anchored VWAP", shorttitle="MTF-VWAP", overlay=true, max_lines_count=20, max_labels_count=20)

// ─── Inputs: Timeframe ────────────────────────────────────────────────────────
tf_mode = input.string("Auto", "Timeframe",
     options=["Auto", "Yearly", "Quarterly", "Monthly", "Weekly"],
     group="Timeframe")

// ─── Inputs: Display ─────────────────────────────────────────────────────────
show_va     = input.bool(true,  "Show Value Area (±1 SD)",  group="Display")
show_sd2    = input.bool(false, "Show ±2 SD Bands",         group="Display")
show_sd3    = input.bool(false, "Show ±3 SD Bands",         group="Display")
show_prev   = input.bool(true,  "Show Previous Period",     group="Display")
show_fill   = input.bool(true,  "Show Value Area Shading",  group="Display")
show_ext    = input.bool(true,  "Extend Developing Lines",  group="Display")
show_labels = input.bool(true,  "Show Labels",              group="Display")

// ─── Inputs: Colours – Developing Period ─────────────────────────────────────
c_vwap  = input.color(color.new(#2196F3, 0),  "VWAP",        group="Colours – Developing")
c_vah   = input.color(color.new(#4CAF50, 0),  "VAH (±1 SD)", group="Colours – Developing")
c_val   = input.color(color.new(#4CAF50, 0),  "VAL (±1 SD)", group="Colours – Developing")
c_sd2   = input.color(color.new(#FF9800, 0),  "±2 SD",       group="Colours – Developing")
c_sd3   = input.color(color.new(#F44336, 0),  "±3 SD",       group="Colours – Developing")
c_fill  = input.color(color.new(#4CAF50, 85), "VA Fill",     group="Colours – Developing")

// ─── Inputs: Colours – Previous Period ───────────────────────────────────────
c_pvwap = input.color(color.new(#9E9E9E, 0),  "Prev VWAP",    group="Colours – Previous")
c_pvah  = input.color(color.new(#9E9E9E, 0),  "Prev VAH",     group="Colours – Previous")
c_pval  = input.color(color.new(#9E9E9E, 0),  "Prev VAL",     group="Colours – Previous")
c_pfill = input.color(color.new(#9E9E9E, 85), "Prev VA Fill", group="Colours – Previous")

// ─── Inputs: Colours – Labels ─────────────────────────────────────────────────
c_lbl_bg = input.color(color.new(#000000, 70), "Label Background", group="Colours – Labels")
c_lbl_tx = input.color(color.new(#FFFFFF, 0),  "Label Text",       group="Colours – Labels")

// ─── Auto Timeframe Detection ─────────────────────────────────────────────────
tf_secs  = timeframe.in_seconds()
eff_mode = tf_mode != "Auto" ? tf_mode :
           tf_secs >= 86400  ? "Yearly" :
           tf_secs >= 14400  ? "Quarterly" :
           tf_secs >= 3600   ? "Monthly" :
                               "Weekly"

// ─── Period Reset Detection ───────────────────────────────────────────────────
t        = time
cur_yr   = year(t)
cur_mo   = month(t)
cur_wk   = weekofyear(t)
cur_qtr  = cur_mo <= 3 ? 1 : cur_mo <= 6 ? 2 : cur_mo <= 9 ? 3 : 4
prv_yr   = year(t[1])
prv_mo   = month(t[1])
prv_wk   = weekofyear(t[1])
prv_qtr  = prv_mo <= 3 ? 1 : prv_mo <= 6 ? 2 : prv_mo <= 9 ? 3 : 4

new_year  = barstate.isfirst or cur_yr != prv_yr
new_qtr   = new_year or cur_qtr != prv_qtr
new_month = new_year or cur_mo  != prv_mo
new_week  = new_year or cur_wk  != prv_wk

new_period = eff_mode == "Yearly"    ? new_year  :
             eff_mode == "Quarterly" ? new_qtr   :
             eff_mode == "Monthly"   ? new_month : new_week

// ─── VWAP Accumulators ────────────────────────────────────────────────────────
var float cum_tpv   = 0.0
var float cum_vol   = 0.0
var float cum_tp2v  = 0.0
var float prev_vwap = na
var float prev_sd   = na

tp = close

if new_period
    if cum_vol > 0.0
        float pv   = cum_tpv / cum_vol
        float pvar = math.max(cum_tp2v / cum_vol - pv * pv, 0.0)
        prev_vwap := pv
        prev_sd   := math.sqrt(pvar)
    cum_tpv  := tp * volume
    cum_vol  := volume
    cum_tp2v := tp * tp * volume
else
    cum_tpv  += tp * volume
    cum_vol  += volume
    cum_tp2v += tp * tp * volume

vwap = cum_tpv / cum_vol
vvar = math.max(cum_tp2v / cum_vol - vwap * vwap, 0.0)
sd   = math.sqrt(vvar)

// ─── RHS Extension Lines (Developing Period) ──────────────────────────────────
var line ln_vwap = na
var line ln_vah  = na
var line ln_val  = na

if show_ext
    if new_period
        line.delete(ln_vwap)
        line.delete(ln_vah)
        line.delete(ln_val)
        ln_vwap := line.new(bar_index, vwap, bar_index + 1, vwap,
             extend=extend.right, color=c_vwap, style=line.style_dashed, width=1)
        ln_vah  := line.new(bar_index, vwap + sd, bar_index + 1, vwap + sd,
             extend=extend.right, color=c_vah, style=line.style_dashed, width=1)
        ln_val  := line.new(bar_index, vwap - sd, bar_index + 1, vwap - sd,
             extend=extend.right, color=c_val, style=line.style_dashed, width=1)
    else
        if not na(ln_vwap)
            line.set_y1(ln_vwap, vwap)
            line.set_y2(ln_vwap, vwap)
        if not na(ln_vah)
            line.set_y1(ln_vah, vwap + sd)
            line.set_y2(ln_vah, vwap + sd)
        if not na(ln_val)
            line.set_y1(ln_val, vwap - sd)
            line.set_y2(ln_val, vwap - sd)

// ─── Plots ────────────────────────────────────────────────────────────────────
p_vwap = plot(vwap,                       "VWAP",   c_vwap, 2)
p_vah  = plot(show_va ? vwap + sd : na,   "VAH",    c_vah,  1)
p_val  = plot(show_va ? vwap - sd : na,   "VAL",    c_val,  1)
plot(show_sd2 ? vwap + 2 * sd : na, "VAH +2", c_sd2, 1)
plot(show_sd2 ? vwap - 2 * sd : na, "VAL -2", c_sd2, 1)
plot(show_sd3 ? vwap + 3 * sd : na, "VAH +3", c_sd3, 1)
plot(show_sd3 ? vwap - 3 * sd : na, "VAL -3", c_sd3, 1)

fill(p_vah, p_val, show_fill ? c_fill : na)

p_pv  = plot(show_prev and not na(prev_vwap) ? prev_vwap           : na, "PVWAP", c_pvwap, 1)
p_pvh = plot(show_prev and not na(prev_sd)   ? prev_vwap + prev_sd : na, "PVAH",  c_pvah,  1)
p_pvl = plot(show_prev and not na(prev_sd)   ? prev_vwap - prev_sd : na, "PVAL",  c_pval,  1)

fill(p_pvh, p_pvl, show_prev and not na(prev_sd) and show_fill ? c_pfill : na)

// ─── Labels (30% in from RHS) ─────────────────────────────────────────────────
var label lb_vwap  = na
var label lb_dvah  = na
var label lb_dval  = na
var label lb_pvwap = na
var label lb_pvah  = na
var label lb_pval  = na

if show_labels and barstate.islast
    int lft  = chart.left_visible_bar_time
    int rgt  = chart.right_visible_bar_time
    int xpos = lft + int((rgt - lft) * 0.70)

    label.delete(lb_vwap)
    lb_vwap  := label.new(xpos, vwap,
         "VWAP " + str.tostring(vwap, format.mintick),
         xloc=xloc.bar_time, color=c_lbl_bg, textcolor=c_lbl_tx,
         style=label.style_label_left, size=size.small)

    label.delete(lb_dvah)
    lb_dvah  := label.new(xpos, vwap + sd,
         "DVAH " + str.tostring(vwap + sd, format.mintick),
         xloc=xloc.bar_time, color=c_lbl_bg, textcolor=c_lbl_tx,
         style=label.style_label_left, size=size.small)

    label.delete(lb_dval)
    lb_dval  := label.new(xpos, vwap - sd,
         "DVAL " + str.tostring(vwap - sd, format.mintick),
         xloc=xloc.bar_time, color=c_lbl_bg, textcolor=c_lbl_tx,
         style=label.style_label_left, size=size.small)

    if not na(prev_vwap)
        label.delete(lb_pvwap)
        lb_pvwap := label.new(xpos, prev_vwap,
             "PVWAP " + str.tostring(prev_vwap, format.mintick),
             xloc=xloc.bar_time, color=c_lbl_bg, textcolor=c_lbl_tx,
             style=label.style_label_left, size=size.small)

        label.delete(lb_pvah)
        lb_pvah  := label.new(xpos, prev_vwap + prev_sd,
             "PVAH " + str.tostring(prev_vwap + prev_sd, format.mintick),
             xloc=xloc.bar_time, color=c_lbl_bg, textcolor=c_lbl_tx,
             style=label.style_label_left, size=size.small)

        label.delete(lb_pval)
        lb_pval  := label.new(xpos, prev_vwap - prev_sd,
             "PVAL " + str.tostring(prev_vwap - prev_sd, format.mintick),
             xloc=xloc.bar_time, color=c_lbl_bg, textcolor=c_lbl_tx,
             style=label.style_label_left, size=size.small)

// ─── Alerts ───────────────────────────────────────────────────────────────────
alertcondition(ta.cross(close, vwap),        "Price × VWAP",  "Price crossed VWAP")
alertcondition(ta.cross(close, vwap + sd),   "Price × VAH",   "Price crossed VAH +1 SD")
alertcondition(ta.cross(close, vwap - sd),   "Price × VAL",   "Price crossed VAL -1 SD")
alertcondition(ta.cross(close, prev_vwap),   "Price × PVWAP", "Price crossed Previous VWAP")
```

---

## Settings Reference

| Group | Setting | Default | Description |
|-------|---------|---------|-------------|
| Timeframe | Timeframe | Auto | Auto, Yearly, Quarterly, Monthly, or Weekly |
| Display | Show Value Area | On | Toggle ±1 SD value area bands |
| Display | Show ±2 SD Bands | Off | Toggle ±2 SD bands |
| Display | Show ±3 SD Bands | Off | Toggle ±3 SD bands |
| Display | Show Previous Period | On | Toggle prior period VWAP/VAH/VAL |
| Display | Show Value Area Shading | On | Toggle fill between VAH and VAL |
| Display | Extend Developing Lines | On | Toggle dashed RHS extension lines |
| Display | Show Labels | On | Toggle VWAP/DVAH/DVAL/PVWAP/PVAH/PVAL labels |
| Colours – Developing | VWAP | Blue | Line colour for current VWAP |
| Colours – Developing | VAH / VAL | Green | Line colour for current ±1 SD bands |
| Colours – Developing | ±2 SD | Orange | Line colour for ±2 SD bands |
| Colours – Developing | ±3 SD | Red | Line colour for ±3 SD bands |
| Colours – Developing | VA Fill | Green (85% transparent) | Fill colour between VAH and VAL |
| Colours – Previous | Prev VWAP / VAH / VAL | Grey | Line colours for previous period |
| Colours – Previous | Prev VA Fill | Grey (85% transparent) | Fill for previous period value area |
| Colours – Labels | Label Background | Black (70% transparent) | Label box colour |
| Colours – Labels | Label Text | White | Label text colour |

## Alerts Available

| Alert Name | Triggers When |
|------------|---------------|
| Price × VWAP | Price crosses the VWAP line |
| Price × VAH | Price crosses the upper value area band |
| Price × VAL | Price crosses the lower value area band |
| Price × PVWAP | Price crosses the previous period VWAP |
