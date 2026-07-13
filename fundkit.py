# -*- coding: utf-8 -*-
"""
fundkit.py —— 基金分析统一核心模块（重构版）

把原本散落在 download_fund_history*.py / fund_analysis.py / import_today.py /
update.py 等 6+ 份重复脚本里的逻辑，收敛成唯一一份可复用实现。

相对原版修复的问题：
  1. 路径全部基于本文件位置计算（BASE_DIR），不再硬编码 E:/AKshare。
  2. 基金名称只拉取一次全量列表并缓存（原版每只基金都请求一次全量，120 只=120 次网络）。
  3. 区间涨幅/极值改用「真实日期」计算（latest_date - N 天），不再用行号偏移，
     避免停牌/节假日导致“7天”实际跨了 9 个交易日。
  4. 原 download_fund_history3.py 调用了未定义的 get_fund_index_metrics（运行时 NameError），
     这里补上：夏普比率由净值日收益年化计算，跟踪误差/信息比率需基准故置空。
  5. fund_list.txt 容忍脏数据（缺失逗号、类型字段被复用为指数代码等）。
  6. 统一返回中文字段名的 dict，跨脚本一致。

用法：
    python fundkit.py                # 读取 fund_list.txt，批量分析并落盘 Excel
    from fundkit import get_fund_metrics, batch_process_funds
"""
from __future__ import annotations

import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import akshare as ak
import pandas as pd

# ===================== 路径配置（相对化，不再硬编码） =====================
BASE_DIR = Path(__file__).resolve().parent          # 仓库根目录
DATA_DIR = BASE_DIR / "data"                        # 输出 Excel 等落盘目录
DATA_DIR.mkdir(exist_ok=True)

DEFAULT_LIST = BASE_DIR / "fund_list.txt"

# ===================== 基金名称缓存（只拉一次） =====================
_fund_name_cache: dict[str, str] = {}


def _load_fund_names() -> dict[str, str]:
    """一次性拉取全部基金代码->简称映射。"""
    try:
        df = ak.fund_name_em()
        return dict(zip(df["基金代码"].astype(str), df["基金简称"].astype(str)))
    except Exception as e:  # 网络/接口异常时退化为用代码本身
        print(f"[WARN] 基金名称表拉取失败，将直接用代码: {e}")
        return {}


def get_fund_name(fund_code: str) -> str:
    """返回基金简称；首次调用时拉取全表并缓存。"""
    global _fund_name_cache
    if not _fund_name_cache:
        _fund_name_cache = _load_fund_names()
    return _fund_name_cache.get(str(fund_code), str(fund_code))


# ===================== 读取基金清单 =====================
def read_fund_list(filename: str | os.PathLike = DEFAULT_LIST) -> list[dict]:
    """
    读取基金清单，格式：基金代码,基金类型,自定义天数
    容忍脏数据：缺失逗号、类型字段被复用为指数代码等。
    """
    fund_list: list[dict] = []
    try:
        with open(filename, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = [p.strip() for p in line.split(",")]
                code = re.sub(r"\D", "", parts[0])[:6]  # 提取前 6 位数字作为代码
                if not code:
                    continue
                ftype = parts[1] if len(parts) > 1 else "ETF"
                try:
                    custom_days = int(parts[2]) if len(parts) > 2 else 7
                except ValueError:
                    custom_days = 7
                fund_list.append({"code": code, "type": ftype, "custom_days": custom_days})
        print(f"从 {filename} 读取了 {len(fund_list)} 只基金")
        return fund_list
    except FileNotFoundError:
        print(f"错误：找不到文件 {filename}")
        return []
    except Exception as e:
        print(f"读取文件失败: {e}")
        return []


# ===================== 区间指标计算（按真实日期） =====================
def calculate_return(nav_df: pd.DataFrame, date_col: str, value_col: str, days: int):
    """
    计算“最新净值”相对“最新日期 - days 个日历日之前”的涨幅(%)。
    使用真实日期偏移，而非行号，避免交易缺口导致的偏差。
    nav_df 约定按 date_col 降序（最新在 index 0）。
    """
    if len(nav_df) == 0:
        return None
    latest_date = nav_df.loc[0, date_col]
    target_date = latest_date - timedelta(days=days)
    past = nav_df[nav_df[date_col] <= target_date]
    if past.empty:
        return None
    past_value = float(past.iloc[0][value_col])   # 降序下第一段即最接近 target 的历史点
    latest_value = float(nav_df.loc[0, value_col])
    if past_value == 0:
        return None
    return (latest_value - past_value) / past_value * 100


def get_price_extremes(nav_df: pd.DataFrame, date_col: str, value_col: str, days: int):
    """返回最近 days 个日历日窗口内的最低/最高净值。"""
    if len(nav_df) == 0:
        return None, None
    latest_date = nav_df.loc[0, date_col]
    target_date = latest_date - timedelta(days=days)
    window = nav_df[nav_df[date_col] >= target_date]
    if window.empty:
        return None, None
    return float(window[value_col].min()), float(window[value_col].max())


def get_fund_index_metrics(nav_df: pd.DataFrame, date_col: str, value_col: str) -> dict:
    """
    指数类指标。夏普比率由净值日收益年化计算；
    跟踪误差/信息比率需要基准指数，这里无基准故置空（返回 None）。
    """
    s = pd.to_numeric(nav_df[value_col], errors="coerce").dropna()
    if len(s) < 3:
        return {"跟踪误差": None, "夏普比率": None, "信息比率": None}
    s = s.sort_index()
    rets = s.pct_change().dropna()
    if rets.empty or rets.std() == 0:
        sharpe = None
    else:
        sharpe = round((rets.mean() / rets.std()) * (252 ** 0.5), 3)
    return {"跟踪误差": None, "夏普比率": sharpe, "信息比率": None}


# ===================== 获取单只基金指标 =====================
def get_fund_nav(fund_code: str):
    """
    多接口回退获取历史净值，统一为含 [日期, 单位净值, 日增长率] 的 DataFrame（降序）。
    回退顺序：开放式基金 EM -> ETF EM -> A 股历史。
    """
    try:
        nav_df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
    except Exception as e1:
        print(f"开放式基金接口失败，尝试 ETF 接口: {e1}")
        try:
            nav_df = ak.fund_etf_hist_em(
                symbol=fund_code, period="daily",
                start_date="20230101", end_date=datetime.now().strftime("%Y%m%d"), adjust="",
            ).rename(columns={"日期": "净值日期", "收盘": "单位净值", "涨跌幅": "日增长率"})
        except Exception as e2:
            print(f"ETF 接口也失败，尝试股票接口: {e2}")
            nav_df = ak.stock_zh_a_hist(
                symbol=fund_code, period="daily",
                start_date="20230101", end_date=datetime.now().strftime("%Y%m%d"), adjust="",
            ).rename(columns={"日期": "净值日期", "收盘": "单位净值", "涨跌幅": "日增长率"})

    # 自适应列名
    date_col = "净值日期" if "净值日期" in nav_df.columns else ("日期" if "日期" in nav_df.columns else nav_df.columns[0])
    if "单位净值" in nav_df.columns:
        value_col = "单位净值"
    elif "累计净值" in nav_df.columns:
        value_col = "累计净值"
    elif "收盘" in nav_df.columns:
        value_col = "收盘"
    else:
        value_col = nav_df.columns[1]

    nav_df[date_col] = pd.to_datetime(nav_df[date_col])
    nav_df = nav_df.sort_values(by=date_col, ascending=False).reset_index(drop=True)
    nav_df[value_col] = pd.to_numeric(nav_df[value_col], errors="coerce")
    return nav_df, date_col, value_col


def get_fund_metrics(fund_code: str, fund_type: str = "ETF", custom_days: int = 7,
                     save_to_excel: bool = False) -> dict | None:
    """获取单只基金历史净值并计算各区间涨幅/极值/指数指标。"""
    try:
        fund_name = get_fund_name(fund_code)
        print(f"正在获取基金 {fund_code} ({fund_name}) 的历史净值数据...")

        nav_df, date_col, value_col = get_fund_nav(fund_code)

        latest_nav = float(nav_df.loc[0, value_col]) if len(nav_df) > 0 else None
        daily_change = None
        if "日增长率" in nav_df.columns and len(nav_df) > 0:
            dc = nav_df.loc[0, "日增长率"]
            if isinstance(dc, str):
                dc = dc.replace("%", "").strip()
            daily_change = float(dc) if pd.notna(dc) and dc != "" else None

        # 各区间涨幅（真实日期）
        three_day = calculate_return(nav_df, date_col, value_col, 3)
        five_day = calculate_return(nav_df, date_col, value_col, 5)
        seven_day = calculate_return(nav_df, date_col, value_col, 7)
        fourteen_day = calculate_return(nav_df, date_col, value_col, 14)
        custom_day = calculate_return(nav_df, date_col, value_col, custom_days)
        three_month = calculate_return(nav_df, date_col, value_col, 90)
        six_month = calculate_return(nav_df, date_col, value_col, 180)
        one_year = calculate_return(nav_df, date_col, value_col, 365)

        one_m_min, one_m_max = get_price_extremes(nav_df, date_col, value_col, 30)
        three_m_min, three_m_max = get_price_extremes(nav_df, date_col, value_col, 90)
        six_m_min, six_m_max = get_price_extremes(nav_df, date_col, value_col, 180)

        index_metrics = get_fund_index_metrics(nav_df, date_col, value_col)

        result = {
            "基金代码": fund_code,
            "基金名称": fund_name,
            "股票类型": fund_type,
            "当日净值": round(latest_nav, 4) if latest_nav else None,
            "当日涨幅(%)": round(daily_change, 2) if daily_change else None,
            "天": custom_days,
            "3天涨幅(%)": round(three_day, 2) if three_day is not None else None,
            "5天涨幅(%)": round(five_day, 2) if five_day is not None else None,
            "7天涨幅(%)": round(seven_day, 2) if seven_day is not None else None,
            "14天涨幅(%)": round(fourteen_day, 2) if fourteen_day is not None else None,
            f"{custom_days}天涨幅(%)": round(custom_day, 2) if custom_day is not None else None,
            "三个月涨幅(%)": round(three_month, 2) if three_month is not None else None,
            "半年涨幅(%)": round(six_month, 2) if six_month is not None else None,
            "一年涨幅(%)": round(one_year, 2) if one_year is not None else None,
            "1个月最低": round(one_m_min, 4) if one_m_min else None,
            "3个月最低": round(three_m_min, 4) if three_m_min else None,
            "6个月最低": round(six_m_min, 4) if six_m_min else None,
            "1个月最高": round(one_m_max, 4) if one_m_max else None,
            "3个月最高": round(three_m_max, 4) if three_m_max else None,
            "6个月最高": round(six_m_max, 4) if six_m_max else None,
            "跟踪误差": index_metrics["跟踪误差"],
            "夏普比率": index_metrics["夏普比率"],
            "信息比率": index_metrics["信息比率"],
            "数据更新时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        for k, v in result.items():
            print(f"{k}: {v}")

        if save_to_excel:
            save_to_excel_file(result, nav_df, fund_code, fund_name, custom_days, date_col, value_col)

        return result

    except Exception as e:
        print(f"获取数据失败: {e}")
        import traceback
        traceback.print_exc()
        return None


# ===================== 落盘 Excel =====================
def get_unique_filename(base_filename: str) -> str:
    """若文件被占用则追加序号/时间戳，避免 PermissionError。"""
    if not os.path.exists(base_filename):
        return base_filename
    name, ext = os.path.splitext(base_filename)
    counter = 1
    while counter <= 99:
        cand = f"{name}_{counter:02d}{ext}"
        if not os.path.exists(cand):
            return cand
        counter += 1
    return f"{name}_{datetime.now().strftime('%H%M%S')}{ext}"


def _safe_sheet_name(df: pd.DataFrame) -> pd.ExcelWriter:
    return None  # 占位，保持接口清晰


def save_to_excel_file(result: dict, full_data_df: pd.DataFrame, fund_code: str,
                       fund_name: str, custom_days: int = 7,
                       date_col: str = "净值日期", value_col: str = "单位净值") -> None:
    """保存单只基金：指标汇总 + 历史净值两个 Sheet。"""
    today = datetime.now().strftime("%Y%m%d")
    safe_name = re.sub(r'[\\/*?:<>|""]', "", str(fund_name)).replace("/", "-")
    base = DATA_DIR / f"fund_{fund_code}_{safe_name}_{custom_days}day_{today}.xlsx"
    filename = get_unique_filename(str(base))

    disp = full_data_df.copy()
    if "净值日期" in disp.columns:
        disp = disp.rename(columns={"净值日期": "日期", "单位净值": "净值"})
    try:
        with pd.ExcelWriter(filename, engine="openpyxl") as writer:
            pd.DataFrame([result]).to_excel(writer, sheet_name="指标汇总", index=False)
            disp.to_excel(writer, sheet_name="历史净值", index=False)
        print(f"✅ 数据已保存到: {os.path.abspath(filename)}")
    except PermissionError:
        ts = datetime.now().strftime("%H%M%S")
        filename = str(base).replace(".xlsx", f"_{ts}.xlsx")
        with pd.ExcelWriter(filename, engine="openpyxl") as writer:
            pd.DataFrame([result]).to_excel(writer, sheet_name="指标汇总", index=False)
            disp.to_excel(writer, sheet_name="历史净值", index=False)
        print(f"✅ 数据已保存到: {os.path.abspath(filename)}")


def save_batch_results(results_list: list[dict]) -> None:
    """批量保存多只基金到同一个汇总 Excel。"""
    if not results_list:
        return
    today = datetime.now().strftime("%Y%m%d")
    base = DATA_DIR / f"funds_batch_analysis_{today}.xlsx"
    filename = get_unique_filename(str(base))
    df = pd.DataFrame(results_list)
    try:
        with pd.ExcelWriter(filename, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="基金分析汇总", index=False)
            ws = writer.sheets["基金分析汇总"]
            for i, col in enumerate(df.columns):
                max_len = max(int(df[col].astype(str).map(len).max() or 0), len(str(col))) + 2
                letter = chr(65 + i) if i < 26 else chr(64 + i // 26) + chr(65 + i % 26)
                ws.column_dimensions[letter].width = min(max_len, 30)
        print(f"✅ 批量分析结果已保存到: {os.path.abspath(filename)}")
    except PermissionError:
        ts = datetime.now().strftime("%H%M%S")
        filename = str(base).replace(".xlsx", f"_{ts}.xlsx")
        with pd.ExcelWriter(filename, engine="openpyxl") as writer:
            pd.DataFrame(results_list).to_excel(writer, sheet_name="基金分析汇总", index=False)
        print(f"✅ 批量分析结果已保存到: {os.path.abspath(filename)}")


# ===================== 批量入口 =====================
def batch_process_funds(fund_list: list[dict], save_to_excel: bool = True) -> list[dict]:
    """批量分析多只基金，可选落盘到单个汇总 Excel。"""
    all_results = []
    for info in fund_list:
        code = info.get("code")
        ftype = info.get("type", "ETF")
        days = info.get("custom_days", 7)
        res = get_fund_metrics(code, fund_type=ftype, custom_days=days, save_to_excel=False)
        if res:
            all_results.append(res)
        time.sleep(0.3)  # 轻量限流，避免触发接口风控
    if save_to_excel and all_results:
        save_batch_results(all_results)
    return all_results


# ===================== 命令行入口 =====================
if __name__ == "__main__":
    fund_list = read_fund_list(DEFAULT_LIST)
    if not fund_list:
        print("使用默认示例基金...")
        fund_list = [{"code": "022365", "type": "混合型", "custom_days": 10}]
    print(f"\n开始分析 {len(fund_list)} 只基金...")
    results = batch_process_funds(fund_list)
    print(f"\n分析完成！共成功分析 {len(results)} 只基金")
