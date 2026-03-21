//@version=2
// =============================================================================
// Lowkeigh-LTVW v2 — Aggregated Multi-Timeframe VWAP + Value Areas
// MMT Platform — JavaScript v2 Format
//
// v2 changes:
//   - Fixed crossesLevel() shared-state bug: now uses per-alert-id Map so
//     evaluating multiple alerts on the same bar no longer corrupts prev-close
//   - Migrated settings from descriptor schema to input.* calls (v2 API)
//
// Ported from: Agg-MTF-VWAP.pine (Lowkeigh-LTVW, PineScript v6)
//
// Features:
//   - Aggregated cross-exchange VWAP (Binance, Bybit, Coinbase, Kraken,
//     MEXC, OKX, KuCoin, Blofin, Bitget, CoinEx)
//   - Multi-timeframe period detection (Auto, Yearly, Quarterly, Monthly,
//     Weekly, Daily)
//   - Developing VWAP with ±1 SD, ±SD2, ±SD3 value area bands
//   - Previous period VWAP + Value Area (VAH / VAL)
//   - Rolling VWAP with configurable day lookback
//   - Extension lines + labels
// =============================================================================

indicator("Lowkeigh-LTVW v2", true)

// ── Inputs ────────────────────────────────────────────────────────────────────
// Timeframe
const tf_mode    = input.string("Timeframe", "Auto", { options: ["Auto", "Yearly", "Quarterly", "Monthly", "Weekly", "Daily"], group: "Timeframe" })

// Display
const show_sd1   = input.bool("Show Value Area (±1 SD)", true,  { group: "Display" })
const shade_dev  = input.bool("Shade Developing Value Area", true,  { group: "Display" })
const show_sd2   = input.bool("Show ±SD2 Bands", false, { group: "Display" })
const sd2_mult   = input.float("SD2 Multiplier", 1.5, { min: 0.1, step: 0.1, tooltip: "Custom multiplier for SD band 2 (default 1.5)", group: "Display" })
const show_sd3   = input.bool("Show ±SD3 Bands", false, { group: "Display" })
const sd3_mult   = input.float("SD3 Multiplier", 2.0, { min: 0.1, step: 0.1, tooltip: "Custom multiplier for SD band 3 (default 2.0)", group: "Display" })
const show_prev  = input.bool("Show Previous Period", true,  { group: "Display" })
const shade_prev = input.bool("Shade Previous Value Area", false, { group: "Display" })
const show_lbl   = input.bool("Show Labels", true,  { group: "Display" })
const show_ext   = input.bool("Extend Developing Lines to RHS", true,  { group: "Display" })

// Rolling VWAP
const rv_show    = input.bool("Enable Rolling VWAP", false, { group: "Rolling VWAP" })
const rv_days    = input.int("Duration (days)", 30, { min: 1, tooltip: "Number of calendar days to look back for the rolling VWAP.", group: "Rolling VWAP" })
const rv_show_sd = input.bool("Show ±1 SD Bands (rvVAH / rvVAL)", false, { group: "Rolling VWAP" })
const rv_shade   = input.bool("Shade Rolling Value Area", false, { group: "Rolling VWAP" })
const c_rv_vwap  = input.color("rvVWAP colour", "#FF9800",   { group: "Rolling VWAP" })
const c_rv_vah   = input.color("rvVAH colour",  "#FF5722",   { group: "Rolling VWAP" })
const c_rv_val   = input.color("rvVAL colour",  "#FF5722",   { group: "Rolling VWAP" })
const c_rv_fill  = input.color("rvVA Fill",     "#FF980026", { group: "Rolling VWAP" })

// Colours: Developing
const c_vwap     = input.color("VWAP",             "#2196F3",   { group: "Colours: Developing" })
const c_vah      = input.color("VAH",              "#4CAF50",   { group: "Colours: Developing" })
const c_val      = input.color("VAL",              "#4CAF50",   { group: "Colours: Developing" })
const c_sd2      = input.color("±SD2",             "#FF9800CC", { group: "Colours: Developing" })
const c_sd3      = input.color("±SD3",             "#F44336CC", { group: "Colours: Developing" })
const c_fill_dev = input.color("Value Area Fill",  "#4CAF5026", { group: "Colours: Developing" })

// Colours: Previous
const c_pvwap    = input.color("Prev VWAP",        "#9E9E9EB3", { group: "Colours: Previous" })
const c_pvah     = input.color("Prev VAH",         "#9E9E9EB3", { group: "Colours: Previous" })
const c_pval     = input.color("Prev VAL",         "#9E9E9EB3", { group: "Colours: Previous" })
const c_fill_prv = input.color("Value Area Fill",  "#9E9E9E26", { group: "Colours: Previous" })

// Colours: Labels
const c_lbl_d_bg = input.color("Dev Label BG",    "#2196F3E6", { group: "Colours: Labels" })
const c_lbl_d_tx = input.color("Dev Label Text",  "#FFFFFF",   { group: "Colours: Labels" })
const c_lbl_p_bg = input.color("Prev Label BG",   "#9E9E9EE6", { group: "Colours: Labels" })
const c_lbl_p_tx = input.color("Prev Label Text", "#FFFFFF",   { group: "Colours: Labels" })

// ── State ─────────────────────────────────────────────────────────────────────
let cum_tpv  = 0.0;
let cum_vol  = 0.0;
let cum_tp2v = 0.0;
let prev_vwap = null;
let prev_sd   = null;

// Rolling VWAP history buffers
const rv_tpv_buf  = [];
const rv_vol_buf  = [];
const rv_tp2v_buf = [];

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Resolve effective timeframe from settings or chart resolution.
 * @param {string} tf_mode - "Auto" or explicit TF name
 * @param {number} tf_secs - Current chart timeframe in seconds
 * @returns {string}
 */
function getEffTf(tf_mode, tf_secs) {
  if (tf_mode !== "Auto") return tf_mode;
  if (tf_secs >= 86400) return "Yearly";
  if (tf_secs >  14400) return "Quarterly";
  if (tf_secs >= 3600)  return "Monthly";
  if (tf_secs >= 1800)  return "Weekly";
  return "Daily";
}

/**
 * Detect whether the bar opens a new period.
 * @param {object} bar     - Current bar { time, year, month, week, day }
 * @param {object} prevBar - Previous bar (same shape), null on first bar
 * @param {string} eff_tf  - Effective timeframe string
 * @returns {boolean}
 */
function isNewPeriod(bar, prevBar, eff_tf) {
  if (!prevBar) return true;

  const quarter     = (m) => m <= 3 ? 1 : m <= 6 ? 2 : m <= 9 ? 3 : 4;
  const new_year    = bar.year  !== prevBar.year;
  const new_qtr     = new_year  || quarter(bar.month) !== quarter(prevBar.month);
  const new_month   = new_qtr   || bar.month !== prevBar.month;
  const new_week    = new_month || bar.week  !== prevBar.week;
  const new_day     = new_week  || bar.day   !== prevBar.day;

  switch (eff_tf) {
    case "Yearly":    return new_year;
    case "Quarterly": return new_qtr;
    case "Monthly":   return new_month;
    case "Weekly":    return new_week;
    default:          return new_day;   // Daily
  }
}

/**
 * Aggregate volume-weighted price data across all connected exchanges.
 * Supply null/undefined for any exchange that is unavailable.
 *
 * @param {Array<{tp: number|null, vol: number|null}>} feeds
 * @returns {{ agg_vol, agg_tpv, agg_tp2v }}
 */
function aggregateFeeds(feeds) {
  let agg_vol = 0, agg_tpv = 0, agg_tp2v = 0;
  for (const feed of feeds) {
    if (feed == null) continue;
    const { tp, vol } = feed;
    if (tp == null || vol == null || isNaN(tp) || isNaN(vol)) continue;
    agg_vol  += vol;
    agg_tpv  += tp * vol;
    agg_tp2v += tp * tp * vol;
  }
  return { agg_vol, agg_tpv, agg_tp2v };
}

/**
 * Compute VWAP + standard deviation from cumulative accumulators.
 * @returns {{ vwap: number|null, sd: number|null }}
 */
function calcVwapSd(cum_tpv, cum_vol, cum_tp2v) {
  if (cum_vol <= 0) return { vwap: null, sd: null };
  const vwap    = cum_tpv / cum_vol;
  const raw_var = Math.max(cum_tp2v / cum_vol - vwap * vwap, 0);
  const sd      = Math.sqrt(raw_var);
  return { vwap, sd };
}

/**
 * Rolling VWAP: push latest bar values into circular buffers and compute.
 * @param {number} agg_tpv  - Current bar aggregated tpv
 * @param {number} agg_vol  - Current bar aggregated vol
 * @param {number} agg_tp2v - Current bar aggregated tp2v
 * @param {number} rv_bars  - Number of bars to look back
 * @returns {{ rv_vwap, rv_sd }}
 */
function calcRollingVwap(agg_tpv, agg_vol, agg_tp2v, rv_bars) {
  rv_tpv_buf.push(agg_tpv);
  rv_vol_buf.push(agg_vol);
  rv_tp2v_buf.push(agg_tp2v);

  // Trim buffers to the rolling window length
  while (rv_tpv_buf.length  > rv_bars) rv_tpv_buf.shift();
  while (rv_vol_buf.length  > rv_bars) rv_vol_buf.shift();
  while (rv_tp2v_buf.length > rv_bars) rv_tp2v_buf.shift();

  const sum_vol  = rv_vol_buf.reduce((a, b) => a + b, 0);
  const sum_tpv  = rv_tpv_buf.reduce((a, b) => a + b, 0);
  const sum_tp2v = rv_tp2v_buf.reduce((a, b) => a + b, 0);

  const { vwap: rv_vwap, sd: rv_sd } = calcVwapSd(sum_tpv, sum_vol, sum_tp2v);
  return { rv_vwap, rv_sd };
}

// ── Label prefix helpers ──────────────────────────────────────────────────────
function devPrefix(eff_tf) {
  return { Yearly: "dy", Quarterly: "dq", Monthly: "dm", Weekly: "dw" }[eff_tf] ?? "dd";
}

function prevPrefix(eff_tf) {
  return { Yearly: "py", Quarterly: "pq", Monthly: "pm", Weekly: "pw" }[eff_tf] ?? "pd";
}

// ── Main per-bar callback ─────────────────────────────────────────────────────
/**
 * Called once per completed (or developing) bar by the MMT runtime.
 *
 * @param {object} bar - Bar data provided by the platform:
 *   {
 *     open, high, low, close, volume,
 *     time      {Date},
 *     year      {number},
 *     month     {number},  // 1-12
 *     week      {number},  // ISO week
 *     day       {number},  // day of month
 *     tf_secs   {number},  // chart timeframe in seconds
 *     isFirst   {boolean},
 *     isLast    {boolean},
 *
 *     // Per-exchange feeds — { tp: hlc3 | null, vol: volume | null }
 *     feeds: {
 *       binance, bybit, coinbase, kraken,
 *       mexc, okx, kucoin, blofin, bitget, coinex
 *     }
 *   }
 * @param {object|null} prevBar - Previous bar (null on first bar)
 * @returns {object} Plot data consumed by the MMT rendering engine
 */
function onBar(bar, prevBar) {
  const eff_tf  = getEffTf(tf_mode, bar.tf_secs);
  const new_per = isNewPeriod(bar, prevBar, eff_tf);

  // ── Aggregate cross-exchange data ─────────────────────────────────────────
  const { agg_vol, agg_tpv, agg_tp2v } = aggregateFeeds(
    Object.values(bar.feeds ?? {})
  );

  // ── Developing VWAP accumulators ──────────────────────────────────────────
  if (new_per) {
    // Snapshot previous period before resetting
    if (cum_vol > 0) {
      const snap = calcVwapSd(cum_tpv, cum_vol, cum_tp2v);
      prev_vwap = snap.vwap;
      prev_sd   = snap.sd;
    }
    cum_tpv  = agg_tpv;
    cum_vol  = agg_vol;
    cum_tp2v = agg_tp2v;
  } else {
    cum_tpv  += agg_tpv;
    cum_vol  += agg_vol;
    cum_tp2v += agg_tp2v;
  }

  // ── Developing VWAP values ────────────────────────────────────────────────
  const { vwap, sd } = calcVwapSd(cum_tpv, cum_vol, cum_tp2v);

  const vhi  = vwap != null && sd != null ? vwap + sd : null;
  const vlo  = vwap != null && sd != null ? vwap - sd : null;
  const vhi2 = vwap != null && sd != null ? vwap + sd2_mult * sd : null;
  const vlo2 = vwap != null && sd != null ? vwap - sd2_mult * sd : null;
  const vhi3 = vwap != null && sd != null ? vwap + sd3_mult * sd : null;
  const vlo3 = vwap != null && sd != null ? vwap - sd3_mult * sd : null;

  // ── Previous period values ────────────────────────────────────────────────
  const pvhi = prev_vwap != null && prev_sd != null ? prev_vwap + prev_sd : null;
  const pvlo = prev_vwap != null && prev_sd != null ? prev_vwap - prev_sd : null;

  // ── Rolling VWAP ──────────────────────────────────────────────────────────
  // Always accumulate buffers so toggling rv_show on mid-chart gives correct data.
  const rv_bars = bar.tf_secs > 0 ? Math.max(1, Math.round(rv_days * 86400 / bar.tf_secs)) : 1;
  const { rv_vwap: _rv, rv_sd: _rs } = calcRollingVwap(agg_tpv, agg_vol, agg_tp2v, rv_bars);
  let rv_vwap = null, rv_vah = null, rv_val = null;
  if (rv_show) {
    rv_vwap = _rv;
    if (rv_show_sd && _rv != null && _rs != null) {
      rv_vah = _rv + _rs;
      rv_val = _rv - _rs;
    }
  }

  // ── Label prefixes ────────────────────────────────────────────────────────
  const d_pfx = devPrefix(eff_tf);
  const p_pfx = prevPrefix(eff_tf);

  // ── Return plot spec ──────────────────────────────────────────────────────
  return {
    // Developing VWAP
    plots: [
      { id: "vwap",  value: vwap,                        color: c_vwap,  lineWidth: 2 },
      { id: "vah",   value: show_sd1 ? vhi  : null,      color: c_vah,   lineWidth: 1 },
      { id: "val",   value: show_sd1 ? vlo  : null,      color: c_val,   lineWidth: 1 },
      { id: "vah2",  value: show_sd2 ? vhi2 : null,      color: c_sd2,   lineWidth: 1 },
      { id: "val2",  value: show_sd2 ? vlo2 : null,      color: c_sd2,   lineWidth: 1 },
      { id: "vah3",  value: show_sd3 ? vhi3 : null,      color: c_sd3,   lineWidth: 1 },
      { id: "val3",  value: show_sd3 ? vlo3 : null,      color: c_sd3,   lineWidth: 1 },

      // Previous period
      { id: "pvwap", value: show_prev ? prev_vwap : null, color: c_pvwap, lineWidth: 1, style: "dashed" },
      { id: "pvah",  value: show_prev ? pvhi      : null, color: c_pvah,  lineWidth: 1, style: "dashed" },
      { id: "pval",  value: show_prev ? pvlo      : null, color: c_pval,  lineWidth: 1, style: "dashed" },

      // Rolling VWAP
      { id: "rv_vwap", value: rv_vwap,                   color: c_rv_vwap, lineWidth: 2 },
      { id: "rv_vah",  value: rv_vah,                    color: c_rv_vah,  lineWidth: 1 },
      { id: "rv_val",  value: rv_val,                    color: c_rv_val,  lineWidth: 1 },
    ],

    // Band fills
    fills: [
      // Developing value area (VAH ↔ VAL)
      shade_dev && show_sd1 && vhi != null && vlo != null
        ? { upper: "vah", lower: "val", color: c_fill_dev }
        : null,

      // Previous value area
      shade_prev && show_prev && pvhi != null && pvlo != null
        ? { upper: "pvah", lower: "pval", color: c_fill_prv }
        : null,

      // Rolling value area
      rv_shade && rv_show && rv_vah != null && rv_val != null
        ? { upper: "rv_vah", lower: "rv_val", color: c_rv_fill }
        : null,
    ].filter(Boolean),

    // Extension lines (extending to right-hand side on developing period)
    extensions: show_ext ? [
      vwap  != null ? { id: "ext_vwap", value: vwap,  color: c_vwap,  style: "dashed" } : null,
      vhi   != null ? { id: "ext_vah",  value: vhi,   color: c_vah,   style: "dashed" } : null,
      vlo   != null ? { id: "ext_val",  value: vlo,   color: c_val,   style: "dashed" } : null,
    ].filter(Boolean) : [],

    // Labels (rendered only on the latest bar)
    labels: show_lbl && bar.isLast ? [
      vwap  != null ? { id: "lbl_dvwap",  value: vwap,      text: `${d_pfx}VWAP ${vwap.toFixed(2)}`,      bgColor: c_lbl_d_bg, textColor: c_lbl_d_tx } : null,
      vhi   != null ? { id: "lbl_dvah",   value: vhi,       text: `${d_pfx}VAH ${vhi.toFixed(2)}`,        bgColor: c_lbl_d_bg, textColor: c_lbl_d_tx } : null,
      vlo   != null ? { id: "lbl_dval",   value: vlo,       text: `${d_pfx}VAL ${vlo.toFixed(2)}`,        bgColor: c_lbl_d_bg, textColor: c_lbl_d_tx } : null,

      show_prev && prev_vwap != null ? { id: "lbl_pvwap", value: prev_vwap, text: `${p_pfx}VWAP ${prev_vwap.toFixed(2)}`, bgColor: c_lbl_p_bg, textColor: c_lbl_p_tx } : null,
      show_prev && pvhi != null      ? { id: "lbl_pvah",  value: pvhi,      text: `${p_pfx}VAH ${pvhi.toFixed(2)}`,       bgColor: c_lbl_p_bg, textColor: c_lbl_p_tx } : null,
      show_prev && pvlo != null      ? { id: "lbl_pval",  value: pvlo,      text: `${p_pfx}VAL ${pvlo.toFixed(2)}`,       bgColor: c_lbl_p_bg, textColor: c_lbl_p_tx } : null,

      rv_show && rv_vwap != null ? { id: "lbl_rv_vwap", value: rv_vwap, text: `rvVWAP(${rv_days}d) ${rv_vwap.toFixed(2)}`, bgColor: c_rv_vwap, textColor: "#FFFFFF" } : null,
      rv_show && rv_vah  != null ? { id: "lbl_rv_vah",  value: rv_vah,  text: `rvVAH(${rv_days}d) ${rv_vah.toFixed(2)}`,  bgColor: c_rv_vah,  textColor: "#FFFFFF" } : null,
      rv_show && rv_val  != null ? { id: "lbl_rv_val",  value: rv_val,  text: `rvVAL(${rv_days}d) ${rv_val.toFixed(2)}`,  bgColor: c_rv_val,  textColor: "#FFFFFF" } : null,
    ].filter(Boolean) : [],

    // Metadata for the current bar
    meta: {
      new_period: new_per,
      eff_tf,
    },
  };
}

// ── Alerts ────────────────────────────────────────────────────────────────────
const alerts = [
  { id: "price_x_vwap",      description: "Price crossed Agg-VWAP",               condition: (bar, out) => crossesLevel("price_x_vwap",    bar.close, out.plots.find(p => p.id === "vwap")?.value)    },
  { id: "price_x_vah",       description: "Price crossed Agg-VAH (+1 SD)",         condition: (bar, out) => crossesLevel("price_x_vah",     bar.close, out.plots.find(p => p.id === "vah")?.value)     },
  { id: "price_x_val",       description: "Price crossed Agg-VAL (-1 SD)",         condition: (bar, out) => crossesLevel("price_x_val",     bar.close, out.plots.find(p => p.id === "val")?.value)     },
  { id: "price_x_pvwap",     description: "Price crossed Previous Agg-VWAP",       condition: (bar, out) => crossesLevel("price_x_pvwap",   bar.close, out.plots.find(p => p.id === "pvwap")?.value)   },
  { id: "price_x_rv_vwap",   description: "Price crossed Rolling VWAP",            condition: (bar, out) => crossesLevel("price_x_rv_vwap", bar.close, out.plots.find(p => p.id === "rv_vwap")?.value) },
  { id: "price_x_rv_vah",    description: "Price crossed Rolling VAH (+1 SD)",     condition: (bar, out) => crossesLevel("price_x_rv_vah",  bar.close, out.plots.find(p => p.id === "rv_vah")?.value)  },
  { id: "price_x_rv_val",    description: "Price crossed Rolling VAL (-1 SD)",     condition: (bar, out) => crossesLevel("price_x_rv_val",  bar.close, out.plots.find(p => p.id === "rv_val")?.value)  },
];

// Helper: returns true when close crosses level.
// Uses a per-alert-id Map so that evaluating multiple alerts on the same bar
// does not corrupt the shared prev-close state (bug present in v1).
const _prevCloseMap = new Map();
function crossesLevel(alertId, close, level) {
  const prevClose = _prevCloseMap.get(alertId) ?? null;
  _prevCloseMap.set(alertId, close);
  if (level == null || prevClose == null) return false;
  return (prevClose <= level && close > level) || (prevClose >= level && close < level);
}

// ── Exports (consumed by MMT platform runtime) ────────────────────────────────
// Guard against environments (e.g. MMT sandbox) where the CommonJS `module`
// global is not defined — the runtime consumes onBar/alerts directly.
// Settings are declared via input.* calls above (v2 API).
if (typeof module !== "undefined") {
  module.exports = {
    name:        "Lowkeigh-LTVW v2",
    shortTitle:  "Lowkeigh-LTVW v2",
    version:     2,
    overlay:     true,
    onBar,
    alerts,
  };
}
