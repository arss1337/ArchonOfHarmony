import os
import asyncio
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, LabeledPrice, ChatInviteLink
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN")  # опционально (Telegram Payments)

WHITE_CHAT_ID = int(os.getenv("WHITE_CHAT_ID", "0"))
BLACK_CHAT_ID = int(os.getenv("BLACK_CHAT_ID", "0"))
GREY_CHAT_ID  = int(os.getenv("GREY_CHAT_ID",  "0"))

bot = Bot(BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()

# In-memory (MVP). На проде замени на БД.
def kb(rows):
    b = InlineKeyboardBuilder()
    for row in rows:
        if isinstance(row, list):
            for text, data in row:
                b.button(text=text, callback_data=data)
            b.row()
        else:
            text, data = row
            b.button(text=text, callback_data=data)
            b.row()
    return b.as_markup()

class Quiz(StatesGroup):
    q1 = State()
    q2 = State()
    q3 = State()

@dp.message(CommandStart())
async def start(m: Message, state: FSMContext):
    await state.clear()
    await state.update_data(score_power=0, score_control=0, score_harmony=0)
    await m.answer(
        "👁 Добро пожаловать в <b>4D | Архонт Гармонизации</b>.\nГотов пройти короткий тест?",
        reply_markup=kb([("👉 Пройти испытание", "start_quiz")])
    )

@dp.callback_query(F.data == "start_quiz")
async def q1(c: CallbackQuery, state: FSMContext):
    await state.set_state(Quiz.q1)
    await c.message.edit_text(
        "⚖ <b>Вопрос 1/3</b>\nЧто важнее прямо сейчас?",
        reply_markup=kb([
            ("⚡ Сила","q1_power"),
            ("🎛 Контроль","q1_control"),
            ("☯ Гармония","q1_harmony")
        ])
    )

@dp.callback_query(Quiz.q1, F.data.startswith("q1_"))
async def q1_answer(c: CallbackQuery, state: FSMContext):
    d = await state.get_data()
    if c.data.endswith("power"):   d["score_power"]   += 1
    elif c.data.endswith("control"): d["score_control"] += 1
    else:                           d["score_harmony"] += 1
    await state.update_data(**d)
    await state.set_state(Quiz.q2)
    await c.message.edit_text(
        "🔥 <b>Вопрос 2/3</b>\nЧто ближе сердцу?",
        reply_markup=kb([
            ("📈 Влияние","q2_power"),
            ("🧭 Предсказуемость","q2_control"),
            ("🕊 Спокойствие","q2_harmony")
        ])
    )

@dp.callback_query(Quiz.q2, F.data.startswith("q2_"))
async def q2_answer(c: CallbackQuery, state: FSMContext):
    d = await state.get_data()
    if c.data.endswith("power"):   d["score_power"]   += 1
    elif c.data.endswith("control"): d["score_control"] += 1
    else:                           d["score_harmony"] += 1
    await state.update_data(**d)
    await state.set_state(Quiz.q3)
    await c.message.edit_text(
        "🧩 <b>Вопрос 3/3</b>\nЧто выбираешь в конфликте?",
        reply_markup=kb([
            ("⚔️ Давить и побеждать","q3_power"),
            ("♟️ Считать ходы наперёд","q3_control"),
            ("⚖️ Уравновесить и интегрировать","q3_harmony")
        ])
    )

@dp.callback_query(Quiz.q3, F.data.startswith("q3_"))
async def result_teaser(c: CallbackQuery, state: FSMContext):
    d = await state.get_data()
    if c.data.endswith("power"):   d["score_power"]   += 1
    elif c.data.endswith("control"): d["score_control"] += 1
    else:                           d["score_harmony"] += 1
    await state.update_data(**d)

    scores = { "black": d["score_power"], "grey": d["score_control"], "white": d["score_harmony"] }
    hat = max(scores, key=scores.get)
    await state.update_data(hat=hat)
    title = {"black":"⚫ Чёрная","grey":"⚪⚫ Серая","white":"⚪ Белая"}[hat]

    await c.message.edit_text(
        f"✨ Твой текущий вектор: <b>{title}</b>.\nЭто лишь 30% карты.\nОткрыть полный отчёт + доступ в Орден?",
        reply_markup=kb([
            ("💳 Открыть полный отчёт ($9)","pay"),
            ("🧠 Выбрать Шляпу бесплатно","free_hat")
        ])
    )

@dp.callback_query(F.data == "pay")
async def pay(c: CallbackQuery, state: FSMContext):
    if not PROVIDER_TOKEN:
        await c.answer("Платежи не настроены", show_alert=True)
        return
    await bot.send_invoice(
        chat_id=c.message.chat.id,
        title="4D Full Report + Hat Chat",
        description="Полная расшифровка карты + доступ в закрытый Орден.",
        payload=f"order_{c.from_user.id}",
        provider_token=PROVIDER_TOKEN,
        currency="USD",
        prices=[LabeledPrice(label="Access", amount=900)],  # $9.00
        start_parameter="archon_access"
    )

@dp.pre_checkout_query()
async def pre_checkout(q):
    await bot.answer_pre_checkout_query(q.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment(m: Message, state: FSMContext):
    data = await state.get_data()
    hat = data.get("hat", "grey")
    await m.answer("💎 Оплата прошла. Открываю доступ…")
    await give_invite(m, hat)
    await m.answer("Готов к Уроку 1/7?", reply_markup=kb([("▶️ Урок 1","lesson1")]))

async def give_invite(m: Message, hat: str):
    chat_id = {"white": WHITE_CHAT_ID, "black": BLACK_CHAT_ID, "grey": GREY_CHAT_ID}[hat]
    if not chat_id:
        await m.answer("Чат не настроен. Сообщи поддержку @your_support.")
        return
    link: ChatInviteLink = await bot.create_chat_invite_link(chat_id=chat_id, member_limit=1)
    await m.answer(f"Твой Орден: <b>{hat}</b>\nВход по ссылке (1 раз):\n{link.invite_link}")

@dp.callback_query(F.data == "free_hat")
async def free_hat(c: CallbackQuery):
    await c.message.edit_text(
        "🔮 Выбери Шляпу для открытого уровня:",
        reply_markup=kb([
            ("⚪ Белая","fh_white"),
            ("⚫ Чёрная","fh_black"),
            ("⚪⚫ Серая","fh_grey")
        ])
    )

# Замените на свои открытые чаты (или уберите вовсе)
FREE_WHITE = "https://t.me/+YOUR_WHITE_FREE"
FREE_BLACK = "https://t.me/+YOUR_BLACK_FREE"
FREE_GREY  = "https://t.me/+YOUR_GREY_FREE"

@dp.callback_query(F.data.in_(("fh_white","fh_black","fh_grey")))
async def free_link(c: CallbackQuery):
    link = FREE_WHITE if c.data=="fh_white" else FREE_BLACK if c.data=="fh_black" else FREE_GREY
    await c.message.edit_text(f"Твой открытый чат: {link}")

@dp.callback_query(F.data == "lesson1")
async def lesson1(c: CallbackQuery):
    await c.message.edit_text(
        "Урок 1/7 — <b>Карта твоего пути</b>\n(вставь свой контент)",
        reply_markup=kb([("▶️ Урок 2","lesson2")])
    )

@dp.callback_query(F.data == "lesson2")
async def lesson2(c: CallbackQuery):
    await c.message.edit_text(
        "Урок 2/7 — <b>Пусть сердце увидит карту</b>\n(контент)",
        reply_markup=kb([("▶️ Урок 3","lesson3")])
    )

# ... добавь lesson3..7 по аналогии

async def main():
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
