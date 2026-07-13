# -*- coding: utf-8 -*-
"""生成 011062 择时分析网页(框架 + 指标 + NAV 走势图 + 逐笔赎回)"""
import json, os
from datetime import date

ROOT = r"E:\AKshare"
res = json.load(open(os.path.join(ROOT, "_011062_timing.json"), encoding="utf-8"))

def pct(v, d=2):
    return "—" if v is None else f"{v*100:.{d}f}%"
def money(v, d=2):
    return "—" if v is None else f"{v:,.{d}f}"

# ---------- 构建 NAV 走势 SVG ----------
pts = []  # (date, nav, kind)  kind: B=买, S=卖(盈), L=卖(亏), C=当前
for b in res["buys"]:
    pts.append((date.fromisoformat(b["date"]), b["nav"], "B"))
for s in res["sells"]:
    kind = "L" if s["nav"] < res["avg_buy_nav"] else "S"
    pts.append((date.fromisoformat(s["date"]), s["nav"], kind))
pts.append((date.fromisoformat(res["val_date"]), res["cur_nav"], "C"))
pts.sort(key=lambda x: x[0])

x0, x1, y0, y1 = 60, 700, 30, 300
dmin = pts[0][0].toordinal(); dmax = pts[-1][0].toordinal()
nav_min, nav_max = res["min_nav"] - 0.01, res["max_nav"] + 0.01
def X(d): return x0 + (d.toordinal() - dmin) / (dmax - dmin) * (x1 - x0)
def Y(nav): return y1 - (nav - nav_min) / (nav_max - nav_min) * (y1 - y0)

# 网格 + 轴
svg = [f'<svg viewBox="0 0 720 340" class="chart" font-family="monospace" font-size="10">']
svg.append(f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" fill="#fcfcfd" stroke="#e8e8ec"/>')
# y 网格
for g in [nav_min, (nav_min+nav_max)/2, res["avg_buy_nav"], res["mid_nav"], res["cur_nav"], nav_max]:
    yy = Y(g)
    svg.append(f'<line x1="{x0}" y1="{yy:.1f}" x2="{x1}" y2="{yy:.1f}" stroke="#f0f0f3"/>')
    svg.append(f'<text x="{x0-6}" y="{yy+3:.1f}" text-anchor="end" fill="#8a8f99">{g:.4f}</text>')
# 平均买入净值(红虚线) 与 当前净值(灰虚线)
svg.append(f'<line x1="{x0}" y1="{Y(res["avg_buy_nav"]):.1f}" x2="{x1}" y2="{Y(res["avg_buy_nav"]):.1f}" stroke="#d4380d" stroke-dasharray="4 3"/>')
svg.append(f'<text x="{x1+2}" y="{Y(res["avg_buy_nav"])+3:.1f}" fill="#d4380d">平均买 {res["avg_buy_nav"]:.4f}</text>')
svg.append(f'<line x1="{x0}" y1="{Y(res["cur_nav"]):.1f}" x2="{x1}" y2="{Y(res["cur_nav"]):.1f}" stroke="#8a8f99" stroke-dasharray="4 3"/>')
svg.append(f'<text x="{x1+2}" y="{Y(res["cur_nav"])+3:.1f}" fill="#8a8f99">当前 {res["cur_nav"]:.4f}</text>')
# 净值连线(按日期)
path = " ".join(f"{X(d):.1f},{Y(n):.1f}" for d, n, _ in pts)
svg.append(f'<polyline points="{path}" fill="none" stroke="#bfbfbf" stroke-width="1.5"/>')
# 标记
for d, n, kind in pts:
    xx, yy = X(d), Y(n)
    if kind == "B":
        svg.append(f'<path d="M{xx:.1f},{yy-6:.1f} l5,9 l-10,0 z" fill="#d4380d"/>')          # 红▲买
    elif kind == "C":
        svg.append(f'<path d="M{xx-5:.1f},{yy-5:.1f} l10,0 l0,10 l-10,0 z" fill="#722ed1"/>')  # 紫■当前
    elif kind == "L":
        svg.append(f'<path d="M{xx:.1f},{yy+6:.1f} l5,-9 l-10,0 z" fill="#fa8c16"/>')          # 橙▼亏损卖
    else:
        svg.append(f'<path d="M{xx:.1f},{yy+6:.1f} l5,-9 l-10,0 z" fill="#1d6fb8"/>')          # 蓝▼盈利卖
# x 轴标签(年份)
for yr in [2024, 2025, 2026]:
    dd = date(yr, 7, 1).toordinal()
    if dmin <= dd <= dmax:
        svg.append(f'<text x="{X(date(yr,7,1)):.1f}" y="{y1+16}" text-anchor="middle" fill="#8a8f99">{yr}</text>')
svg.append(f'<text x="{(x0+x1)/2:.1f}" y="{y1+32}" text-anchor="middle" fill="#8a8f99">交易日期(净值点位由每笔 元/份 反推; 非每日序列)</text>')
svg.append('</svg>')

# 图例
legend = ('<div class="legend"><span class="lg lg-b">▲ 买入</span>'
          '<span class="lg lg-s">▼ 盈利卖出</span>'
          '<span class="lg lg-l">▼ 亏损卖出</span>'
          '<span class="lg lg-c">■ 当前市值</span>'
          '<span class="lg lg-ab">— — 平均买入净值</span>'
          '<span class="lg lg-cn">— — 当前净值</span></div>')

# ---------- 逐笔赎回表 ----------
sell_rows = ""
for s in res["sells"]:
    col = "#237804" if s["vs_cost"] >= 0 else "#d4380d"
    tag = "亏损" if s["vs_cost"] < 0 else "盈利"
    sell_rows += (f'<tr><td>{s["date"]}</td><td class="num">{money(s["amt"])}</td>'
                  f'<td class="num">{s["nav"]:.4f}</td>'
                  f'<td class="num" style="color:{col}">{pct(s["vs_cost"])} <small>({tag})</small></td>'
                  f'<td class="num">{s["hold_days"]}</td></tr>')

# ---------- 指标卡 ----------
xc = "#d4380d" if res["timing_annual"] >= 0 else "#237804"
metric_cards = f"""
<div class="metric-row">
  <div class="metric"><div class="mlabel">基金本身收益(TWR)</div><div class="mval">{pct(res['twr_total'])}<small> 年化{pct(res['twr_annual'])}</small></div></div>
  <div class="metric"><div class="mlabel">你的资金加权(XIRR)</div><div class="mval">{pct(res['xirr_total'])}<small> 年化{pct(res['xirr'])}</small></div></div>
  <div class="metric"><div class="mlabel">择时归因(XIRR−TWR)</div><div class="mval" style="color:{xc}">{pct(res['timing_annual'])}<small> /年</small></div></div>
  <div class="metric"><div class="mlabel">平均买入净值</div><div class="mval">{res['avg_buy_nav']:.4f}</div></div>
  <div class="metric"><div class="mlabel">平均卖出净值</div><div class="mval">{res['avg_sell_nav']:.4f}</div></div>
  <div class="metric"><div class="mlabel">卖/买溢价</div><div class="mval" style="color:#237804">+{pct(res['sell_premium'])}</div></div>
  <div class="metric"><div class="mlabel">低位买入占比</div><div class="mval">{pct(res['low_buy_ratio'],1)}</div></div>
  <div class="metric"><div class="mlabel">亏损赎回</div><div class="mval" style="color:#d4380d">{res['loss_sell_cnt']}笔 / {money(res['loss_sell_amt'])}</div></div>
</div>"""

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>011062 择时分析（买卖是否适当）</title>
<style>
  * {{ box-sizing:border-box; }}
  body {{ font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif; background:#f5f6f8; color:#1f2329; margin:0; padding:24px; }}
  .wrap {{ max-width:1000px; margin:0 auto; }}
  h1 {{ font-size:21px; margin:0 0 4px; }}
  .sub {{ color:#8a8f99; font-size:13px; margin-bottom:16px; }}
  .panel {{ background:#fff; border:1px solid #e8e8ec; border-radius:10px; padding:16px 18px; margin-bottom:16px; box-shadow:0 1px 3px rgba(0,0,0,.04); }}
  .sub-title {{ font-size:14px; font-weight:700; margin:0 0 10px; color:#1f2329; border-left:3px solid #1677ff; padding-left:8px; }}
  .metric-row {{ display:flex; flex-wrap:wrap; gap:10px; }}
  .metric {{ flex:1; min-width:150px; background:#fafafb; border:1px solid #f0f0f3; border-radius:8px; padding:8px 10px; }}
  .mlabel {{ font-size:11px; color:#8a8f99; }}
  .mval {{ font-size:17px; font-weight:700; font-variant-numeric:tabular-nums; }}
  .mval small {{ font-size:11px; font-weight:500; color:#8a8f99; }}
  .chart {{ width:100%; height:auto; display:block; margin-top:6px; }}
  .legend {{ font-size:11px; color:#646a73; margin-top:6px; display:flex; gap:14px; flex-wrap:wrap; }}
  .lg::before {{ content:''; display:inline-block; width:10px; height:10px; margin-right:3px; vertical-align:middle; border-radius:2px; }}
  .lg-b::before {{ background:#d4380d; clip-path:polygon(50% 0,100% 100%,0 100%); }}
  .lg-s::before {{ background:#1d6fb8; clip-path:polygon(50% 100%,100% 0,0 0); }}
  .lg-l::before {{ background:#fa8c16; clip-path:polygon(50% 100%,100% 0,0 0); }}
  .lg-c::before {{ background:#722ed1; }}
  .lg-ab::before, .lg-cn::before {{ background:#bfbfbf; border-radius:0; height:3px; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th,td {{ padding:7px 9px; text-align:left; border-bottom:1px solid #f0f0f3; }}
  th {{ background:#fafafb; color:#646a73; font-weight:600; }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  .framework li {{ margin:5px 0; line-height:1.65; }}
  .framework code {{ background:#f2f3f5; padding:1px 5px; border-radius:4px; font-size:12px; }}
  .verdict {{ background:#f6ffed; border:1px solid #d9f7be; border-radius:8px; padding:10px 14px; font-size:13px; line-height:1.75; }}
  .verdict b.r {{ color:#d4380d; }} .verdict b.g {{ color:#237804; }}
  .note {{ font-size:12px; color:#8a8f99; line-height:1.6; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>011062 择时分析：我的买卖是否适当？</h1>
  <div class="sub">广发中债7-10年国开债指数E　·　首买 {res['first_buy_date']} → 估值日 {res['val_date']}（{res['days_total']}天）　·　当前市值 {money(res['current_value'])}</div>

  <div class="panel">
    <div class="sub-title">一、分析框架：择时归因（Timing Attribution）</div>
    <div class="framework">
      <p style="margin:0 0 8px">把"操作是否适当"拆成两个层层递进的问题，再落到可量化指标：</p>
      <ul>
        <li><b>① 基准线（基金本身走势收益）= 时间加权收益率 TWR</b><br>
        假设从你首笔买入一路持有到现在、不增不减的收益，<u>剔除你买卖时点的影响</u>，纯粹反映基金涨跌。本例 TWR = <b>{pct(res['twr_total'])}</b>（年化 {pct(res['twr_annual'])}）。它回答了"这只基自己争不争气"。</li>
        <li><b>② 你的真实收益 = 资金加权收益率 XIRR</b><br>
        把你每笔钱进出的真实时点折现，得到的年化。本例 XIRR = <b>{pct(res['xirr'])}</b>。它回答了"按你实际的操作，这笔钱年化赚多少"。</li>
        <li><b>③ 择时归因 = XIRR − TWR</b><br>
        这是核心指标：<b style="color:{xc}">{pct(res['timing_annual'])}/年</b>。
        <span class="note">正=你的择时<b class="g">帮了忙</b>（买低卖高）；负=择时<b class="r">拖了后腿</b>（买高卖低或频繁错配）；≈0=中性。</span></li>
      </ul>
      <p style="margin:8px 0 4px"><b>对比哪些二级指标（买低卖高 / 是否踩准）：</b></p>
      <ul>
        <li><b>平均买入净值 vs 平均卖出净值</b> → 卖/买溢价 {pct(res['sell_premium'])}（>0 即"卖在成本之上"）。</li>
        <li><b>低位买入占比</b> → 建仓资金中落在期间净值中枢以下的占比 {pct(res['low_buy_ratio'],1)}。</li>
        <li><b>每笔赎回 vs 平均成本</b> → 看每次卖在盈利区还是亏损区、持有了多久（下表）。</li>
        <li><b>亏损赎回笔数/金额</b> → 卖在成本之下的操作，是择时失误的直接信号。</li>
        <li><b>现金择时比率（可选）</b> → 低位区净投入金额占比，衡量"低位敢不敢加仓"。</li>
      </ul>
      <p class="note" style="margin:6px 0 0">注：本基为被动债券指数基金，其"走势基准"≈基金净值本身；若为主动基，还应叠加对比业绩比较基准指数。完整净值每日序列本地缺失，本图净值点位由每笔交易的"金额÷份额"反推，恰好落在你做决策的那些日期上——对择时分析而言，这正是最该看的位置。</p>
    </div>
  </div>

  <div class="panel">
    <div class="sub-title">二、011062 核心指标</div>
    {metric_cards}
  </div>

  <div class="panel">
    <div class="sub-title">三、净值走势 vs 你的买卖点</div>
    {''.join(svg)}
    {legend}
  </div>

  <div class="panel">
    <div class="sub-title">四、逐笔赎回诊断（相对平均成本 {res['avg_buy_nav']:.4f}）</div>
    <table>
      <thead><tr><th>赎回日期</th><th class="num">赎回金额</th><th class="num">当时净值</th><th class="num">相对成本盈亏</th><th class="num">持有天数</th></tr></thead>
      <tbody>{sell_rows}</tbody>
    </table>
  </div>

  <div class="panel">
    <div class="sub-title">五、结论：你的操作是否适当？</div>
    <div class="verdict">
      <p style="margin:0 0 6px"><b>买入：<b class="g">非常适当</b>。</b> {pct(res['low_buy_ratio'],1)} 的资金建仓在期间净值中枢（{res['mid_nav']:.4f}）以下，买在 ~{res['avg_buy_nav']:.4f} 的低位区，时点选得很好。</p>
      <p style="margin:0 0 6px"><b>卖出：<b class="g">总体适当，但有两处可优化</b>。</b> 平均卖在成本之上 <b class="g">+{pct(res['sell_premium'])}</b>，且多在 1.30~1.37 的上涨后高位区；但整体仍低于当前净值 {res['cur_nav']:.4f}，说明<b class="r">卖早了</b>——尤其 2025-03-11 那笔巨额赎回（{money(11405.35)}）后，基金又涨了约 5% 才到现价位，相当于提前下车少赚一段。</p>
      <p style="margin:0 0 6px"><b>唯一明显失误：</b> 2024-04-29 买入仅 13 天后就以 <b class="r">-0.97%</b> 小亏卖出 1000 份（全周期唯一一笔亏损赎回），属短线非理性操作。</p>
      <p style="margin:0"><b>整体择时：中性（{pct(res['timing_annual'])}/年）。</b> XIRR（{pct(res['xirr'])}）与基金本身 TWR（{pct(res['twr_annual'])}）几乎持平，说明你的主动买卖基本没带来超额、也没造成大亏。对债券指数基金这种低波动品种，<b>长期持有 / 定投往往优于频繁择时</b>（还省赎回费）——你已买在低位，其实"拿住不动"会是更简单也更优的策略。</p>
    </div>
    <p class="note" style="margin-top:8px">数据自洽校验：XNPV(XIRR) = {res['xnpv_check']:.6f}（≈0，收敛）；剩余份额 {res['remaining_shares']:.2f}，当前隐含净值 {res['cur_nav']:.4f}。脚本：analyze_011062_timing.py。</p>
  </div>
</div>
</body>
</html>"""

out = os.path.join(ROOT, "011062择时分析.html")
open(out, "w", encoding="utf-8").write(html)
print("已生成:", out, "(", os.path.getsize(out), "字节 )")
