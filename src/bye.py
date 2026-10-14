import re
import requests
from bs4 import BeautifulSoup


def compute_draw_byes(soup: BeautifulSoup, draw_id: str) -> dict:
    draw_id = draw_id.upper()

    if draw_id not in {"MS", "WS"}:
        raise ValueError("draw_id must be 'MS' or 'WS'")
    draw_parts = soup.select(f'.cDrawPart[data-id="{draw_id}"]')
    if not draw_parts:
        print("No draw section found")
        return 0.0
    grid_selector = "td.cDrawSeq.cDrawGridEven, " "td.cDrawSeq.cDrawGridOdd"

    def get_grid_numbers(draw_part):
        grid_numbers = []

        for cell in draw_part.select(grid_selector):
            text = cell.get_text(strip=True)

            if re.fullmatch(r"\d+", text):
                grid_numbers.append(int(text))

        return grid_numbers

    # Some pages can contain multiple versions/views of the same draw.
    # Use the section with the highest grid position as the full draw.
    draw_part, grid_numbers = max(
        ((part, get_grid_numbers(part)) for part in draw_parts),
        key=lambda item: max(item[1], default=0),
    )

    if not grid_numbers:
        raise ValueError(f"No grid sequence numbers found for draw_id={draw_id!r}")

    draw_size = max(grid_numbers)

    byes = len(draw_part.select('pname[alt="Bye"][data-id="0"]'))

    return {
        "draw_id": draw_id,
        "draw_size": draw_size,
        "byes": byes,
        "bye_rate": byes / draw_size if draw_size else 0.0,
    }


def get_draw_info(event_id, year, tour):
    url = f"https://www.live-tennis.cn/zh/draw/ajax/{event_id}/{year}/device/0/horizontal/true"
    session = requests.session()
    try:
        html = session.get(
            url,
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"https://www.live-tennis.cn/zh/draw/{event_id}/{year}",
            },
            timeout=90,
        ).text
    except Exception as e:
        print(f"Failed to parse draw data: {e}")
        return {}

    soup = BeautifulSoup(html, "html.parser")
    return compute_draw_byes(soup, tour)


# Usage
if __name__ == "__main__":
    get_draw_info("31020", 2026, "ms")
