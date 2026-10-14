"""Reusable homepage HTML fragments."""
from __future__ import annotations

_INDEX_COMBINED_SECTION = """\
    <div class="section">
        <div class="sec-hd"><span class="sec-label">联合排名</span><div class="sec-rule"></div></div>
        <div class="card-grid">
            <a href="combined_instant_ranking.html" class="card all">
                <div class="card-eye"><b>ALL · Combined Live</b></div>
                <div class="card-title">联合即时排名</div>
                <div class="card-desc">ATP + WTA 即时积分合计榜</div>
                <span class="card-arrow">→</span>
            </a>
            <a href="combined_ranking.html" class="card all">
                <div class="card-eye"><b>ALL · Combined Race</b></div>
                <div class="card-title">联合冠军排名</div>
                <div class="card-desc">ATP + WTA 冠军积分合计榜</div>
                <span class="card-arrow">→</span>
            </a>
        </div>
    </div>
"""

_INDEX_PLAYER_STATS_SECTION = """\
    <div class="section">
        <div class="sec-hd"><span class="sec-label">球员生涯统计</span><div class="sec-rule"></div></div>
        <div class="card-grid">
            <a href="atp_show.html" class="card atp">
                <div class="card-eye"><b>ATP · Career Stats</b></div>
                <div class="card-title">ATP 生涯统计</div>
                <div class="card-desc">周期参赛、夺冠夺亚、连胜连败与存活率</div>
                <span class="card-arrow">→</span>
            </a>
            <a href="wta_show.html" class="card wta">
                <div class="card-eye"><b>WTA · Career Stats</b></div>
                <div class="card-title">WTA 生涯统计</div>
                <div class="card-desc">周期参赛、夺冠夺亚、连胜连败与存活率</div>
                <span class="card-arrow">→</span>
            </a>
        </div>
    </div>
"""

_INDEX_CALENDAR_SECTION = """\
    <div class="section">
        <div class="sec-hd"><span class="sec-label">幸存者赛历</span><div class="sec-rule"></div></div>
        <div class="card-grid">
            <a href="survivor_calendar_atp.html" class="card atp">
                <div class="card-eye"><b>ATP · Season Calendar</b></div>
                <div class="card-title">ATP幸存者赛历</div>
                <div class="card-desc">男单赛程 · 按年份与级别浏览本站得分</div>
                <span class="card-arrow">→</span>
            </a>
            <a href="survivor_calendar_wta.html" class="card wta">
                <div class="card-eye"><b>WTA · Season Calendar</b></div>
                <div class="card-title">WTA幸存者赛历</div>
                <div class="card-desc">女单赛程 · 按年份与级别浏览本站得分</div>
                <span class="card-arrow">→</span>
            </a>
        </div>
    </div>
"""
