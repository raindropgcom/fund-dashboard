# -*- coding: utf-8 -*-
"""根据 _fund_irr_batch.json 生成网页版汇总报告"""
import json, os
from datetime import date

ROOT = r"E:\AKshare"
res = json.load(open(os.path.join(ROOT, "_fund_irr_batch.json"), encoding="utf-8"))
VAL_DATE = "2026-07-12"

def pct(v, d=2):
    return "—" if v is None else f"{v*100:.{d}f}%"

def money(v, d=2):
    return "—" if v is None else f"{v:,.{d}f}"

def sign_color(v):
    """中国习惯: 涨(正)=红, 跌(负)=绿"""
    if v is None:
        return "#888"
    return "#d4380d" if v >= 0 else "#237804"

rows_summary = ""
for r in res:
    if "error" in r:
        rows_summary += f"<tr><td>{r['code']}</td><td colspan='7' style='color:#cf1322'>{r['error']}</td></tr>"
        continue
    xc = sign_color(r["xirr"])
    pc = sign_color(r["profit"])
    rows_summary += f"""
    <tr>
      <td class='code'>{r['code']}</td>
      <td class='name'>{r['name']}</td>
      <td class='num'>{money(r['amount'])}</td>
      <td class='num'>{money(r['net'])}</td>
      <td class='num' style='color:{pc};font-weight:600'>{money(r['profit'])}</td>
      <td class='num'>{money(r['avg_capital'])}</td>
      <td class='num'>{pct(r['simple_holding'])}</td>
      <td class='num' style='color:{xc};font-weight:700'>{pct(r['xirr'])}</td>
      <td class='num'>{r['days']}</td>
    </tr>"""

detail_html = ""
for r in res:
    if "error" in r:
        continue
    xc = sign_color(r["xirr"])
    pc = sign_color(r["profit"])
    # 流水表
    ledger_rows = ""
    for d, tp, cash, days, cd in r["ledger"]:
        ccol = "#237804" if cash >= 0 else "#d4380d"
        ledger_rows += f"<tr><td>{d}</td><td>{tp}</td><td class='num' style='color:{ccol}'>{money(cash)}</td><td class='num'>{days}</td><td class='num'>{money(cd,1)}</td></tr>"
    assumptions = "".join(f"<li>{a}</li>" for a in r.get("assumptions", [])) or "<li>无特殊处理</li>"
    roots_txt = "、".join(pct(x) for x in r["roots"]) if r["roots"] else "无解"
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
      <ul class='notes'>{assumptions}</ul>
    </div>"""

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>基金资金占用内在回报率（按交易日 XIRR）</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
         background:#f5f6f8; color:#1f2329; margin:0; padding:24px; }}
  .wrap {{ max-width:1040px; margin:0 auto; }}
  h1 {{ font-size:22px; margin:0 0 4px; }}
  .subtitle {{ color:#8a8f99; font-size:13px; margin-bottom:18px; }}
  .panel {{ background:#fff; border:1px solid #e8e8ec; border-radius:10px; padding:18px 20px; margin-bottom:18px; box-shadow:0 1px 3px rgba(0,0,0,.04); }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th, td {{ padding:8px 10px; text-align:left; border-bottom:1px solid #f0f0f3; }}
  th {{ background:#fafafb; color:#646a73; font-weight:600; }}
  td.num, th.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  td.code {{ font-family:monospace; font-weight:600; }}
  td.name {{ color:#41464c; }}
  .summary thead th {{ position:sticky; top:0; }}
  .method {{ font-size:13px; line-height:1.7; color:#41464c; }}
  .method code {{ background:#f2f3f5; padding:1px 5px; border-radius:4px; font-size:12px; }}
  .fund-card {{ background:#fff; border:1px solid #e8e8ec; border-radius:10px; padding:16px 18px; margin-bottom:16px; }}
  .fund-head {{ display:flex; align-items:baseline; gap:10px; border-bottom:1px solid #f0f0f3; padding-bottom:10px; margin-bottom:12px; }}
  .fcode {{ font-family:monospace; font-weight:700; font-size:16px; }}
  .fname {{ color:#8a8f99; font-size:13px; flex:1; }}
  .fxirr {{ font-size:18px; font-weight:700; }}
  .metric-row {{ display:flex; flex-wrap:wrap; gap:10px; margin-bottom:12px; }}
  .metric {{ flex:1; min-width:120px; background:#fafafb; border:1px solid #f0f0f3; border-radius:8px; padding:8px 10px; }}
  .mlabel {{ font-size:11px; color:#8a8f99; }}
  .mval {{ font-size:16px; font-weight:600; font-variant-numeric:tabular-nums; }}
  .mval.small {{ font-size:12px; font-weight:500; line-height:1.4; }}
  .verify {{ font-size:12px; color:#646a73; background:#f6ffed; border:1px solid #d9f7be; border-radius:6px; padding:6px 10px; margin-bottom:12px; }}
  .sub {{ font-size:12px; color:#8a8f99; font-weight:600; margin:10px 0 6px; }}
  .ledger td {{ font-size:12px; }}
  .notes {{ font-size:12px; color:#646a73; margin:0; padding-left:18px; line-height:1.6; }}
  .legend {{ font-size:12px; color:#8a8f99; margin-top:6px; }}
  .legend b.r {{ color:#d4380d; }} .legend b.g {{ color:#237804; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>基金资金占用内在回报率（按交易日 XIRR）</h1>
  <div class="subtitle">估值日 {VAL_DATE}　·　数据源：stocklist.xlsx（当前市值）+ 基金流水/*.xlsx（逐笔交易）　·　红=正收益，绿=负收益</div>

  <div class="panel">
    <div class="sub" style="margin-top:0">汇总（stocklist 列表内全部基金）</div>
    <table class="summary">
      <thead><tr>
        <th>代码</th><th>基金名称</th><th class="num">当前市值</th><th class="num">净投入</th>
        <th class="num">实际利润</th><th class="num">平均资金占用</th><th class="num">简单收益(持有)</th>
        <th class="num">XIRR(年化)</th><th class="num">天数</th>
      </tr></thead>
      <tbody>{rows_summary}</tbody>
    </table>
    <div class="legend"><b class="r">红色</b>=正（涨/盈利），<b class="g">绿色</b>=负（跌/亏损）。XIRR = 资金加权、严格按交易日折现的内在回报率。</div>
  </div>

  <div class="panel method">
    <div class="sub" style="margin-top:0">计算方法</div>
    <p><b>核心思路：</b>把每一只基金当成一支独立的"投资账户"。你投进去的每一笔钱（买入/转入/转换）记为负现金流，赎回和现金分红记为正现金流，最后把<b>当前市值</b>作为估值日的一笔正现金流（相当于把剩余持仓按现价变现）。然后求让净现值归零的年化折现率：</p>
    <p style="text-align:center"><code>Σ CFᵢ / (1 + r)^((dᵢ − d₀)/365) = 0</code>　→　解得的 <code>r</code> 即 XIRR（与 Excel 的 XIRR 完全一致）</p>
    <ul>
      <li><b>严格按交易日：</b>每一笔买卖都保留它的确切日期，<b>不做任何月度/区间合并</b>，资金占用时长精确到天。</li>
      <li><b>资金占用天数：</b>平均资金占用 = Σ(每笔净流出 × 到估值日的天数) ÷ 总天数。它解释了"利润不大但 IRR 不低"——钱只在场上待了一段时间。利润 ÷ 平均占用 ≈ 持有期总回报，年化后应逼近 XIRR。</li>
      <li><b>数据清洗：</b>状态含"撤单 / 失败(支付失败)"的订单一律剔除（款项已退回，不构成真实持仓）；现金分红计入正现金流；"超级转换"只有份额，用该基金当日隐含净值（由邻近买卖的"金额÷份额"反推并插值）估值后计入买入。</li>
    </ul>
    <p style="color:#8a8f99;font-size:12px;margin-bottom:0">说明：XIRR 是<b>资金加权</b>收益率，会受你的买卖时点影响（低位多买则偏高、频繁赎回则偏低），反映"这笔钱被占用的真实效率"；它不等同于基金本身的涨跌（那是时间加权 TWR）。报你赚了多少钱，看"实际利润"最实在。</p>
  </div>

  {detail_html}

  <div class="panel" style="font-size:12px;color:#8a8f99">
    报告由脚本自动生成 · 估值日 {VAL_DATE} · 每只基金 XNPV 均已回代校验 ≈0
  </div>
</div>
</body>
</html>"""

out = os.path.join(ROOT, "基金IRR汇总_按日XIRR.html")
open(out, "w", encoding="utf-8").write(html)
print("已生成网页:", out, "(", os.path.getsize(out), "字节 )")
