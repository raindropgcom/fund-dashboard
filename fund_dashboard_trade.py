#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
基金实时估值 Dashboard（交易记录标注版 + 买入/卖出金额排序）
"""

import requests
import json
import re
import time
import os
import sys
import pandas as pd
import warnings
from io import StringIO
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from apscheduler.schedulers.background import BackgroundScheduler

warnings.filterwarnings("ignore", category=FutureWarning)

# ==================== 配置区（路径相对化，不再硬编码 E:\AKshare） ====================
_BASE = os.path.dirname(os.path.abspath(__file__))
CODE_FILE = os.path.join(_BASE, "fund_code", "fund_codes.txt")
TRADE_DIR = os.path.join(_BASE, "trades")
OUTPUT_HTML = os.path.join(_BASE, "fund_code", "fund_dashboard.html")
INTERVAL_SECONDS = 20
MAX_WORKERS = 10
REQUEST_TIMEOUT = 15
FETCH_RETRIES = 3
FETCH_RETRY_DELAY = 0.5
BATCH_DELAY = 0.3
HISTORY_DAYS = 7
# 历史净值至少多少分钟强制重新抓取一次（避免进程常驻后历史列冻结在旧日期，新交易日涨跌不出现）
HIST_REFRESH_MINUTES = 30
# ================================================

cached_data = {}
cached_hist_data = {}
cached_hist_date = None
cached_trades = {}
# 上次抓取历史净值的时间，用于控制历史列按周期刷新
last_hist_fetch = None


def read_fund_codes(filepath):
    if not os.path.exists(filepath):
        print(f"找不到基金代码文件: {filepath}")
        return []
    codes = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                codes.append(line.zfill(6))
    return list(dict.fromkeys(codes))


# ==================== 交易记录解析模块 ====================

def parse_trade_excel(filepath):
    try:
        df = pd.read_excel(filepath, header=None, dtype=str)
    except Exception as e:
        print(f"  [ERROR] 读取Excel失败 {os.path.basename(filepath)}: {e}")
        return []

    trades = []
    i = 0

    while i < len(df):
        row = df.iloc[i]

        if len(row) == 0 or all(pd.isna(v) or str(v).strip() == '' for v in row):
            i += 1
            continue

        first_col = str(row.iloc[0]).strip() if not pd.isna(row.iloc[0]) else ''

        date_match = re.match(r'^(\d{4}-\d{2}-\d{2})', first_col)
        if not date_match:
            i += 1
            continue

        trade_date = date_match.group(1)

        if len(row) < 4:
            i += 1
            continue

        product_name = str(row.iloc[1]).strip() if len(row) > 1 and not pd.isna(row.iloc[1]) else ''
        biz_type = str(row.iloc[2]).strip() if len(row) > 2 and not pd.isna(row.iloc[2]) else ''
        apply_str = str(row.iloc[3]).strip() if len(row) > 3 and not pd.isna(row.iloc[3]) else ''
        confirm_str = str(row.iloc[4]).strip() if len(row) > 4 and not pd.isna(row.iloc[4]) else ''

        if not product_name or not biz_type:
            i += 1
            continue

        fund_code = None
        code_match = re.search(r'(\d{4,6})$', product_name)
        if code_match:
            fund_code = code_match.group(1).zfill(6)

        if not fund_code and i + 1 < len(df):
            next_row = df.iloc[i + 1]
            if len(next_row) > 1 and not pd.isna(next_row.iloc[1]):
                # 对账单格式：代码单独成行（如 001593 被存成 1593），放宽到 4-6 位并去掉可能的 .0 浮点尾
                next_val = str(next_row.iloc[1]).split('.')[0].strip()
                if re.match(r'^\d{4,6}$', next_val):
                    fund_code = next_val.zfill(6)
                    i += 1

        if not fund_code:
            i += 1
            continue

        trade_type = None
        if any(k in biz_type for k in ['买入', '转入', '申购']):
            trade_type = '买入'
        elif any(k in biz_type for k in ['卖出', '赎回', '转出']):
            trade_type = '卖出'

        if not trade_type:
            i += 1
            continue

        buy_amount = None
        buy_shares = None
        sell_amount = None
        sell_shares = None

        if trade_type == '买入':
            m = re.search(r'([\d.]+)', apply_str)
            if m:
                buy_amount = float(m.group(1))
            m = re.search(r'([\d.]+)', confirm_str)
            if m and confirm_str != '--':
                buy_shares = float(m.group(1))
        else:
            m = re.search(r'([\d.]+)', apply_str)
            if m:
                sell_shares = float(m.group(1))
            m = re.search(r'([\d.]+)', confirm_str)
            if m and confirm_str != '--':
                sell_amount = float(m.group(1))

        trades.append({
            'fund_code': fund_code,
            'trade_date': trade_date,
            'trade_type': trade_type,
            'buy_amount': buy_amount,
            'buy_shares': buy_shares,
            'sell_amount': sell_amount,
            'sell_shares': sell_shares,
            'product_name': product_name,
            'biz_type': biz_type,
        })

        i += 1

    unique_trades = []
    seen = set()
    for t in trades:
        key = (t['fund_code'], t['trade_date'], t['trade_type'],
               round(t.get('buy_amount') or 0, 2), round(t.get('sell_amount') or 0, 2))
        if key not in seen:
            seen.add(key)
            unique_trades.append(t)

    print(f"  [OK] {os.path.basename(filepath)}: 原始解析{len(trades)}条，去重后{len(unique_trades)}条")
    return unique_trades


def load_all_trades(trade_dir):
    all_trades = []

    if not os.path.exists(trade_dir):
        os.makedirs(trade_dir)
        print(f"[{now()}] 创建交易记录目录: {trade_dir}")
        return {}

    files = [f for f in os.listdir(trade_dir) if f.endswith(('.xlsx', '.xls'))]
    if not files:
        print(f"[{now()}] [WARN] 交易记录目录为空: {trade_dir}")
        return {}

    print(f"[{now()}] 发现 {len(files)} 个交易记录文件")

    for filename in sorted(files):
        filepath = os.path.join(trade_dir, filename)
        trades = parse_trade_excel(filepath)
        all_trades.extend(trades)

    trades_by_code = {}
    for t in all_trades:
        code = t['fund_code']
        if code not in trades_by_code:
            trades_by_code[code] = []
        trades_by_code[code].append(t)

    for code in trades_by_code:
        trades_by_code[code].sort(key=lambda x: x['trade_date'], reverse=True)

    total = sum(len(v) for v in trades_by_code.values())
    print(f"[{now()}] 共加载 {total} 条有效交易记录，涉及 {len(trades_by_code)} 只基金")

    if trades_by_code:
        print(f"[{now()}] [DEBUG] 样本数据:")
        for code in list(trades_by_code.keys())[:5]:
            t = trades_by_code[code][0]
            print(f"         {code}: {t['trade_date']} {t['trade_type']} 买{t.get('buy_amount')}元/{t.get('buy_shares')}份 卖{t.get('sell_amount')}元/{t.get('sell_shares')}份")

    return trades_by_code


def get_recent_trades(trades_by_code, fund_code):
    if not trades_by_code or fund_code not in trades_by_code:
        return []

    trades = trades_by_code.get(fund_code, [])
    if not trades:
        return []

    latest_date = trades[0]['trade_date']
    return [t for t in trades if t['trade_date'] == latest_date]


# ==================== 实时估值模块 ====================

def fetch_live_valuation(fund_code):
    code = str(fund_code).strip().zfill(6)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "http://fund.eastmoney.com/"
    }
    for attempt in range(FETCH_RETRIES):
        try:
            ts = int(time.time() * 1000)
            url = f"http://fundgz.1234567.com.cn/js/{code}.js?rt={ts}"
            resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                match = re.search(r"jsonpgz\((.*)\);", resp.text)
                if match:
                    data = json.loads(match.group(1))
                    return {
                        "fundcode": data.get("fundcode", code),
                        "name": data.get("name", ""),
                        "gsz": data.get("gsz", ""),
                        "gszzl": data.get("gszzl", ""),
                        "dwjz": data.get("dwjz", ""),
                        "gztime": data.get("gztime", ""),
                    }
        except Exception:
            pass
        if attempt < FETCH_RETRIES - 1:
            time.sleep(FETCH_RETRY_DELAY)
    return None


def fetch_history_7days(fund_code):
    code = str(fund_code).strip().zfill(6)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": f"http://fund.eastmoney.com/f10/jjjz_{code}.html"
    }
    for attempt in range(FETCH_RETRIES):
        try:
            url = f"http://fund.eastmoney.com/f10/F10DataApi.aspx?type=lsjz&code={code}&page=1&per={HISTORY_DAYS}"
            resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                match = re.search(r'content:"(.*?)"\s*,\s*records:', resp.text, re.DOTALL)
                if match:
                    html = match.group(1).replace('\\"', '"').replace('\\/', '/')
                    try:
                        tables = pd.read_html(StringIO(html))
                        if tables and len(tables[0]) > 0:
                            df_hist = tables[0]
                            records = []
                            total = 0.0
                            for _, row in df_hist.iterrows():
                                date = str(row.iloc[0])
                                rate_str = str(row.iloc[3]) if len(row) > 3 else "0%"
                                try:
                                    rate_val = float(rate_str.replace('%', '').replace('---', '0'))
                                except:
                                    rate_val = 0.0
                                records.append({"date": date, "rate": rate_val})
                                total += rate_val
                            return records, round(total, 2)
                    except Exception:
                        pass
        except Exception:
            pass
        if attempt < FETCH_RETRIES - 1:
            time.sleep(FETCH_RETRY_DELAY)
    return [], None


def fetch_all_data(fund_codes):
    global cached_data, cached_hist_data, cached_hist_date, last_hist_fetch
    results = {}
    total = len(fund_codes)
    today_str = datetime.now().strftime("%Y-%m-%d")
    print(f"[{now()}] 开始抓取 {total} 只基金...")
    start = time.time()

    # 历史净值周期刷新：每 HIST_REFRESH_MINUTES 分钟强制清空缓存重新抓取，
    # 保证新交易日的净值公布后自动出现在历史列（避免常驻进程历史列冻结在旧日期）。
    now_dt = datetime.now()
    if last_hist_fetch is None or (now_dt - last_hist_fetch).total_seconds() >= HIST_REFRESH_MINUTES * 60:
        cached_hist_data = {}
        last_hist_fetch = now_dt

    def fetch_in_batches(fetch_func, codes, batch_size=MAX_WORKERS):
        data = {}
        for i in range(0, len(codes), batch_size):
            batch = codes[i:i+batch_size]
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                future_to_code = {executor.submit(fetch_func, c): c for c in batch}
                for future in as_completed(future_to_code):
                    code = future_to_code[future]
                    try:
                        result = future.result()
                        if result:
                            data[code] = result
                    except Exception:
                        pass
            if i + batch_size < len(codes):
                time.sleep(BATCH_DELAY)
        return data

    live_data = fetch_in_batches(fetch_live_valuation, fund_codes)
    missing_hist_codes = [c for c in fund_codes if c not in cached_hist_data]

    if not missing_hist_codes:
        hist_data = cached_hist_data
        print(f"[{now()}] 使用今日历史净值缓存")
    else:
        new_hist = fetch_in_batches(fetch_history_7days, missing_hist_codes)
        cached_hist_data.update(new_hist)
        cached_hist_date = today_str
        hist_data = cached_hist_data

    elapsed = time.time() - start
    live_new = len(live_data)
    live_cached = 0

    for code in fund_codes:
        if code in live_data:
            live = live_data[code]
            if code not in cached_data:
                cached_data[code] = {}
            cached_data[code].update({
                "name": live.get("name", ""),
                "gsz": live.get("gsz", ""),
                "gszzl": live.get("gszzl", ""),
                "dwjz": live.get("dwjz", ""),
                "gztime": live.get("gztime", ""),
            })
        elif code in cached_data:
            live = cached_data[code]
            live_cached += 1
        else:
            live = {}

        hist = hist_data.get(code, ([], None))
        if hist == ([], None) and code in cached_data:
            hist = (cached_data[code].get("history", []), cached_data[code].get("total_7d"))

        if hist != ([], None):
            if code not in cached_data:
                cached_data[code] = {}
            cached_data[code]["history"] = hist[0]
            cached_data[code]["total_7d"] = hist[1]

        results[code] = {
            "fundcode": code,
            "name": live.get("name", ""),
            "gsz": live.get("gsz", ""),
            "gszzl": live.get("gszzl", ""),
            "dwjz": live.get("dwjz", ""),
            "gztime": live.get("gztime", ""),
            "history": hist[0],
            "total_7d": hist[1],
        }

    print(f"[{now()}] 完成: 新估值{live_new}只 缓存估值{live_cached}只 耗时{elapsed:.1f}s")
    return results


# ==================== HTML生成（带买入/卖出排序）====================

def generate_html(data_list, trades_by_code):
    date_cols = []
    if data_list and data_list[0]["history"]:
        date_cols = [h["date"] for h in data_list[0]["history"]]

    rows = []

    # 顶部统计
    total_buy_all = 0.0
    total_sell_all = 0.0
    trade_funds = set()
    latest_trade_date = None

    for code in trades_by_code:
        trades = get_recent_trades(trades_by_code, code)
        for t in trades:
            trade_funds.add(code)
            if latest_trade_date is None:
                latest_trade_date = t['trade_date']
            if t['trade_type'] == '买入' and t.get('buy_amount'):
                total_buy_all += t['buy_amount']
            elif t['trade_type'] == '卖出':
                if t.get('sell_amount'):
                    total_sell_all += t['sell_amount']

    for item in data_list:
        code = item["fundcode"]
        name = item["name"]
        gsz = item["gsz"]
        gszzl = item["gszzl"]
        dwjz = item["dwjz"]
        gztime = item["gztime"]
        history = item["history"]
        total_7d = item["total_7d"]

        recent_trades = get_recent_trades(trades_by_code, code)

        total_buy_amount = 0.0
        total_buy_shares = 0.0
        total_sell_amount = 0.0
        total_sell_shares = 0.0

        for t in recent_trades:
            if t['trade_type'] == '买入':
                if t.get('buy_amount'):
                    total_buy_amount += t['buy_amount']
                if t.get('buy_shares'):
                    total_buy_shares += t['buy_shares']
            else:
                if t.get('sell_amount'):
                    total_sell_amount += t['sell_amount']
                if t.get('sell_shares'):
                    total_sell_shares += t['sell_shares']

        trade_badges = ""
        trade_details = ""
        has_trade = False

        if total_buy_amount > 0:
            has_trade = True
            trade_badges += '<span class="trade-badge buy">买</span>'
            detail = f"买入 <b>{total_buy_amount:.2f}元</b>"
            if total_buy_shares > 0:
                detail += f" <span class='shares'>({total_buy_shares:.2f}份)</span>"
            if dwjz and dwjz not in ['', None, '--']:
                detail += f" <span class='nav'>@净值{dwjz}</span>"
            trade_details += f'<div class="trade-line buy-line">{detail}</div>'

        if total_sell_amount > 0:
            has_trade = True
            trade_badges += '<span class="trade-badge sell">卖</span>'
            detail = f"卖出 <b>{total_sell_amount:.2f}元</b>"
            trade_details += f'<div class="trade-line sell-line">{detail}</div>'
        elif total_sell_shares > 0:
            has_trade = True
            trade_badges += '<span class="trade-badge sell">卖</span>'
            detail = f"卖出 <b>{total_sell_shares:.2f}份</b>"
            if dwjz and dwjz not in ['', None, '--']:
                try:
                    estimated = total_sell_shares * float(dwjz)
                    detail += f" <span class='nav'>(约{estimated:.2f}元)</span>"
                except:
                    pass
            trade_details += f'<div class="trade-line sell-line">{detail}</div>'

        try:
            gszzl_num = float(gszzl) if gszzl not in ["", None, "--"] else 0
        except:
            gszzl_num = 0

        total_num = total_7d if total_7d is not None else 0

        hist_cells = ""
        for h in history:
            rate = h["rate"]
            color = "red" if rate > 0 else ("green" if rate < 0 else "black")
            hist_cells += f'<td class="{color}" data-sort="{rate}">{rate:+.2f}%</td>'
        for _ in range(HISTORY_DAYS - len(history)):
            hist_cells += '<td class="black" data-sort="0">-</td>'

        gszzl_color = "red" if gszzl_num > 0 else ("green" if gszzl_num < 0 else "black")
        gszzl_str = f"{gszzl_num:+.2f}%" if gszzl not in ["", None] else "-"

        total_color = "red" if total_num > 0 else ("green" if total_num < 0 else "black")
        total_str = f"{total_num:+.2f}%" if total_7d is not None else "-"

        row_highlight = 'class="has-trade"' if has_trade else ''

        # 隐藏排序列：买入金额、卖出金额
        buy_sort = total_buy_amount if total_buy_amount > 0 else 0
        sell_sort = total_sell_amount if total_sell_amount > 0 else (total_sell_shares if total_sell_shares > 0 else 0)

        rows.append({
            "code": code,
            "name": name,
            "dwjz": dwjz,
            "gsz": gsz,
            "gszzl_str": gszzl_str,
            "gszzl_num": gszzl_num,
            "gszzl_color": gszzl_color,
            "gztime": gztime,
            "total_str": total_str,
            "total_num": total_num,
            "total_color": total_color,
            "hist_cells": hist_cells,
            "trade_badges": trade_badges,
            "trade_details": trade_details,
            "row_highlight": row_highlight,
            "buy_sort": buy_sort,
            "sell_sort": sell_sort,
        })

    rows_html = []
    for r in rows:
        rows_html.append(f"""
        <tr {r['row_highlight']}>
            <td class="code">{r['code']}</td>
            <td class="name">
                <div class="name-text">{r['name']}</div>
                <div class="trade-badges">{r['trade_badges']}</div>
                {r['trade_details']}
            </td>
            <td>{r['dwjz']}</td>
            <td>{r['gsz']}</td>
            <td class="{r['gszzl_color']}" data-sort="{r['gszzl_num']}"><b>{r['gszzl_str']}</b></td>
            <td class="{r['total_color']}" data-sort="{r['total_num']}"><b>{r['total_str']}</b></td>
            <td class="time">{r['gztime']}</td>
            <td class="sort-col" data-sort="{r['buy_sort']}">{r['buy_sort']:.2f}</td>
            <td class="sort-col" data-sort="{r['sell_sort']}">{r['sell_sort']:.2f}</td>
            {r['hist_cells']}
        </tr>
        """)

    hist_headers = ""
    for d in date_cols:
        hist_headers += f'<th>{d}</th>'
    for _ in range(HISTORY_DAYS - len(date_cols)):
        hist_headers += '<th>-</th>'

    stats_html = ""
    if latest_trade_date:
        stats_html = f"""
        <div class="trade-stats">
            <div class="stat-item">
                <div class="stat-value stat-buy">{total_buy_all:,.2f}</div>
                <div class="stat-label">买入金额（元）</div>
            </div>
            <div class="stat-item">
                <div class="stat-value stat-sell">{total_sell_all:,.2f}</div>
                <div class="stat-label">卖出金额（元）</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">{len(trade_funds)}</div>
                <div class="stat-label">交易基金数</div>
            </div>
            <div class="stat-item">
                <div class="stat-value" style="font-size:16px;">{latest_trade_date}</div>
                <div class="stat-label">交易日期</div>
            </div>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="{INTERVAL_SECONDS}">
    <title>基金实时估值 Dashboard - 交易记录版</title>
    <style>
        body {{
            font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
            background: #f5f6fa;
            margin: 20px;
        }}
        h2 {{
            text-align: center;
            color: #2c3e50;
            margin-bottom: 8px;
        }}
        .info {{
            text-align: center;
            color: #7f8c8d;
            font-size: 13px;
            margin-bottom: 10px;
        }}
        .trade-stats {{
            display: flex;
            justify-content: center;
            gap: 40px;
            background: white;
            padding: 15px;
            margin-bottom: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}
        .stat-item {{
            text-align: center;
        }}
        .stat-value {{
            font-size: 26px;
            font-weight: bold;
            color: #2c3e50;
        }}
        .stat-label {{
            font-size: 12px;
            color: #7f8c8d;
            margin-top: 4px;
        }}
        .stat-buy {{ color: #e74c3c; }}
        .stat-sell {{ color: #27ae60; }}
        .controls {{
            text-align: center;
            margin-bottom: 15px;
        }}
        .controls button {{
            margin: 0 4px;
            padding: 6px 14px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            background: #34495e;
            color: white;
        }}
        .controls button:hover {{
            background: #2c3e50;
        }}
        .controls button.buy-sort {{
            background: #e74c3c;
        }}
        .controls button.buy-sort:hover {{
            background: #c0392b;
        }}
        .controls button.sell-sort {{
            background: #27ae60;
        }}
        .controls button.sell-sort:hover {{
            background: #1e8449;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            font-size: 13px;
        }}
        th {{
            background: #34495e;
            color: white;
            padding: 10px 6px;
            text-align: center;
            font-weight: 600;
            position: sticky;
            top: 0;
            cursor: pointer;
            user-select: none;
        }}
        th:hover {{
            background: #2c3e50;
        }}
        th::after {{
            content: " ⇅";
            font-size: 11px;
            color: #bdc3c7;
        }}
        td {{
            padding: 8px 6px;
            text-align: center;
            border-bottom: 1px solid #ecf0f1;
        }}
        tr:hover {{
            background: #f8f9fa;
        }}
        tr.has-trade {{
            background: #fff8e1 !important;
            border-left: 3px solid #f39c12;
        }}
        tr.has-trade td {{
            border-bottom: 1px solid #f0e6c8;
        }}
        .code {{
            font-family: Consolas, monospace;
            color: #7f8c8d;
            font-size: 12px;
        }}
        .name {{
            text-align: left;
            font-weight: 500;
            min-width: 220px;
            position: relative;
        }}
        .name-text {{
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            max-width: 200px;
            display: inline-block;
            vertical-align: middle;
        }}
        .time {{
            font-size: 11px;
            color: #95a5a6;
        }}
        .red {{
            color: #e74c3c;
            font-weight: 600;
        }}
        .green {{
            color: #27ae60;
            font-weight: 600;
        }}
        .black {{
            color: #2c3e50;
        }}
        .trade-badges {{
            display: inline-block;
            margin-left: 4px;
            vertical-align: middle;
        }}
        .trade-badge {{
            display: inline-block;
            width: 18px;
            height: 18px;
            line-height: 18px;
            text-align: center;
            border-radius: 50%;
            color: white;
            font-size: 10px;
            font-weight: bold;
            margin-right: 3px;
        }}
        .trade-badge.buy {{
            background: #e74c3c;
        }}
        .trade-badge.sell {{
            background: #27ae60;
        }}
        .trade-line {{
            font-size: 11px;
            margin-top: 3px;
            padding: 2px 8px;
            border-radius: 3px;
            width: fit-content;
            line-height: 1.4;
        }}
        .buy-line {{
            background: #fdeaea;
            color: #c0392b;
        }}
        .sell-line {{
            background: #e8f8f5;
            color: #27ae60;
        }}
        .trade-line .shares {{
            color: #666;
            font-weight: normal;
        }}
        .trade-line .nav {{
            color: #999;
            font-weight: normal;
            font-size: 10px;
        }}
        /* 隐藏排序列 */
        .sort-col {{
            display: none;
        }}
        th.sort-col {{
            display: none;
        }}
        .summary {{
            text-align: center;
            margin-top: 15px;
            font-size: 14px;
            color: #34495e;
        }}
    </style>
</head>
<body>
    <h2>基金实时估值 Dashboard</h2>
    <div class="info">
        更新时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | 
        <span id="refresh-countdown">{INTERVAL_SECONDS}</span> 秒后自动刷新
    </div>
    {stats_html}
    <div class="controls">
        <button onclick="sortTable(4, 'desc')">当天涨跌 ↓</button>
        <button onclick="sortTable(4, 'asc')">当天涨跌 ↑</button>
        <button onclick="sortTable(5, 'desc')">7日合计 ↓</button>
        <button onclick="sortTable(5, 'asc')">7日合计 ↑</button>
        <button class="buy-sort" onclick="sortTable(7, 'desc')">买入金额 ↓</button>
        <button class="sell-sort" onclick="sortTable(8, 'desc')">卖出金额 ↓</button>
        <button onclick="location.reload()">刷新数据</button>
    </div>
    <table id="fundTable">
        <thead>
            <tr>
                <th onclick="sortTable(0, 'asc')">基金代码</th>
                <th onclick="sortTable(1, 'asc')">基金名称</th>
                <th onclick="sortTable(2, 'asc')">昨日净值</th>
                <th onclick="sortTable(3, 'asc')">实时估值</th>
                <th onclick="sortTable(4, 'desc')">当天估算涨跌</th>
                <th onclick="sortTable(5, 'desc')">前7日合计涨幅</th>
                <th onclick="sortTable(6, 'asc')">估值时间</th>
                <th class="sort-col" onclick="sortTable(7, 'desc')">买入金额</th>
                <th class="sort-col" onclick="sortTable(8, 'desc')">卖出金额</th>
                {hist_headers}
            </tr>
        </thead>
        <tbody>
            {''.join(rows_html)}
        </tbody>
    </table>
    <div class="summary">
        共 {len(data_list)} 只基金 | 黄色高亮 = 有交易记录 | 点击表头或上方按钮可排序
    </div>

    <script>
        function sortTable(colIndex, order) {{
            const table = document.getElementById("fundTable");
            const tbody = table.querySelector("tbody");
            const rows = Array.from(tbody.querySelectorAll("tr"));

            rows.sort((a, b) => {{
                let aVal, bVal;
                const aCell = a.cells[colIndex];
                const bCell = b.cells[colIndex];

                if (aCell.hasAttribute("data-sort") && bCell.hasAttribute("data-sort")) {{
                    aVal = parseFloat(aCell.getAttribute("data-sort"));
                    bVal = parseFloat(bCell.getAttribute("data-sort"));
                }} else {{
                    aVal = aCell.textContent.trim();
                    bVal = bCell.textContent.trim();
                    const aNum = parseFloat(aVal);
                    const bNum = parseFloat(bVal);
                    if (!isNaN(aNum) && !isNaN(bNum)) {{
                        aVal = aNum;
                        bVal = bNum;
                    }}
                }}

                if (aVal < bVal) return order === 'asc' ? -1 : 1;
                if (aVal > bVal) return order === 'asc' ? 1 : -1;
                return 0;
            }});

            rows.forEach(row => tbody.appendChild(row));
            localStorage.setItem("fundSortCol", colIndex);
            localStorage.setItem("fundSortOrder", order);
        }}

        (function() {{
            const col = localStorage.getItem("fundSortCol");
            const order = localStorage.getItem("fundSortOrder");
            if (col !== null && order !== null) {{
                sortTable(parseInt(col), order);
            }}
        }})();

        // ==== 自动刷新（JS 版，比 meta refresh 可靠）====
        // 每 {INTERVAL_SECONDS} 秒重新加载页面；带倒计时便于确认刷新是否生效
        (function() {{
            var remaining = {INTERVAL_SECONDS};
            var el = document.getElementById("refresh-countdown");
            var timer = setInterval(function() {{
                remaining -= 1;
                if (el) el.textContent = remaining;
                if (remaining <= 0) {{
                    clearInterval(timer);
                    // 用时间戳做 hash 触发彻底重载，避免浏览器用缓存
                    location.reload();
                }}
            }}, 1000);
        }})();
    </script>
</body>
</html>"""
    return html


def now():
    return datetime.now().strftime("%H:%M:%S")


def update_dashboard():
    fund_codes = read_fund_codes(CODE_FILE)
    if not fund_codes:
        print(f"[{now()}] 未读取到有效基金代码")
        return

    global cached_trades
    cached_trades = load_all_trades(TRADE_DIR)

    data = fetch_all_data(fund_codes)

    data_list = []
    for code in fund_codes:
        data_list.append(data.get(code, {
            "fundcode": code, "name": "", "gsz": "", "gszzl": "",
            "dwjz": "", "gztime": "", "history": [], "total_7d": None,
        }))

    html_content = generate_html(data_list, cached_trades)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"[{now()}] Dashboard已更新: {OUTPUT_HTML}")


def main():
    print("=" * 70)
    print("基金实时估值 Dashboard（交易记录标注版 + 买入/卖出排序）")
    print("=" * 70)
    print(f"基金代码文件 : {CODE_FILE}")
    print(f"交易记录目录 : {TRADE_DIR}")
    print(f"输出HTML     : {OUTPUT_HTML}")
    print(f"刷新间隔     : {INTERVAL_SECONDS} 秒")
    print("=" * 70)

    if not os.path.exists(CODE_FILE):
        print(f"找不到基金代码文件: {CODE_FILE}")
        return

    if not os.path.exists(TRADE_DIR):
        os.makedirs(TRADE_DIR)
        print(f"已创建交易记录目录: {TRADE_DIR}")
        print("请将天天基金交易记录Excel放入此目录后重新运行")
        return

    update_dashboard()

    # 单次模式（--once）：供 GitHub Actions 调用，生成一次后立即退出，不启动常驻定时器
    if "--once" in sys.argv:
        print(f"[{now()}] 单次模式完成，已退出。")
        return

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        update_dashboard,
        "interval",
        seconds=INTERVAL_SECONDS,
        id="dashboard_updater",
        replace_existing=True
    )
    scheduler.start()
    print(f"\n[{now()}] 定时器已启动")

    # 服务常驻模式（--service N）：运行 N 秒后自动退出，供任务计划在工作时段调用，
    # 期间每 INTERVAL_SECONDS 秒重写一次 HTML（单价实时更新），到点自动停止。
    if "--service" in sys.argv:
        try:
            idx = sys.argv.index("--service")
            dur = int(sys.argv[idx + 1])
        except (IndexError, ValueError):
            dur = 7200
        print(f"[{now()}] 服务常驻模式：{dur} 秒（{dur // 3600} 小时）后自动退出")
        try:
            time.sleep(dur)
        except (KeyboardInterrupt, SystemExit):
            pass
        scheduler.shutdown()
        print(f"[{now()}] 服务时长到，已退出")
        return

    print(f"[{now()}] 请用浏览器打开: {OUTPUT_HTML}")
    print("按 Ctrl+C 停止\n")

    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        print("\n正在关闭...")
        scheduler.shutdown()
        print("已退出")


if __name__ == "__main__":
    main()