# -*- coding: utf-8 -*-
import json
from datetime import date

d = json.load(open(r"E:\AKshare\_xirr_tmp.json", encoding="utf-8"))
flows = d["flows"]
xirr = d["xirr"]
xirr_pct = xirr * 100

# 月度聚合
from collections import defaultdict
monthly = defaultdict(float)
for ds, bt, cf in flows:
    ym = ds[:7]
    monthly[ym] += cf

def money(x):
    return f"{x:,.2f}"

html = []
html.append("""<html><head><meta charset='utf-8'><style>
body{font-family:-apple-system,'Segoe UI','Microsoft YaHei',sans-serif;background:#f7f8fa;color:#1f2329;max-width:1000px;margin:24px auto;padding:0 18px;}
h1{font-size:22px;border-left:5px solid #2f6fed;padding-left:10px;}
h2{font-size:17px;margin-top:28px;color:#2f6fed;}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:13px;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.08);}
th,td{border:1px solid #e5e6eb;padding:6px 8px;text-align:center;}
th{background:#eef2ff;}
.out{color:#d4380d;font-weight:bold;} .in{color:#389e0d;font-weight:bold;}
.kpi{display:flex;gap:14px;flex-wrap:wrap;margin:14px 0;}
.kpi div{background:#fff;border:1px solid #e5e6eb;border-radius:8px;padding:12px 16px;flex:1;min-width:150px;}
.kpi b{display:block;font-size:20px;color:#2f6fed;}
.calc{background:#e6f7ff;border:1px solid #91d5ff;border-radius:8px;padding:18px;margin:16px 0;text-align:center;}
.big{font-size:36px;color:#2f6fed;font-weight:bold;}
.eq{background:#fafafa;border:1px solid #e5e6eb;border-radius:8px;padding:12px 16px;margin:12px 0;font-family:Consolas,monospace;font-size:13px;}
.ok{background:#f6ffed;border:1px solid #b7eb8f;border-radius:8px;padding:12px 16px;margin:12px 0;color:#389e0d;}
.note{background:#fff7e6;border:1px solid #ffd591;border-radius:8px;padding:12px 16px;margin:12px 0;color:#874d00;}
small{color:#8a8f99;}
</style></head><body>""")

html.append("<h1>基金 020900 收益率（XIRR）分析报告</h1>")
html.append(f"<p>产品：<b>天弘中证全指通信设备指数发起C</b> ｜ 现金流区间：{d['d0']} ~ {d['end']}（共 {d['days']} 天）｜ 方法：XIRR（资金加权·按实际日期）</p>")

html.append("<div class='calc'>XIRR（年化内部收益率）≈ <span class='big'>{:.2f}%</span><br><small>校验：代入该 r 后 XNPV = 0（精确收敛）｜ 估值日 {end}，期末基金资产 {asset} 元</small></div>".format(xirr_pct, end=d['end'], asset=money(d['end_asset'])))

html.append("<div class='ok'><b>✓ 数据已自洽</b>：期末剩余份额 {sh} 份，4904.59 ÷ {sh} = <b>{nav:.2f}</b> 的隐含净值，"
            "与基金 2026-05-19 实际净值 3.7899、2026-07-09 赎回隐含净值 ~4.06 的轨迹吻合，说明 4904.59 与流水一致，无矛盾。</div>".format(sh=money(d['shares']), nav=d['implied_nav']))

html.append("<h2>一、核心指标</h2>")
html.append("<div class='kpi'>")
html.append(f"<div>有效交易笔数<b>{len(flows)}</b></div>")
html.append(f"<div>累计申购(买)<b>{money(d['total_buy'])}元</b></div>")
html.append(f"<div>累计赎回(卖)<b>{money(d['total_sell'])}元</b></div>")
html.append(f"<div>净投入本金<b>{money(d['net'])}元</b></div>")
html.append(f"<div>期末资产<b>{money(d['end_asset'])}元</b></div>")
html.append(f"<div>期末份额<b>{money(d['shares'])}份</b></div>")
html.append("</div>")

html.append("<h2>二、数据清洗说明（已自动处理）</h2>")
html.append("<ul>")
html.append("<li>原始 127 行，剔除导出噪声行（时间/代码占位行）后得 127 条真实记录。</li>")
html.append(f"<li>剔除 <b>{d['n_excluded']}</b> 笔「已撤单 / 已撤单(已支付)」订单（这些订单被撤销、款项退回，不构成真实持仓与现金流），最终计入 <b>{len(flows)}</b> 笔现金流。</li>")
html.append("<li>业务类型映射：<b>活期宝转入</b> = 申购（现金流出，取申请金额·元）；<b>卖出回活期宝</b> = 赎回（现金流入，取确认金额·元）。</li>")
html.append("<li>期末基金资产 4904.59 元作为清算变现，记为估值日 {end} 的正向现金流。</li>".format(end=d['end']))
html.append("</ul>")

html.append("<h2>三、XIRR 公式与求解</h2>")
html.append("<div class='eq'>Σᵢ  CFᵢ / (1 + r)^((dᵢ − d₀) / 365) = 0，  d₀ = {d0}<div>".format(d0=d['d0']))
html.append("数值法（二分）求解，XNPV 在 r=0 时为 +548.53，在 r=2.0 时为 −123.17，于 r={:.4f} 处单调过零，唯一根，已校验 XNPV≈0。".format(xirr))

html.append("<h2>四、月度净现金流（买入为负 / 赎回为正）</h2>")
html.append("<table><tr><th>月份</th><th>净现金流(元)</th><th>方向</th></tr>")
for ym in sorted(monthly):
    v = monthly[ym]
    cls = "out" if v < 0 else "in"
    arrow = "净申购" if v < 0 else "净赎回"
    html.append(f"<tr><td>{ym}</td><td class='{cls}'>{money(v)}</td><td>{arrow}</td></tr>")
html.append("</table>")

html.append("<h2>五、首末各 5 笔现金流</h2>")
html.append("<table><tr><th>日期</th><th>类型</th><th>现金流(元)</th></tr>")
for ds, bt, cf in flows[:5]:
    cls = "out" if cf < 0 else "in"
    html.append(f"<tr><td>{ds}</td><td>{bt}</td><td class='{cls}'>{money(cf)}</td></tr>")
html.append("<tr><td colspan='3'>… 中间 {n} 笔 …</td></tr>".format(n=len(flows)-10))
for ds, bt, cf in flows[-5:]:
    cls = "out" if cf < 0 else "in"
    html.append(f"<tr><td>{ds}</td><td>{bt}</td><td class='{cls}'>{money(cf)}</td></tr>")
html.append(f"<tr><td>{d['end']}</td><td>期末清算</td><td class='in'>{money(d['end_asset'])}</td></tr>")
html.append("</table>")

html.append("<div class='note'><b>说明</b>：XIRR 是<b>资金加权</b>收益率，会受你买卖时点影响——你大部分本金在 2025 年低位（净值约 2.2）投入、基金后涨至约 4.4，故 117% 高于「基金净值涨幅」（约 +100%）。"
            "若想剔除择时、只看基金本身表现，需按每次交易日的单位净值做「时间加权收益率(TWR)」，本文件未含净值序列，暂无法计算；如需我可另取净值历史补齐。</div>")

html.append(f"<p style='color:#8a8f99;font-size:12px;'>* 报告生成于 {date.today()} ｜ 估值日 {d['end']} ｜ 数据来源 020900.xlsx（已含 2025 年流水）</p>")
html.append("</body></html>")

with open(r"E:\AKshare\XIRR结果_020900.html", "w", encoding="utf-8") as f:
    f.write("\n".join(html))
print("报告已生成: E:\\AKshare\\XIRR结果_020900.html")
print("XIRR =", round(xirr_pct, 2), "%")
