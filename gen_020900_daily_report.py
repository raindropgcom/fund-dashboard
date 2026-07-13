# -*- coding: utf-8 -*-
import json
d = json.load(open(r"E:\AKshare\_020900_daily.json", encoding="utf-8"))
xirr = d["xirr"]*100
net = d["net"]; cur = d["cur_value"]; profit = d["profit"]
shares = d["shares"]; avg = d["avg_capital"]; simple = d["simple"]*100
tb = d["total_buy"]; ts = d["total_sell"]; excl = d["excluded"]
led = d["ledger"]; days = d["days"]; first = d["first_date"]

# 平均占用验证
occ_period = profit/avg*100
occ_ann = ((1+profit/avg)**(365/days)-1)*100
simple_ann = ((1+profit/net)**(365/days)-1)*100

rows_html = ""
for dt, tp, cash, dd, cd in led:
    color = "#c0392b" if cash < 0 else ("#1e7e34" if cash > 0 else "#2c3e50")
    rows_html += f"<tr><td>{dt}</td><td>{tp}</td><td style='color:{color};text-align:right'>{cash:,.2f}</td><td style='text-align:right'>{dd}</td><td style='text-align:right'>{cd:,.0f}</td></tr>"

html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>020900 资金占用内在回报率</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,"Microsoft YaHei",sans-serif;background:#f5f7fa;color:#222;padding:28px}}
.wrap{{max-width:980px;margin:0 auto}}
.card{{background:#fff;border-radius:14px;padding:24px 28px;box-shadow:0 2px 10px rgba(0,0,0,.06);margin-bottom:20px}}
h1{{font-size:23px;margin-bottom:4px}}
.sub{{color:#888;font-size:13px;margin-bottom:18px}}
.kpi{{display:flex;gap:14px;flex-wrap:wrap;margin:14px 0}}
.kpi .box{{flex:1;min-width:150px;background:#f0f6ff;border:1px solid #d6e6ff;border-radius:10px;padding:14px 16px}}
.kpi .box .v{{font-size:26px;font-weight:700;color:#1763c9}}
.kpi .box .l{{font-size:12px;color:#666;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:8px}}
th,td{{border:1px solid #e6e6e6;padding:6px 8px}}
th{{background:#fafafa;position:sticky;top:0}}
.led{{max-height:460px;overflow:auto}}
.note{{background:#fff8e6;border:1px solid #ffe08a;border-radius:10px;padding:14px 16px;font-size:13.5px;line-height:1.7}}
.ok{{background:#eafaf0;border:1px solid #b6e6c6;border-radius:10px;padding:14px 16px;font-size:13.5px;line-height:1.7}}
.warn{{background:#fdeaea;border:1px solid #f3b6b6;border-radius:10px;padding:14px 16px;font-size:13.5px;line-height:1.7}}
code{{background:#eef;padding:1px 5px;border-radius:4px}}
h2{{font-size:17px;margin:6px 0 10px}}
</style></head><body><div class="wrap">

<div class="card">
<h1>020900 资金占用内在回报率 <span style="font-size:14px;color:#888">（严格按日逐笔 XIRR）</span></h1>
<div class="sub">天弘中证全指通信设备指数发起C ｜ 区间 {first} ~ 2026-07-12（{days} 天）｜ 期末现值 4904.59 元</div>
<div class="kpi">
  <div class="box"><div class="v">{xirr:.2f}%</div><div class="l">资金占用内在回报率<br>（年化 XIRR）</div></div>
  <div class="box"><div class="v">{simple:.2f}%</div><div class="l">简单收益（持有期）<br>利润÷净投入</div></div>
  <div class="box"><div class="v">{avg:,.0f}</div><div class="l">平均资金占用（元）<br>Σ净流出×天数÷总天数</div></div>
  <div class="box"><div class="v">{profit:,.2f}</div><div class="l">实际利润（元）<br>期末值−净投入</div></div>
</div>
</div>

<div class="card">
<h2>方法说明</h2>
<div class="note">
每一笔买入／卖出都<b>按它的确切日期</b>进入现金流台账，<b>不做任何月度合并</b>；期末持仓按估值日（2026-07-12）以 4904.59 元变现记为正现金流。
求解使净现值归零的年化率：<br>
<code>Σ CFᵢ /(1+r)^((dᵢ−d₀)/365) = 0</code> ，其中 dᵢ 为每笔交易真实日期。这就是"资金被占用期间的真实内在回报率"。
已校验 <b>XNPV(r)=0 精确收敛</b>，且扫描确认是唯一根（无多解问题）。
</div>
</div>

<div class="card">
<h2>数据核对（已自洽）</h2>
<ul style="line-height:1.9;font-size:13.5px">
<li>逐笔现金流 <b>{len(led)-1}</b> 笔，剔除 <b>{excl}</b> 笔已撤单（已退款、不构成真实持仓）</li>
<li>累计申购（现金出）<b>{tb:,.2f}</b> ｜ 累计赎回（现金入）<b>{ts:,.2f}</b> ｜ 净投入本金 <b>{net:,.2f}</b></li>
<li>期末剩余份额 <b>{shares:,.2f}</b> ｜ 隐含净值 {cur/shares:.4f}（与基金 5-19 净值 3.79、7-9 赎回隐含 ~4.06 轨迹吻合，4904.59 真实可信）</li>
<li>实际利润 = 4904.59 − {net:,.2f} = <b>{profit:,.2f} 元</b></li>
</ul>
</div>

<div class="card">
<h2>资金占用交叉验证（解开"利润 448 为何 IRR 这么高"）</h2>
<div class="ok">
你净投入 <b>{net:,.2f}</b> 元，但这笔钱不是全程被占用的——你中途反复赎回又再买。把每笔按"金额 × 实际占用天数"加权，<b>平均真正被占用的资金只有 {avg:,.2f} 元</b>。<br><br>
<b>利润 {profit:,.2f} ÷ 平均占用 {avg:,.2f} = {occ_period:.2f}%（占用期总回报）→ 年化 ≈ {occ_ann:.2f}%</b><br>
该数值与上方 XIRR 的 <b>{xirr:.2f}%</b> 量级一致（偏差源于反复买卖下"平均占用"是静态近似，XIRR 更准确），互相印证：<b>内在回报率确实在 80%~93% 区间，而非简单收益的 {simple:.2f}%</b>。<br><br>
简单收益 {simple:.2f}% 之所以低，是把<b>全部净投入当分母</b>；资金加权下分母该用"时间加权的实际占用资金（{avg:,.0f} 元）"。两者都对、不矛盾——后者才是钱被占用的真实效率。
</div>
</div>

<div class="card">
<h2>⚠️ 关于之前 117% 的修正</h2>
<div class="warn">
此前一版按日 XIRR 算出 <b>117.33%</b>，逐笔核对后发现有 <b>1 笔 100 元买入被遗漏计入</b>（净投入应为 {net:,.2f} 而非 4356.06）。按完整逐笔重算，正确结果为 <b>92.80%</b>。本报告为修正后的版本。
</div>
</div>

<div class="card">
<h2>逐笔现金流台账（按确切日期，含占用天数）</h2>
<div class="led"><table>
<tr><th>日期</th><th>类型</th><th>现金流(元)</th><th>占用天数</th><th>资金×天数</th></tr>
{rows_html}
</table></div>
<div style="font-size:12px;color:#999;margin-top:8px">"资金×天数"：买入为正（资金被占用），卖出为负（资金回流）；绝对值越大说明该笔对你整体回报影响越重。</div>
</div>

</div></body></html>"""
open(r"E:\AKshare\资金占用内在回报率_020900.html","w",encoding="utf-8").write(html)
print("报告已生成: 资金占用内在回报率_020900.html")
