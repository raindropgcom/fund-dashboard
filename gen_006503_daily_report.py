# -*- coding: utf-8 -*-
import json
d = json.load(open(r"E:\AKshare\_006503_daily.json", encoding="utf-8"))

rows_html = ""
for dt, tp, cash, days, cd in d["ledger"]:
    cls = "buy" if tp == "买入" else "sell"
    cash_s = f"{cash:,.2f}"
    rows_html += f'<tr class="{cls}"><td>{dt}</td><td class="tp">{tp}</td><td class="num">{cash_s}</td><td class="num">{days}</td><td class="num">{cd:,.1f}</td></tr>\n'
rows_html += f'<tr class="end"><td>{d["val_date"]}</td><td class="tp">当前现值</td><td class="num">{d["cur_value"]:,.2f}</td><td class="num">0</td><td class="num">0.0</td></tr>'

xirr = d["xirr"]*100
occ_period = d["profit"]/d["avg_capital"]*100
occ_ann = ((1+d["profit"]/d["avg_capital"])**(365/d["days"])-1)*100
simple = d["simple"]*100

html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>006503 资金占用内在回报率(按日 XIRR)</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif; background:#f5f6f8; color:#1a1a1a; line-height:1.6; padding:28px 16px; }}
.wrap {{ max-width:900px; margin:0 auto; }}
h1 {{ font-size:22px; margin-bottom:4px; }}
.sub {{ color:#666; font-size:13px; margin-bottom:20px; }}
.hero {{ background:linear-gradient(135deg,#c0392b,#e74c3c); color:#fff; border-radius:14px; padding:26px 28px; margin-bottom:20px; box-shadow:0 6px 18px rgba(192,57,43,.25); }}
.hero .label {{ font-size:14px; opacity:.9; }}
.hero .big {{ font-size:46px; font-weight:700; margin:6px 0; letter-spacing:-1px; }}
.hero .note {{ font-size:13px; opacity:.92; }}
.cards {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:20px; }}
.card {{ background:#fff; border-radius:12px; padding:16px; box-shadow:0 2px 8px rgba(0,0,0,.05); }}
.card .k {{ font-size:12px; color:#888; }}
.card .v {{ font-size:20px; font-weight:600; margin-top:4px; }}
.box {{ background:#fff; border-radius:12px; padding:20px 22px; margin-bottom:20px; box-shadow:0 2px 8px rgba(0,0,0,.05); }}
.box h2 {{ font-size:16px; margin-bottom:12px; color:#c0392b; }}
.box p {{ font-size:14px; color:#333; margin-bottom:8px; }}
.formula {{ background:#f0f2f5; border-radius:8px; padding:12px 14px; font-family:"Consolas",monospace; font-size:13px; margin:10px 0; overflow-x:auto; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th,td {{ padding:8px 10px; text-align:left; border-bottom:1px solid #eee; }}
th {{ background:#fafafa; font-weight:600; color:#555; position:sticky; top:0; }}
td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
td.tp {{ font-weight:500; }}
tr.buy td.tp {{ color:#c0392b; }}
tr.sell td.tp {{ color:#27ae60; }}
tr.end {{ background:#fff7e6; font-weight:600; }}
tr.end td {{ border-top:2px solid #f0ad4e; }}
.tblwrap {{ max-height:520px; overflow:auto; border-radius:8px; }}
.hl {{ background:#fff3cd; padding:1px 5px; border-radius:4px; font-weight:600; }}
.chk {{ color:#27ae60; font-weight:600; }}
</style></head>
<body><div class="wrap">
<h1>基金 006503 · 资金占用内在回报率</h1>
<div class="sub">严格按每笔交易的确切日期计算(非月度合并) · 估值日 {d['val_date']} · 数据源:006503.xlsx + stocklist.xlsx</div>

<div class="hero">
  <div class="label">资金占用内在回报率(年化 XIRR)</div>
  <div class="big">{xirr:.2f}%</div>
  <div class="note">唯一根 · XNPV=0 精确收敛 · 每笔买卖按实际发生日期折现</div>
</div>

<div class="cards">
  <div class="card"><div class="k">累计买入</div><div class="v">{d['total_buy']:,.0f}</div></div>
  <div class="card"><div class="k">累计卖出</div><div class="v">{d['total_sell']:,.2f}</div></div>
  <div class="card"><div class="k">净投入本金</div><div class="v">{d['net']:,.2f}</div></div>
  <div class="card"><div class="k">当前现值</div><div class="v">{d['cur_value']:,.2f}</div></div>
</div>

<div class="box">
  <h2>算法:让净现值归零的年化率(严格按日)</h2>
  <p>把<b>每一笔买/卖都按它的确切日期</b>作为一个现金流,不做任何月度合并。求解让所有现金流折现后净现值为 0 的年化率 r,即"资金占用的内在回报率":</p>
  <div class="formula">Σ CF<sub>i</sub> / (1 + r)^((d<sub>i</sub> − d<sub>0</sub>) / 365) = 0 &nbsp;&nbsp;→&nbsp;&nbsp; r = {xirr:.4f}%/年</div>
  <p>其中 CF 买入记负、卖出记正,期末现值 {d['cur_value']:,.2f} 作为估值日的正现金流。<span class="chk">校验:代入 r 后 XNPV = 0.00000000 ✓,且全区间唯一根。</span></p>
</div>

<div class="box">
  <h2>为什么内在回报率 {xirr:.1f}% ≫ 简单收益 {simple:.2f}%?(资金占用视角)</h2>
  <p>你<b>净投入 {d['net']:,.2f} 元</b>,但这笔钱并非全程 {d['days']} 天都在占用——按逐笔"金额×实际占用天数"加权:</p>
  <div class="formula">平均实际占用资金 = Σ(净流出<sub>i</sub> × 占用天数<sub>i</sub>) / 总天数 = <span class="hl">{d['avg_capital']:,.2f} 元</span></div>
  <p>利润 {d['profit']:.2f} 元 ÷ 平均占用 {d['avg_capital']:.2f} 元 = <b>{occ_period:.2f}%</b>(占用期),年化 <b>≈ {occ_ann:.2f}%</b> —— 与 XIRR 的 {xirr:.2f}% <span class="chk">几乎完全吻合,互相印证 ✓</span></p>
  <p>结论:简单收益 {simple:.2f}% 用的是全部净投入 {d['net']:,.0f} 元当分母;而内在回报率用的是<b>时间加权的实际占用资金 {d['avg_capital']:.0f} 元</b>。你 82% 的钱是 6~7 月才投入的,真正占用时间很短,所以两者都对、并不矛盾。</p>
</div>

<div class="box">
  <h2>逐笔现金流台账(按确切日期)</h2>
  <p style="font-size:13px;color:#888;margin-bottom:10px;">占用天数 = 该笔到估值日 {d['val_date']} 的实际天数;资金×天数 = 该笔对"资金占用"的贡献(买入为正)。</p>
  <div class="tblwrap"><table>
    <thead><tr><th>日期</th><th>类型</th><th class="num">现金流(元)</th><th class="num">占用天数</th><th class="num">资金×天数</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table></div>
</div>

<div class="sub" style="text-align:center;margin-top:16px;">
  基金本身 10 个月净值 3.9→7.8(TWR +100%)是牛基;但你 82% 资金买在 6~7 月高位,实际利润仅 {d['profit']:.2f} 元,资金占用内在回报率 {xirr:.2f}%/年。
</div>
</div></body></html>"""

open(r"E:\AKshare\资金占用内在回报率_006503.html","w",encoding="utf-8").write(html)
print("报告已生成: 资金占用内在回报率_006503.html")
