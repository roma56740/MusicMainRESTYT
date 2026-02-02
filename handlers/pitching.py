from __future__ import annotations

import os
import re
from math import ceil
from typing import List, Tuple, Optional

from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    BufferedInputFile,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from db import (
    add_pitching_request,
    set_pitching_request_pdf_path,
    set_pitching_request_status,
    count_user_pitching_requests,
    list_user_pitching_requests,
    count_all_pitching_requests,
    list_all_pitching_requests,
    get_pitching_request,
    delete_pitching_request,
)

router = Router()

BTN_USER_ENTRY = "🚀 Релиз на питчинг"
BTN_ADMIN_ENTRY = "📮 Релизы на питчинг"   # можно добавить админам в меню, хэндлер уже есть

PAGE_SIZE = 5
PDF_DIR = os.getenv("PITCH_PDF_DIR", "pitching_pdfs")

YANDEX_DISK_RE = re.compile(r"^https?://(yadi\.sk|disk\.yandex\.[a-z]+|disk\.yandex\.ru)/", re.I)


PITCH_FORM_STEPS = [
"""• название релиза и псевдоним артиста""",
"""• Описание релиза и артиста
Оптимальный объем 4-6 предложения. Постарайтесь указать наиболее интересные и важные факты из
карьеры артиста или процесса создания релиза.""",
"""• Ссылка на фотографии
Укажите ссылку на облако, убедитесь что доступ для просмотра предоставлен и не загружайте
изображения на которые у вас нет прав.
ВАЖНО: отправляйте только те фотографии, которые готовы увидеть на обложках плейлистов,
баннерах.""",
"""• Ссылка на прослушивание
Укажите ссылку на облако, убедитесь что доступ для просмотра предоставлен.
ВАЖНО: по ссылке должно быть доступно прослушивание трека, а не скачивание файла или архива.
Желательно использовать MP3, не WAV: FLAC и др.""",
"""• Ссылка на предпросмотр клипа (если есть)
Укажите ссылку на облако, убедитесь что доступ для просмотра предоставлен.""",
"""• Ссылки на соцсети артиста
Укажите ссылки через запятую. Это поможет музыкальным редакторам составить более полное
впечатление об артисте, согласовать совместные маркетинговые активности и начать следить за
артистом.""",
"""• Дополнительная информация
Качество и полнота предоставляемой информации напрямую влияет на интерес редакторов к вашему
релизу и возможность нашей команды маркетинга согласовать дополнительную поддержку.
Постарайтесь указать информацию о росте артиста, планах на ближайшее время, предоставить
качественный визуал и рабочие ссылки."""
]

FIELDS = [
    "release_artist",
    "description",
    "photos_link",
    "listen_link",
    "clip_link",
    "socials",
    "extra",
]


class PitchForm(StatesGroup):
    step1 = State()
    step2 = State()
    step3 = State()
    step4 = State()
    step5 = State()
    step6 = State()
    step7 = State()
    preview = State()


def _admin_ids() -> List[int]:
    # поддержка обоих вариантов:
    # ADMIN_ID=5255...
    # ADMIN_IDS=1,2,3
    raw = (os.getenv("ADMIN_IDS") or "").strip()
    if not raw:
        raw = (os.getenv("ADMIN_ID") or "").strip()

    if not raw:
        return []

    out: List[int] = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            out.append(int(part))
    return out



def _is_admin(user_id: int) -> bool:
    return user_id in set(_admin_ids())


def _is_yandex_disk_link(s: str) -> bool:
    s = (s or "").strip()
    return bool(YANDEX_DISK_RE.match(s))


def _menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Новая заявка", callback_data="pitch:new")],
        [InlineKeyboardButton(text="📋 Мои заявки", callback_data="pitch:my:0")],
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="pitch:main")],
    ])


def _cancel_kb(show_back: bool) -> InlineKeyboardMarkup:
    row = []
    if show_back:
        row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data="pitch:back"))
    row.append(InlineKeyboardButton(text="✖️ Отмена", callback_data="pitch:cancel"))
    return InlineKeyboardMarkup(inline_keyboard=[row])


def _preview_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Отправить", callback_data="pitch:send"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data="pitch:back"),
        ],
        [InlineKeyboardButton(text="✖️ Отмена", callback_data="pitch:cancel")],
    ])


def _paginate(total: int, page: int, page_size: int) -> Tuple[int, int, int]:
    pages = max(1, ceil(total / page_size)) if total >= 0 else 1
    page = max(0, min(page, pages - 1))
    offset = page * page_size
    return pages, page, offset


def _my_list_kb(page: int, pages: int, items: List[dict]) -> InlineKeyboardMarkup:
    kb: List[List[InlineKeyboardButton]] = []
    for it in items:
        rid = it["id"]
        kb.append([
            InlineKeyboardButton(text=f"Открыть #{rid}", callback_data=f"pitch:open:{rid}"),
            InlineKeyboardButton(text=f"Удалить #{rid}", callback_data=f"pitch:delask:{rid}"),
        ])

    nav: List[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"pitch:my:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{pages}", callback_data="pitch:noop"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"pitch:my:{page+1}"))
    kb.append(nav)

    kb.append([
        InlineKeyboardButton(text="📝 Новая заявка", callback_data="pitch:new"),
        InlineKeyboardButton(text="⬅️ Назад", callback_data="pitch:menu"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def _admin_list_kb(page: int, pages: int, items: List[dict]) -> InlineKeyboardMarkup:
    kb: List[List[InlineKeyboardButton]] = []
    for it in items:
        rid = it["id"]
        kb.append([
            InlineKeyboardButton(text=f"Открыть #{rid}", callback_data=f"pitch_admin:open:{rid}"),
            InlineKeyboardButton(text=f"Удалить #{rid}", callback_data=f"pitch_admin:delask:{rid}"),
        ])

    nav: List[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"pitch_admin:list:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{pages}", callback_data="pitch:noop"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"pitch_admin:list:{page+1}"))
    kb.append(nav)

    kb.append([InlineKeyboardButton(text="⬅️ Главное меню", callback_data="pitch:main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def _req_text(req: dict) -> str:
    def v(key: str) -> str:
        val = req.get(key)
        if val is None:
            return ""
        # в БД telegram_id/int, чтобы не падало
        if not isinstance(val, str):
            val = str(val)
        return val.strip()

    head = f"<b>Заявка #{req['id']}</b>\n"
    head += f"Дата: <code>{v('created_at')}</code>\n"
    head += f"Пользователь: <code>{v('telegram_id')}</code>"
    if v("username"):
        head += f" @{v('username')}"
    head += "\n"
    head += f"Статус: <code>{v('status')}</code>\n\n"

    parts = [
        ("• название релиза и псевдоним артиста", v("release_artist")),
        ("• Описание релиза и артиста", v("description")),
        ("• Ссылка на фотографии", v("photos_link")),
        ("• Ссылка на прослушивание", v("listen_link")),
        ("• Ссылка на предпросмотр клипа (если есть)", v("clip_link")),
        ("• Ссылки на соцсети артиста", v("socials")),
        ("• Дополнительная информация", v("extra")),
    ]

    body = ""
    for label, val in parts:
        body += f"<b>{label}</b>\n{val}\n\n"
    return head + body


def _try_build_pdf_bytes(req: dict) -> bytes:
    try:
        from io import BytesIO
        from xml.sax.saxutils import escape as xml_escape

        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        # ---- найти TimesNewRoman.ttf ----
        base_dir = os.path.dirname(os.path.abspath(__file__))          # .../handlers
        project_dir = os.path.normpath(os.path.join(base_dir, ".."))   # корень проекта

        candidates = [
            os.path.join(project_dir, "fonts", "TimesNewRoman.ttf"),
            os.path.join(os.getcwd(), "fonts", "TimesNewRoman.ttf"),
            r"C:\Windows\Fonts\times.ttf",
            r"C:\Windows\Fonts\timesnewroman.ttf",
        ]
        font_path = ""
        for p in candidates:
            p = os.path.normpath(p)
            if os.path.exists(p):
                font_path = p
                break

        font_name = "TNR"
        if font_path:
            if font_name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(font_name, font_path))

        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, title="Pitching request")

        base_styles = getSampleStyleSheet()

        # ---- свои стили (без <b>, чтобы не переключался на Helvetica-Bold) ----
        if font_name in pdfmetrics.getRegisteredFontNames():
            title_style = ParagraphStyle(
                "TNR_Title", parent=base_styles["Title"],
                fontName=font_name, fontSize=18, leading=22
            )
            normal_style = ParagraphStyle(
                "TNR_Normal", parent=base_styles["Normal"],
                fontName=font_name, fontSize=10, leading=14
            )
            heading_style = ParagraphStyle(
                "TNR_Heading", parent=base_styles["Heading4"],
                fontName=font_name, fontSize=12, leading=16, spaceAfter=4
            )
            body_style = ParagraphStyle(
                "TNR_Body", parent=base_styles["BodyText"],
                fontName=font_name, fontSize=10, leading=14
            )
        else:
            # если шрифт не нашли — сгенерим как есть (будут квадраты), но не упадём
            title_style = base_styles["Title"]
            normal_style = base_styles["Normal"]
            heading_style = base_styles["Heading4"]
            body_style = base_styles["BodyText"]

        def esc(s: str) -> str:
            return xml_escape(s or "").replace("\n", "<br/>")

        story = []

        story.append(Paragraph("Заявка на питчинг", title_style))
        story.append(Spacer(1, 10))

        story.append(Paragraph(esc(f"Заявка #{req.get('id','')}"), normal_style))
        story.append(Paragraph(esc(f"Дата: {req.get('created_at','')}"), normal_style))
        story.append(Paragraph(esc(f"Пользователь: {req.get('telegram_id','')} @{req.get('username','')}"), normal_style))
        story.append(Spacer(1, 12))

        def add_block(label: str, value: str):
            # заменим "•" на "-" чтобы не словить квадрат именно на маркере
            safe_label = (label or "").replace("•", "-")
            story.append(Paragraph(esc(safe_label), heading_style))
            story.append(Paragraph(esc(value or ""), body_style))
            story.append(Spacer(1, 10))

        add_block("• название релиза и псевдоним артиста", req.get("release_artist", ""))
        add_block("• Описание релиза и артиста", req.get("description", ""))
        add_block("• Ссылка на фотографии", req.get("photos_link", ""))
        add_block("• Ссылка на прослушивание", req.get("listen_link", ""))
        add_block("• Ссылка на предпросмотр клипа (если есть)", req.get("clip_link", ""))
        add_block("• Ссылки на соцсети артиста", req.get("socials", ""))
        add_block("• Дополнительная информация", req.get("extra", ""))

        doc.build(story)
        return buf.getvalue()
    except Exception:
        return b""


async def _send_pdf_if_any(bot: Bot, chat_id: int, req: dict, caption: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> bool:
    pdf_bytes = _try_build_pdf_bytes(req)
    if not pdf_bytes:
        return False
    filename = f"pitching_request_{req['id']}.pdf"
    await bot.send_document(
        chat_id=chat_id,
        document=BufferedInputFile(pdf_bytes, filename=filename),
        caption=caption[:1000],
        reply_markup=reply_markup,
    )
    return True


@router.message(F.text == BTN_USER_ENTRY)
async def pitch_entry(message: Message):
    txt = (
        "<b>Релиз на питчинг</b>\n\n"
        "Выберите действие.\n"
        "Важно: все ссылки должны быть на Яндекс.Диск."
    )
    await message.answer(txt, reply_markup=_menu_kb())


@router.callback_query(F.data == "pitch:menu")
async def pitch_menu_cb(call: CallbackQuery):
    await call.message.edit_text(
        "<b>Релиз на питчинг</b>\n\nВыберите действие.\nВажно: все ссылки должны быть на Яндекс.Диск.",
        reply_markup=_menu_kb()
    )
    await call.answer()


@router.callback_query(F.data == "pitch:main")
async def pitch_main_cb(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.answer()
    await call.message.edit_text("Готово. Вы в главном меню.")


@router.callback_query(F.data == "pitch:cancel")
async def pitch_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.answer()
    await call.message.edit_text("Отменено.", reply_markup=_menu_kb())


@router.callback_query(F.data == "pitch:noop")
async def pitch_noop(call: CallbackQuery):
    await call.answer()


@router.callback_query(F.data == "pitch:new")
async def pitch_new(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(PitchForm.step1)
    await state.update_data(step_index=0, answers={})
    await call.answer()
    await call.message.edit_text(PITCH_FORM_STEPS[0], reply_markup=_cancel_kb(show_back=False))


@router.callback_query(F.data == "pitch:back")
async def pitch_back(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    step_index = int(data.get("step_index", 0))

    # если в preview -> назад на последний шаг
    cur_state = await state.get_state()
    if cur_state == PitchForm.preview.state:
        step_index = 6
        await state.set_state(PitchForm.step7)
        await state.update_data(step_index=step_index)
        await call.answer()
        await call.message.edit_text(PITCH_FORM_STEPS[step_index], reply_markup=_cancel_kb(show_back=True))
        return

    if step_index <= 0:
        await call.answer()
        await call.message.edit_text("<b>Релиз на питчинг</b>\n\nВыберите действие.\nВажно: все ссылки должны быть на Яндекс.Диск.", reply_markup=_menu_kb())
        await state.clear()
        return

    step_index -= 1
    await state.update_data(step_index=step_index)
    # выставляем state по индексу
    states = [PitchForm.step1, PitchForm.step2, PitchForm.step3, PitchForm.step4, PitchForm.step5, PitchForm.step6, PitchForm.step7]
    await state.set_state(states[step_index])

    await call.answer()
    await call.message.edit_text(PITCH_FORM_STEPS[step_index], reply_markup=_cancel_kb(show_back=True))


async def _handle_step(message: Message, state: FSMContext, value: str):
    data = await state.get_data()
    step_index = int(data.get("step_index", 0))
    answers = dict(data.get("answers", {}))

    value = (value or "").strip()

    # валидации ссылок
    if step_index == 2:  # photos_link
        if not _is_yandex_disk_link(value):
            await message.answer("Нужна ссылка на Яндекс.Диск. Отправьте корректную ссылку.", reply_markup=_cancel_kb(show_back=True))
            return
    if step_index == 3:  # listen_link
        if not _is_yandex_disk_link(value):
            await message.answer("Нужна ссылка на Яндекс.Диск. Отправьте корректную ссылку.", reply_markup=_cancel_kb(show_back=True))
            return
    if step_index == 4:  # clip_link (optional)
        if value in ("-", "—", "нет", "Нет", "NONE", "none"):
            value = ""
        elif value and (not _is_yandex_disk_link(value)):
            await message.answer("Нужна ссылка на Яндекс.Диск (или отправьте '-' если нет).", reply_markup=_cancel_kb(show_back=True))
            return

    answers[FIELDS[step_index]] = value

    # следующий шаг
    step_index += 1
    await state.update_data(step_index=step_index, answers=answers)

    if step_index >= len(PITCH_FORM_STEPS):
        # preview
        await state.set_state(PitchForm.preview)
        preview = (
            "<b>Проверьте заявку перед отправкой</b>\n\n"
            f"<b>• название релиза и псевдоним артиста</b>\n{answers.get('release_artist','')}\n\n"
            f"<b>• Описание релиза и артиста</b>\n{answers.get('description','')}\n\n"
            f"<b>• Ссылка на фотографии</b>\n{answers.get('photos_link','')}\n\n"
            f"<b>• Ссылка на прослушивание</b>\n{answers.get('listen_link','')}\n\n"
            f"<b>• Ссылка на предпросмотр клипа (если есть)</b>\n{answers.get('clip_link','')}\n\n"
            f"<b>• Ссылки на соцсети артиста</b>\n{answers.get('socials','')}\n\n"
            f"<b>• Дополнительная информация</b>\n{answers.get('extra','')}\n"
        )
        await message.answer(preview, reply_markup=_preview_kb())
        return

    # установить state по индексу
    states = [PitchForm.step1, PitchForm.step2, PitchForm.step3, PitchForm.step4, PitchForm.step5, PitchForm.step6, PitchForm.step7]
    await state.set_state(states[step_index])

    # маленькая подсказка только для опционального шага
    if step_index == 4:
        await message.answer("Если клипа нет — отправьте '-'.")
    await message.answer(PITCH_FORM_STEPS[step_index], reply_markup=_cancel_kb(show_back=True))


@router.message(PitchForm.step1)
async def pitch_step1(message: Message, state: FSMContext):
    await _handle_step(message, state, message.text or "")


@router.message(PitchForm.step2)
async def pitch_step2(message: Message, state: FSMContext):
    await _handle_step(message, state, message.text or "")


@router.message(PitchForm.step3)
async def pitch_step3(message: Message, state: FSMContext):
    await _handle_step(message, state, message.text or "")


@router.message(PitchForm.step4)
async def pitch_step4(message: Message, state: FSMContext):
    await _handle_step(message, state, message.text or "")


@router.message(PitchForm.step5)
async def pitch_step5(message: Message, state: FSMContext):
    await _handle_step(message, state, message.text or "")


@router.message(PitchForm.step6)
async def pitch_step6(message: Message, state: FSMContext):
    await _handle_step(message, state, message.text or "")


@router.message(PitchForm.step7)
async def pitch_step7(message: Message, state: FSMContext):
    await _handle_step(message, state, message.text or "")


@router.callback_query(F.data == "pitch:send")
async def pitch_send(call: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    answers = dict(data.get("answers", {}))

    user = call.from_user
    telegram_id = int(user.id)
    username = user.username or ""

    req_id = add_pitching_request(
        telegram_id=telegram_id,
        username=username,
        release_artist=answers.get("release_artist", ""),
        description=answers.get("description", ""),
        photos_link=answers.get("photos_link", ""),
        listen_link=answers.get("listen_link", ""),
        clip_link=answers.get("clip_link", ""),
        socials=answers.get("socials", ""),
        extra=answers.get("extra", ""),
        status="new",
        pdf_path="",
    )

    req = get_pitching_request(req_id) or {}
    os.makedirs(PDF_DIR, exist_ok=True)

    # пробуем сделать PDF и сохранить путь
    pdf_bytes = _try_build_pdf_bytes(req)
    if pdf_bytes:
        pdf_path = os.path.join(PDF_DIR, f"pitching_request_{req_id}.pdf")
        try:
            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes)
            set_pitching_request_pdf_path(req_id, pdf_path)
            req["pdf_path"] = pdf_path
        except Exception:
            pass

    await state.clear()
    await call.answer()

    # пользователю
    await call.message.edit_text(f"Отправили на питчинг.\nЗаявка #{req_id}.", reply_markup=_menu_kb())

    # админам
    admins = _admin_ids()
    if admins:
        caption = f"Новая заявка #{req_id}.\nПользователь: {telegram_id} @{username}\nРелиз: {req.get('release_artist','')}"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"Открыть заявку #{req_id}", callback_data=f"pitch_admin:open:{req_id}")],
            [InlineKeyboardButton(text="Открыть список заявок", callback_data="pitch_admin:list:0")],
        ])

        for admin_id in admins:
            try:
                # 1) всегда отправляем уведомление текстом (чтобы точно дошло)
                await bot.send_message(admin_id, caption, reply_markup=kb)

                # 2) если есть PDF — отправляем вторым сообщением
                path = req.get("pdf_path")
                if path:
                    path = str(path).strip()
                else:
                    path = ""

                if path and os.path.exists(path):
                    try:
                        with open(path, "rb") as f:
                            b = f.read()
                        await bot.send_document(
                            chat_id=admin_id,
                            document=BufferedInputFile(b, filename=f"pitching_request_{req_id}.pdf"),
                            caption=f"PDF заявки #{req_id}"
                        )
                    except Exception:
                        pass

            except Exception:
                pass



@router.callback_query(F.data.startswith("pitch:my:"))
async def pitch_my_list(call: CallbackQuery):
    page = int(call.data.split(":")[-1])
    user_id = int(call.from_user.id)

    total = count_user_pitching_requests(user_id)
    pages, page, offset = _paginate(total, page, PAGE_SIZE)
    items = list_user_pitching_requests(user_id, offset=offset, limit=PAGE_SIZE)

    lines = [f"<b>Мои заявки</b> (страница {page+1}/{pages})\n"]
    if not items:
        lines.append("Пока нет заявок.")
    else:
        for it in items:
            short = (it.get("release_artist") or "").strip()
            if len(short) > 44:
                short = short[:44] + "…"
            lines.append(f"#{it['id']} • <code>{it.get('created_at','')}</code> • {short}")

    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=_my_list_kb(page, pages, items))


@router.callback_query(F.data.startswith("pitch:open:"))
async def pitch_open(call: CallbackQuery, bot: Bot):
    req_id = int(call.data.split(":")[-1])
    user_id = int(call.from_user.id)

    req = get_pitching_request(req_id)
    await call.answer()

    if not req or int(req.get("telegram_id", 0)) != user_id:
        await call.message.edit_text("Заявка не найдена.", reply_markup=_menu_kb())
        return

    kb_rows = [
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="pitch:my:0")],
    ]
    if req.get("pdf_path"):
        kb_rows.insert(0, [InlineKeyboardButton(text="📄 Скачать PDF", callback_data=f"pitch:pdf:{req_id}")])
    kb_rows.append([InlineKeyboardButton(text="🗑 Удалить", callback_data=f"pitch:delask:{req_id}")])

    await call.message.edit_text(_req_text(req), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))


@router.callback_query(F.data.startswith("pitch:pdf:"))
async def pitch_pdf(call: CallbackQuery, bot: Bot):
    req_id = int(call.data.split(":")[-1])
    user_id = int(call.from_user.id)
    req = get_pitching_request(req_id)
    await call.answer()

    if not req or int(req.get("telegram_id", 0)) != user_id:
        await call.message.edit_text("Файл не найден.", reply_markup=_menu_kb())
        return

    path = (req.get("pdf_path") or "").strip()
    if not path or not os.path.exists(path):
        await call.message.edit_text("PDF пока недоступен.", reply_markup=_menu_kb())
        return

    try:
        with open(path, "rb") as f:
            b = f.read()
        await bot.send_document(
            chat_id=user_id,
            document=BufferedInputFile(b, filename=f"pitching_request_{req_id}.pdf"),
            caption=f"Заявка #{req_id}"
        )
    except Exception:
        await call.message.edit_text("Не удалось отправить PDF.", reply_markup=_menu_kb())


@router.callback_query(F.data.startswith("pitch:delask:"))
async def pitch_del_ask(call: CallbackQuery):
    req_id = int(call.data.split(":")[-1])
    await call.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🗑 Да, удалить", callback_data=f"pitch:del:{req_id}"),
            InlineKeyboardButton(text="✖️ Отмена", callback_data=f"pitch:open:{req_id}"),
        ]
    ])
    await call.message.edit_text(f"Удалить заявку #{req_id}?", reply_markup=kb)


@router.callback_query(F.data.startswith("pitch:del:"))
async def pitch_del(call: CallbackQuery):
    req_id = int(call.data.split(":")[-1])
    user_id = int(call.from_user.id)

    ok = delete_pitching_request(req_id, telegram_id=user_id)
    await call.answer()
    if ok:
        await call.message.edit_text("Удалено.", reply_markup=_menu_kb())
    else:
        await call.message.edit_text("Не удалось удалить (возможно, уже удалено).", reply_markup=_menu_kb())


# =========================
# Admin
# =========================

@router.message(F.text == BTN_ADMIN_ENTRY)
@router.message(F.text == "/pitching")
async def admin_entry(message: Message):
    if not _is_admin(int(message.from_user.id)):
        return
    await message.answer("Открываю список заявок.", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Открыть", callback_data="pitch_admin:list:0")]]
    ))


@router.callback_query(F.data.startswith("pitch_admin:list:"))
async def admin_list(call: CallbackQuery):
    if not _is_admin(int(call.from_user.id)):
        await call.answer()
        return

    page = int(call.data.split(":")[-1])
    total = count_all_pitching_requests()
    pages, page, offset = _paginate(total, page, PAGE_SIZE)
    items = list_all_pitching_requests(offset=offset, limit=PAGE_SIZE)

    lines = [f"<b>Релизы на питчинг</b> (страница {page+1}/{pages})\n"]
    if not items:
        lines.append("Пока нет заявок.")
    else:
        for it in items:
            short = (it.get("release_artist") or "").strip()
            if len(short) > 44:
                short = short[:44] + "…"
            u = str(it.get("telegram_id", ""))
            un = (it.get("username") or "").strip()
            user_str = f"{u}" + (f" @{un}" if un else "")
            lines.append(f"#{it['id']} • <code>{it.get('created_at','')}</code> • {user_str} • {short}")

    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=_admin_list_kb(page, pages, items))


@router.callback_query(F.data.startswith("pitch_admin:open:"))
async def admin_open(call: CallbackQuery, bot: Bot):
    if not _is_admin(int(call.from_user.id)):
        await call.answer()
        return

    req_id = int(call.data.split(":")[-1])
    req = get_pitching_request(req_id)
    await call.answer()

    if not req:
        await call.message.edit_text("Заявка не найдена.")
        return

    # отметим просмотр
    try:
        if req.get("status") == "new":
            set_pitching_request_status(req_id, "viewed")
            req["status"] = "viewed"
    except Exception:
        pass

    kb_rows = [
        [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="pitch_admin:list:0")],
        [InlineKeyboardButton(text="✅ Отметить как обработано", callback_data=f"pitch_admin:done:{req_id}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"pitch_admin:delask:{req_id}")],
    ]
    if req.get("pdf_path"):
        kb_rows.insert(0, [InlineKeyboardButton(text="📄 Скачать PDF", callback_data=f"pitch_admin:pdf:{req_id}")])

    await call.message.edit_text(_req_text(req), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))


@router.callback_query(F.data.startswith("pitch_admin:done:"))
async def admin_done(call: CallbackQuery):
    if not _is_admin(int(call.from_user.id)):
        await call.answer()
        return

    req_id = int(call.data.split(":")[-1])
    set_pitching_request_status(req_id, "done")
    await call.answer("Готово")
    await call.message.edit_text("Отмечено как обработано.", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="pitch_admin:list:0")],
            [InlineKeyboardButton(text=f"Открыть #{req_id}", callback_data=f"pitch_admin:open:{req_id}")],
        ]
    ))


@router.callback_query(F.data.startswith("pitch_admin:pdf:"))
async def admin_pdf(call: CallbackQuery, bot: Bot):
    if not _is_admin(int(call.from_user.id)):
        await call.answer()
        return

    req_id = int(call.data.split(":")[-1])
    req = get_pitching_request(req_id)
    await call.answer()

    if not req:
        await call.message.edit_text("Файл не найден.")
        return

    path = (req.get("pdf_path") or "").strip()
    if not path or not os.path.exists(path):
        await call.message.edit_text("PDF пока недоступен.")
        return

    try:
        with open(path, "rb") as f:
            b = f.read()
        await bot.send_document(
            chat_id=int(call.from_user.id),
            document=BufferedInputFile(b, filename=f"pitching_request_{req_id}.pdf"),
            caption=f"Заявка #{req_id}"
        )
    except Exception:
        await call.message.edit_text("Не удалось отправить PDF.")


@router.callback_query(F.data.startswith("pitch_admin:delask:"))
async def admin_del_ask(call: CallbackQuery):
    if not _is_admin(int(call.from_user.id)):
        await call.answer()
        return

    req_id = int(call.data.split(":")[-1])
    await call.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🗑 Да, удалить", callback_data=f"pitch_admin:del:{req_id}"),
            InlineKeyboardButton(text="✖️ Отмена", callback_data=f"pitch_admin:open:{req_id}"),
        ]
    ])
    await call.message.edit_text(f"Удалить заявку #{req_id}?", reply_markup=kb)


@router.callback_query(F.data.startswith("pitch_admin:del:"))
async def admin_del(call: CallbackQuery):
    if not _is_admin(int(call.from_user.id)):
        await call.answer()
        return

    req_id = int(call.data.split(":")[-1])
    ok = delete_pitching_request(req_id, telegram_id=None)
    await call.answer()
    if ok:
        await call.message.edit_text("Удалено.", reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ К списку", callback_data="pitch_admin:list:0")]]
        ))
    else:
        await call.message.edit_text("Не удалось удалить (возможно, уже удалено).")
