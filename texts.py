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
    "seat_gone": {
        RU: (
            "К сожалению, места на эту дату закончились, "
            "пока вы оформляли запись. 😔\n\n"
            "Свяжитесь с администратором — он поможет с переносом или возвратом."
        ),
        UZ_CYRL: (
            "Афсуски, сиз ариза тўлдираётган пайтда "
            "бу санада жойлар тугади. 😔\n\n"
            "Администратор билан боғланинг — у бошқа санага ўтказиш ёки "
            "пулни қайтариш бўйича ёрдам беради."
        ),
        UZ_LATN: (
            "Afsuski, siz ariza to'ldirayotgan paytda "
            "bu sanada joylar tugadi. 😔\n\n"
            "Administrator bilan bog'laning — u boshqa sanaga o'tkazish yoki "
            "pulni qaytarish bo'yicha yordam beradi."
        ),
    },
    "receipt_received": {
        RU: "Спасибо! Чек принят. ⏳\n\nДождитесь подтверждения администратора.",
        UZ_CYRL: "Раҳмат! Чек қабул қилинди. ⏳\n\nАдминистратор тасдиқлашини кутинг.",
        UZ_LATN: "Rahmat! Chek qabul qilindi. ⏳\n\nAdministrator tasdiqlashini kuting.",
    },
    "btn_add_more": {
        RU: "➕ Записать ещё одного",
        UZ_CYRL: "➕ Яна бирини ёздириш",
        UZ_LATN: "➕ Yana birini yozdirish",
    },
    "ask_applicant_name": {
        RU: (
            "Кого записываем? 👤\n\n"
            "Пришлите имя и фамилию человека — так, как в загранпаспорте."
        ),
        UZ_CYRL: (
            "Кимни ёздирамиз? 👤\n\n"
            "Ўша одамнинг исм-фамилиясини юборинг — чет эл паспортидагидек."
        ),
        UZ_LATN: (
            "Kimni yozdiramiz? 👤\n\n"
            "O'sha odamning ism-familiyasini yuboring — chet el pasportidagidek."
        ),
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
    "exam_reminder": {
        RU: (
            "Напоминание: завтра у вас экзамен по русскому языку. 📌\n\n"
            "Дата: {title}\n"
            "Возьмите с собой загранпаспорт и приходите заранее.\n\n"
            "📍 Адрес проведения:"
        ),
        UZ_CYRL: (
            "Эслатма: эртага сизда рус тили имтиҳони бор. 📌\n\n"
            "Сана: {title}\n"
            "Ўзингиз билан чет эл паспортини олинг ва олдиндан келинг.\n\n"
            "📍 Ўтказиладиган манзил:"
        ),
        UZ_LATN: (
            "Eslatma: ertaga sizda rus tili imtihoni bor. 📌\n\n"
            "Sana: {title}\n"
            "O'zingiz bilan chet el pasportini oling va oldindan keling.\n\n"
            "📍 O'tkaziladigan manzil:"
        ),
    },
    "abandoned_nudge": {
        RU: (
            "Вы начали запись на экзамен, но не завершили её. 🙂\n\n"
            "Свободные места ещё есть. Нажмите кнопку ниже, "
            "чтобы выбрать дату и закончить запись."
        ),
        UZ_CYRL: (
            "Сиз имтиҳонга ёзилишни бошладингиз, лекин якунламадингиз. 🙂\n\n"
            "Бўш жойлар ҳали бор. Сана танлаб, ёзилишни тугатиш учун "
            "қуйидаги тугмани босинг."
        ),
        UZ_LATN: (
            "Siz imtihonga yozilishni boshladingiz, lekin yakunlamadingiz. 🙂\n\n"
            "Bo'sh joylar hali bor. Sana tanlab, yozilishni tugatish uchun "
            "quyidagi tugmani bosing."
        ),
    },
    "referral_link": {
        RU: (
            "Хотите пригласить друзей? 🤝\n\n"
            "Отправьте им вашу личную ссылку:\n"
            "{link}\n\n"
            "Мы увидим, что они пришли от вас."
        ),
        UZ_CYRL: (
            "Дўстларингизни таклиф қилмоқчимисиз? 🤝\n\n"
            "Уларга шахсий ҳаволангизни юборинг:\n"
            "{link}\n\n"
            "Улар сиздан келганини биз кўрамиз."
        ),
        UZ_LATN: (
            "Do'stlaringizni taklif qilmoqchimisiz? 🤝\n\n"
            "Ularga shaxsiy havolangizni yuboring:\n"
            "{link}\n\n"
            "Ular sizdan kelganini biz ko'ramiz."
        ),
    },
    "cert_renewal": {
        RU: (
            "Напоминание о сертификате. 📄\n\n"
            "Ваш сертификат за {title} действует до {expires} — "
            "осталось меньше двух месяцев.\n\n"
            "Чтобы продлить, запишитесь на экзамен заранее: "
            "нажмите кнопку ниже."
        ),
        UZ_CYRL: (
            "Сертификат ҳақида эслатма. 📄\n\n"
            "{title} учун сертификатингиз {expires} гача амал қилади — "
            "икки ойдан камроқ вақт қолди.\n\n"
            "Уни янгилаш учун имтиҳонга олдиндан ёзилинг: "
            "қуйидаги тугмани босинг."
        ),
        UZ_LATN: (
            "Sertifikat haqida eslatma. 📄\n\n"
            "{title} uchun sertifikatingiz {expires} gacha amal qiladi — "
            "ikki oydan kamroq vaqt qoldi.\n\n"
            "Uni yangilash uchun imtihonga oldindan yoziling: "
            "quyidagi tugmani bosing."
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
