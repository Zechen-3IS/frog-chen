import requests
from datetime import datetime
from logger import get_logger

logger = get_logger(__name__)

WMO = {
    0: ("☀️", "晴"),
    1: ("🌤️", "多云"),
    2: ("⛅", "局部多云"),
    3: ("☁️", "阴"),
    45: ("🌫️", "雾"),
    48: ("🌫️", "冻雾"),
    51: ("🌦️", "毛毛雨"),
    53: ("🌦️", "毛毛雨"),
    55: ("🌧️", "毛毛雨"),
    56: ("🌧️", "冻毛毛雨"),
    57: ("🌧️", "冻毛毛雨"),
    61: ("🌧️", "小雨"),
    63: ("🌧️", "中雨"),
    65: ("🌧️", "大雨"),
    66: ("🌧️", "冻雨"),
    67: ("🌧️", "冻雨"),
    71: ("🌨️", "小雪"),
    73: ("🌨️", "中雪"),
    75: ("❄️", "大雪"),
    77: ("🌨️", "雪粒"),
    80: ("🌦️", "阵雨"),
    81: ("🌧️", "强阵雨"),
    82: ("⛈️", "暴雨"),
    85: ("🌨️", "阵雪"),
    86: ("❄️", "强阵雪"),
    95: ("⛈️", "雷雨"),
    96: ("⛈️", "雷雨冰雹"),
    99: ("⛈️", "雷雨冰雹"),
}

WEEKDAY = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


WIND_UNIT_LABEL = {"kmh": "km/h", "ms": "m/s", "mph": "mph", "kn": "kn"}


def build_weather_cards(latitude, longitude, hours=12, step=3, wind_speed_unit="kmh"):
    """
    获取指定坐标未来 `hours` 小时的逐小时天气，
    返回 .weather-scroll 内部的 HTML 字符串（若干 <div class='wx'> 卡片）。
    时间使用该地区的本地时区（timezone=auto）。

    参数:
        latitude, longitude : 场馆经纬度
        hours               : 预报覆盖的小时数 (默认 12)
        step                : 每隔几小时取一张卡片 (默认 3)
        wind_speed_unit     : km/h (默认), ms, mph, kn
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "temperature_2m,precipitation_probability,wind_speed_10m,weather_code",
        "current": "temperature_2m",  # 用于定位当前本地时间
        "timezone": "auto",
        "wind_speed_unit": wind_speed_unit,
    }

    try:
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        logger.exception("天气获取失败:", e)
        return '<div class="wx"><div class="wx-cond">天气数据暂不可用</div></div>'

    h = data["hourly"]
    times = h["time"]

    # Truncate current time to the hour — the API returns current[time] at
    # 15-minute granularity (interval=900s), which never matches hourly slots.
    raw = data["current"]["time"]  # e.g. "2026-06-07T21:45"
    current_hour = raw[:13] + ":00"  # → "2026-06-07T21:00"
    start = times.index(current_hour) if current_hour in times else 0

    # 自当前小时起，每隔 step 小时取一个，覆盖未来 hours 小时
    idxs = [
        i
        for i in range(start, min(start + hours, len(times)))
        if (i - start) % step == 0
    ]

    cards, last_day = [], None
    for n, i in enumerate(idxs):
        t = datetime.fromisoformat(times[i])
        emoji, cond = WMO.get(h["weather_code"][i], ("❓", "未知"))
        temp = h["temperature_2m"][i]
        rain = h["precipitation_probability"][i]
        wind = h["wind_speed_10m"][i]

        day_key = t.strftime("%Y%m%d")
        day_lbl = WEEKDAY[t.weekday()] if day_key != last_day else "&nbsp;"
        last_day = day_key

        now_cls = " now" if n == 0 else ""
        cards.append(f"""                        <div class="wx{now_cls}">
                            <div class="wx-day">{day_lbl}</div>
                            <div class="wx-time">{t.strftime('%H:%M')}</div>
                            <div class="wx-icon">{emoji}</div>
                            <div class="wx-temp">{int(temp)}°C</div>
                            <div class="wx-cond">{cond}</div>
                            <div class="wx-row"><span class="wx-rain">💧{rain}%</span></div>
                            <div class="wx-row">💨{wind:.1f}{WIND_UNIT_LABEL.get(wind_speed_unit, wind_speed_unit)}</div>
                        </div>""")

    return "\n".join(cards)


# Example usage
if __name__ == "__main__":
    # forecast = get_hourly_weather(51.4868794, -0.2122196, hours=24)  # London coords
    forecast = build_weather_cards(
        51.7123943, 5.4156334, hours=24, step=1
    )  # 's-Hertogenbosch coords
    with open("weather_example.html", "w", encoding="utf-8") as f:
        f.write(forecast)
