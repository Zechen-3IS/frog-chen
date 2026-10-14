# frog_chen_web × chen_web 功能并集方案

> 目标：以 **frog_chen_web** 的 UI 与代码结构为底座，把 **chen_web**（survivor_champion_ranking）的差异功能迁入。  
> 原则：抽逻辑、不搬模板；新能力进独立模块；页面走现有 `site_html` 渲染管线。

**对照仓库**

| 项目 | 路径 | 角色 |
|------|------|------|
| frog_chen_web | 本仓库 | 底座（保留） |
| chen_web | `/Users/yinzechen/程序/chen_web` | 功能来源 |

---

## 1. 现状（已具备，不重做）

- ATP / WTA 即时排名、冠军积分（race）排名
- 选人明细、今日状态、排名升降、夺冠路线查询
- 赛季 / 历年杀手榜页
- 冠军殿堂页（筛选 + 生涯夺冠明细）
- H2H 对战查询与用户汇总
- 赛地天气、硬地 / 红土 / 草地主题、暗色模式
- `config.yaml`、赛事自动发现、`bye_rate` 抓取
- HTML 生成层已拆为 `site_html/`（便于后续加页）

---

## 2. 待加功能总表

| ID | 功能 | 优先级 | 主要来源（chen_web） | 建议落点（frog） |
|----|------|--------|---------------------|------------------|
| F1 | 签表实时结算 | P0 | `survivor/process.py` 结算链路、`fetch.py` 签表 | 新模块 `live_settlement.py` → 接入 `build_table` / `live_ranking` |
| F2 | 首页上/本/下周赛况卡 | P0 | `survivor/home.py` | `site_html/index.py` + 数据组装模块 |
| F3 | ATP+WTA 合排名（即时 / 冠军） | P1 | `process.build_combined` | 新模块 + `site_html/combined.py` |
| F4 | 球员生涯统计页 | P1 | `survivor/stats.py` + `data/player_events.json` | 新模块 `player_stats.py` + `site_html/show.py` |
| F5 | 死亡种子统计 | P2 | `process.seed_death_stats` | 排名页侧栏 / 折叠面板 |
| F6 | 今日选人结果着色汇总 | P2 | `process.choice_summary` | 排名页 summary 增强 |
| F7 | 本站当日杀手统计 | P2 | `process.killer_stats` | 排名页面板（与历年杀手榜互补） |
| F8 | CI 半小时自动刷新 | P3 | `.github/workflows` | 可选迁入 Actions |
| F9 | 历史新闻页 | P3 | `history_news.html` | **默认不做**（已脱链、静态存档） |
| F10 | 幸存者赛历 + 各站得分 | P1 | live-tennis calendar/score | `event_calendar.py` + `site_html/calendar.py` |

---

## 3. 功能说明与验收

### F1 · 签表实时结算（P0）✅ 已实现

**要解决什么**  
官方 survivor score 更新滞后时，仍能根据签表比分提前判定：胜 / 负 / 首日轮空 / 自杀 / 待定（pending），并回写本站得分与杀手球员。

**实现落点**

| 文件 | 职责 |
|------|------|
| `src/draw_status.py` | 签表解析、`DrawStatus`、抓取 draw AJAX + my 页（day_points / 轮空配额 / pick_days） |
| `src/live_settlement.py` | `settle_tour_scores` / `apply_live_settlement` / `current_play_day` |
| `src/main.py` → `build_tour_tables` | 抓表后结算，用 `play_day` 建榜；Day1 轮空写回「今日状态」 |
| `src/build_table.py` | `use_settled_score=True` 时 Day1 也走 score 路径 |
| `config.yaml` → `settlement.enabled` | 开关，默认 `true` |

**行为要点**

- 无官方 score 时从 submission 合成初始分表再结算
- 官方已跟上的用户不会被重复推进（只处理 `fill_status==存活` 且 day 之后的选人）
- 关闭：`settlement.enabled: false`

**验收（已做）**

- 单元：模拟淘汰 / 晋级 / 进行中 / 首日轮空
- 联调：ATP 上海 Day7（待定选人）、WTA 武汉（官方已同步时 counts 为 0）
- `build_tour_tables` 端到端生成排名表成功

---

### F2 · 首页周赛况卡（P0）✅ 已实现

**要解决什么**  
首页除天气与导航外，展示：

- 上周赛事结果（冠军或最高分）
- 本周赛事（参赛 / 幸存、卫冕情况；可链到 live-tennis）
- 下周赛事预告

**实现落点**

| 文件 | 职责 |
|------|------|
| `src/home_weeks.py` | 日历周解析、未完赛周延续、`build_replace_map` 赛事对应、卫冕查询 |
| `src/site_html/index.py` | 赛况日历 UI（跟现有主题，不搬 chen CSS） |
| `config.yaml` → `home.week_cards` | 开关；`last_calendar_path` 指向去年日历 |

**行为要点**

- ATP / WTA 各自解析上/本/下周（可错开周一）
- 卫冕 /「对应去年」走 slam+1000 锚点映射，**不是**简单同名或 −52 周
- 本周参赛 / 幸存复用 F1 结算后的 `get_meta_stats`

**验收**

- 无赛事周、单巡有赛、双巡同城 / 异地都能正常显示
- 本周幸存数与 F1 结算结果一致（有结算时）
- 例：2026 武汉 ↔ 2025 武汉（宁波为下一周，不对齐）

---

### F3 · 合排名（P1）

**页面**

- 合排名 · 冠军积分（对应 chen `combined_ranking.html`）
- 合排名 · 即时（对应 chen `combined_instant_ranking.html`）

**逻辑**

- 复用单巡计算结果做 ATP+WTA 合并（`build_combined`）
- 积分规则以 frog `points_calculation.py` 为准，用 chen 用例对照

**UI**

- 新渲染模块 `site_html/combined.py`（或复用 `ranking.py`）
- 首页导航增加入口

**文件名（已定）**

- 兼容 chen 旧链：`combined_instant_ranking.html` / `combined_ranking.html`

**验收**

- 合排名总分 = ATP即时积分 + WTA即时积分（outer merge on `user_id`）
- 筛选、暗色、主题与现有排名页一致；无选人明细弹层

---

### F4 · 球员生涯统计（P1）

**页面**

- `atp_show.html` / `wta_show.html`（或 frog 命名风格等价物）

**指标（对齐 chen）**

- 周期参赛数 / 周期冠军数
- 历史冠军数、夺冠明细、历史亚军数、夺亚明细
- 历史最佳排名、最长连胜 / 连败（含细节）
- 世界第一周数、历史最高得分
- 赛季存活率、历史存活率

**数据**

- 增量缓存：`data/player_events.json`（从 chen 迁增量抓取逻辑）
- 更新节奏建议单独节流：CLI `--stats` 或配置小时 / 每周（勿每次全量拖慢主流程）

**验收**

- 缓存增量更新不重复写已完成赛事
- 表格可搜可筛，主题与全站一致

---

### F5 · 死亡种子统计（P2）

- 基于上周排名 top N（chen 默认 16）统计种子日死亡情况
- 挂在即时排名页（折叠面板），不单独占导航

---

### F6 · 今日选人结果着色汇总（P2）✅ 已实现（等价）

- 胜 / 负 / 待定 ≡ 确认存活 / 淘汰 / 未完赛
- 已并入排名页 summary bar 球员着色，不另开一套摘要

---

### F7 · 本站每日杀手统计（P2）✅ 已实现

- 按存活天数聚合本周「球员输球」杀手 Top2（`day_killers.daily_killer_stats`）
- 排名页折叠面板「显示每日杀手统计」；与赛季 / 历年杀手榜页互补

---

### F8 · CI 自动刷新（P3）✅ 已实现

- `python main.py --live` / `--daily`；Actions：`update-live.yml`（15 分钟）、`update-daily.yml`（每日 23:00 北京）
- 生成器仓库跑 job，经 `PUBLISH_TOKEN` 推 HTML 到 Pages 仓库 `frog-chen`

---

### F9 · history_news（默认不做）

- 静态社区新闻存档，chen 首页已不链
- 除非有明确内容维护计划，否则不迁入

---

## 4. 重叠能力：对齐逻辑，不照搬 UI

| 主题 | frog 现状 | chen 现状 | 并集策略 |
|------|-----------|-----------|----------|
| best-18 积分 | `points_calculation.py` | `TourRules` + keep-best | 以 frog 为准，对照测 |
| 轮空 / 自杀 | 提交态 + bye_rate | 签表结算链路 | F1 后统一状态字段 |
| 杀手 | H2H 历史榜页 | 本周当日面板 | 保留榜页 + 加 F7 |
| 首页 | 天气 + 导航卡 | 周赛况卡 | 保留现 UI，加 F2 一节 |

---

## 5. 推荐落地顺序

```
Phase 1  F1 实时结算
    ↓
Phase 2  F2 首页周赛况（可与 F1 后半并行 UI）
    ↓
Phase 3  F3 合排名
    ↓
Phase 4  F4 生涯统计 + player_events 缓存
    ↓
Phase 5  F5–F7 排名页增强
    ↓
Phase 6  F8 CI（可选）
```

**依赖关系**

- F2 本周幸存数、F6/F7 展示质量 → 依赖 F1
- F3 → 依赖稳定的单巡即时 / race 表（F1 完成后更可靠）
- F4 → 独立数据管线，可与 F3 并行，但不要和 F1 抢同一大波改动面

---

## 6. 实现约定

1. **新逻辑独立成模块**，不要继续堆进 `main.py` / 单一大文件。  
2. **新页面进 `site_html/`**，共享 `common` / `css` / `js` / `state.apply_theme`。  
3. **主题切换**使用 `apply_theme(name)`，不要再赋值 `_CSS_VARS`。  
4. **不整包复制** chen 的 `survivor/` 包；只抽函数与数据结构。  
5. **配置**：结算开关、stats 更新小时等进 `config.yaml`，默认安全（可关）。

**建议配置草案（实现时再落）**

```yaml
settlement:
  enabled: true          # F1

home:
  week_cards: true       # F2

stats:
  enabled: true          # F4
  cache_path: "../data/player_events.json"
  update_hour: 3         # 或改用 CLI --stats / 周更

combined:
  enabled: true          # F3
```

---

## 7. 待拍板事项

1. **合排名 / 生涯页文件名**：兼容 chen 旧链，还是统一 frog 命名？  
2. **生涯统计更新节奏**：跟主流程、独立 `--stats`，还是每周 CI？  
3. **合排名是否每次跑主流程都生成**？（建议：是，成本低）  
4. **F8 CI**：是否本仓库也要 GitHub Actions，还是继续本地 / cron？

---

## 8. 非目标（本轮不做）

- 用 chen 的 UI 替换 frog 视觉
- 双栈并行维护两套抓取 / 两套 HTML 模板
- 全面重写积分引擎或 H2H 体系
- 迁入 `history_news.html`（除非另开需求）

---

## 9. 进度勾选

- [x] HTML 轻重构（`site_html/`）
- [x] F1 签表实时结算
- [x] F2 首页周赛况卡
- [x] F3 合排名
- [x] F4 球员生涯统计
- [ ] F5 死亡种子统计（暂不做）
- [x] F6 今日选人着色汇总（summary 存活/淘汰/未完赛）
- [x] F7 本站每日杀手
- [ ] F8 CI（可选，暂不做）
- [ ] F9 history_news（默认跳过）
