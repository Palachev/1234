from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.config import Settings
from app.keyboards.common import tariffs_keyboard
from app.services.payments import PaymentService
from app.services.subscription import SubscriptionService

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.text == "💳 Купить VPN")
async def choose_plan(message: Message) -> None:
    await message.answer(
        "Выбери срок подписки. Оплата занимает 1–2 минуты.",
        reply_markup=tariffs_keyboard(),
    )


@router.callback_query(F.data.startswith("buy:"))
async def start_payment(
    callback: CallbackQuery,
    payment_service: PaymentService,
    subscription_service: SubscriptionService,
    settings: Settings,
) -> None:
    tariff_code = callback.data.split(":", maxsplit=1)[1]
    tariff = subscription_service.get_tariff(tariff_code)
    amount_minor_units = _to_minor_units(tariff.price, settings.payment_currency)

    if amount_minor_units <= 0:
        await callback.message.answer(
            "Не удалось открыть оплату: сумма должна быть больше 0. "
            "Проверь цены в тарифах."
        )
        await callback.answer()
        return

    invoice = await payment_service.create_invoice(
        callback.from_user.id,
        tariff_code,
        amount_minor_units,
    )

    try:
        payment_url = await payment_service.create_yookassa_payment(
            invoice_id=invoice.invoice_id,
            amount_minor=invoice.amount_minor,
            description=f"VPN подписка: {tariff.title}",
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to create YooKassa payment: %s", exc)
        await callback.message.answer(
            "Не удалось открыть оплату. Попробуй позже или обратись в поддержку."
        )
        await callback.answer()
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", url=payment_url)],
        ]
    )

    await callback.message.answer(
        "Для продолжения оплаты нажми кнопку ниже.",
        reply_markup=keyboard,
    )
    await callback.answer()


def _to_minor_units(amount: float, currency: str) -> int:
    minor_units = {"RUB": 2}
    exponent = minor_units.get(currency.upper(), 2)
    value = Decimal(str(amount)).quantize(Decimal(f"1e-{exponent}"), rounding=ROUND_HALF_UP)
    return int(value * (10**exponent))
