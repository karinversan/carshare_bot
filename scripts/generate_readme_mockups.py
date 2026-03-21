from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "screenshots"
SAMPLE_DIR = ROOT / "sample-data"

FONT_REGULAR = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, size=size)


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def draw_card(base: Image.Image, box: tuple[int, int, int, int], fill: str, radius: int = 34, shadow: bool = True) -> None:
    x1, y1, x2, y2 = box
    if shadow:
        shadow_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow_layer)
        sd.rounded_rectangle((x1, y1 + 10, x2, y2 + 10), radius=radius, fill=(26, 44, 31, 38))
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(18))
        base.alpha_composite(shadow_layer)
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle(box, radius=radius, fill=fill)
    base.alpha_composite(layer)


def fit_image(path: Path, size: tuple[int, int], contain: bool = False) -> Image.Image:
    image = Image.open(path).convert("RGB")
    target_w, target_h = size
    src_w, src_h = image.size
    if contain:
        scale = min(target_w / src_w, target_h / src_h)
    else:
        scale = max(target_w / src_w, target_h / src_h)
    resized = image.resize((int(src_w * scale), int(src_h * scale)))
    canvas = Image.new("RGB", size, (240, 245, 241))
    offset = ((target_w - resized.size[0]) // 2, (target_h - resized.size[1]) // 2)
    canvas.paste(resized, offset)
    return canvas


def paste_rounded(base: Image.Image, image: Image.Image, xy: tuple[int, int], radius: int) -> None:
    x, y = xy
    tile = image.convert("RGBA")
    mask = rounded_mask(image.size, radius)
    tile.putalpha(mask)
    base.paste(tile, (x, y), tile)


def create_phone_screen() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    w, h = 900, 1800
    base = Image.new("RGBA", (w, h), "#EEF3EF")
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse((-180, -80, 520, 520), fill=(122, 231, 134, 120))
    od.rectangle((0, 0, w, 300), fill=(196, 245, 198, 120))
    overlay = overlay.filter(ImageFilter.GaussianBlur(20))
    base.alpha_composite(overlay)
    draw = ImageDraw.Draw(base)
    return base, draw


def create_desktop_screen() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    w, h = 1600, 1000
    base = Image.new("RGBA", (w, h), "#EFF4F2")
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse((-120, -90, 560, 520), fill=(184, 255, 44, 78))
    od.ellipse((1050, -180, 1740, 400), fill=(37, 99, 235, 42))
    overlay = overlay.filter(ImageFilter.GaussianBlur(24))
    base.alpha_composite(overlay)
    draw = ImageDraw.Draw(base)
    return base, draw


def create_prediction_screen() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    w, h = 1480, 940
    base = Image.new("RGBA", (w, h), "#EFF4F2")
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse((-120, -60, 520, 460), fill=(122, 231, 134, 92))
    od.ellipse((980, -180, 1620, 340), fill=(37, 99, 235, 48))
    od.ellipse((820, 520, 1560, 1120), fill=(255, 159, 10, 28))
    overlay = overlay.filter(ImageFilter.GaussianBlur(26))
    base.alpha_composite(overlay)
    return base, ImageDraw.Draw(base)


def label_pill(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, fill: str, color: str = "#10202E") -> None:
    draw.rounded_rectangle(box, radius=(box[3] - box[1]) // 2, fill=fill)
    draw.text((box[0] + 18, box[1] + 12), text, font=font(28, bold=True), fill=color)


def add_title(draw: ImageDraw.ImageDraw, title: str, subtitle: str) -> None:
    draw.text((58, 88), title, font=font(62, bold=True), fill="#152019")
    draw.text((58, 164), subtitle, font=font(30), fill="#708078")


def slot_thumb(base: Image.Image, slot_box: tuple[int, int, int, int], img_path: Path, title: str, status: str, status_fill: str) -> None:
    x1, y1, x2, y2 = slot_box
    draw_card(base, slot_box, "#FFFFFF", radius=30, shadow=False)
    img = fit_image(img_path, (x2 - x1 - 28, y2 - y1 - 110), contain=True)
    paste_rounded(base, img, (x1 + 14, y1 + 58), 22)
    draw = ImageDraw.Draw(base)
    draw.text((x1 + 16, y1 + 14), title, font=font(28, bold=True), fill="#152019")
    label_pill(draw, (x2 - 170, y1 + 12, x2 - 18, y1 + 58), status, status_fill, "#17351C")


def draw_overlay(base: Image.Image, image_box: tuple[int, int, int, int]) -> None:
    x1, y1, x2, y2 = image_box
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.polygon(
        [
            (x1 + 130, y1 + 300),
            (x1 + 220, y1 + 260),
            (x1 + 278, y1 + 332),
            (x1 + 196, y1 + 388),
        ],
        fill=(255, 159, 10, 90),
        outline=(255, 159, 10, 255),
    )
    draw.polygon(
        [
            (x1 + 430, y1 + 190),
            (x1 + 502, y1 + 172),
            (x1 + 548, y1 + 238),
            (x1 + 470, y1 + 274),
        ],
        fill=(255, 92, 89, 90),
        outline=(255, 92, 89, 255),
    )
    base.alpha_composite(layer)


def banner(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fill: str, text_fill: str = "#10202E") -> None:
    x, y = xy
    width = 26 + int(font(24, bold=True).getlength(text))
    draw.rounded_rectangle((x, y, x + width, y + 46), radius=23, fill=fill)
    draw.text((x + 14, y + 10), text, font=font(24, bold=True), fill=text_fill)


def prediction_layout(
    title: str,
    subtitle: str,
    image: Image.Image,
    status_text: str,
    status_fill: str,
    right_title: str,
    lines: list[tuple[str, str]],
    overlays: list[tuple[list[tuple[int, int]], str]] | None = None,
) -> Image.Image:
    base, draw = create_prediction_screen()
    draw_card(base, (36, 32, 1444, 132), "#FFFFFF", radius=30)
    draw.text((72, 58), title, font=font(38, bold=True), fill="#10202E")
    draw.text((72, 102), subtitle, font=font(22), fill="#6D7781")

    draw_card(base, (48, 164, 956, 892), "#FFFFFF", radius=34)
    paste_rounded(base, image.resize((850, 620)), (76, 228), 28)
    draw = ImageDraw.Draw(base)
    banner(draw, (76, 182), status_text, status_fill, "#10301A" if status_fill != "#1B2620" else "#FFFFFF")

    if overlays:
        layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        for poly, color in overlays:
            ld.polygon(poly, fill=tuple(int(color[i:i+2], 16) for i in (1, 3, 5)) + (78,), outline=color)
        base.alpha_composite(layer)

    draw_card(base, (992, 164, 1432, 892), "#FFFFFF", radius=34)
    draw.text((1028, 208), right_title, font=font(30, bold=True), fill="#10202E")
    top = 282
    for label, value in lines:
        draw.rounded_rectangle((1028, top, 1396, top + 88), radius=24, fill="#F8FBFC")
        draw.text((1052, top + 18), label, font=font(20, bold=True), fill="#6B7280")
        draw.text((1052, top + 46), value, font=font(26, bold=True), fill="#10202E")
        top += 104
    return base.convert("RGB")


def sample(path: str, blur: float = 0.0, brightness: float = 1.0) -> Image.Image:
    img = Image.open(SAMPLE_DIR / path).convert("RGB")
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    if brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(brightness)
    return img


def generate_bot_entry() -> None:
    base, draw = create_phone_screen()
    draw.rounded_rectangle((34, 34, 866, 1766), radius=62, outline="#D8E3DB", width=6)
    draw.rounded_rectangle((300, 56, 600, 92), radius=18, fill="#DCE8DE")
    draw_card(base, (48, 108, 852, 258), "#F7FBF8", radius=38)
    draw.text((78, 146), "Car Inspection Bot", font=font(40, bold=True), fill="#152019")
    draw.text((78, 198), "Маршрут, статус аренды и запуск осмотра", font=font(28), fill="#708078")

    draw_card(base, (68, 316, 832, 456), "#FFFFFF", radius=34)
    draw.text((96, 348), "Найти авто", font=font(30, bold=True), fill="#10202E")
    draw.text((96, 392), "Выберите машину для начала поездки", font=font(24), fill="#6D7781")

    for idx, title in enumerate([
        "Volkswagen Polo · 4 мин",
        "Kia Rio · 6 мин",
        "Skoda Rapid · 3 мин",
    ]):
        top = 492 + idx * 172
        draw_card(base, (68, top, 832, top + 144), "#FFFFFF", radius=34)
        draw.rounded_rectangle((92, top + 32, 176, top + 116), radius=24, fill="#C4F5C6")
        draw.text((206, top + 30), title, font=font(30, bold=True), fill="#152019")
        draw.text((206, top + 74), "Pickup: центр Москвы · Mini App осмотр перед стартом", font=font(22), fill="#708078")

    draw_card(base, (68, 1048, 832, 1320), "#1B2620", radius=40)
    draw.text((98, 1092), "Текущая поездка", font=font(28, bold=True), fill="#DDF9E4")
    draw.text((98, 1138), "Volkswagen Polo · awaiting_pickup_inspection", font=font(24), fill="#E7F1EA")
    label_pill(draw, (98, 1192, 294, 1246), "Открыть осмотр", "#57E36E", "#10301A")
    draw.text((98, 1268), "Телеграм-бот даёт вход в сценарий и держит контекст аренды.", font=font(24), fill="#B3C1B7")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base.convert("RGB").save(OUT_DIR / "bot-entry.png", quality=95)


def generate_capture_step() -> None:
    base, draw = create_phone_screen()
    add_title(draw, "Сделайте 4 фото", "Mini App направляет пользователя по обязательным ракурсам")

    draw_card(base, (50, 270, 850, 1080), "#FFFFFF", radius=42)
    draw.text((86, 316), "Следующий ракурс", font=font(30, bold=True), fill="#152019")
    label_pill(draw, (574, 304, 808, 360), "Front / Перед", "#EAF6EE")
    preview = fit_image(SAMPLE_DIR / "front_left_demo.jpg", (720, 560), contain=True)
    paste_rounded(base, preview, (90, 390), 34)
    draw.text((96, 976), "Система принимает фото, проверяет качество и соответствие ракурсу.", font=font(24), fill="#708078")

    draw_card(base, (50, 1116, 850, 1648), "#FFFFFF", radius=42)
    draw.text((86, 1156), "Прогресс осмотра", font=font(30, bold=True), fill="#152019")
    for idx, item in enumerate([("Перед", "Принято"), ("Левый бок", "Осталось"), ("Правый бок", "Осталось"), ("Зад", "Осталось")]):
        top = 1210 + idx * 96
        draw.rounded_rectangle((86, top, 814, top + 74), radius=24, fill="#F7FBF8")
        draw.text((114, top + 18), item[0], font=font(26, bold=True), fill="#152019")
        label_pill(draw, (620, top + 10, 790, top + 58), item[1], "#C4F5C6" if idx == 0 else "#EEF3EF")

    base.convert("RGB").save(OUT_DIR / "miniapp-capture.png", quality=95)


def generate_required_grid() -> None:
    base, draw = create_phone_screen()
    add_title(draw, "Набор фото готов", "Перед анализом можно переснять любой кадр и добавить close-up")

    draw_card(base, (50, 276, 850, 1350), "#FFFFFF", radius=42)
    slots = [
        ("Перед", SAMPLE_DIR / "front_left_demo.jpg"),
        ("Левый бок", SAMPLE_DIR / "rear_left_demo.jpg"),
        ("Правый бок", SAMPLE_DIR / "front_right_demo.jpg"),
        ("Зад", SAMPLE_DIR / "rear_right_demo.jpg"),
    ]
    positions = [
        (82, 340, 426, 816),
        (474, 340, 818, 816),
        (82, 846, 426, 1322),
        (474, 846, 818, 1322),
    ]
    for (title, path), box in zip(slots, positions):
        slot_thumb(base, box, path, title, "Принято", "#C4F5C6")

    draw_card(base, (50, 1390, 850, 1670), "#FFFFFF", radius=42)
    draw.text((86, 1434), "Перед запуском анализа", font=font(30, bold=True), fill="#152019")
    draw.text((86, 1482), "Пользователь подтверждает, что проверил все 4 обязательных ракурса.", font=font(24), fill="#708078")
    label_pill(draw, (86, 1540, 420, 1596), "Проверка подтверждена", "#1B2620", "#FFFFFF")
    label_pill(draw, (446, 1540, 812, 1596), "Запустить анализ", "#57E36E", "#10301A")

    base.convert("RGB").save(OUT_DIR / "miniapp-grid.png", quality=95)


def generate_review_screen() -> None:
    base, draw = create_phone_screen()
    add_title(draw, "Проверка повреждений", "После инференса пользователь подтверждает или отклоняет находки")

    draw_card(base, (50, 276, 850, 980), "#FFFFFF", radius=42)
    draw.text((86, 316), "Передний ракурс", font=font(30, bold=True), fill="#152019")
    label_pill(draw, (628, 304, 808, 360), "Готово", "#C4F5C6")
    preview = fit_image(SAMPLE_DIR / "front_left_demo.jpg", (720, 520), contain=True)
    paste_rounded(base, preview, (90, 392), 34)
    draw_overlay(base, (90, 392, 810, 912))

    draw_card(base, (50, 1014, 850, 1650), "#FFFFFF", radius=42)
    draw.text((86, 1056), "Найденные повреждения", font=font(30, bold=True), fill="#152019")
    items = [
        ("Царапина", "Автопринято · confidence 0.81", "#FF9F0A", "#EAF6EE"),
        ("Сломанная деталь", "Нужна проверка админа · confidence 0.58", "#FF5C59", "#FFF4ED"),
    ]
    for idx, (title, sub, chip, chip_bg) in enumerate(items):
        top = 1120 + idx * 214
        draw.rounded_rectangle((86, top, 814, top + 184), radius=30, fill="#F8FBFC")
        draw.ellipse((114, top + 28, 162, top + 76), fill=chip)
        draw.text((188, top + 22), title, font=font(28, bold=True), fill="#152019")
        draw.text((188, top + 68), sub, font=font(22), fill="#708078")
        label_pill(draw, (188, top + 114, 366, top + 164), "Подтвердить", "#C4F5C6")
        label_pill(draw, (392, top + 114, 562, top + 164), "Отклонить", "#F2F5F3")

    base.convert("RGB").save(OUT_DIR / "miniapp-review.png", quality=95)


def generate_closeups_screen() -> None:
    base, draw = create_phone_screen()
    add_title(draw, "Manual review и close-ups", "Можно добавить ручное повреждение и загрузить крупные планы")

    draw_card(base, (50, 276, 850, 980), "#FFFFFF", radius=42)
    draw.text((86, 316), "Левый бок", font=font(30, bold=True), fill="#152019")
    preview = fit_image(SAMPLE_DIR / "rear_left_demo.jpg", (720, 520), contain=True)
    paste_rounded(base, preview, (90, 392), 34)
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.ellipse((332, 628, 388, 684), fill=(37, 99, 235, 230))
    ld.ellipse((322, 618, 398, 694), outline=(255, 255, 255, 255), width=6)
    base.alpha_composite(layer)

    draw_card(base, (50, 1014, 850, 1650), "#FFFFFF", radius=42)
    draw.text((86, 1056), "Дополнительные фото", font=font(30, bold=True), fill="#152019")
    crops = [
        Image.open(SAMPLE_DIR / "rear_left_demo.jpg").convert("RGB").crop((240, 180, 520, 430)),
        Image.open(SAMPLE_DIR / "rear_left_demo.jpg").convert("RGB").crop((420, 210, 700, 470)),
        Image.open(SAMPLE_DIR / "rear_left_demo.jpg").convert("RGB").crop((180, 260, 460, 530)),
    ]
    positions = [(86, 1126), (356, 1126), (626, 1126)]
    for crop, (x, y) in zip(crops, positions):
        thumb = crop.resize((188, 188))
        paste_rounded(base, thumb, (x, y), 26)
    draw.text((86, 1348), "Ручное повреждение: Вмятина · severity medium", font=font(26, bold=True), fill="#152019")
    draw.text((86, 1396), "Ревьюер может уточнить тип, размер и прикрепить close-up к конкретной находке.", font=font(22), fill="#708078")
    label_pill(draw, (86, 1462, 370, 1518), "Сохранить manual damage", "#57E36E", "#10301A")

    base.convert("RGB").save(OUT_DIR / "miniapp-closeups.png", quality=95)


def generate_admin_queue() -> None:
    base, draw = create_desktop_screen()
    draw_card(base, (44, 38, 1556, 136), "#FFFFFF", radius=30)
    draw.text((84, 68), "Admin review panel", font=font(38, bold=True), fill="#10202E")
    draw.text((84, 112), "Queue of cases created after pre/post inspection comparison", font=font(22), fill="#6D7781")

    for idx, stat in enumerate([("12", "всего кейсов"), ("4", "на проверке"), ("3", "новых повреждения"), ("91%", "SLA до 1ч")]):
        left = 52 + idx * 376
        draw_card(base, (left, 176, left + 328, 314), "#FFFFFF", radius=30)
        draw.text((left + 28, 206), stat[0], font=font(44, bold=True), fill="#10202E")
        draw.text((left + 28, 258), stat[1], font=font(22), fill="#6D7781")

    draw_card(base, (52, 354, 676, 932), "#FFFFFF", radius=34)
    draw.text((82, 390), "Очередь кейсов", font=font(32, bold=True), fill="#10202E")
    cases = [
        ("Case #CI-014", "Volkswagen Polo · possible_new", "#F59E0B"),
        ("Case #CI-011", "Kia Rio · in_review", "#2563EB"),
        ("Case #CI-008", "Skoda Rapid · resolved_confirmed", "#21C45A"),
        ("Case #CI-005", "Volkswagen Polo · dismissed", "#EF4444"),
    ]
    for idx, (title, sub, color) in enumerate(cases):
        top = 448 + idx * 116
        draw.rounded_rectangle((82, top, 646, top + 92), radius=22, fill="#F8FBFC")
        draw.ellipse((106, top + 28, 138, top + 60), fill=color)
        draw.text((160, top + 18), title, font=font(26, bold=True), fill="#10202E")
        draw.text((160, top + 52), sub, font=font(20), fill="#6D7781")

    draw_card(base, (712, 354, 1548, 932), "#FFFFFF", radius=34)
    draw.text((742, 390), "Выбранный кейс", font=font(32, bold=True), fill="#10202E")
    draw.text((742, 436), "Перед поездкой / После поездки / Match summary", font=font(22), fill="#6D7781")
    left_img = fit_image(SAMPLE_DIR / "front_left_demo.jpg", (350, 248), contain=True)
    right_img = fit_image(SAMPLE_DIR / "front_right_demo.jpg", (350, 248), contain=True)
    paste_rounded(base, left_img, (742, 494), 24)
    paste_rounded(base, right_img, (1168, 494), 24)
    draw_overlay(base, (1168, 494, 1518, 742))
    draw.rounded_rectangle((742, 776, 1518, 884), radius=24, fill="#F8FBFC")
    draw.text((776, 804), "Новый скол на переднем бампере · match score 0.58 · requires admin review", font=font(24, bold=True), fill="#10202E")
    draw.text((776, 842), "Панель даёт быстрый обзор кейса и доступ к деталям сравнения.", font=font(20), fill="#6D7781")

    base.convert("RGB").save(OUT_DIR / "admin-queue.png", quality=95)


def generate_admin_case_detail() -> None:
    base, draw = create_desktop_screen()
    draw_card(base, (44, 38, 1556, 136), "#FFFFFF", radius=30)
    draw.text((84, 68), "Case detail: probable new damage", font=font(38, bold=True), fill="#10202E")
    draw.text((84, 112), "Evidence, close-ups, assignee and final resolution controls", font=font(22), fill="#6D7781")

    draw_card(base, (52, 176, 1548, 932), "#FFFFFF", radius=34)
    draw.text((88, 214), "Volkswagen Polo · Case #CI-014", font=font(34, bold=True), fill="#10202E")
    label_pill(draw, (1246, 202, 1494, 258), "На проверке", "#DDEBFF", "#1F4ED8")

    draw.text((88, 286), "Evidence", font=font(30, bold=True), fill="#10202E")
    img_before = fit_image(SAMPLE_DIR / "rear_left_demo.jpg", (430, 280), contain=True)
    img_after = fit_image(SAMPLE_DIR / "rear_right_demo.jpg", (430, 280), contain=True)
    paste_rounded(base, img_before, (88, 334), 26)
    paste_rounded(base, img_after, (548, 334), 26)
    draw_overlay(base, (548, 334, 978, 614))

    draw_card(base, (1018, 334, 1506, 614), "#F8FBFC", radius=28, shadow=False)
    draw.text((1050, 370), "Summary", font=font(28, bold=True), fill="#10202E")
    summary_lines = [
        "match score: 0.58",
        "pre-existing: нет",
        "post-trip finding: scratch",
        "severity hint: medium",
        "requires close-up review",
    ]
    for idx, line in enumerate(summary_lines):
        draw.text((1050, 430 + idx * 42), line, font=font(22), fill="#4B5563")

    draw.text((88, 660), "Close-ups", font=font(30, bold=True), fill="#10202E")
    crops = [
        Image.open(SAMPLE_DIR / "rear_right_demo.jpg").convert("RGB").crop((260, 200, 500, 420)),
        Image.open(SAMPLE_DIR / "rear_right_demo.jpg").convert("RGB").crop((440, 240, 700, 500)),
        Image.open(SAMPLE_DIR / "rear_right_demo.jpg").convert("RGB").crop((190, 300, 460, 560)),
    ]
    for idx, crop in enumerate(crops):
        thumb = crop.resize((244, 180))
        paste_rounded(base, thumb, (88 + idx * 270, 710), 22)

    draw_card(base, (940, 664, 1506, 902), "#F8FBFC", radius=28, shadow=False)
    draw.text((972, 700), "Resolution", font=font(28, bold=True), fill="#10202E")
    draw.text((972, 746), "Assignee: Karin", font=font(22), fill="#4B5563")
    draw.text((972, 786), "Комментарий: новое повреждение подтверждено", font=font(22), fill="#4B5563")
    label_pill(draw, (972, 832, 1166, 884), "Подтвердить", "#DDF9E4", "#14532D")
    label_pill(draw, (1188, 832, 1398, 884), "Без issue", "#EEF3EF", "#334155")

    base.convert("RGB").save(OUT_DIR / "admin-case-detail.png", quality=95)


def generate_prediction_accepted() -> None:
    img = sample("front_left_demo.jpg")
    base = prediction_layout(
        title="Prediction example: accepted capture",
        subtitle="Correct slot, acceptable quality, image goes to the next stage of the inspection flow",
        image=img,
        status_text="Accepted · quality=good · predicted_view=front_left_3q",
        status_fill="#C4F5C6",
        right_title="Validation output",
        lines=[
            ("expected_slot", "front"),
            ("predicted_view", "front_left_3q"),
            ("quality_label", "good"),
            ("quality_score", "0.94"),
            ("accepted", "true"),
        ],
    )
    base.save(OUT_DIR / "prediction-accepted.png", quality=95)


def generate_prediction_quality_reject() -> None:
    img = sample("front_left_demo.jpg", blur=7.5, brightness=0.82)
    base = prediction_layout(
        title="Prediction example: unsuitable photo",
        subtitle="The quality gate rejects the image before damage review because the frame is too blurry",
        image=img,
        status_text="Rejected · reason=too_blurry",
        status_fill="#FFD7D5",
        right_title="Quality gate output",
        lines=[
            ("expected_slot", "front"),
            ("predicted_view", "front_left_3q"),
            ("quality_label", "too_blurry"),
            ("blur_score", "18.4"),
            ("accepted", "false"),
        ],
    )
    base.save(OUT_DIR / "prediction-quality-reject.png", quality=95)


def generate_prediction_view_mismatch() -> None:
    img = sample("front_right_demo.jpg")
    base = prediction_layout(
        title="Prediction example: wrong viewpoint",
        subtitle="The image can be sharp enough, but still rejected if the expected slot does not match the predicted view",
        image=img,
        status_text="Rejected · reason=viewpoint_mismatch",
        status_fill="#FFF0D7",
        right_title="View validation output",
        lines=[
            ("expected_slot", "rear"),
            ("predicted_view", "front_right_3q"),
            ("view_threshold", "0.82"),
            ("quality_label", "good"),
            ("accepted", "false"),
        ],
    )
    base.save(OUT_DIR / "prediction-view-mismatch.png", quality=95)


def generate_prediction_segmentation() -> None:
    img = sample("rear_right_demo.jpg")
    resized = img.resize((850, 620))
    base = prediction_layout(
        title="Prediction example: damage segmentation",
        subtitle="The segmentation service returns polygons, boxes, confidence scores and damage classes",
        image=resized,
        status_text="Damage segmentation · 3 detections",
        status_fill="#DDEBFF",
        right_title="Detected classes",
        lines=[
            ("scratch", "confidence 0.81"),
            ("dent", "confidence 0.74"),
            ("crack", "confidence 0.63"),
            ("overlay_png_b64", "generated"),
            ("model_backend", "real / weights"),
        ],
        overlays=[
            ([(280, 470), (348, 430), (410, 502), (330, 548)], "#FF9F0A"),
            ([(520, 344), (592, 328), (644, 384), (566, 432)], "#FF5C59"),
            ([(648, 586), (736, 566), (768, 622), (682, 656)], "#4F7CFF"),
        ],
    )
    base.save(OUT_DIR / "prediction-segmentation.png", quality=95)


def generate_prediction_classification() -> None:
    base, draw = create_prediction_screen()
    draw_card(base, (36, 32, 1444, 132), "#FFFFFF", radius=30)
    draw.text((72, 58), "Prediction example: finding classification and review states", font=font(38, bold=True), fill="#10202E")
    draw.text((72, 102), "After inference, findings move through auto-confirmation, rejection or admin-review states", font=font(22), fill="#6D7781")
    draw_card(base, (48, 164, 1432, 892), "#FFFFFF", radius=34)
    cols = [
        ("Autoconfirmed", "#DDF9E4", "#14532D", [("scratch", "small", "0.84"), ("dent", "medium", "0.78")]),
        ("Needs admin review", "#FFF0D7", "#9A5800", [("crack", "medium", "0.58"), ("broken_part", "severe", "0.53")]),
        ("Rejected / filtered", "#F2F5F3", "#475569", [("scratch", "small", "0.29"), ("dent", "small", "0.33")]),
    ]
    for idx, (title, bg, fg, rows) in enumerate(cols):
        left = 84 + idx * 442
        draw.rounded_rectangle((left, 214, left + 394, 842), radius=30, fill="#F8FBFC")
        banner(draw, (left + 24, 238), title, bg, fg)
        top = 318
        for damage_type, severity, conf in rows:
            draw.rounded_rectangle((left + 24, top, left + 370, top + 122), radius=24, fill="#FFFFFF")
            draw.text((left + 46, top + 24), damage_type, font=font(28, bold=True), fill="#10202E")
            draw.text((left + 46, top + 64), f"severity={severity} · confidence={conf}", font=font(20), fill="#6D7781")
            top += 144
    base.convert("RGB").save(OUT_DIR / "prediction-classification.png", quality=95)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    generate_bot_entry()
    generate_capture_step()
    generate_required_grid()
    generate_review_screen()
    generate_closeups_screen()
    generate_admin_queue()
    generate_admin_case_detail()
    generate_prediction_accepted()
    generate_prediction_quality_reject()
    generate_prediction_view_mismatch()
    generate_prediction_segmentation()
    generate_prediction_classification()
    print(f"saved mockups to {OUT_DIR}")


if __name__ == "__main__":
    main()
