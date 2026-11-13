"""SMIOT design tokens and shell styling.

One visual language for every page: greenhouse film white, vine green,
melon-flesh orange for "watch", red only for "act". Pages get this through
``pages.home.CUSTOM_CSS`` (fonts first, theme last so it wins over the
legacy rules it replaces).
"""

THEME_FONTS = """
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
"""

THEME_CSS = """
:root {
    --sm-film: #F1F3F2;
    --sm-surface: #FFFFFF;
    --sm-sunken: #F6F8F7;
    --sm-ink: #14261D;
    --sm-ink-2: #46574D;
    --sm-ink-3: #6B7A71;
    --sm-vine: #1B6447;
    --sm-vine-deep: #0F241B;
    --sm-vine-tint: #E3EEE6;
    --sm-net: #C9D3C8;
    --sm-net-soft: #E1E7E0;
    --sm-ok: #23774F;
    --sm-ok-tint: #E4F2E9;
    --sm-watch: #B4600C;
    --sm-watch-fill: #F08A24;
    --sm-watch-tint: #FDEFDD;
    --sm-act: #C2362B;
    --sm-act-tint: #FBE7E4;
    --sm-none: #7A8580;
    --sm-none-tint: #ECEFED;
    --sm-info: #2B5F8A;
    --sm-info-tint: #E5EEF5;
    --sm-dd: #632CA6;
    --sm-display: 'IBM Plex Sans', system-ui, -apple-system, 'Segoe UI', sans-serif;
    --sm-body: 'IBM Plex Sans', system-ui, -apple-system, 'Segoe UI', sans-serif;
    --sm-r-s: 4px;
    --sm-r-m: 6px;
    --sm-r-l: 8px;
    --sm-rail: 216px;
}

html, body, #q-app {
    background: var(--sm-film) !important;
    font-family: var(--sm-body) !important;
    color: var(--sm-ink);
    font-variant-numeric: tabular-nums;
    -webkit-font-smoothing: antialiased;
}
body .q-btn, body .q-field, body .q-item, body .q-table, body .q-tab { font-family: var(--sm-body); }

:focus-visible { outline: 2px solid var(--sm-vine); outline-offset: 2px; border-radius: 4px; }
a { color: var(--sm-vine); }

/* ── Rail (sidebar) ───────────────────────────── */
.sidebar {
    width: var(--sm-rail);
    background: var(--sm-vine-deep);
    backdrop-filter: none; -webkit-backdrop-filter: none;
    border-right: 0; box-shadow: none;
    overflow-y: auto; height: 100vh; scrollbar-width: none;
}
.sidebar::-webkit-scrollbar { display: none; }
.sidebar-logo {
    padding: 18px 18px 14px; border-bottom: 1px solid rgba(255,255,255,.09);
    color: #fff; gap: 10px;
}
.sidebar-logo .sm-brand { font-family: var(--sm-display); font-weight: 800; font-size: 19px; line-height: 1; color: #fff; letter-spacing: 0; }
.sidebar-logo .sm-brand-sub { font-size: 11px; color: #A9C3B4; font-weight: 500; margin-top: 3px; }
.sidebar-section {
    padding: 16px 18px 5px; font-size: 11px; font-weight: 600;
    color: #8FB09E; letter-spacing: 0; text-transform: none;
}
.nav-item {
    margin: 1px 10px; padding: 8px 10px; border-radius: var(--sm-r-s);
    color: #D5E3DA; font-size: 13.5px; font-weight: 500;
    transition: background .12s ease;
}
.nav-item i { color: #8FB09E; font-size: 17px; transition: none; }
.nav-item:hover { background: rgba(255,255,255,.07); color: #fff; }
.nav-item:hover i { color: #fff; transform: none; }
.nav-item.active { background: #F3F6F1; color: var(--sm-vine-deep); font-weight: 700; }
.nav-item.active i { color: var(--sm-vine); }
.nav-item.active::before { display: none; }
.sm-rail-foot { padding: 14px 18px; border-top: 1px solid rgba(255,255,255,.09); font-size: 11px; color: #8FB09E; line-height: 1.5; }

.main-content { padding-left: var(--sm-rail); background: var(--sm-film); }

/* ── Top bar ──────────────────────────────────── */
.top-bar {
    background: var(--sm-surface); border-bottom: 1px solid var(--sm-net-soft);
    padding: 10px 22px !important; gap: 12px; min-height: 58px;
}
.top-bar-title { gap: 12px !important; min-width: 0; }
.sm-page-title { font-family: var(--sm-display); font-weight: 700; font-size: 20px; line-height: 1.15; color: var(--sm-ink); }
.sm-farm-pick .q-field__native, .sm-farm-pick .q-field__input { font-weight: 600; color: var(--sm-vine-deep); font-size: 13px; }
.sm-farm-pick { background: var(--sm-vine-tint); border-radius: var(--sm-r-s); padding: 0 10px; min-width: 168px; }
.sm-farm-static { background: var(--sm-vine-tint); color: var(--sm-vine-deep); font-weight: 600; font-size: 13px; padding: 6px 10px; border-radius: var(--sm-r-s); }
.sm-user { display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 13px; font-weight: 600; color: var(--sm-ink); }

.content-area { padding: 20px 22px 28px; background: var(--sm-film); }

/* ── Surfaces: no hover lift, no glass, no moving gradients ── */
.card, .glass-card {
    background: var(--sm-surface) !important; border: 1px solid var(--sm-net-soft) !important;
    border-radius: var(--sm-r-l); box-shadow: none !important;
    backdrop-filter: none !important; -webkit-backdrop-filter: none !important;
    transition: none !important;
}
.card:hover, .hover-elevate:hover, .weather-card:hover, .ai-card:hover {
    transform: none !important; box-shadow: none !important; border-color: var(--sm-net) !important;
}
.neon-glow, .neon-glow:hover { box-shadow: none !important; }
.shimmer-overlay { display: none !important; }
.progress-bar::after { display: none; }
.card-title { font-family: var(--sm-display); font-size: 16px; color: var(--sm-ink); }
.metric-box { background: var(--sm-sunken); border-radius: var(--sm-r-m); }
.metric-label, .sub-section, .section-header {
    text-transform: none; letter-spacing: 0; font-size: 12px; font-weight: 600; color: var(--sm-ink-3);
}
.metric-value { color: var(--sm-ink); font-family: var(--sm-display); }
.weather-card { background: var(--sm-vine-deep); animation: none; border-radius: var(--sm-r-l); }
.ai-card { background: var(--sm-ink); border: 0 !important; border-radius: var(--sm-r-l); box-shadow: none; }
.flow-total-box { background: var(--sm-ink); }
.badge { text-transform: none; letter-spacing: 0; font-weight: 600; border-radius: var(--sm-r-s); }
.dot-green, .dot-blue, .dot-red, .dot-yellow { animation: none; }

/* ── Kit: page header ─────────────────────────── */
.sm-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin-bottom: 16px; }
.sm-head h1, .sm-h1 { font-family: var(--sm-display); font-weight: 800; font-size: 28px; line-height: 1.1; margin: 0; color: var(--sm-ink); }
.sm-head p, .sm-lede { margin: 6px 0 0; font-size: 14px; line-height: 1.5; color: var(--sm-ink-2); max-width: 68ch; }
.sm-h2 { font-family: var(--sm-display); font-weight: 700; font-size: 18px; line-height: 1.2; color: var(--sm-ink); margin: 0; }
.sm-note { font-size: 12px; line-height: 1.45; color: var(--sm-ink-3); }

/* ── Kit: panel ───────────────────────────────── */
.sm-panel { background: var(--sm-surface); border: 1px solid var(--sm-net-soft); border-radius: var(--sm-r-l); padding: 16px 18px; width: 100%; min-width: 0; }
.sm-panel-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
.sm-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 0; border-top: 1px solid var(--sm-net-soft); min-width: 0; }
.sm-row:first-child { border-top: 0; }

/* ── Kit: status chip (shape + word, never colour alone) ── */
.sm-chip {
    display: inline-flex; align-items: center; gap: 6px; white-space: nowrap;
    font-size: 12px; font-weight: 600; line-height: 1; padding: 5px 9px; border-radius: var(--sm-r-s);
    background: var(--sm-none-tint); color: var(--sm-ink-2);
}
.sm-chip::before { content: '○'; font-size: 10px; line-height: 1; }
.sm-chip.ok { background: var(--sm-ok-tint); color: var(--sm-ok); }
.sm-chip.ok::before { content: '●'; }
.sm-chip.watch { background: var(--sm-watch-tint); color: var(--sm-watch); }
.sm-chip.watch::before { content: '▲'; }
.sm-chip.act { background: var(--sm-act-tint); color: var(--sm-act); }
.sm-chip.act::before { content: '■'; }
.sm-chip.stale { background: var(--sm-none-tint); color: var(--sm-ink-2); }
.sm-chip.stale::before { content: '◐'; }
.sm-chip.info { background: var(--sm-info-tint); color: var(--sm-info); }
.sm-chip.info::before { content: '◆'; }
.sm-chip.sim { background: transparent; color: var(--sm-watch); border: 1px dashed var(--sm-watch-fill); }
.sm-chip.sim::before { content: none; }

/* ── Kit: evidence chain (sent → ACK → verified) ── */
.sm-chain { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(0, 1fr); gap: 0; width: 100%; }
.sm-step { position: relative; padding: 0 10px 0 0; min-width: 0; }
.sm-step-mark { display: flex; align-items: center; gap: 0; margin-bottom: 7px; }
.sm-step-dot {
    width: 18px; height: 18px; border-radius: 50%; flex: none; box-sizing: border-box;
    border: 2px solid var(--sm-net); background: var(--sm-surface);
    display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; color: #fff;
}
.sm-step-line { flex: 1; height: 2px; background: var(--sm-net-soft); margin-left: 4px; }
.sm-step:last-child .sm-step-line { display: none; }
.sm-step.done .sm-step-dot { background: var(--sm-ok); border-color: var(--sm-ok); }
.sm-step.done .sm-step-dot::after { content: '✓'; }
.sm-step.done .sm-step-line { background: var(--sm-ok); }
.sm-step.waiting .sm-step-dot { border-color: var(--sm-watch-fill); border-style: dashed; }
.sm-step.failed .sm-step-dot { background: var(--sm-act); border-color: var(--sm-act); }
.sm-step.failed .sm-step-dot::after { content: '!'; }
.sm-step-label { font-size: 13px; font-weight: 600; color: var(--sm-ink); line-height: 1.25; }
.sm-step.none .sm-step-label { color: var(--sm-ink-3); font-weight: 500; }
.sm-step-detail { font-size: 12px; color: var(--sm-ink-3); line-height: 1.4; margin-top: 2px; overflow-wrap: anywhere; }
.sm-step.failed .sm-step-detail { color: var(--sm-act); }
.sm-step.waiting .sm-step-detail { color: var(--sm-watch); }

/* ── Kit: loading / stale / empty / error ─────── */
.sm-state { display: flex; gap: 12px; align-items: flex-start; padding: 16px 18px; border-radius: var(--sm-r-m); background: var(--sm-sunken); border: 1px dashed var(--sm-net); width: 100%; }
.sm-state-mark { font-size: 16px; line-height: 1.3; color: var(--sm-ink-3); flex: none; width: 18px; text-align: center; }
.sm-state-title { font-size: 14px; font-weight: 600; color: var(--sm-ink); line-height: 1.35; }
.sm-state-detail { font-size: 13px; color: var(--sm-ink-2); line-height: 1.45; margin-top: 2px; max-width: 64ch; }
.sm-state.error { background: var(--sm-act-tint); border: 1px solid #EFC4BE; }
.sm-state.error .sm-state-mark, .sm-state.error .sm-state-title { color: var(--sm-act); }
.sm-state.stale { background: var(--sm-watch-tint); border: 1px solid #F3D3A8; }
.sm-state.stale .sm-state-mark, .sm-state.stale .sm-state-title { color: var(--sm-watch); }
.sm-state.loading .sm-state-mark { animation: sm-spin 1s linear infinite; }
@keyframes sm-spin { to { transform: rotate(360deg); } }
.sm-skeleton { border-radius: var(--sm-r-m); background: var(--sm-net-soft); min-height: 14px; }

/* ── Kit: buttons and links ───────────────────── */
.sm-btn.q-btn { background: var(--sm-vine) !important; color: #fff !important; border-radius: var(--sm-r-s); font-weight: 600; text-transform: none; padding: 4px 14px; box-shadow: none; }
.sm-btn-quiet.q-btn { background: transparent !important; color: var(--sm-vine) !important; border: 1px solid var(--sm-net); border-radius: var(--sm-r-s); font-weight: 600; text-transform: none; padding: 4px 12px; box-shadow: none; }
.sm-btn-danger.q-btn { background: var(--sm-act) !important; color: #fff !important; border-radius: var(--sm-r-s); font-weight: 600; text-transform: none; box-shadow: none; }
.sm-link { color: var(--sm-vine); font-weight: 600; font-size: 13px; text-decoration: underline; text-underline-offset: 3px; text-decoration-color: var(--sm-net); }
.sm-link:hover { text-decoration-color: var(--sm-vine); }
.sm-ext::after { content: ' ↗'; font-weight: 500; }

/* ── Kit: key/value facts and tables ──────────── */
.sm-facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px 18px; }
.sm-fact-k { font-size: 12px; color: var(--sm-ink-3); line-height: 1.3; }
.sm-fact-v { font-size: 15px; font-weight: 600; color: var(--sm-ink); line-height: 1.3; overflow-wrap: anywhere; }
.sm-big { font-family: var(--sm-display); font-weight: 800; font-size: 32px; line-height: 1; color: var(--sm-ink); }
.sm-id { font-size: 12px; color: var(--sm-ink-3); overflow-wrap: anywhere; }

/* ── Phone ────────────────────────────────────── */
@media (max-width: 768px) {
    .main-content { padding-left: 0; }
    .sidebar {
        width: 100%; height: 62px; background: var(--sm-vine-deep);
        border-top: 0; box-shadow: none; backdrop-filter: none; -webkit-backdrop-filter: none;
        padding: 0 6px;
    }
    .sidebar-logo, .sidebar-section, .sm-rail-foot, .sm-rail-gap { display: none !important; }
    .nav-item { color: #D5E3DA; min-width: 68px; border-radius: var(--sm-r-s); margin: 0 1px; }
    .nav-item i { color: #8FB09E; }
    .nav-item.active { background: #F3F6F1; color: var(--sm-vine-deep); }
    .nav-item.active i { color: var(--sm-vine); }
    .top-bar { padding: 8px 14px !important; min-height: 0; }
    .sm-page-title { font-size: 17px; }
    .sm-farm-pick { min-width: 0; width: 150px !important; }
    .sm-user-name { display: none; }
    .content-area { padding: 14px 14px 24px !important; }
    .sm-head h1, .sm-h1 { font-size: 23px; }
    .sm-panel { padding: 14px; }
    .sm-chain { grid-auto-flow: row; grid-auto-columns: auto; gap: 10px; }
    .sm-step { display: grid; grid-template-columns: 22px 1fr; column-gap: 8px; padding: 0; }
    .sm-step-mark { margin: 0; grid-row: span 2; align-items: flex-start; }
    .sm-step-line { display: none; }
}

@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation: none !important; transition: none !important; }
}
"""

# ── Second layer: Quasar alignment, numbers, tables, charts, greenhouse bays ──
THEME_CSS += """
body {
    --q-primary: #1F5A41 !important; --q-secondary: #46574D !important; --q-accent: #F08A24 !important;
    --q-positive: #23774F !important; --q-negative: #C2362B !important; --q-warning: #F08A24 !important;
    --q-info: #2B5F8A !important; --q-dark: #14261D !important;
}
::selection { background: #CFE3D5; color: var(--sm-ink); }
.content-area { scrollbar-width: thin; scrollbar-color: var(--sm-net) transparent; }
.content-area > * { max-width: 1480px; width: 100%; margin-inline: auto; }

/* Quasar pieces every page uses */
.q-btn { text-transform: none; letter-spacing: 0; font-weight: 600; border-radius: var(--sm-r-s); }
.q-btn:before { box-shadow: none !important; }
.q-card { border-radius: var(--sm-r-l); box-shadow: none; border: 1px solid var(--sm-net-soft); }
.q-dialog__backdrop { background: rgba(20,38,29,.46); }
.q-dialog .q-card { border: 0; box-shadow: 0 18px 50px rgba(20,38,29,.22); }
.q-menu { border-radius: var(--sm-r-m); border: 1px solid var(--sm-net-soft); box-shadow: 0 10px 30px rgba(20,38,29,.12); }
.q-field--outlined .q-field__control { border-radius: var(--sm-r-s); }
.q-field--outlined .q-field__control:before { border-color: var(--sm-net); }
.q-notification { border-radius: var(--sm-r-m); font-weight: 500; box-shadow: 0 10px 30px rgba(20,38,29,.18); }
.q-tab { text-transform: none; font-weight: 600; letter-spacing: 0; }
.q-tab__indicator { height: 3px; border-radius: 3px 3px 0 0; }
.q-table__card { box-shadow: none; border: 1px solid var(--sm-net-soft); border-radius: var(--sm-r-l); }
.q-table thead th { font-size: 12px; font-weight: 600; color: var(--sm-ink-3); background: var(--sm-sunken); }
.q-table tbody td { font-size: 13px; color: var(--sm-ink); border-color: var(--sm-net-soft); }
.q-separator { background: var(--sm-net-soft); }

/* Bell */
.sm-bell { width: 38px; height: 38px; border-radius: var(--sm-r-s); border: 1px solid var(--sm-net-soft); background: var(--sm-surface); display: flex; align-items: center; justify-content: center; cursor: pointer; position: relative; }
.sm-bell:hover { border-color: var(--sm-net); background: var(--sm-sunken); }
.sm-bell-count { position: absolute; top: -6px; right: -6px; min-width: 18px; height: 18px; padding: 0 4px; border-radius: 9px; background: var(--sm-act); color: #fff; font-size: 11px; font-weight: 700; display: flex; align-items: center; justify-content: center; border: 2px solid var(--sm-surface); }

/* Number tile: value, unit, then when and where it came from */
.sm-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1px; background: var(--sm-net-soft); border: 1px solid var(--sm-net-soft); border-radius: var(--sm-r-l); overflow: hidden; }
.sm-stat { background: var(--sm-surface); padding: 14px 16px; min-width: 0; }
.sm-stat-k { font-size: 12px; color: var(--sm-ink-3); line-height: 1.3; }
.sm-stat-v { font-family: var(--sm-display); font-weight: 700; font-size: 26px; line-height: 1.1; color: var(--sm-ink); margin-top: 4px; white-space: nowrap; }
.sm-stat-v small { font-family: var(--sm-body); font-size: 13px; font-weight: 500; color: var(--sm-ink-3); margin-left: 3px; }
.sm-stat-m { font-size: 11.5px; color: var(--sm-ink-3); line-height: 1.35; margin-top: 4px; }
.sm-stat.watch .sm-stat-v { color: var(--sm-watch); }
.sm-stat.act .sm-stat-v { color: var(--sm-act); }
.sm-stat.none .sm-stat-v { color: var(--sm-none); }

/* Plain table */
.sm-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.sm-table th { text-align: left; font-size: 12px; font-weight: 600; color: var(--sm-ink-3); padding: 8px 12px; background: var(--sm-sunken); border-bottom: 1px solid var(--sm-net-soft); white-space: nowrap; }
.sm-table td { padding: 9px 12px; border-bottom: 1px solid var(--sm-net-soft); color: var(--sm-ink); vertical-align: top; }
.sm-table tr:last-child td { border-bottom: 0; }
.sm-table td.num, .sm-table th.num { text-align: right; }

/* Layout helpers */
.sm-stack { display: flex; flex-direction: column; gap: 16px; width: 100%; min-width: 0; }
.sm-split { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr); gap: 16px; align-items: start; width: 100%; }
.sm-cols-2 { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; width: 100%; }
.sm-cols-3 { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; width: 100%; }
.sm-inline { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; min-width: 0; }
.sm-banner { display: flex; align-items: center; gap: 10px; padding: 9px 14px; border-radius: var(--sm-r-m); background: var(--sm-watch-tint); color: var(--sm-watch); font-size: 13px; font-weight: 500; width: 100%; }
.sm-banner.act { background: var(--sm-act-tint); color: var(--sm-act); }

/* Numbered case-file sections (real sequences only) */
.sm-file-step { display: grid; grid-template-columns: 34px minmax(0, 1fr); gap: 0 14px; width: 100%; }
.sm-file-no { width: 34px; height: 34px; border-radius: 50%; background: var(--sm-vine-tint); color: var(--sm-vine-deep); font-family: var(--sm-display); font-weight: 700; font-size: 16px; display: flex; align-items: center; justify-content: center; }
.sm-file-step.done .sm-file-no { background: var(--sm-vine); color: #fff; }
.sm-file-step.missing .sm-file-no { background: var(--sm-none-tint); color: var(--sm-none); }
.sm-file-rail { grid-column: 1; justify-self: center; width: 2px; background: var(--sm-net-soft); min-height: 14px; }
.sm-file-body { padding-bottom: 18px; min-width: 0; }

/* Greenhouse bays: the fleet at a glance */
.sm-bays { display: grid; grid-template-columns: repeat(10, minmax(0, 1fr)); gap: 6px; width: 100%; align-items: start; }
.sm-bay { appearance: none; border: 0; background: transparent; padding: 6px 2px 8px; margin: 0; cursor: pointer; text-align: center; font: inherit; color: inherit; border-radius: var(--sm-r-m); min-width: 0; display: flex; flex-direction: column; align-items: center; }
.sm-bay:hover { background: rgba(31,90,65,.06); }
.sm-bay svg { width: 100%; height: auto; display: block; max-width: 132px; }
.sm-bay .skin { fill: var(--sm-none-tint); stroke: var(--sm-none); }
.sm-bay .rib { stroke: var(--sm-none); opacity: .45; }
.sm-bay .crop { stroke: var(--sm-none); opacity: .5; }
.sm-bay.ok .skin { fill: var(--sm-ok-tint); stroke: var(--sm-ok); }
.sm-bay.ok .rib, .sm-bay.ok .crop { stroke: var(--sm-ok); }
.sm-bay.watch .skin { fill: var(--sm-watch-tint); stroke: var(--sm-watch-fill); }
.sm-bay.watch .rib, .sm-bay.watch .crop { stroke: var(--sm-watch-fill); }
.sm-bay.act .skin { fill: var(--sm-act); stroke: var(--sm-act); }
.sm-bay.act .rib, .sm-bay.act .crop { stroke: #fff; opacity: .55; }
.sm-bay.none .skin { stroke-dasharray: 5 4; }
.sm-bay-name { font-family: var(--sm-display); font-weight: 700; font-size: 14px; line-height: 1.2; color: var(--sm-ink); margin-top: 6px; }
.sm-bay-state { font-size: 12px; font-weight: 600; line-height: 1.2; margin-top: 3px; color: var(--sm-ink-3); }
.sm-bay.ok .sm-bay-state { color: var(--sm-ok); }
.sm-bay.watch .sm-bay-state { color: var(--sm-watch); }
.sm-bay.act .sm-bay-state { color: var(--sm-act); }
.sm-bay-cause { font-size: 11.5px; line-height: 1.35; color: var(--sm-ink-2); margin-top: 3px; overflow-wrap: anywhere; }
.sm-ground { height: 3px; background: var(--sm-vine-deep); border-radius: 2px; opacity: .8; margin-top: -2px; }

@media (max-width: 1180px) {
    .sm-bays { grid-template-columns: repeat(5, minmax(0, 1fr)); row-gap: 14px; }
    .sm-split { grid-template-columns: minmax(0, 1fr); }
    .sm-cols-3 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 768px) {
    .sm-cols-2, .sm-cols-3 { grid-template-columns: minmax(0, 1fr); }
    .sm-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .sm-stat-v { font-size: 22px; }
    .sm-bay-cause { display: none; }
    .sm-bay-name { font-size: 12.5px; }
    .sm-bay-state { font-size: 11px; }
    .sm-file-step { grid-template-columns: 28px minmax(0, 1fr); gap: 0 10px; }
    .sm-file-no { width: 28px; height: 28px; font-size: 14px; }
}
"""

THEME_CSS += """
.sm-ground { display: none; }
@media (max-width: 768px) {
    .top-bar { flex-wrap: nowrap !important; gap: 8px; }
    .top-bar-title { flex-wrap: nowrap !important; flex: 1 1 auto; }
    .top-bar > div:last-child { flex-wrap: nowrap !important; gap: 8px !important; flex: none; }
    .top-bar .sm-chip.ok { display: none; }
    .top-bar .sm-chip.sim { font-size: 11px; padding: 4px 6px; }
    .top-bar .sm-chip.act { font-size: 11px; padding: 4px 6px; }
    .sm-page-title { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .sm-farm-pick { width: 132px !important; }
    .sm-bays { gap: 2px; }
}
@media (max-width: 420px) {
    /* The simulation label never disappears; it only shortens. */
    .top-bar .sm-chip.sim { font-size: 0; }
    .top-bar .sm-chip.sim::after { content: 'Mô phỏng'; font-size: 11px; }
}
"""

# ── Control-room density: one technical typeface, flat surfaces, compact rows ──
THEME_CSS += """
html, body, #q-app { font-size: 13.5px; line-height: 1.45; }
.sidebar-logo .sm-brand { font-weight: 700; font-size: 16px; letter-spacing: .04em; }
.sidebar-logo .sm-brand-sub { font-size: 11px; }
.sidebar-section { font-size: 10.5px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: #6F9282; padding: 18px 18px 6px; }
.nav-item { font-size: 13px; padding: 7px 10px; border-radius: 4px; }
.nav-item.active { background: rgba(255,255,255,.10); color: #fff; font-weight: 600; box-shadow: inset 2px 0 0 #6FD3A2; }
.nav-item.active i { color: #6FD3A2; }
.top-bar { min-height: 52px; padding: 8px 20px !important; }
.sm-page-title { font-weight: 600; font-size: 16px; }
.content-area { padding: 18px 20px 28px; }
.sm-head { margin-bottom: 14px; align-items: center; }
.sm-head h1, .sm-h1 { font-weight: 600; font-size: 22px; line-height: 1.25; letter-spacing: -.01em; }
.sm-head p, .sm-lede { font-size: 13px; margin-top: 3px; color: var(--sm-ink-3); }
.sm-h2 { font-weight: 600; font-size: 14.5px; }
.card-title { font-weight: 600; font-size: 14.5px; }
.sm-panel { padding: 14px 16px; }
.sm-panel-head { margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid var(--sm-net-soft); }
.sm-row { padding: 8px 0; }
.sm-chip { font-size: 11.5px; font-weight: 500; padding: 3px 7px; border-radius: 3px; gap: 5px; }
.sm-chip::before { font-size: 8px; }
.sm-stat { padding: 12px 14px; }
.sm-stat-k { font-size: 11.5px; }
.sm-stat-v { font-weight: 600; font-size: 22px; letter-spacing: -.01em; }
.sm-stat-v small { font-size: 12px; }
.sm-big { font-weight: 600; font-size: 26px; }
.sm-step-dot { width: 16px; height: 16px; font-size: 9px; }
.sm-step-label { font-size: 12.5px; }
.sm-step-detail { font-size: 11.5px; }
.sm-state { padding: 12px 14px; }
.sm-state-title { font-size: 13px; }
.sm-state-detail { font-size: 12.5px; }
.sm-file-no { font-weight: 600; font-size: 13px; width: 28px; height: 28px; border-radius: 4px; }
.sm-file-step { grid-template-columns: 28px minmax(0, 1fr); }
.metric-value { font-weight: 600; }

/* Fleet board: ten cells in two rows of five, read left to right */
.sm-bays { gap: 8px; grid-template-columns: repeat(5, minmax(0, 1fr)); }
.sm-bay {
    align-items: stretch; text-align: left; padding: 10px 10px 10px 12px; min-height: 92px;
    background: var(--sm-surface); border: 1px solid var(--sm-net-soft); border-left: 3px solid var(--sm-none);
    border-radius: 4px;
}
.sm-bay:hover { background: var(--sm-sunken); border-color: var(--sm-net); }
.sm-bay.ok { border-left-color: var(--sm-ok); }
.sm-bay.watch { border-left-color: var(--sm-watch-fill); background: #FFFBF5; }
.sm-bay.act { border-left-color: var(--sm-act); background: #FFF7F6; }
.sm-bay.none { border-left-style: dashed; }
.sm-bay-name { font-weight: 600; font-size: 13px; margin-top: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sm-bay-state { font-size: 11.5px; font-weight: 500; margin-top: 4px; }
.sm-bay-cause { font-size: 11.5px; margin-top: 6px; color: var(--sm-ink-2); }
.sm-bay-age { font-size: 11px; color: var(--sm-ink-3); margin-top: auto; padding-top: 6px; }
@media (max-width: 768px) {
    .sm-bays { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; row-gap: 6px; }
    .sm-bay { min-height: 0; padding: 8px 8px 8px 10px; }
    .sm-bay-cause { display: block; }
    .nav-item.active { box-shadow: inset 0 2px 0 #6FD3A2; background: rgba(255,255,255,.10); color: #fff; }
    .nav-item.active i { color: #6FD3A2; }
    .sm-head h1, .sm-h1 { font-size: 18px; }
}
"""
# ── Farm switcher, time-range pills, chart frame ──
THEME_CSS += """
.sm-farmtabs { display: flex; gap: 4px; width: 100%; overflow-x: auto; scrollbar-width: none; padding: 3px; background: var(--sm-surface); border: 1px solid var(--sm-net-soft); border-radius: 6px; }
.sm-farmtabs::-webkit-scrollbar { display: none; }
.sm-farmtab { appearance: none; border: 0; background: transparent; font: inherit; cursor: pointer; flex: 1 0 auto; display: inline-flex; align-items: center; justify-content: center; gap: 6px; padding: 6px 10px; border-radius: 4px; font-size: 12.5px; font-weight: 500; color: var(--sm-ink-2); white-space: nowrap; }
.sm-farmtab:hover { background: var(--sm-sunken); }
.sm-farmtab.active { background: var(--sm-vine-deep); color: #fff; font-weight: 600; }
.sm-farmtab::before { content: '●'; font-size: 8px; color: var(--sm-none); }
.sm-farmtab.ok::before { color: var(--sm-ok); }
.sm-farmtab.watch::before { content: '▲'; color: var(--sm-watch-fill); }
.sm-farmtab.act::before { content: '■'; color: var(--sm-act); }
.sm-farmtab.none::before { content: '○'; }
.sm-farmtab.all::before { content: none; }
.sm-pills { display: inline-flex; padding: 2px; background: var(--sm-sunken); border: 1px solid var(--sm-net-soft); border-radius: 4px; gap: 2px; }
.sm-pill { appearance: none; border: 0; background: transparent; font: inherit; cursor: pointer; padding: 3px 9px; border-radius: 3px; font-size: 12px; font-weight: 500; color: var(--sm-ink-2); }
.sm-pill.active { background: var(--sm-surface); color: var(--sm-ink); font-weight: 600; box-shadow: 0 0 0 1px var(--sm-net); }
.sm-chart { width: 100%; min-width: 0; }
.sm-scroll-x { width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; }
.sm-source { font-size: 12px; color: var(--sm-ink-3); margin-top: 6px; }

/* Vai nguon du lieu: tim = Datadog (doc qua API, chi doc), xanh = MongoDB */
.sm-stat-v.text { font-size: 15px; line-height: 1.3; white-space: normal; overflow-wrap: anywhere; }
.sm-code { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 12px; color: var(--sm-ink-3); overflow-wrap: anywhere; word-break: break-all; }
.dd-panel { border-left: 3px solid var(--sm-dd) !important; }
.mongo-panel { border-left: 3px solid var(--sm-vine) !important; }
.dd-src { font-size: 12px; color: var(--sm-dd); font-weight: 600; margin-left: auto; }
.dd-card { display: block; text-decoration: none; color: inherit; background: var(--sm-surface); border: 1px solid var(--sm-net-soft); border-left: 3px solid var(--sm-dd); border-radius: var(--sm-r-s); padding: 10px 12px; min-width: 0; min-height: 44px; }
.dd-card:hover { background: var(--sm-sunken); }
.dd-card.off { background: var(--sm-sunken); border-style: dashed; border-left-color: var(--sm-net); }
.dd-card-t { font-weight: 600; font-size: 13px; color: var(--sm-vine); }
.dd-card.off .dd-card-t { color: var(--sm-ink-3); }
.dd-card-d { font-size: 12px; color: var(--sm-ink-2); margin-top: 3px; line-height: 1.4; }
.dd-card-go { font-size: 12px; color: var(--sm-dd); margin-top: 6px; font-weight: 600; }
.dd-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px; width: 100%; margin-top: 10px; }
.dd-cases { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; width: 100%; }
.dd-case { background: var(--sm-surface); border: 1px solid var(--sm-net-soft); border-left: 3px solid var(--sm-dd); border-radius: var(--sm-r-s); padding: 10px 12px; min-width: 0; display: flex; flex-direction: column; gap: 5px; }
.dd-case.on { background: #F4EFFA; }
.dd-case-btn { appearance: none; border: 0; background: transparent; padding: 0; text-align: left; font: inherit; cursor: pointer; color: var(--sm-ink); font-weight: 600; font-size: 13px; line-height: 1.35; }
.sm-phase { background: var(--sm-surface); border: 1px solid var(--sm-net-soft); border-left: 3px solid var(--sm-vine); border-radius: var(--sm-r-l); padding: 14px 16px; width: 100%; min-width: 0; }
.sm-phase.datadog { border-left-color: var(--sm-dd); }
.sm-phase.mixed { border-left-color: var(--sm-dd); border-right: 3px solid var(--sm-vine); }
.sm-phase-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--sm-net-soft); }
.sm-phase-no { width: 26px; height: 26px; border-radius: 4px; background: var(--sm-vine); color: #fff; font-weight: 700; font-size: 13px; display: flex; align-items: center; justify-content: center; }
.sm-phase.datadog .sm-phase-no, .sm-phase.mixed .sm-phase-no { background: var(--sm-dd); }
.sm-phase-no.missing { background: var(--sm-none); }
.sm-phase-src { font-size: 12px; color: var(--sm-ink-3); margin-left: auto; }
.sm-phase-body { display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.sm-phases { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1px; background: var(--sm-net-soft); border: 1px solid var(--sm-net-soft); border-radius: var(--sm-r-l); overflow: hidden; width: 100%; }
.sm-phases > div { background: var(--sm-surface); padding: 12px 14px; min-width: 0; }
.sm-phases .ph-t { font-size: 12px; font-weight: 700; color: var(--sm-dd); }
.sm-phases .ph-t.mongo { color: var(--sm-vine); }
.sm-phases .ph-1 { font-size: 13.5px; font-weight: 600; margin-top: 4px; overflow-wrap: anywhere; }
.sm-phases .ph-2 { font-size: 12px; color: var(--sm-ink-2); margin-top: 3px; }
.sm-dots { display: inline-flex; gap: 4px; align-items: center; }
.sm-dot { width: 18px; height: 18px; border-radius: 50%; font-size: 10px; font-weight: 700; display: inline-flex; align-items: center; justify-content: center; border: 1px solid var(--sm-net); color: var(--sm-ink-3); background: var(--sm-surface); }
.sm-dot.done { background: var(--sm-ok); border-color: var(--sm-ok); color: #fff; }
.sm-dot.wait { border-color: var(--sm-watch-fill); color: var(--sm-watch); }
.sm-tabs { display: flex; gap: 4px; flex-wrap: wrap; }
.sm-tab { appearance: none; border: 1px solid var(--sm-net-soft); background: var(--sm-surface); font: inherit; cursor: pointer; padding: 6px 12px; border-radius: var(--sm-r-s); font-size: 13px; font-weight: 500; color: var(--sm-ink-2); min-height: 36px; }
.sm-tab.active { background: var(--sm-vine-deep); color: #fff; border-color: var(--sm-vine-deep); font-weight: 600; }
@media (max-width: 1180px) { .dd-cases { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 768px) {
    .dd-cases { grid-template-columns: 1fr; }
    .sm-phases { grid-template-columns: minmax(0, 1fr); }
    .dd-cases { grid-template-columns: minmax(0, 1fr); }
    .sm-stack-table .sm-table { min-width: 0 !important; }
    .sm-stack-table .sm-table thead { display: none; }
    .sm-stack-table .sm-table, .sm-stack-table .sm-table tbody, .sm-stack-table .sm-table tr, .sm-stack-table .sm-table td { display: block; width: 100%; }
    .sm-stack-table .sm-table tr { border: 1px solid var(--sm-net-soft); border-radius: var(--sm-r-m); margin-bottom: 8px; padding: 6px 10px; }
    .sm-stack-table .sm-table td { border: 0; padding: 4px 0; display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; }
    .sm-stack-table .sm-table td::before { content: attr(data-label); font-size: 12px; color: var(--sm-ink-3); min-width: 84px; font-weight: 600; }
    .sm-stack-table .sm-table td[data-label=""]::before { content: none; }
}
"""
# Chart colours for echarts/SVG. Status colours never double as series colours.
CHART = {
    "font": "IBM Plex Sans, system-ui, sans-serif",
    "ink": "#14261D", "muted": "#6B7A71", "grid": "#E1E7E0", "surface": "#FFFFFF",
    "series": ["#1B6447", "#2B5F8A", "#B58A1B", "#7A4E6B", "#5E9C8F", "#8A6A4A"],
    "level": {"ok": "#23774F", "watch": "#F08A24", "act": "#C2362B", "none": "#7A8580", "info": "#2B5F8A"},
    "tint": {"ok": "#E4F2E9", "watch": "#FDEFDD", "act": "#FBE7E4", "none": "#ECEFED", "info": "#E5EEF5"},
    "band": "rgba(240,138,36,.16)",
    "dd": "#632CA6",
}
