from datetime import datetime
import pytz
import pandas as pd
from typing import Optional
from logger import get_logger

logger = get_logger(__name__)

OUTPUT_COLS = [
    "即时排名",
    "当前排名",
    "用户名",
    "当前状态",
    "存活天数",
    "杀手球员",
    "今日主选",
    "今日备选",
    "今日状态",
    "本站得分",
    "扣除积分",
    "即时积分",
    "选人明细",
]


def format_rank_change(x):
    # Handle NaN first
    if pd.isna(x):
        return '<span class="rank up"></span>'  # arrow only

    try:
        x = int(x)
    except:
        return x

    if x > 0:
        return f'<span class="rank up">+{x}</span>'
    elif x < 0:
        return f'<span class="rank down">{x}</span>'
    else:
        return '<span class="rank same"></span>'


def prepare_rank_change(df):
    df = df.loc[:, [c for c in OUTPUT_COLS if c in df.columns]].copy()
    df["排名变化"] = pd.to_numeric(df["当前排名"], errors="coerce") - pd.to_numeric(
        df["即时排名"], errors="coerce"
    )
    df["排名变化"] = df["排名变化"].astype("Int64")
    for col in ("当前排名", "当前积分", "本站得分", "扣除积分", "即时积分", "即时排名", "存活天数"):
        if col in df.columns:
            df[col] = (
                pd.to_numeric(df[col], errors="coerce").round(0).astype("Int64")
            )
    if "今日主选" in df.columns:
        df["今日主选"] = df["今日主选"].fillna("")
        df["今日备选"] = df["今日备选"].fillna("")
        df["今日状态"] = df["今日状态"].fillna("已选")
    return df


_KEEP_TODAY_PICK_STATUS = frozenset({"存活", "未完赛", "未选", "轮空"})


def hide_today_picks_for_eliminated(df: pd.DataFrame) -> pd.DataFrame:
    """
    For display: settled losers keep 杀手球员, but clear 今日主选/备选/状态.

    Call after generate_summary so pick counts still include today's losses.
    """
    if df is None or df.empty or "当前状态" not in df.columns:
        return df
    out = df.copy()
    status = out["当前状态"].astype("string").fillna("").str.strip()
    keep = status.isin(_KEEP_TODAY_PICK_STATUS)
    for col in ("今日主选", "今日备选", "今日状态"):
        if col in out.columns:
            out.loc[~keep, col] = ""
    return out


def mark_unfinished_status(
    df: pd.DataFrame,
    live_players: Optional[list] = None,
    pending_user_ids: Optional[set] = None,
) -> pd.DataFrame:
    """
    Display-only: still-alive users whose today's pick is not settled → 未完赛.

    Covers in-progress matches (``live_players``) and not-yet-started ones
    (``pending_user_ids`` from live settlement). Settled winners stay 存活.
    """
    if df is None or df.empty or "当前状态" not in df.columns:
        return df
    live = {
        str(p).strip()
        for p in (live_players or [])
        if p is not None and str(p).strip()
    }
    pending = {
        str(u).strip()
        for u in (pending_user_ids or set())
        if u is not None and str(u).strip()
    }
    if not live and not pending:
        return df
    out = df.copy()
    status = out["当前状态"].astype("string").fillna("").str.strip()
    unfinished = pd.Series(False, index=out.index)
    if live and "今日主选" in out.columns:
        pick = out["今日主选"].astype("string").fillna("").str.strip()
        unfinished = unfinished | pick.isin(live)
    if pending:
        unfinished = unfinished | _uid_series(out).isin(pending)
    out.loc[status.eq("存活") & unfinished, "当前状态"] = "未完赛"
    return out


def mark_unpicked_status(df: pd.DataFrame) -> pd.DataFrame:
    """
    Display-only: still-alive users with no today's pick → 未选 (or 轮空).

    Surfaces former 今日状态 labels into 当前状态 so that column can be dropped.
    """
    if df is None or df.empty or "当前状态" not in df.columns:
        return df
    out = df.copy()
    status = out["当前状态"].astype("string").fillna("").str.strip()
    alive = status.eq("存活")
    if not alive.any():
        return out
    if "今日状态" in out.columns:
        today = out["今日状态"].astype("string").fillna("").str.strip()
        out.loc[alive & today.eq("未选"), "当前状态"] = "未选"
        out.loc[alive & today.eq("轮空"), "当前状态"] = "轮空"
        return out
    if "今日主选" in out.columns:
        pick = out["今日主选"].astype("string").fillna("").str.strip()
        out.loc[alive & pick.eq(""), "当前状态"] = "未选"
    return out


def drop_today_status_column(df: pd.DataFrame) -> pd.DataFrame:
    """Remove 今日状态 from ranking views (info folded into 当前状态)."""
    if df is None or df.empty or "今日状态" not in df.columns:
        return df
    return df.drop(columns=["今日状态"])


def _uid_series(df: pd.DataFrame) -> pd.Series:
    def _key(value) -> str:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return ""
        text = str(value).strip()
        if text.endswith(".0"):
            try:
                float(text)
                return text[:-2]
            except ValueError:
                return text
        return text

    for col in ("user_id", "主键"):
        if col in df.columns:
            return df[col].map(_key)
    return pd.Series([""] * len(df), index=df.index)


def generate_summary(df: pd.DataFrame, day1: bool = False, bye: bool = False):
    # Day0 / no-submission pages may not contain summary-related columns.
    # In that case, return an empty frame so caller can skip rendering summary.
    required_cols = {"今日主选", "今日状态"}
    if not day1:
        required_cols.add("当前状态")
    missing = required_cols - set(df.columns)
    if missing:
        logger.info(f"Skip summary generation, missing columns: {sorted(missing)}")
        return pd.DataFrame()

    # Normalize status labels to avoid split columns like "已选 " / " 已选"
    # which would make downstream summary parser treat valid picks as 0.
    df = df.copy()
    status = df["今日状态"].astype("string").str.strip()
    status = status.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    known_status = {"已选", "未选", "轮空", "自杀（重复）", "自杀（主备冲突）"}
    # Any unknown non-empty status from pipeline should be treated as selected.
    status = status.where(status.isin(known_status), "已选")
    df["今日状态"] = status.fillna("已选")
    df["今日主选"] = df["今日主选"].astype("string").fillna("").str.strip()

    # Board is already limited to users alive at open (see build_table).
    # Include still-in-pool (存活/未完赛/未选/轮空) + anyone with today's pick.
    if day1 or "当前状态" not in df.columns:
        summary_src = df
    else:
        has_pick = df["今日主选"].astype("string").fillna("").str.strip().ne("")
        in_pool = df["当前状态"].astype("string").fillna("").str.strip().isin(
            _KEEP_TODAY_PICK_STATUS
        )
        summary_src = df.loc[in_pool | has_pick, :]

    stats_df = pd.pivot_table(
        summary_src,
        index="今日主选",
        columns="今日状态",
        aggfunc="size",  # count
        fill_value=0,
    )

    if stats_df.empty:
        return pd.DataFrame()
    # 1. Create the sums
    stats_df["总计"] = stats_df.sum(axis=1)
    stats_df.loc["总计"] = stats_df.sum(axis=0, numeric_only=True)
    stats_df.columns.name = None
    # 2. Reset index so "index" is a column
    stats_df = stats_df.reset_index()

    # 3. Separate the 'Total' row from the main data
    main_data = stats_df[stats_df["今日主选"] != "总计"]
    total_row = stats_df[stats_df["今日主选"] == "总计"]

    # 4. Sort only the main data
    try:
        main_data = main_data.sort_values(by=["已选", "总计"], ascending=False)
    except KeyError as err:
        logger.warning(err)
        main_data = main_data.sort_values(by="总计", ascending=False)
    # 5. Combine them back together
    stats_df = pd.concat([main_data, total_row], ignore_index=True)

    if bye and day1:
        stats_df = stats_df.rename({"已选": "非轮空"}, axis=1)
    return stats_df


def dataframe_to_filterable_html(
    df,
    output_file: str = "table.html",
    title: str = "数据表格",
    encoding: str = "utf-8",
    killer: bool = False,
    summary_stats: bool = False,
    bye: bool = False,
    day1: bool = False,
) -> Optional[str]:

    if df is None:
        logger.warning(f"{title} is empty.")
        return

    # ===== Timestamp =====
    tz = pytz.timezone("Asia/Singapore")
    last_updated = datetime.now(tz).strftime("%Y年%m月%d日 %H:%M:%S")
    if not killer:
        df = prepare_rank_change(df)

    if summary_stats:
        summary_df = generate_summary(df, day1, bye)
        summary_html = summary_df.to_html(
            index=False, classes="summary-table", border=0, escape=False
        )
    else:
        summary_html = ""  # nothing inserted

    summary_section = (
        f"""
        <div class="summary-section">
            <button class="summary-toggle" onclick="toggleSummary()">
                📊 显示选人统计
            </button>

            <div class="summary-content" id="summaryContent">
                {summary_html}
            </div>
        </div>
        """
        if summary_stats
        else ""
    )

    summary_script = (
        """
        function toggleSummary() {
            const content = document.getElementById('summaryContent');
            const btn = document.querySelector('.summary-toggle');

            content.classList.toggle('show');

            if (content.classList.contains('show')) {
                btn.textContent = '📊 隐藏选人统计';
            } else {
                btn.textContent = '📊 显示选人统计';
            }
        }
        """
        if summary_stats
        else ""
    )

    # Convert DataFrame to HTML
    df_html = df.to_html(
        index=False, classes="filterable-table", border=0, escape=False
    )

    # ===== HTML template =====
    # Create the complete HTML with filtering functionality
    html_template = f"""<!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="{encoding}">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <style>
                :root {{
                    --bg-body: #f5f5f5;
                    --bg-container: #ffffff;
                    --text-main: #333333;
                    --text-secondary: #7f8c8d;
                    --text-filter: #6e6d6d;
                    --table-header-bg: #3498db;
                    --table-header-text: #ffffff;
                    --table-row-hover: #f1f7fb;
                    --table-row-even: #fafafa;
                    --border-color: #e0e0e0;
                    --dropdown-bg: #ffffff;
                    --dropdown-border: #ccc;
                    --filter-row-bg: #ecf0f1;
                    --stats-bg: #e8f4f8;
                }}

                body.dark-mode {{
                    --bg-body: #121212;
                    --bg-container: #1e1e1e;
                    --text-main: #e0e0e0;
                    --text-secondary: #a0a0a0;
                    --text-filter: #adacac;
                    --table-header-bg: #1f3d58;
                    --table-header-text: #ffffff;
                    --table-row-hover: #333333;
                    --table-row-even: #252525;
                    --border-color: #333333;
                    --dropdown-bg: #2d2d2d;
                    --dropdown-border: #444;
                    --filter-row-bg: #2c2c2c;
                    --stats-bg: #2c3e50;
                }}

                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}

                body {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB",
                                "Microsoft YaHei", "Helvetica Neue", Helvetica, Arial, sans-serif;
                    padding: 20px;
                    background: var(--bg-body);
                    color: var(--text-main);
                    line-height: 1.5;
                    transition: background 0.3s, color 0.3s;
                }}

                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    background: var(--bg-container);
                    padding: 30px;
                    border-radius: 8px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                    transition: background 0.3s;
                    /* 1. Center alignment layout setup */
                    position: relative; 
                }}

                /* 1. Title centered */
                .header-info {{
                    text-align: center;
                    margin-bottom: 20px;
                    /* Space for the toggle button on the right */
                    padding-right: 60px; 
                }}

                h1 {{
                    color: var(--text-main);
                    font-size: 24px;
                    margin-bottom: 8px;
                    display: block;
                }}

                .last-updated {{
                    font-size: 12px;
                    color: var(--text-secondary);
                    background: var(--filter-row-bg);
                    padding: 4px 12px;
                    border-radius: 12px;
                    display: inline-block;
                }}

                /* 2. Pill-style day/night toggle */
                .theme-toggle {{
                    position: absolute;
                    right: 30px;
                    top: 10px;
                    width: 140px;
                    height: 36px;
                    border-radius: 18px;
                    border: 2px solid var(--border-color);
                    background: var(--filter-row-bg);
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    padding: 0;
                    overflow: hidden;
                    transition: background 0.3s, border-color 0.3s;
                }}

                .theme-toggle .toggle-knob {{
                    width: 32px;
                    height: 32px;
                    border-radius: 50%;
                    background: var(--text-secondary);
                    color: var(--filter-row-bg);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 16px;
                    flex-shrink: 0;
                    margin-left: 1px;
                    transition: background 0.3s, color 0.3s;
                    order: 1;
                }}

                body.dark-mode .theme-toggle .toggle-knob {{
                    order: 2;
                    margin-left: 0;
                    margin-right: 1px;
                }}

                .theme-toggle .toggle-label {{
                    flex: 1;
                    text-align: center;
                    font-size: 11px;
                    font-weight: 700;
                    letter-spacing: 0.05em;
                    color: var(--text-secondary);
                    order: 2;
                    transition: color 0.3s;
                    padding-right: 4px;
                }}

                body.dark-mode .theme-toggle .toggle-label {{
                    order: 1;
                    padding-right: 0;
                    padding-left: 4px;
                }}

                .summary-section {{
                    margin-top: 12px;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    margin-bottom: 20px;
                    padding-right: 60px;
                }}

                .summary-toggle {{
                    background: var(--filter-row-bg);
                    border: 1px solid var(--border-color);
                    color: var(--text-main);
                    padding: 6px 12px;
                    border-radius: 6px;
                    cursor: pointer;
                    font-size: 12px;
                    transition: all 0.2s;
                }}

                /* 3. Summary Section (if applicable) */

                .summary-content {{
                    margin-top: 10px;
                    padding: 12px;
                    border: 1px solid var(--border-color);
                    border-radius: 6px;
                    background: var(--bg-container);
                    display: none;
                }}
                
                .summary-content.show {{
                    display: block;
                    max-height: 300px;
                    overflow-y: auto;
                    overflow-x: auto;
                }}

                /* Summary Table Styling */
                .summary-table {{
                    width: 100%;
                    border-collapse: collapse;
                    font-size: 12px;
                    margin-top: 6px;
                }}

                .summary-table th {{
                    background: var(--filter-row-bg);
                    color: var(--text-main);
                    padding: 8px;
                    text-align: left;
                    font-weight: 600;
                    border-bottom: 2px solid var(--border-color);
                    white-space: nowrap;
                }}

                .summary-table td {{
                    padding: 8px;
                    border-bottom: 1px solid var(--border-color);
                    color: var(--text-main);
                }}

                .summary-table tr:nth-child(even) {{
                    background-color: var(--table-row-even);
                }}

                .summary-table tr:hover {{
                    background-color: var(--table-row-hover);
                }}

                /* Optional: make first column stand out (useful for stats labels) */
                .summary-table td:first-child,
                .summary-table th:first-child {{
                    font-weight: 600;
                }}

                /* Optional: compact look */
                .summary-table.compact th,
                .summary-table.compact td {{
                    padding: 6px;
                    font-size: 11px;
                }}

                .table-wrapper {{
                    max-height: 70vh;
                    overflow-y: auto;
                    overflow-x: auto;
                    border: 1px solid var(--border-color);
                    border-radius: 4px;
                }}

                .filterable-table {{
                    width: 100%;
                    border-collapse: collapse;
                    font-size: 12px; 
                }}

                .filterable-table th {{
                    background: var(--table-header-bg);
                    color: var(--table-header-text);
                    padding: 10px 8px;
                    text-align: left;
                    font-weight: 600;
                    position: sticky;
                    top: 0;
                    z-index: 20;
                    cursor: pointer;
                    user-select: none;
                    white-space: nowrap;
                }}

                .filterable-table td {{
                    padding: 8px;
                    border-bottom: 1px solid var(--border-color);
                    vertical-align: middle;
                    color: var(--text-main);
                }}

                .filterable-table tr:hover {{
                    background-color: var(--table-row-hover);
                }}

                .filterable-table tr:nth-child(even) {{
                    background-color: var(--table-row-even);
                }}

                .filterable-table tr:nth-child(even):hover {{
                    background-color: var(--table-row-hover);
                }}

                .filter-row {{
                    background: var(--filter-row-bg) !important;
                    position: sticky;
                    top: 40px;
                    z-index: 19;
                }}

                .filter-row th {{
                    padding: 8px;
                    background: var(--filter-row-bg) !important;
                    cursor: default;
                    border-bottom: 2px solid var(--border-color);
                }}

                /* 4. Dropdown Styling */
                .filter-dropdown {{
                    position: relative;
                    width: 100%;
                }}

                .filter-trigger {{
                    width: 100%;
                    padding: 6px 8px;
                    border: 1px solid var(--dropdown-border);
                    border-radius: 4px;
                    background: var(--dropdown-bg);
                    color: var(--text-filter);
                    font-size: 11px;
                    cursor: pointer;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }}

                .filter-trigger:hover {{
                    border-color: #3498db;
                }}

                .dropdown-content {{
                    display: none;
                    position: fixed;
                    background-color: var(--dropdown-bg);
                    color: var(--text-filter);
                    min-width: 160px;
                    max-height: 250px;
                    overflow-y: auto;
                    border: 1px solid var(--dropdown-border);
                    box-shadow: 0px 8px 16px rgba(0,0,0,0.2);
                    z-index: 9999;
                }}

                .dropdown-content.show {{
                    display: block;
                }}

                .option-item {{
                    padding: 8px 10px;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    font-size: 12px;
                    border-bottom: 1px solid var(--border-color);
                }}
                
                .option-item:last-child {{
                    border-bottom: none;
                }}

                .option-item:hover {{
                    background-color: var(--table-row-hover);
                }}

                .option-item input[type="checkbox"] {{
                    margin: 0;
                }}

                .dropdown-search {{
                    width: 100%;
                    padding: 8px 10px;
                    border: none;
                    border-bottom: 1px solid var(--border-color);
                    background: var(--dropdown-bg);
                    color: var(--text-main);
                    font-size: 12px;
                    outline: none;
                }}
                .dropdown-search::placeholder {{
                    color: var(--text-secondary);
                }}
                .dropdown-search:focus {{
                    border-bottom-color: #3498db;
                }}

                /* 5. Row count align left */
                .stats {{
                    margin-top: 10px;
                    padding: 8px;
                    background: var(--stats-bg);
                    border-radius: 4px;
                    font-size: 12px;
                    color: var(--text-main);
                    text-align: left;
                }}

                /* Sorting styling */
                th.sort-asc::after {{
                    content: " ▲";
                    font-size: 10px;
                }}
                th.sort-desc::after {{
                    content: " ▼";
                    font-size: 10px;
                }}

                /* Rank styling */
                .rank {{
                    font-weight: 600;
                    display: inline-flex;
                    align-items: center;
                    gap: 4px;
                }}

                .rank.up {{
                    color: #27ae60;
                }}
                .rank.up::before {{
                    content: "▲";
                }}

                .rank.down {{
                    color: #e74c3c;
                }}
                .rank.down::before {{
                    content: "▼";
                }}

                .rank.same {{
                    color: #f39c12;
                }}
                .rank.same::before {{
                    content: "▶";
                }}
                


                @media (max-width: 768px) {{
                    body {{ padding: 8px; }}

                    .container {{ padding: 12px; position: static; }}

                    /* Stack theme toggle below title instead of overlapping it */
                    .theme-toggle {{
                        position: static;
                        margin: 8px auto 0;
                        width: 120px;
                        height: 32px;
                    }}

                    /* Remove the right-padding offset that compensated for the absolute button */
                    .header-info {{ padding-right: 0; margin-bottom: 10px; }}
                    .summary-section {{ padding-right: 0; }}

                    h1 {{ font-size: 18px; }}

                    .last-updated {{ font-size: 11px; }}

                    /* Compact table */
                    .filterable-table {{ font-size: 11px; }}
                    .filterable-table th,
                    .filterable-table td {{ padding: 5px 4px; white-space: nowrap; }}

                    /* Cap dropdown height and widen tap targets */
                    .dropdown-content {{ max-height: 180px; }}
                    .filter-trigger {{ padding: 5px 6px; font-size: 10px; }}

                    /* Use more viewport height for the table on small screens */
                    .table-wrapper {{ max-height: 65vh; }}

                    .stats {{ font-size: 11px; }}

                    .summary-table th, .summary-table td {{ padding: 6px 5px; font-size: 11px; }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header-info">
                    <h1>{title}</h1>
                    <div class="last-updated">
                        ⏱ 更新时间: {last_updated}
                    </div>
                </div>
                
                <!-- 2. Toggle Button -->
                <button class="theme-toggle" id="themeToggle" onclick="toggleTheme()">
                    <span class="toggle-knob" id="themeIcon">☀️</span>
                    <span class="toggle-label" id="themeLabel">亮色模式</span>
                </button>
                
                {summary_section}

                <div class="stats">
                    显示 <span id="visible-count">0</span> / <span id="total-count">0</span> 行
                </div>

                <div class="table-wrapper">
                    <div id="table-container">
                        {df_html}
                    </div>
                </div>
            </div>

            <script>
                // Theme Toggle
                function toggleTheme() {{
                    document.body.classList.toggle('dark-mode');
                    const isDark = document.body.classList.contains('dark-mode');
                    document.getElementById('themeIcon').textContent = isDark ? '🌙' : '☀️';
                    document.getElementById('themeLabel').textContent = isDark ? '夜间模式' : '亮色模式';
                }}

                // summary section
                {summary_script}

                document.addEventListener('DOMContentLoaded', function() {{
                    const table = document.querySelector('.filterable-table');
                    if (!table) return;

                    const thead = table.querySelector('thead');
                    const tbody = table.querySelector('tbody');
                    const rows = tbody.querySelectorAll('tr');

                    // Stats Initialization
                    const totalCount = rows.length;
                    document.getElementById('total-count').textContent = totalCount;
                    document.getElementById('visible-count').textContent = totalCount;

                    const headerRow = thead.querySelector('tr');
                    const headers = headerRow.querySelectorAll('th');
                    
                    // Create Filter Row
                    const filterRow = document.createElement('tr');
                    filterRow.className = 'filter-row';

                    // Track body-mounted option containers per column for filterTable
                    const allOptionContainers = [];

                    headers.forEach((header, index) => {{
                        let sortDirection = 'none';

                        // 4. Build Dropdown UI
                        const thCell = document.createElement('th');
                        const dropdownWrapper = document.createElement('div');
                        dropdownWrapper.className = 'filter-dropdown';
                        
                        const trigger = document.createElement('div');
                        trigger.className = 'filter-trigger';
                        trigger.innerHTML = '<span>筛选...</span> <span style="font-size:10px">▼</span>';
                        
                        const optionsContainer = document.createElement('div');
                        optionsContainer.className = 'dropdown-content';
                        
                        // 🆕 Add Search Input
                        const searchInput = document.createElement('input');
                        searchInput.type = 'text';
                        searchInput.className = 'dropdown-search';
                        searchInput.placeholder = '搜索...';
                        optionsContainer.prepend(searchInput);

                        // 🆕 Search Filter Logic
                        // AFTER
                        searchInput.addEventListener('input', (e) => {{
                            const query = e.target.value.toLowerCase().trim();
                            optionsContainer.querySelectorAll('.option-item').forEach(item => {{
                                if (item.dataset.selectAll) return;
                                const label = item.querySelector('span').textContent.toLowerCase();
                                item.style.display = label.includes(query) ? 'flex' : 'none';
                            }});
                            // Sync 全选 checkbox: checked only if ALL visible items are checked
                            const visibleCbs = Array.from(
                                optionsContainer.querySelectorAll('.option-item:not([data-select-all])')
                            ).filter(item => item.style.display !== 'none')
                            .map(item => item.querySelector('input[type="checkbox"]'));
                            selectAllCb.checked = visibleCbs.length > 0 && visibleCbs.every(cb => cb.checked);
                        }});

                        // 全选 item
                        const selectAllItem = document.createElement('div');
                        selectAllItem.className = 'option-item select-all-item';
                        selectAllItem.dataset.selectAll = '1';
                        selectAllItem.style.borderBottom = '2px solid var(--border-color)';
                        const selectAllCb = document.createElement('input');
                        selectAllCb.type = 'checkbox';
                        selectAllCb.checked = true;
                        const selectAllLabel = document.createElement('span');
                        selectAllLabel.textContent = '全选';
                        selectAllLabel.style.fontWeight = '600';
                        selectAllItem.appendChild(selectAllCb);
                        selectAllItem.appendChild(selectAllLabel);
                        optionsContainer.appendChild(selectAllItem);

                        // AFTER
                        selectAllCb.addEventListener('change', () => {{
                            const checked = selectAllCb.checked;
                            optionsContainer.querySelectorAll('.option-item:not([data-select-all])').forEach(item => {{
                                if (item.style.display !== 'none') {{  // only affect visible items
                                    item.querySelector('input[type="checkbox"]').checked = checked;
                                }}
                            }});
                            filterTable();
                        }});

                        // Populate Options
                        const uniqueValues = new Set();
                        rows.forEach(row => {{
                            const cell = row.children[index];
                            if(cell) uniqueValues.add(cell.textContent.trim());
                        }});

                        const sortedValues = Array.from(uniqueValues).sort((a, b) => {{
                            const numA = parseFloat(a);
                            const numB = parseFloat(b);
                            // Sort numerically if both are numbers, otherwise sort alphabetically
                            if (!isNaN(numA) && !isNaN(numB)) return numA - numB;
                            return a.localeCompare(b, 'zh');
                        }});
                        
                        sortedValues.forEach(val => {{
                            const item = document.createElement('div');
                            item.className = 'option-item';
                            
                            const cb = document.createElement('input');
                            cb.type = 'checkbox';
                            cb.value = val;
                            cb.checked = true;
                            
                            const label = document.createElement('span');
                            label.textContent = val;
                            
                            item.appendChild(cb);
                            item.appendChild(label);
                            optionsContainer.appendChild(item);
                        }});

                        dropdownWrapper.appendChild(trigger);
                        // Append to body so overflow:auto on .table-wrapper doesn't clip it
                        document.body.appendChild(optionsContainer);
                        allOptionContainers.push(optionsContainer);
                        thCell.appendChild(dropdownWrapper);
                        filterRow.appendChild(thCell);

                        // Sorting Logic
                        header.addEventListener('click', () => {{
                            headers.forEach(h => h.classList.remove('sort-asc', 'sort-desc'));

                            if (sortDirection === 'none') sortDirection = 'asc';
                            else if (sortDirection === 'asc') sortDirection = 'desc';
                            else sortDirection = 'none';

                            if (sortDirection !== 'none') {{
                                header.classList.add(`sort-${{sortDirection}}`);
                                
                                const rowsArray = Array.from(tbody.querySelectorAll('tr'));
                                rowsArray.sort((a, b) => {{
                                    const A = a.children[index].textContent.trim();
                                    const B = b.children[index].textContent.trim();

                                    // Treat empty / null-like values
                                    const isEmptyA = A === "" || A.toLowerCase() === "nan" || A === "-";
                                    const isEmptyB = B === "" || B.toLowerCase() === "nan" || B === "-";

                                    // Always push empty values to bottom
                                    if (isEmptyA && !isEmptyB) return 1;
                                    if (!isEmptyA && isEmptyB) return -1;
                                    if (isEmptyA && isEmptyB) return 0;

                                    // Try numeric comparison
                                    const numA = parseFloat(A);
                                    const numB = parseFloat(B);

                                    if (!isNaN(numA) && !isNaN(numB)) {{
                                        return (numA - numB) * (sortDirection === 'asc' ? 1 : -1);
                                    }}

                                    // Fallback to string comparison
                                    return A.localeCompare(B, 'zh') * (sortDirection === 'asc' ? 1 : -1);
                                }});

                                rowsArray.forEach(row => tbody.appendChild(row));
                            }}
                        }});

                        // Dropdown Logic
                        trigger.addEventListener('click', (e) => {{
                            e.stopPropagation();
                            document.querySelectorAll('.dropdown-content').forEach(d => {{
                                if(d !== optionsContainer) d.classList.remove('show');
                            }});
                            const isOpen = optionsContainer.classList.contains('show');
                            optionsContainer.classList.toggle('show');
                            if (!isOpen) {{
                                const rect = trigger.getBoundingClientRect();
                                const dropH = Math.min(250, optionsContainer.scrollHeight);
                                const spaceBelow = window.innerHeight - rect.bottom;
                                optionsContainer.style.width = rect.width + 'px';
                                if (spaceBelow >= dropH || spaceBelow >= 120) {{
                                    optionsContainer.style.top = rect.bottom + 'px';
                                    optionsContainer.style.bottom = '';
                                }} else {{
                                    optionsContainer.style.top = (rect.top - dropH) + 'px';
                                    optionsContainer.style.bottom = '';
                                }}
                                optionsContainer.style.left = rect.left + 'px';
                            }}
                        }});

                        // AFTER
                        optionsContainer.addEventListener('change', (e) => {{
                            if (!e.target.closest('[data-select-all]')) {{
                                const visibleCbs = Array.from(
                                    optionsContainer.querySelectorAll('.option-item:not([data-select-all])')
                                ).filter(item => item.style.display !== 'none')
                                .map(item => item.querySelector('input[type="checkbox"]'));
                                selectAllCb.checked = visibleCbs.length > 0 && visibleCbs.every(cb => cb.checked);
                            }}
                            filterTable();
                        }});
                    }});

                    thead.appendChild(filterRow);

                    // Close all dropdowns when the table scrolls (fixed-position dropdowns won't follow)
                    document.querySelector('.table-wrapper').addEventListener('scroll', () => {{
                        allOptionContainers.forEach(oc => oc.classList.remove('show'));
                    }});

                    // Dynamically set filter row's sticky top to match actual header height
                    // (avoids hardcoded 40px breaking on mobile where header is shorter)
                    function updateFilterRowTop() {{
                        filterRow.style.top = headerRow.getBoundingClientRect().height + 'px';
                    }}
                    updateFilterRowTop();
                    new ResizeObserver(updateFilterRowTop).observe(headerRow);


                    // Filter Function
                    function filterTable() {{
                        let visibleCount = 0;
                        const activeFilters = [];
                        const triggerEls = document.querySelectorAll('.filter-trigger span:first-child');

                        allOptionContainers.forEach((oc, i) => {{
                            // exclude 全选 checkbox from the value list
                            const checkboxes = Array.from(oc.querySelectorAll('.option-item:not([data-select-all]) input[type="checkbox"]'));
                            const selected = checkboxes.filter(cb => cb.checked).map(cb => cb.value);

                            if (triggerEls[i]) {{
                                if (selected.length === 0) triggerEls[i].textContent = "已取消";
                                else if (selected.length === checkboxes.length) triggerEls[i].textContent = "全部";
                                else triggerEls[i].textContent = `已选 ${{selected.length}} 项`;
                            }}

                            activeFilters.push(selected);
                        }});

                        rows.forEach(row => {{
                            let showRow = true;
                            const cells = row.querySelectorAll('td');

                            activeFilters.forEach((selectedValues, index) => {{
                                if (selectedValues.length === 0) return; 
                                if (cells[index]) {{
                                    const cellValue = cells[index].textContent.trim();
                                    if (!selectedValues.includes(cellValue)) {{
                                        showRow = false;
                                    }}
                                }}
                            }});

                            if (showRow) {{
                                row.style.display = '';
                                visibleCount++;
                            }} else {{
                                row.style.display = 'none';
                            }}
                        }});

                        document.getElementById('visible-count').textContent = visibleCount;
                    }}
                }});
            </script>
        </body>
        </html>"""

    with open(output_file, "w", encoding=encoding) as f:
        f.write(html_template)

    return output_file
