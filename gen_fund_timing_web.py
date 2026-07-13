# -*- coding: utf-8 -*-
"""生成 基金IRR汇总_按日XIRR.html + 三只基金独立明细页。
唯一数据源: _fund_timing_batch.json (由 calc_fund_timing_batch.py 产出)。
- 第一部分「聚合择时评价」与第二部分的 XIRR 均读取同一份 json, 杜绝双源不一致。
- 基金名在两张表里均为超链接, 跳转对应明细页。
- 同时生成 基金明细_{code}.html (净值轨迹SVG + 逐笔择时判断表 + 一句话结论 + 返回链接)。
"""
import json, os, re
from datetime import date, datetime
import numpy as np

ROOT = r"E:\AKshare"
VAL_DATE = date(2026, 7, 12)
DATA = json.load(open(os.path.join(ROOT, "_fund_timing_batch.json"), encoding="utf-8"))

DETAIL_PREFIX = "基金明细_"

def pct(v, d=2):
    return "—" if v is None else f"{v*100:.{d}f}%"

def money(v, d=2):
    return "—" if v is None else f"{v:,.{d}f}"

def sign_color(v):
    """中国习惯: 涨(正)=红, 跌(负)=绿"""
    if v is None:
        return "#888"
    return "#d4380d" if v >= 0 else "#237804"

def to_ord(s):
    return datetime.strptime(s, "%Y-%m-%d").toordinal()

# ============ 共享 CSS ============
CSS = """
  * { box-sizing: border-box; }
  body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
         background:#f5f6f8; color:#1f2329; margin:0; padding:24px; }
  .wrap { max-width:1080px; margin:0 auto; }
  h1 { font-size:22px; margin:0 0 4px; }
  h2 { font-size:17px; margin:0 0 10px; color:#1f2329; }
  .subtitle { color:#8a8f99; font-size:13px; margin-bottom:18px; }
  .panel { background:#fff; border:1px solid #e8e8ec; border-radius:10px; padding:18px 20px; margin-bottom:18px; box-shadow:0 1px 3px rgba(0,0,0,.04); }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th, td { padding:8px 10px; text-align:left; border-bottom:1px solid #f0f0f3; }
  th { background:#fafafb; color:#646a73; font-weight:600; }
  td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
  td.code { font-family:monospace; font-weight:600; }
  td.name { color:#41464c; }
  td.name a { color:#0958d9; text-decoration:none; }
  td.name a:hover { text-decoration:underline; }
  .summary thead th { position:sticky; top:0; }
  .method { font-size:13px; line-height:1.7; color:#41464c; }
  .method code { background:#f2f3f5; padding:1px 5px; border-radius:4px; font-size:12px; }
  .fund-card { background:#fff; border:1px solid #e8e8ec; border-radius:10px; padding:16px 18px; margin-bottom:16px; }
  .fund-head { display:flex; align-items:baseline; gap:10px; border-bottom:1px solid #f0f0f3; padding-bottom:10px; margin-bottom:12px; }
  .fcode { font-family:monospace; font-weight:700; font-size:16px; }
  .fname { color:#8a8f99; font-size:13px; flex:1; }
  .fxirr { font-size:18px; font-weight:700; }
  .metric-row { display:flex; flex-wrap:wrap; gap:10px; margin-bottom:12px; }
  .metric { flex:1; min-width:120px; background:#fafafb; border:1px solid #f0f0f3; border-radius:8px; padding:8px 10px; }
  .mlabel { font-size:11px; color:#8a8f99; }
  .mval { font-size:16px; font-weight:600; font-variant-numeric:tabular-nums; }
  .mval.small { font-size:12px; font-weight:500; line-height:1.4; }
  .verify { font-size:12px; color:#646a73; background:#f6ffed; border:1px solid #d9f7be; border-radius:6px; padding:6px 10px; margin-bottom:12px; }
  .sub { font-size:12px; color:#8a8f99; font-weight:600; margin:10px 0 6px; }
  .ledger td { font-size:12px; }
  .notes { font-size:12px; color:#646a73; margin:0; padding-left:18px; line-height:1.6; }
  .legend { font-size:12px; color:#8a8f99; margin-top:6px; }
  .legend b.r { color:#d4380d; } .legend b.g { color:#237804; }
  .topbadge { display:inline-block; background:#e6f4ff; color:#0958d9; border:1px solid #91caff; border-radius:6px; padding:2px 10px; font-size:12px; font-weight:600; margin-bottom:10px; }
  .interp { font-size:13px; line-height:1.6; padding:7px 10px; border-left:3px solid #91caff; background:#f5f9ff; border-radius:0 6px 6px 0; margin:7px 0; }
  .icode { font-family:monospace; font-weight:700; }
  .iname { color:#8a8f99; font-size:12px; }
  .imood { display:block; color:#646a73; font-size:12px; margin-top:3px; }
  .explain { font-size:13px; line-height:1.7; color:#41464c; background:#fafcff; border:1px solid #e6f0ff; border-radius:6px; padding:10px 14px; margin:10px 0 4px; }
  .explain b { color:#0958d9; }
  .xnote { font-size:12px; color:#0958d9; background:#e6f4ff; border:1px solid #91caff; border-radius:6px; padding:6px 12px; margin:8px 0 0; }
  .backlink { display:inline-block; margin:14px 0; font-size:13px; color:#0958d9; text-decoration:none; font-weight:600; }
  .backlink:hover { text-decoration:underline; }
  .concl { font-size:14px; line-height:1.7; padding:10px 14px; border-left:4px solid #0958d9; background:#f5f9ff; border-radius:0 8px 8px 0; margin:6px 0 4px; }
  .jtab td.good { color:#237804; font-weight:600; } .jtab td.bad { color:#d4380d; font-weight:600; } .jtab td.mid { color:#8a8f99; }
  svg text { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; }
"""

# ============ 第一部分: 聚合择时评价 (来自唯一数据源) ============
timing_rows = ""
interpret_html = ""
for r in DATA:
    if "error" in r:
        timing_rows += f"<tr><td>{r['code']}</td><td colspan='11' style='color:#cf1322'>{r['error']}</td></tr>"
        continue
    xc = sign_color(r["xirr"]); tc = sign_color(r["timing"]); pc = sign_color(r["profit"])
    lp = r["loss_sell_cnt"]
    warntag = " ⚠" if r.get("warnings") else ""
    timing_rows += f"""
    <tr>
      <td class='code'>{r['code']}</td>
      <td class='name'><a href='{DETAIL_PREFIX}{r['code']}.html'>{r['code']} {r['name']}</a>{warntag}</td>
      <td class='num'>{money(r['amount'])}</td>
      <td class='num'>{money(r['net'])}</td>
      <td class='num' style='color:{pc};font-weight:600'>{money(r['profit'])}</td>
      <td class='num' style='color:{xc};font-weight:700'>{pct(r['xirr'])}</td>
      <td class='num'>{pct(r['twr_annual'])}</td>
      <td class='num' style='color:{tc};font-weight:700'>{pct(r['timing'])}</td>
      <td class='num'>{r['avg_buy_nav']:.4f}</td>
      <td class='num'>{r['avg_sell_nav']:.4f}</td>
      <td class='num'>{pct(r['sell_premium'])}</td>
      <td class='num'>{pct(r['low_buy_ratio'])}</td>
      <td class='num'>{lp}</td>
    </tr>"""
    t = r["timing"]
    if t is None:
        mood = ("—", "")
    elif t >= 0.01:
        mood = ("正贡献(择时帮忙)", "择时显著正向——低位多买、高位兑现，买卖时点放大了收益。")
    elif t <= -0.01:
        mood = ("拖累(择时不利)", "择时显著负向——多在高位加仓或低位赎回，买卖时点侵蚀了收益。")
    else:
        mood = ("中性", "择时中性——买卖时点基本不影响，XIRR 与基金本身表现一致。")
    if r["low_buy_ratio"] is not None and r["low_buy_ratio"] >= 0.5:
        buy_q = "低位布局充分"
    else:
        buy_q = "高位追涨偏多"
    if r["sell_premium"] is not None and r["sell_premium"] > 0:
        sell_q = "整体高于成本卖出(兑现收益)"
    elif r["sell_premium"] is not None and r["sell_premium"] < 0:
        sell_q = "整体略低于成本卖出"
    else:
        sell_q = "买卖基本持平"
    loss_txt = f"，有{lp}笔亏损赎回" if lp else "，无亏损赎回"
    interpret_html += f"""
      <div class='interp'>
        <span class='icode'>{r['code']}</span>
        <span class='iname'>{r['name']}</span>：
        择时<b style='color:{tc}'>{mood[0]}</b>（{pct(r['timing'])}）；
        {buy_q}（低位买入占比 {pct(r['low_buy_ratio'])}）、{sell_q}
        （卖买溢价 {pct(r['sell_premium'])}）{loss_txt}。
        <span class='imood'>{mood[1]}</span>
      </div>"""

# ============ 第二部分: 按日 XIRR 汇总 (同源, 与第一部分同取 XIRR) ============
rows_summary = ""
detail_html = ""
for r in DATA:
    if "error" in r:
        rows_summary += f"<tr><td>{r['code']}</td><td colspan='7' style='color:#cf1322'>{r['error']}</td></tr>"
        continue
    xc = sign_color(r["xirr"]); pc = sign_color(r["profit"])
    rows_summary += f"""
    <tr>
      <td class='code'>{r['code']}</td>
      <td class='name'><a href='{DETAIL_PREFIX}{r['code']}.html'>{r['code']} {r['name']}</a></td>
      <td class='num'>{money(r['amount'])}</td>
      <td class='num'>{money(r['net'])}</td>
      <td class='num' style='color:{pc};font-weight:600'>{money(r['profit'])}</td>
      <td class='num'>{money(r['avg_capital'])}</td>
      <td class='num'>{pct(r['simple_holding'])}</td>
      <td class='num' style='color:{xc};font-weight:700'>{pct(r['xirr'])}</td>
      <td class='num'>{r['days']}</td>
    </tr>"""
    ledger_rows = ""
    for d, tp, cash, days, cd in r["ledger"]:
        ccol = "#237804" if cash >= 0 else "#d4380d"
        ledger_rows += f"<tr><td>{d}</td><td>{tp}</td><td class='num' style='color:{ccol}'>{money(cash)}</td><td class='num'>{days}</td><td class='num'>{money(cd,1)}</td></tr>"
    assumptions = []
    for t in r["trades"]:
        if t["kind"] == "convert":
            assumptions.append(f"{t['date']} 超级转换 {t['shares']:.2f}份, 按当日隐含净值 {t['nav']:.4f} 估值 ≈ {t['amt']:.2f}元")
        elif t["kind"] == "div":
            assumptions.append(f"{t['date']} 现金分红 +{t['amt']:.2f}元 (计入现金流入)")
    assumptions_html = "".join(f"<li>{a}</li>" for a in assumptions) or "<li>无特殊处理</li>"
    roots_txt = "、".join(pct(x) for x in r["roots"]) if r.get("roots") else "无解"
    detail_html += f"""
    <div class='fund-card'>
      <div class='fund-head'>
        <span class='fcode'>{r['code']}</span>
        <span class='fname'>{r['name']}</span>
        <span class='fxirr' style='color:{xc}'>XIRR {pct(r['xirr'])}</span>
      </div>
      <div class='metric-row'>
        <div class='metric'><div class='mlabel'>当前市值</div><div class='mval'>{money(r['amount'])}</div></div>
        <div class='metric'><div class='mlabel'>净投入</div><div class='mval'>{money(r['net'])}</div></div>
        <div class='metric'><div class='mlabel'>实际利润</div><div class='mval' style='color:{pc}'>{money(r['profit'])}</div></div>
        <div class='metric'><div class='mlabel'>简单收益(持有)</div><div class='mval'>{pct(r['simple_holding'])}</div></div>
        <div class='metric'><div class='mlabel'>平均资金占用</div><div class='mval'>{money(r['avg_capital'])}</div></div>
        <div class='metric'><div class='mlabel'>交易区间</div><div class='mval small'>{r['first_date']}→{r['val_date']}<br>({r['days']}天)</div></div>
      </div>
      <div class='verify'>
        校验 XNPV = {r['xnpv_check']:.6f} （≈0 即收敛）　|　区间唯一根：{roots_txt}　|　XIRR(年化) = <b style='color:{xc}'>{pct(r['xirr'])}</b>
      </div>
      <div class='sub'>逐笔现金流台账（按确切交易日，无月度合并）</div>
      <table class='ledger'>
        <thead><tr><th>日期</th><th>类型</th><th>现金流(元)</th><th>占用天数</th><th>资金×天数</th></tr></thead>
        <tbody>{ledger_rows}</tbody>
      </table>
      <div class='sub'>数据处理假设 / 特殊项</div>
      <ul class='notes'>{assumptions_html}</ul>
    </div>"""

# 第一部分与第二部分的 XIRR 均取自同一份 _fund_timing_batch.json, 数值必然一致。

summary_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>基金IRR汇总（按日XIRR + 聚合择时评价）</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <h1>基金IRR汇总（按日XIRR + 聚合择时评价）</h1>
  <div class="subtitle">估值日 {VAL_DATE}　·　数据源：stocklist.xlsx（当前市值）+ 基金流水/*.xlsx（逐笔交易）　·　红=正收益，绿=负收益</div>

  <!-- ===== 第一部分: 聚合择时评价 (置顶) ===== -->
  <div class="panel">
    <div class="topbadge">置顶 · 聚合择时评价（全基金·全周期层级）</div>
    <h2>一、聚合择时评价</h2>
    <table class="summary">
      <thead><tr>
        <th>基金(名称)</th><th class="num">当前市值</th><th class="num">净投入</th><th class="num">利润</th>
        <th class="num">XIRR年化</th><th class="num">TWR年化</th><th class="num">择时归因(XIRR−TWR)</th>
        <th class="num">平均买NAV</th><th class="num">平均卖NAV</th><th class="num">卖买溢价</th>
        <th class="num">低位买入占比</th><th class="num">亏损赎回笔数</th>
      </tr></thead>
      <tbody>{timing_rows}</tbody>
    </table>
    <div class="explain">
      <b>择时归因 = XIRR − TWR（年化）</b>：XIRR 是<b>资金加权</b>收益（受你买卖时点影响），TWR 是<b>时间加权</b>收益（纯基金本身表现）。
      二者之差即为"择时"贡献——<b style="color:#237804">正=择时帮忙</b>（低位多买/高位兑现）、
      <b style="color:#d4380d">负=择时拖累</b>（高位加仓/低位赎回）、<b>≈0=中性</b>（买卖时点不影响）。
      卖买溢价 = 平均卖NAV ÷ 平均买NAV − 1（&gt;0 表示整体高于成本卖出）；低位买入占比 = 买入金额中当日净值低于全部重建净值点均值的部分。
    </div>
    <div class="xnote">XIRR 为同一组现金流的唯一资金加权年化值，第一部分与第二部分的 XIRR 完全一致；判断择时优劣请对比第一部分内的 XIRR 与 TWR（择时归因 = XIRR − TWR）。</div>
    <div class="sub">逐只解读</div>
    {interpret_html}
    <div class="legend"><b class="r">红色</b>=正（涨/盈利/择时帮忙），<b class="g">绿色</b>=负（跌/亏损/择时拖累）。标注 ⚠ 的基金存在特殊假设或收敛告警。</div>
  </div>

  <!-- ===== 第二部分: 按日 XIRR 汇总 (同源) ===== -->
  <div class="panel">
    <div class="sub" style="margin-top:0">二、按日 XIRR 汇总（资金加权内在回报率）</div>
    <table class="summary">
      <thead><tr>
        <th>代码</th><th>基金名称</th><th class="num">当前市值</th><th class="num">净投入</th>
        <th class="num">实际利润</th><th class="num">平均资金占用</th><th class="num">简单收益(持有)</th>
        <th class="num">XIRR(年化)</th><th class="num">天数</th>
      </tr></thead>
      <tbody>{rows_summary}</tbody>
    </table>
    <div class="xnote">本表 XIRR 与第一部分的 XIRR 取自同一份现金流与同一算法（_fund_timing_batch.json），数值完全一致。</div>
    <div class="legend"><b class="r">红色</b>=正（涨/盈利），<b class="g">绿色</b>=负（跌/亏损）。XIRR = 资金加权、严格按交易日折现的内在回报率。</div>
  </div>

  <div class="panel method">
    <div class="sub" style="margin-top:0">计算方法（按日 XIRR）</div>
    <p><b>核心思路：</b>把每一只基金当成一支独立的"投资账户"。你投进去的每一笔钱（买入/转入/转换）记为负现金流，赎回和现金分红记为正现金流，最后把<b>当前市值</b>作为估值日的一笔正现金流（相当于把剩余持仓按现价变现）。然后求让净现值归零的年化折现率：</p>
    <p style="text-align:center"><code>Σ CFᵢ / (1 + r)^((dᵢ − d₀)/365) = 0</code>　→　解得的 <code>r</code> 即 XIRR（与 Excel 的 XIRR 完全一致）</p>
    <ul>
      <li><b>严格按交易日：</b>每一笔买卖都保留它的确切日期，<b>不做任何月度/区间合并</b>，资金占用时长精确到天。</li>
      <li><b>数据清洗：</b>状态含"撤单 / 失败(支付失败)"的订单一律剔除；现金分红计入正现金流；"超级转换"只有份额，用该基金当日隐含净值（由邻近买卖的"金额÷份额"反推并插值）估值后计入买入。</li>
    </ul>
    <p style="color:#8a8f99;font-size:12px;margin-bottom:0">说明：XIRR 是<b>资金加权</b>收益率，会受你的买卖时点影响（低位多买则偏高、频繁赎回则偏低），反映"这笔钱被占用的真实效率"；它不等同于基金本身的涨跌（那是时间加权 TWR）。报你赚了多少钱，看"实际利润"最实在。</p>
  </div>

  {detail_html}

  <div class="panel" style="font-size:12px;color:#8a8f99">
    报告由脚本自动生成 · 估值日 {VAL_DATE} · 每只基金 XNPV 均已回代校验 ≈0 · 第一/第二部分 XIRR 同源唯一
  </div>
</div>
</body>
</html>"""

out = os.path.join(ROOT, "基金IRR汇总_按日XIRR.html")
open(out, "w", encoding="utf-8").write(summary_html)
print("已生成汇总页:", out, "(", os.path.getsize(out), "字节 )")

# ============ 每只基金独立明细页 ============
def build_nav_svg(r):
    trades = r["trades"]
    nav_pts = [t["nav"] for t in trades if t["nav"] is not None]
    impl = r["implied_nav"]
    if impl is not None:
        nav_pts.append(impl)
    if not nav_pts:
        return "<p style='color:#8a8f99'>无有效净值点，无法绘图。</p>"
    ords = [to_ord(t["date"]) for t in trades]
    d0 = min(ords); d1 = to_ord(r["val_date"])
    if d1 == d0:
        d1 = d0 + 1
    nmin = min(nav_pts); nmax = max(nav_pts)
    if nmax == nmin:
        nmax = nmin + 1
    span = nmax - nmin
    nmin_a = nmin - span * 0.08
    nmax_a = nmax + span * 0.08
    W, H = 720, 360
    padL, padR, padT, padB = 64, 24, 28, 52
    def X(o):
        return padL + (o - d0) / (d1 - d0) * (W - padL - padR)
    def Y(n):
        return (H - padB) - (n - nmin_a) / (nmax_a - nmin_a) * (H - padT - padB)

    parts = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="background:#fafbfc;border:1px solid #eef0f3;border-radius:8px">']
    # y 网格 + 标签
    for i in range(5):
        nv = nmin_a + (nmax_a - nmin_a) * i / 4.0
        y = Y(nv)
        parts.append(f'<line x1="{padL}" y1="{y:.1f}" x2="{W-padR}" y2="{y:.1f}" stroke="#eef0f3" stroke-width="1"/>')
        parts.append(f'<text x="{padL-8}" y="{y+4:.1f}" font-size="11" fill="#8a8f99" text-anchor="end">{nv:.3f}</text>')
    # x 轴标签 (首/中/尾)
    for o in (d0, (d0 + d1) // 2, d1):
        x = X(o)
        parts.append(f'<text x="{x:.1f}" y="{H-padB+18}" font-size="11" fill="#8a8f99" text-anchor="middle">{datetime.fromordinal(o).strftime("%Y-%m-%d")}</text>')
    parts.append(f'<text x="{padL}" y="{padT-10}" font-size="11" fill="#8a8f99">单位净值</text>')

    # 参考线: 平均买NAV(蓝虚线) / 平均卖NAV(橙虚线)
    if r["avg_buy_nav"]:
        yb = Y(r["avg_buy_nav"])
        parts.append(f'<line x1="{padL}" y1="{yb:.1f}" x2="{W-padR}" y2="{yb:.1f}" stroke="#0958d9" stroke-width="1.4" stroke-dasharray="6,4"/>')
        parts.append(f'<text x="{W-padR}" y="{yb-5:.1f}" font-size="10" fill="#0958d9" text-anchor="end">平均买NAV {r["avg_buy_nav"]:.4f}</text>')
    if r["avg_sell_nav"]:
        ys = Y(r["avg_sell_nav"])
        parts.append(f'<line x1="{padL}" y1="{ys:.1f}" x2="{W-padR}" y2="{ys:.1f}" stroke="#fa8c16" stroke-width="1.4" stroke-dasharray="6,4"/>')
        parts.append(f'<text x="{W-padR}" y="{ys+13:.1f}" font-size="10" fill="#fa8c16" text-anchor="end">平均卖NAV {r["avg_sell_nav"]:.4f}</text>')

    # 交易标记
    for t in trades:
        x = X(to_ord(t["date"]))
        if t["kind"] == "div":
            y = (H - padB) - 8
            parts.append(f'<polygon points="{x:.1f},{y-6:.1f} {x+6:.1f},{y:.1f} {x:.1f},{y+6:.1f} {x-6:.1f},{y:.1f}" fill="#722ed1"/>')
            continue
        y = Y(t["nav"])
        if t["kind"] == "buy":
            parts.append(f'<polygon points="{x:.1f},{y-6:.1f} {x-5:.1f},{y+5:.1f} {x+5:.1f},{y+5:.1f}" fill="#0958d9"/>')
        elif t["kind"] == "convert":
            parts.append(f'<polygon points="{x-6:.1f},{y:.1f} {x+5:.1f},{y-5:.1f} {x+5:.1f},{y+5:.1f}" fill="#13c2c2"/>')
        elif t["kind"] == "sell":
            col = "#237804" if t["nav"] >= r["avg_buy_nav"] else "#d4380d"
            parts.append(f'<polygon points="{x:.1f},{y+6:.1f} {x-5:.1f},{y-5:.1f} {x+5:.1f},{y-5:.1f}" fill="{col}"/>')
    # 当前持仓
    if impl is not None:
        xh = X(d1); yh = Y(impl)
        parts.append(f'<rect x="{xh-5:.1f}" y="{yh-5:.1f}" width="10" height="10" fill="#1f2329"/>')
        parts.append(f'<text x="{xh-8:.1f}" y="{yh-9:.1f}" font-size="10" fill="#1f2329" text-anchor="end">当前持仓 {impl:.4f}</text>')

    # 图例
    lx, ly = padL + 6, padT + 12
    leg = [("▲ 买入", "#0958d9"), ("▼ 卖出(盈/亏)", "#237804"), ("◆ 现金分红", "#722ed1"),
           ("◀ 超级转换", "#13c2c2"), ("■ 当前持仓", "#1f2329")]
    for i, (lab, c) in enumerate(leg):
        yy = ly + i * 16
        parts.append(f'<rect x="{lx}" y="{yy-9}" width="10" height="10" fill="{c}" opacity="0.18"/>')
        parts.append(f'<text x="{lx+14}" y="{yy}" font-size="10" fill="#646a73">{lab}</text>')
    parts.append("</svg>")
    return "".join(parts)

def build_judgment(r):
    trades = r["trades"]
    nav_pts = [t["nav"] for t in trades if t["nav"] is not None]
    if r["implied_nav"] is not None:
        nav_pts.append(r["implied_nav"])
    lo_cut = hi_cut = None
    if nav_pts:
        arr = np.array(nav_pts, dtype=float)
        lo_cut = float(np.percentile(arr, 33.33))
        hi_cut = float(np.percentile(arr, 66.67))
    avg_buy = r["avg_buy_nav"]
    buys_dates = [to_ord(t["date"]) for t in trades if t["kind"] == "buy"]
    first_buy_ord = min(buys_dates) if buys_dates else min(to_ord(t["date"]) for t in trades)

    rows = ""
    idx = 0
    for t in trades:
        idx += 1
        nav = t["nav"]
        if nav is None or lo_cut is None:
            nbin = "—"
        elif nav <= lo_cut:
            nbin = "低"
        elif nav >= hi_cut:
            nbin = "高"
        else:
            nbin = "中"
        rel = ("高于" if nav >= avg_buy else "低于") if nav is not None else "—"
        days_from_buy = to_ord(t["date"]) - first_buy_ord
        pnl = (nav / avg_buy - 1) if (t["kind"] == "sell" and nav is not None and avg_buy) else None
        # 判断
        if t["kind"] == "div":
            judge, jcls = "收益落袋", "mid"
        elif t["kind"] in ("buy", "convert"):
            if nbin == "低":
                judge, jcls = "低位买入（好）", "good"
            elif nbin == "高":
                judge, jcls = "高位买入（偏贵）", "bad"
            else:
                judge, jcls = "中位买入", "mid"
        elif t["kind"] == "sell":
            if nav is not None and nav >= avg_buy and nbin == "高":
                judge, jcls = "高位盈利赎回（好）", "good"
            elif nav is not None and nav >= avg_buy:
                judge, jcls = "盈利赎回（尚可）", "mid"
            else:
                judge, jcls = "亏损赎回（不佳）", "bad"
        else:
            judge, jcls = "—", "mid"
        nav_disp = f"{nav:.4f}" if nav is not None else "—"
        pnl_disp = f"{pnl*100:.2f}%" if pnl is not None else "—"
        sh_disp = "—" if t["shares"] is None else f"{t['shares']:.2f}"
        rows += (f"<tr><td>{idx}</td><td>{t['date']}</td><td>{t['type']}</td>"
                 f"<td class='num'>{money(t['amt'])}</td><td class='num'>{sh_disp}</td>"
                 f"<td class='num'>{nav_disp}</td><td>{nbin}</td><td>{rel}</td>"
                 f"<td class='num'>{days_from_buy}</td><td class='num'>{pnl_disp}</td>"
                 f"<td class='{jcls}'>{judge}</td></tr>")
    return rows

def conclusion(r):
    t = r["timing"]
    if t is None:
        mood = "择时数据缺失"
    elif t >= 0.01:
        mood = "择时正向（买卖时点放大收益）"
    elif t <= -0.01:
        mood = "择时负向（买卖时点侵蚀收益）"
    else:
        mood = "择时中性（买卖时点基本不影响）"
    lbr = r["low_buy_ratio"]
    buy = "买点极好（低位布局充分）" if lbr is not None and lbr >= 0.8 else ("买点较好" if lbr is not None and lbr >= 0.5 else "买点偏高（高位追涨偏多）")
    lsc = r["loss_sell_cnt"]; sp = r["sell_premium"]
    if lsc and lsc > 0:
        sell = f"卖点偏弱（{lsc}笔亏损赎回）"
    elif sp is not None and sp > 0:
        sell = "卖点较好（整体高于成本兑现）"
    else:
        sell = "卖点中性（买卖基本持平）"
    return f"{r['code']} {r['name']}：{mood}（择时归因 {pct(t)}），{buy}、{sell}。"

for r in DATA:
    if "error" in r:
        continue
    xc = sign_color(r["xirr"]); pc = sign_color(r["profit"]); tc = sign_color(r["timing"])
    svg = build_nav_svg(r)
    jrows = build_judgment(r)
    concl = conclusion(r)
    warntag = ""
    if r.get("warnings"):
        warntag = "<div class='verify' style='background:#fffbe6;border-color:#ffe58f;color:#ad6800'>⚠ " + \
                  "；".join(r["warnings"]) + "</div>"

    body = f"""
  <h1>{r['code']} {r['name']}</h1>
  <div class="subtitle">估值日 {r['val_date']}　·　明细页（净值轨迹 + 逐笔择时判断）　·　红=正，绿=负</div>

  <div class="panel">
    <div class="metric-row">
      <div class="metric"><div class="mlabel">当前市值</div><div class="mval">{money(r['amount'])}</div></div>
      <div class="metric"><div class="mlabel">净投入</div><div class="mval">{money(r['net'])}</div></div>
      <div class="metric"><div class="mlabel">利润</div><div class="mval" style="color:{pc}">{money(r['profit'])}</div></div>
      <div class="metric"><div class="mlabel">XIRR年化</div><div class="mval" style="color:{xc}">{pct(r['xirr'])}</div></div>
      <div class="metric"><div class="mlabel">TWR年化</div><div class="mval">{pct(r['twr_annual'])}</div></div>
      <div class="metric"><div class="mlabel">择时归因</div><div class="mval" style="color:{tc}">{pct(r['timing'])}</div></div>
    </div>
    {warntag}
  </div>

  <div class="panel">
    <div class="sub" style="margin-top:0">净值轨迹（由每笔交易"金额÷份额"重建 · 浅色背景）</div>
    {svg}
    <div class="legend">蓝虚线=平均买NAV，橙虚线=平均卖NAV；卖出▲▼按"卖出净值是否≥平均买NAV"判盈亏（绿盈/红亏）。</div>
  </div>

  <div class="panel">
    <div class="sub" style="margin-top:0">逐笔买卖择时判断表</div>
    <table class="jtab summary">
      <thead><tr>
        <th>序号</th><th>日期</th><th>类型</th><th class="num">金额</th><th class="num">份额</th>
        <th class="num">当日净值(重建)</th><th>净值区间</th><th>相对平均成本</th>
        <th class="num">距首笔买入天数</th><th class="num">盈亏%</th><th>判断</th>
      </tr></thead>
      <tbody>{jrows}</tbody>
    </table>
    <div class="legend">净值区间按该基金所有重建净值点（买+卖+期末）的分位：≤33%低、≥67%高、其余中。盈亏%仅卖出时计算 = 卖出净值 ÷ 平均买NAV − 1。</div>
  </div>

  <div class="panel">
    <div class="sub" style="margin-top:0">基金级一句话择时结论</div>
    <div class="concl">{concl}</div>
  </div>

  <a class="backlink" href="基金IRR汇总_按日XIRR.html">← 返回汇总</a>
"""
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{r['code']} {r['name']} 明细</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">{body}</div>
</body>
</html>"""
    fpath = os.path.join(ROOT, f"{DETAIL_PREFIX}{r['code']}.html")
    open(fpath, "w", encoding="utf-8").write(html)
    print("已生成明细页:", fpath, "(", os.path.getsize(fpath), "字节 )")

# 打印核对
print("\n=== XIRR 一致性核对 (Part1 == Part2, 同源) ===")
for r in DATA:
    if "error" in r:
        continue
    print(f"  {r['code']} {r['name'][:14]:<14}  XIRR = {pct(r['xirr'])}   (Part1=Part2 同源唯一)")
print("\n全部网页已生成。")
