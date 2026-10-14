# 签表幸存者

ATP / WTA 签表幸存者游戏的数据处理与静态网页生成工具。参与者每天选一场比赛的胜者——选对存活得分，选错淘汰。系统从 [live-tennis.cn](https://www.live-tennis.cn) 抓取数据，按官方规则计算积分，生成页面发布至 GitHub Pages。

---

## 功能一览

| 页面 / 能力 | 说明 |
|-------------|------|
| 首页 | 导航、赛况日历（上/本周）、赛地天气、暗色 / 场地主题 |
| 即时 / 冠军积分排名 | ATP、WTA 单巡；含选人明细、今日状态、排名升降 |
| 联合排名 | ATP+WTA 即时 / 冠军积分合计；支持积分构成图 |
| 幸存者赛历 | 分 ATP / WTA；按年份、级别筛选；点进各站得分页 |
| 各站得分页 | 冠军、单日/累计克星、最大爆冷；本站得分与选人明细 |
| 生涯统计 | 周期参赛、夺冠夺亚、连胜连败、存活率等 |
| 杀手榜 | 赛季 / 历年 |
| H2H | 用户对战与汇总 |
| 实时结算 | 签表比分提前判定胜负；**第一盘内退赛 / W/O 可启用备选** |

> 冠军殿堂页（`atp_champion.html` / `wta_champion.html`）仍可生成，首页已不再入口；本站冠军见赛历得分页，生涯夺冠见生涯统计。

---

## 项目结构

```
frog_chen_web/
├── index.html
├── atp_ranking.html / wta_ranking.html
├── atp_race_ranking.html / wta_race_ranking.html
├── combined_instant_ranking.html / combined_ranking.html
├── survivor_calendar.html              # 赛历入口（选巡）
├── survivor_calendar_atp.html / _wta.html
├── events/{year}/{MS|WS}_{event_id}.html   # 各站得分
├── atp_show.html / wta_show.html       # 生涯统计
├── atpkiller.html / wtakiller.html / 2026*killer.html
├── h2h_atp.html / h2h_wta.html
│
├── data/                               # 运行时缓存（通常不提交）
│   ├── champions.csv
│   ├── h2h_records.csv
│   ├── calendar_*.json
│   ├── event_scores/                   # 各站得分缓存
│   ├── event_draws/                    # 签表对阵缓存（克星/爆冷）
│   ├── event_day_rounds/               # 选人日→轮次标签
│   ├── breakdown_*.json / *.js         # 积分构成
│   └── player_events.json              # 生涯统计缓存
│
├── src/
│   ├── main.py                         # 入口
│   ├── parser.py                       # 抓取
│   ├── build_table.py / live_ranking.py
│   ├── points_calculation.py           # 最佳 18 站
│   ├── live_settlement.py / draw_status.py   # 签表实时结算
│   ├── event_calendar.py               # 赛历 + 各站得分 + 统计条
│   ├── user_breakdown.py               # 积分构成数据
│   ├── combined_ranking.py
│   ├── home_weeks.py                   # 首页周赛况
│   ├── player_stats.py / champion_stats.py / h2h.py
│   ├── site_html/                      # HTML 渲染
│   └── …
│
├── config.yaml
├── docs/feature-merge-plan.md          # 与 chen_web 功能并集说明
├── requirements.txt
└── README.md
```

---

## 快速开始

```bash
pip install -r requirements.txt
cd src
python main.py
```

默认流程：更新赛事配置 → 抓取排名/提交/得分 → **签表实时结算** → 生成首页与排名页等。

### 常用子命令

```bash
# 幸存者赛历 + 各站得分（增量抓缓存）
python main.py --calendar
python main.py --calendar-cache-only          # 只用本地缓存重生
python main.py --calendar --calendar-year 2025

# 球员生涯统计
python main.py --stats
python main.py --stats-cache-only

# CI 模式
python main.py --live    # 选人相关：首页 / 排名 / 联合榜 / 当年赛历得分
python main.py --daily   # 每日：上述 + H2H / 杀手 / 生涯统计 / 全部赛历
```

---

## GitHub Actions 自动更新

生成器仓库：[Zechen-3IS/frog-chen](https://github.com/Zechen-3IS/frog-chen)。Actions 在默认分支跑，生成的 HTML 推到同仓库的 **`pages`** 分支（测试用；之后可用 Variables 改回 `silly-hp/tennis-survivor-webpage` / `frog-chen`）。

| Workflow | 频率 | 内容 |
|----------|------|------|
| `update-live.yml` | 每 15 分钟 | `--live` 选人相关页 |
| `update-daily.yml` | 每天 23:00（北京时间） | `--daily` 其余页 |

赛历得分/签表为**增量**：完赛赛事读 `data/event_scores`（及 draws）缓存不再抓；进行中赛事与刚完赛一站会刷新。CI 会从 `pages` 分支与 Actions cache 恢复这些缓存。

**测试仓库启用：**

1. 代码在 `main`；首次可在 Actions 里手动跑 `Update live`
2. 同仓库发布用自带 `GITHUB_TOKEN` 即可；若改推到别的仓库，再加 Secret `PUBLISH_TOKEN`
3. 可选 Variables：`PUBLISH_REPOSITORY`、`PUBLISH_BRANCH`
4. 预览：仓库 Settings → Pages → Source 选 `pages` 分支，或打开  
   `https://zechen-3is.github.io/frog-chen/`（启用 Pages 后）

---

## 配置（`config.yaml`）

```yaml
year: 2026
theme: hard          # hard / clay / grass
output_dir: ".."

atp:
  event: "25014"     # null = 本周无赛事
  name: "上海"
  bye_rate: 0.25
  week_start_date: "2026-10-05"

wta:
  event: "31075"
  name: "武汉"
  bye_rate: 0.125
  week_start_date: "2026-10-12"

settlement:
  enabled: true      # 签表实时结算开关

h2h:
  csv_path: "../data/h2h_records.csv"
  update_hour: 23
```

赛事 ID / 名称等可由 `write_config.py` 按日历自动发现更新。

---

## 核心逻辑摘要

### 积分（`points_calculation.py`）

WTA / ATP 均为**最佳 18 站**（大满贯与强制 1000 等槽位规则见源码）。年终总决赛为额外奖励，不占 18 站。

### 实时排名（`live_ranking.py`）

去掉去年同站积分 → 加上本站当前得分 → 重算总分排名。本站得分可经实时结算提前更新。

### 实时结算（`live_settlement.py` + `draw_status.py`）

对照签表判定当日选人：胜 / 负 / 待定 / 自杀 / 首日轮空。

**退赛与备选：**

- 从签表比分识别 `Ret.` / `W/O` 及盘分（如 `52`、`64 Ret.`）
- **第一盘未结束**即退赛（或 W/O）→ 可启用备选，按备选继续结算
- 第一盘已结束再退 → 主选算输，不启用备选

### 赛历统计条（`event_calendar.py`）

各站得分页上方：

| 指标 | 含义 |
|------|------|
| 冠军 | 得分 = 本站理论满分（大满贯 2000 等）；可无人夺冠 |
| 单日克星 | 单场「赢球并送走选了对手的人」最多 |
| 累计克星 | 各轮送走人数合计最多 |
| 最大爆冷 | 同场两边都有人选，且选得少的一方赢了；主文展示选爆冷的用户，小字为比赛与选人比 |

克星 / 爆冷依赖 `data/event_draws/` 签表对阵缓存（`--calendar` 时同步）。

---

## 数据来源

[live-tennis.cn](https://www.live-tennis.cn)：

- 排名 / 冠军积分 / 提交明细 / 本站得分
- 赛历、签表（含比分与退赛标记）

---

## 相关文档

- [`docs/feature-merge-plan.md`](docs/feature-merge-plan.md) — 与 chen_web 功能对照与实现落点
