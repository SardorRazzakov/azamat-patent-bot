"""Тексты для клиента на трёх языках.

Админка не переводится и остаётся на русском — её строки живут в handlers/admin.py.

Ключ сообщения -> перевод на каждый язык. Плейсхолдеры подставляются
через t(key, lang, name=value).
"""

RU = "ru"
UZ_CYRL = "uz_cyrl"
UZ_LATN = "uz_latn"

LANGUAGES = (RU, UZ_CYRL, UZ_LATN)

# Язык для тех, кто ещё не выбирал: до появления выбора бот говорил
# на узбекской латинице, так что старые клиенты ничего не заметят.
DEFAULT_LANG = UZ_LATN

# Подписи кнопок выбора — каждая намеренно на своём языке.
LANGUAGE_NAMES = {
    RU: "Русский",
    UZ_CYRL: "Ўзбекча",
    UZ_LATN: "O'zbekcha",
}

# Заголовок экрана выбора языка: ни на одном языке в отдельности.
CHOOSE_LANGUAGE = "🌐 Til · Тил · Язык"


TEXTS: dict[str, dict[str, str]] = {
    "greeting": {
        RU: (
            "Здравствуйте! 👋\n\n"
            "Вас интересует запись на экзамен по русскому языку "
            "для получения сертификата?\n\n"
            "Экзамен проводится в Ташкенте.\n"
            "Стоимость записи: 1 400 000 сум.\n\n"
            "Чтобы продолжить и узнать свободные даты, нажмите кнопку ниже."
        ),
        UZ_CYRL: (
            "Ассалому алайкум! 👋\n\n"
            "Сизни сертификат олиш учун рус тили имтиҳонига ёзилиш "
            "қизиқтиряптими?\n\n"
            "Имтиҳон Тошкентда ўтказилади.\n"
            "Ёзилиш нархи: 1 400 000 сўм.\n\n"
            "Давом этиш ва бўш саналарни билиш учун қуйидаги тугмани босинг."
        ),
        UZ_LATN: (
            "Assalomu alaykum! 👋\n\n"
            "Sizni sertifikat olish uchun rus tili imtihoniga yozilish "
            "qiziqtiryaptimi?\n\n"
            "Imtihon Toshkentda o'tkaziladi.\n"
            "Yozilish narxi: 1 400 000 so'm.\n\n"
            "Davom etish va bo'sh sanalarni bilish uchun quyidagi tugmani bosing."
        ),
    },
    "btn_continue": {
        RU: "Продолжить",
        UZ_CYRL: "Давом этиш",
        UZ_LATN: "Davom etish",
    },
    "already_booked": {
        RU: (
            "Вы уже записаны на экзамен. ✅\n"
            "Если есть вопросы, свяжитесь с администратором."
        ),
        UZ_CYRL: (
            "Сиз аллақачон имтиҳонга ёзилгансиз. ✅\n"
            "Саволлар бўлса, администратор билан боғланинг."
        ),
        UZ_LATN: (
            "Siz allaqachon imtihonga yozilgansiz. ✅\n"
            "Savollar bo'lsa, administrator bilan bog'laning."
        ),
    },
    "no_dates": {
        RU: "Свободных дат пока нет. Попробуйте позже.",
        UZ_CYRL: "Ҳозирча бўш саналар йўқ. Кейинроқ уриниб кўринг.",
        UZ_LATN: "Hozircha bo'sh sanalar yo'q. Keyinroq urinib ko'ring.",
    },
    "choose_date": {
        RU: "Выберите удобную дату экзамена:",
        UZ_CYRL: "Имтиҳон учун қулай санани танланг:",
        UZ_LATN: "Imtihon uchun qulay sanani tanlang:",
    },
    "date_full": {
        RU: "На эту дату свободных мест не осталось. Выберите другую.",
        UZ_CYRL: "Бу санада бўш жой қолмади. Бошқа санани танланг.",
        UZ_LATN: "Bu sanada bo'sh joy qolmadi. Boshqa sanani tanlang.",
    },
    "date_chosen": {
        RU: (
            "Вы выбрали {title} ✅\n\n"
            "Чтобы завершить запись, пришлите, пожалуйста, фото загранпаспорта."
        ),
        UZ_CYRL: (
            "Сиз {title} санасини танладингиз ✅\n\n"
            "Ёзилишни якунлаш учун, илтимос, чет эл паспортингиз расмини юборинг."
        ),
        UZ_LATN: (
            "Siz {title} sanasini tanladingiz ✅\n\n"
            "Yozilishni yakunlash uchun, iltimos, chet el pasportingiz rasmini yuboring."
        ),
    },
    "need_passport": {
        RU: "Жду фото загранпаспорта. 📄",
        UZ_CYRL: "Чет эл паспортингиз расмини кутяпман. 📄",
        UZ_LATN: "Chet el pasportingiz rasmini kutyapman. 📄",
    },
    "passport_received": {
        RU: (
            "Спасибо! Паспорт принят. 📄\n\n"
            "Для оплаты используйте одну из ссылок:\n\n"
            "💳 Payme: {payme}\n"
            "💳 Click: {click}\n\n"
            "После оплаты пришлите, пожалуйста, скриншот чека."
        ),
        UZ_CYRL: (
            "Раҳмат! Паспорт қабул қилинди. 📄\n\n"
            "Тўлов учун қуйидаги ҳаволалардан бирини ишлатинг:\n\n"
            "💳 Payme: {payme}\n"
            "💳 Click: {click}\n\n"
            "Тўловдан сўнг, илтимос, чекнинг скриншотини юборинг."
        ),
        UZ_LATN: (
            "Rahmat! Pasport qabul qilindi. 📄\n\n"
            "To'lov uchun quyidagi havolalardan birini ishlating:\n\n"
            "💳 Payme: {payme}\n"
            "💳 Click: {click}\n\n"
            "To'lovdan so'ng, iltimos, chekning skrinshotini yuboring."
        ),
    },
    "need_receipt": {
        RU: "Жду скриншот чека об оплате. 🧾",
        UZ_CYRL: "Тўлов чекининг скриншотини кутяпман. 🧾",
        UZ_LATN: "To'lov chekining skrinshotini kutyapman. 🧾",
    },
    "receipt_received": {
        RU: "Спасибо! Чек принят. ⏳\n\nДождитесь подтверждения администратора.",
        UZ_CYRL: "Раҳмат! Чек қабул қилинди. ⏳\n\nАдминистратор тасдиқлашини кутинг.",
        UZ_LATN: "Rahmat! Chek qabul qilindi. ⏳\n\nAdministrator tasdiqlashini kuting.",
    },
    "payment_confirmed": {
        RU: (
            "Оплата подтверждена! ✅\n\n"
            "Место на экзамене забронировано.\n\n"
            "📍 Место проведения экзамена:"
        ),
        UZ_CYRL: (
            "Тўлов тасдиқланди! ✅\n\n"
            "Сиз учун имтиҳонда жой банд қилинди.\n\n"
            "📍 Имтиҳон ўтказиладиган жой:"
        ),
        UZ_LATN: (
            "To'lov tasdiqlandi! ✅\n\n"
            "Siz uchun imtihonda joy band qilindi.\n\n"
            "📍 Imtihon o'tkaziladigan joy:"
        ),
    },
    "booking_cancelled": {
        RU: (
            "Ваша запись на экзамен отменена. ❌\n\n"
            "Если есть вопросы, свяжитесь с администратором."
        ),
        UZ_CYRL: (
            "Сизнинг имтиҳонга ёзилишингиз бекор қилинди. ❌\n\n"
            "Саволлар бўлса, администратор билан боғланинг."
        ),
        UZ_LATN: (
            "Sizning imtihonga yozilishingiz bekor qilindi. ❌\n\n"
            "Savollar bo'lsa, administrator bilan bog'laning."
        ),
    },
    "fallback": {
        RU: (
            "Не понял вас. 🤔\n\n"
            "Нажмите кнопку ниже, чтобы продолжить, "
            "или отправьте /start, чтобы начать заново."
        ),
        UZ_CYRL: (
            "Тушунмадим. 🤔\n\n"
            "Давом этиш учун қуйидаги тугмани босинг "
            "ёки қайта бошлаш учун /start юборинг."
        ),
        UZ_LATN: (
            "Tushunmadim. 🤔\n\n"
            "Davom etish uchun quyidagi tugmani bosing "
            "yoki qaytadan boshlash uchun /start yuboring."
        ),
    },
}


def lang_or_default(lang: str | None) -> str:
    """Приводит что угодно к поддерживаемому языку."""
    return lang if lang in LANGUAGES else DEFAULT_LANG


def t(key: str, lang: str, **kwargs) -> str:
    translations = TEXTS[key]
    text = translations.get(lang) or translations[DEFAULT_LANG]
    return text.format(**kwargs) if kwargs else text
