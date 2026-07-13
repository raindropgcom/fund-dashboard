#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
交易日归档脚本（独立运行）
功能：
  1. 检查昨天是否有交易记录
  2. 如果总库没有昨天的数据，执行归档
  3. 如果总库已有或昨天无交易，跳过
  4. 可手动运行，也可加入Windows计划任务定时执行
"""

import json
import re
import os
import sys
import pandas as pd
import hashlib
from datetime import datetime, timedelta

# ==================== 配置区（路径相对化，不再硬编码 E:\AKshare） ====================
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 仓库根目录
TRADE_DIR = os.path.join(_BASE, "fund_code", "trades")
TRADE_DB_FILE = os.path.join(_BASE, "fund_code", "trade_db.json")
TRADE_META_FILE = os.path.join(_BASE, "fund_code", "trade_meta.json")
LOG_FILE = os.path.join(_BASE, "fund_code", "archive_log.txt")
# ================================================


def log(msg):
    """记录日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def parse_trade_excel(filepath):
    """解析天天基金交易记录Excel"""
    try:
        df = pd.read_excel(filepath, header=None, dtype=str)
    except Exception as e:
        log(f"[ERROR] 读取Excel失败 {os.path.basename(filepath)}: {e}")
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
        code_match = re.search(r'(\d{6})$', product_name)
        if code_match:
            fund_code = code_match.group(1).zfill(6)

        if not fund_code and i + 1 < len(df):
            next_row = df.iloc[i + 1]
            if len(next_row) > 1 and not pd.isna(next_row.iloc[1]):
                next_val = str(next_row.iloc[1]).strip()
                if re.match(r'^\d{5,6}$', next_val):
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
            'source_file': os.path.basename(filepath),
        })

        i += 1

    # 去重
    unique_trades = []
    seen = set()
    for t in trades:
        key = (t['fund_code'], t['trade_date'], t['trade_type'],
               round(t.get('buy_amount') or 0, 2), round(t.get('sell_amount') or 0, 2))
        if key not in seen:
            seen.add(key)
            unique_trades.append(t)

    return unique_trades


def load_trade_db():
    """加载交易总库"""
    if os.path.exists(TRADE_DB_FILE):
        try:
            with open(TRADE_DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log(f"[WARN] 加载总库失败: {e}")
    return {}


def save_trade_db(trade_db):
    """保存交易总库"""
    try:
        with open(TRADE_DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(trade_db, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log(f"[ERROR] 保存总库失败: {e}")
        return False


def load_trade_meta():
    """加载文件元数据"""
    if os.path.exists(TRADE_META_FILE):
        try:
            with open(TRADE_META_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log(f"[WARN] 加载元数据失败: {e}")
    return {}


def save_trade_meta(meta):
    """保存文件元数据"""
    try:
        with open(TRADE_META_FILE, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log(f"[ERROR] 保存元数据失败: {e}")
        return False


def file_md5(filepath):
    """计算文件MD5"""
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def get_yesterday():
    """获取昨天日期"""
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")


def check_yesterday_trades():
    """
    检查昨天是否有交易记录
    返回: (has_trades: bool, trade_files: list)
    """
    yesterday = get_yesterday()
    trade_files = []

    if not os.path.exists(TRADE_DIR):
        log(f"[INFO] 交易目录不存在: {TRADE_DIR}")
        return False, []

    files = [f for f in os.listdir(TRADE_DIR) if f.endswith(('.xlsx', '.xls'))]
    if not files:
        log(f"[INFO] 交易目录为空")
        return False, []

    for filename in files:
        filepath = os.path.join(TRADE_DIR, filename)
        trades = parse_trade_excel(filepath)
        for t in trades:
            if t['trade_date'] == yesterday:
                trade_files.append(filepath)
                break  # 这个文件有昨天的交易，记录后跳出

    has_trades = len(trade_files) > 0
    if has_trades:
        log(f"[INFO] 发现昨天({yesterday})交易文件: {len(trade_files)}个")
    else:
        log(f"[INFO] 昨天({yesterday})无交易记录")

    return has_trades, trade_files


def check_db_has_yesterday():
    """
    检查总库是否已包含昨天数据
    返回: bool
    """
    yesterday = get_yesterday()
    trade_db = load_trade_db()

    if not trade_db:
        log(f"[INFO] 总库为空，需要归档")
        return False

    # 检查是否有昨天的记录
    has_yesterday = any(
        t['trade_date'] == yesterday
        for t in trade_db.values()
    )

    if has_yesterday:
        log(f"[INFO] 总库已包含昨天({yesterday})数据，跳过归档")
    else:
        log(f"[INFO] 总库不包含昨天({yesterday})数据，需要归档")

    return has_yesterday


def archive_yesterday_trades():
    """
    执行归档：把昨天的交易数据复制到总库
    前置条件：昨天有交易 且 总库没有
    """
    yesterday = get_yesterday()
    log(f"[INFO] 开始归档昨天({yesterday})的交易数据...")

    # 1. 找到包含昨天交易的所有文件
    has_trades, trade_files = check_yesterday_trades()
    if not has_trades:
        log(f"[INFO] 昨天无交易，归档终止")
        return False

    # 2. 再次确认总库没有（双重检查）
    if check_db_has_yesterday():
        log(f"[INFO] 总库已有数据，归档终止")
        return False

    # 3. 解析并归档
    trade_db = load_trade_db()
    meta = load_trade_meta()
    total_added = 0

    for filepath in trade_files:
        filename = os.path.basename(filepath)
        trades = parse_trade_excel(filepath)

        # 只取昨天的交易
        yesterday_trades = [t for t in trades if t['trade_date'] == yesterday]

        for t in yesterday_trades:
            # 生成唯一key
            key = f"{t['fund_code']}_{t['trade_date']}_{t['trade_type']}_{t.get('buy_amount', 0)}_{t.get('sell_amount', 0)}"

            if key in trade_db:
                log(f"[SKIP] 记录已存在: {key}")
                continue

            trade_db[key] = t
            total_added += 1

        # 更新元数据
        meta[filename] = {
            'md5': file_md5(filepath),
            'mtime': os.path.getmtime(filepath),
            'archived_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'record_count': len(yesterday_trades)
        }

        log(f"[OK] 归档文件 {filename}: {len(yesterday_trades)}条记录")

    # 4. 保存
    if save_trade_db(trade_db) and save_trade_meta(meta):
        log(f"[SUCCESS] 归档完成: 新增{total_added}条记录到总库")
        return True
    else:
        log(f"[ERROR] 归档保存失败")
        return False


def main():
    """主入口：条件判断 + 执行"""
    print("=" * 60)
    print("交易日归档脚本")
    print("=" * 60)
    print(f"交易目录 : {TRADE_DIR}")
    print(f"总库文件 : {TRADE_DB_FILE}")
    print(f"日志文件 : {LOG_FILE}")
    print("=" * 60)

    yesterday = get_yesterday()
    log(f"[START] 归档检查开始，目标日期: {yesterday}")

    # 条件判断链
    # 条件1: 昨天是否有交易？
    has_trades, _ = check_yesterday_trades()
    if not has_trades:
        log(f"[END] 昨天无交易，无需归档")
        print(f"\n结论: 昨天({yesterday})无交易记录，不执行归档")
        return 0  # 正常退出，码0表示"无需执行"

    # 条件2: 总库是否已有？
    db_has = check_db_has_yesterday()
    if db_has:
        log(f"[END] 总库已有数据，无需归档")
        print(f"\n结论: 总库已包含昨天({yesterday})数据，不执行归档")
        return 0  # 正常退出，码0表示"已存在"

    # 条件满足：执行归档
    print(f"\n条件满足: 昨天有交易 且 总库未包含")
    print(f"开始执行归档...")

    success = archive_yesterday_trades()

    if success:
        print(f"\n[SUCCESS] 归档完成！")
        return 0
    else:
        print(f"\n[FAILED] 归档失败！")
        return 1


if __name__ == "__main__":
    sys.exit(main())