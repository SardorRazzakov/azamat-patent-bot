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
    "exam_address": {
        RU: "Тест-центр, Ташкент, ул. Паркентская, д. 331",
        UZ_CYRL: "Тест-марказ, Тошкент, Паркент кўчаси, 331-уй",
        UZ_LATN: "Test-markaz, Toshkent, Parkent ko'chasi, 331-uy",
    },
    "after_payment_links": {
        RU: (
            "Подпишитесь на нашу группу, чтобы не пропустить важное "
            "об экзамене.\n\n"
            "А подготовиться поможет бесплатный тренажёр: тесты "
            "и устная часть."
        ),
        UZ_CYRL: (
            "Имтиҳон ҳақидаги муҳим янгиликларни ўтказиб юбормаслик учун "
            "гуруҳимизга обуна бўлинг.\n\n"
            "Тайёргарлик учун бепул тренажёр бор: тестлар ва оғзаки қисм."
        ),
        UZ_LATN: (
            "Imtihon haqidagi muhim yangiliklarni o'tkazib yubormaslik uchun "
            "guruhimizga obuna bo'ling.\n\n"
            "Tayyorgarlik uchun bepul trenajyor bor: testlar va og'zaki qism."
        ),
    },
    "btn_group": {
        RU: "📣 Наша группа",
        UZ_CYRL: "📣 Гуруҳимиз",
        UZ_LATN: "📣 Guruhimiz",
    },
    "btn_trainer": {
        RU: "🎯 Тренажёр",
        UZ_CYRL: "🎯 Тренажёр",
        UZ_LATN: "🎯 Trenajyor",
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
            "Посмотрите частые вопросы или начните запись — кнопки ниже."
        ),
        UZ_CYRL: (
            "Тушунмадим. 🤔\n\n"
            "Кўп сўраладиган саволларни кўринг ёки ёзилишни бошланг — "
            "тугмалар қуйида."
        ),
        UZ_LATN: (
            "Tushunmadim. 🤔\n\n"
            "Ko'p so'raladigan savollarni ko'ring yoki yozilishni boshlang — "
            "tugmalar quyida."
        ),
    },
    # ---------- FAQ ----------
    # Разделы и порядок вопросов заданы в FAQ_SECTIONS ниже.
    "btn_faq": {
        RU: "❓ Частые вопросы",
        UZ_CYRL: "❓ Кўп сўраладиган саволлар",
        UZ_LATN: "❓ Ko'p so'raladigan savollar",
    },
    "btn_signup": {
        RU: "📝 Записаться",
        UZ_CYRL: "📝 Ёзилиш",
        UZ_LATN: "📝 Yozilish",
    },
    "btn_back": {
        RU: "⬅️ Назад",
        UZ_CYRL: "⬅️ Орқага",
        UZ_LATN: "⬅️ Orqaga",
    },
    "faq_title": {
        RU: "❓ Частые вопросы\n\nВыберите раздел:",
        UZ_CYRL: "❓ Кўп сўраладиган саволлар\n\nБўлимни танланг:",
        UZ_LATN: "❓ Ko'p so'raladigan savollar\n\nBo'limni tanlang:",
    },
    "faq_pick_question": {
        RU: "Выберите вопрос:",
        UZ_CYRL: "Саволни танланг:",
        UZ_LATN: "Savolni tanlang:",
    },
    # Строка-подсказка внутри записи: кнопку там не показываем, чтобы не
    # сбивать клиента с шага, но про раздел напоминаем.
    "faq_hint": {
        RU: "Есть вопросы? Отправьте /faq",
        UZ_CYRL: "Саволингиз борми? /faq юборинг",
        UZ_LATN: "Savolingiz bormi? /faq yuboring",
    },

    "faq_sec_exam": {
        RU: "📕 Об экзамене",
        UZ_CYRL: "📕 Имтиҳон ҳақида",
        UZ_LATN: "📕 Imtihon haqida",
    },
    "faq_sec_pay": {
        RU: "💳 Оплата и обучение",
        UZ_CYRL: "💳 Тўлов ва ўқиш",
        UZ_LATN: "💳 To'lov va o'qish",
    },
    "faq_sec_cert": {
        RU: "📄 Сертификат",
        UZ_CYRL: "📄 Сертификат",
        UZ_LATN: "📄 Sertifikat",
    },
    "faq_sec_other": {
        RU: "🗂 Другое",
        UZ_CYRL: "🗂 Бошқа саволлар",
        UZ_LATN: "🗂 Boshqa savollar",
    },

    # --- Об экзамене ---
    "faq_q_dates": {
        RU: "Даты и время",
        UZ_CYRL: "Сана ва вақт",
        UZ_LATN: "Sana va vaqt",
    },
    "faq_a_dates": {
        RU: (
            "Экзамен проходит по понедельникам, средам и пятницам. "
            "Начало в 9:00.\n\n"
            "Актуальные свободные даты вы увидите при записи."
        ),
        UZ_CYRL: (
            "Имтиҳон душанба, чоршанба ва жума кунлари ўтказилади. "
            "Бошланиши соат 9:00 да.\n\n"
            "Бўш саналарни ёзилиш пайтида кўрасиз."
        ),
        UZ_LATN: (
            "Imtihon dushanba, chorshanba va juma kunlari o'tkaziladi. "
            "Boshlanishi soat 9:00 da.\n\n"
            "Bo'sh sanalarni yozilish paytida ko'rasiz."
        ),
    },
    "faq_q_address": {
        RU: "Адрес",
        UZ_CYRL: "Манзил",
        UZ_LATN: "Manzil",
    },
    "faq_a_address": {
        RU: (
            "г. Ташкент, ул. Паркентская, 331.\n\n"
            "Ориентир — напротив метро Яшнабад."
        ),
        UZ_CYRL: (
            "Тошкент шаҳри, Паркент кўчаси, 331-уй.\n\n"
            "Мўлжал — Яшнобод метроси рўпараси."
        ),
        UZ_LATN: (
            "Toshkent shahri, Parkent ko'chasi, 331-uy.\n\n"
            "Mo'ljal — Yashnobod metrosi ro'parasi."
        ),
    },
    "faq_q_bring": {
        RU: "Что взять с собой",
        UZ_CYRL: "Ўзингиз билан нима олиш керак",
        UZ_LATN: "O'zingiz bilan nima olish kerak",
    },
    "faq_a_bring": {
        RU: (
            "Только оригинал загранпаспорта. Без оригинала на экзамен "
            "не допускают.\n\n"
            "Опаздывать нельзя — опоздавших также не допускают.\n\n"
            "В обоих случаях деньги не возвращаются, записаться можно "
            "на другой день с полной оплатой."
        ),
        UZ_CYRL: (
            "Фақат чет эл паспортининг асл нусхаси. Асл нусхасиз "
            "имтиҳонга киритилмайди.\n\n"
            "Кечикиш мумкин эмас — кечиккканлар ҳам киритилмайди.\n\n"
            "Иккала ҳолатда ҳам пул қайтарилмайди, бошқа кунга тўлиқ "
            "тўлов билан ёзилиш мумкин."
        ),
        UZ_LATN: (
            "Faqat chet el pasportining asl nusxasi. Asl nusxasiz "
            "imtihonga kiritilmaydi.\n\n"
            "Kechikish mumkin emas — kechikkanlar ham kiritilmaydi.\n\n"
            "Ikkala holatda ham pul qaytarilmaydi, boshqa kunga to'liq "
            "to'lov bilan yozilish mumkin."
        ),
    },
    "faq_q_duration": {
        RU: "Сколько длится",
        UZ_CYRL: "Қанча давом этади",
        UZ_LATN: "Qancha davom etadi",
    },
    "faq_a_duration": {
        RU: (
            "90 минут.\n\n"
            "Экзамен состоит из двух частей: тестовой и устной."
        ),
        UZ_CYRL: (
            "90 дақиқа.\n\n"
            "Имтиҳон икки қисмдан иборат: тест ва оғзаки."
        ),
        UZ_LATN: (
            "90 daqiqa.\n\n"
            "Imtihon ikki qismdan iborat: test va og'zaki."
        ),
    },
    "faq_q_online": {
        RU: "Можно ли сдать онлайн",
        UZ_CYRL: "Онлайн топширса бўладими",
        UZ_LATN: "Onlayn topshirsa bo'ladimi",
    },
    "faq_a_online": {
        RU: (
            "Нет. Экзамен сдаётся только лично, в Ташкенте "
            "по адресу ул. Паркентская, 331."
        ),
        UZ_CYRL: (
            "Йўқ. Имтиҳон фақат шахсан, Тошкентда Паркент кўчаси "
            "331-уй манзилида топширилади."
        ),
        UZ_LATN: (
            "Yo'q. Imtihon faqat shaxsan, Toshkentda Parkent ko'chasi "
            "331-uy manzilida topshiriladi."
        ),
    },
    "faq_q_failed": {
        RU: "Что если не сдал",
        UZ_CYRL: "Топшира олмасам нима бўлади",
        UZ_LATN: "Topshira olmasam nima bo'ladi",
    },
    "faq_a_failed": {
        RU: (
            "Пересдача возможна в другой свободный день, "
            "не в день экзамена.\n\n"
            "Пересдаётся весь экзамен целиком — обе части, даже если одна "
            "была сдана успешно.\n\n"
            "Пересдача платная, по полной стоимости."
        ),
        UZ_CYRL: (
            "Қайта топшириш бошқа бўш кунда мумкин, имтиҳон кунида эмас.\n\n"
            "Имтиҳон тўлиқ қайта топширилади — иккала қисм ҳам, "
            "биттаси муваффақиятли топширилган бўлса ҳам.\n\n"
            "Қайта топшириш пулли, тўлиқ нархда."
        ),
        UZ_LATN: (
            "Qayta topshirish boshqa bo'sh kunda mumkin, imtihon kunida emas.\n\n"
            "Imtihon to'liq qayta topshiriladi — ikkala qism ham, "
            "bittasi muvaffaqiyatli topshirilgan bo'lsa ham.\n\n"
            "Qayta topshirish pulli, to'liq narxda."
        ),
    },

    # --- Оплата и обучение ---
    "faq_q_price": {
        RU: "Сколько стоит",
        UZ_CYRL: "Нархи қанча",
        UZ_LATN: "Narxi qancha",
    },
    "faq_a_price": {
        RU: (
            "Запись на экзамен — 1 400 000 сум.\n\n"
            "Оплата только полная.\n\n"
            "Частями платить нельзя.\n\n"
            "Скидок нет."
        ),
        UZ_CYRL: (
            "Имтиҳонга ёзилиш — 1 400 000 сўм.\n\n"
            "Тўлов фақат тўлиқ.\n\n"
            "Бўлиб тўлаш мумкин эмас.\n\n"
            "Чегирмалар йўқ."
        ),
        UZ_LATN: (
            "Imtihonga yozilish — 1 400 000 so'm.\n\n"
            "To'lov faqat to'liq.\n\n"
            "Bo'lib to'lash mumkin emas.\n\n"
            "Chegirmalar yo'q."
        ),
    },
    "faq_q_how_pay": {
        RU: "Как оплатить",
        UZ_CYRL: "Қандай тўлаш керак",
        UZ_LATN: "Qanday to'lash kerak",
    },
    "faq_a_how_pay": {
        RU: (
            "Ссылки на оплату через Payme или Click бот пришлёт "
            "автоматически после выбора даты.\n\n"
            "После оплаты отправьте скриншот чека."
        ),
        UZ_CYRL: (
            "Payme ёки Click орқали тўлов ҳаволаларини сана танлангандан "
            "сўнг бот автоматик юборади.\n\n"
            "Тўловдан кейин чек скриншотини юборинг."
        ),
        UZ_LATN: (
            "Payme yoki Click orqali to'lov havolalarini sana tanlangandan "
            "so'ng bot avtomatik yuboradi.\n\n"
            "To'lovdan keyin chek skrinshotini yuboring."
        ),
    },
    "faq_q_refund": {
        RU: "Возврат",
        UZ_CYRL: "Пулни қайтариш",
        UZ_LATN: "Pulni qaytarish",
    },
    "faq_a_refund": {
        RU: "Возврат возможен, если предупредить минимум за 2 дня до экзамена.",
        UZ_CYRL: (
            "Пулни қайтариш имтиҳондан камида 2 кун олдин огоҳлантирилса мумкин."
        ),
        UZ_LATN: (
            "Pulni qaytarish imtihondan kamida 2 kun oldin ogohlantirilsa mumkin."
        ),
    },
    "faq_q_training": {
        RU: "Обучение",
        UZ_CYRL: "Ўқув курслари",
        UZ_LATN: "O'quv kurslari",
    },
    "faq_a_training": {
        RU: (
            "Подготовка проводится в Ташкенте и в г. Хазарасп "
            "(Хорезмская область).\n\n"
            "100 000 сум за день, занятия с 9:30 до 17:00.\n\n"
            "Например, запись плюс 2 дня обучения — 1 600 000 сум."
        ),
        UZ_CYRL: (
            "Тайёргарлик Тошкентда ва Хазорасп шаҳрида "
            "(Хоразм вилояти) ўтказилади.\n\n"
            "Кунига 100 000 сўм, дарслар соат 9:30 дан 17:00 гача.\n\n"
            "Масалан, ёзилиш ва 2 кунлик ўқиш — 1 600 000 сўм."
        ),
        UZ_LATN: (
            "Tayyorgarlik Toshkentda va Xazarasp shahrida "
            "(Xorazm viloyati) o'tkaziladi.\n\n"
            "Kuniga 100 000 so'm, darslar soat 9:30 dan 17:00 gacha.\n\n"
            "Masalan, yozilish va 2 kunlik o'qish — 1 600 000 so'm."
        ),
    },
    "faq_q_housing": {
        RU: "Проживание",
        UZ_CYRL: "Яшаш жойи",
        UZ_LATN: "Yashash joyi",
    },
    "faq_a_housing": {
        RU: (
            "Для приезжих из других регионов есть партнёрские хостелы, "
            "60 000 сум за ночь.\n\n"
            "Скажите менеджеру, если нужно место."
        ),
        UZ_CYRL: (
            "Бошқа вилоятлардан келганлар учун ҳамкор хостеллар бор, "
            "бир кечага 60 000 сўм.\n\n"
            "Жой керак бўлса, менежерга айтинг."
        ),
        UZ_LATN: (
            "Boshqa viloyatlardan kelganlar uchun hamkor xostellar bor, "
            "bir kechaga 60 000 so'm.\n\n"
            "Joy kerak bo'lsa, menejerga ayting."
        ),
    },

    # --- Сертификат ---
    "faq_q_patent": {
        RU: "Подходит ли для патента",
        UZ_CYRL: "Патент учун тўғри келадими",
        UZ_LATN: "Patent uchun to'g'ri keladimi",
    },
    "faq_a_patent": {
        RU: "Да. Сертификат предназначен именно для оформления трудового патента.",
        UZ_CYRL: (
            "Ҳа. Сертификат айнан меҳнат патентини расмийлаштириш учун мўлжалланган."
        ),
        UZ_LATN: (
            "Ha. Sertifikat aynan mehnat patentini rasmiylashtirish uchun mo'ljallangan."
        ),
    },
    "faq_q_residence": {
        RU: "Подходит ли для ВНЖ и гражданства",
        UZ_CYRL: "ВНЖ ва фуқаролик учун тўғри келадими",
        UZ_LATN: "VNJ va fuqarolik uchun to'g'ri keladimi",
    },
    "faq_a_residence": {
        RU: "Нет. Для ВНЖ и гражданства этот сертификат не подходит.",
        UZ_CYRL: "Йўқ. ВНЖ ва фуқаролик учун бу сертификат тўғри келмайди.",
        UZ_LATN: "Yo'q. VNJ va fuqarolik uchun bu sertifikat to'g'ri kelmaydi.",
    },
    "faq_q_where": {
        RU: "Где признаётся",
        UZ_CYRL: "Қаерда тан олинади",
        UZ_LATN: "Qayerda tan olinadi",
    },
    "faq_a_where": {
        RU: "Сертификат признаётся на всей территории Российской Федерации.",
        UZ_CYRL: "Сертификат Россия Федерациясининг бутун ҳудудида тан олинади.",
        UZ_LATN: "Sertifikat Rossiya Federatsiyasining butun hududida tan olinadi.",
    },
    "faq_q_validity": {
        RU: "Срок действия",
        UZ_CYRL: "Амал қилиш муддати",
        UZ_LATN: "Amal qilish muddati",
    },
    "faq_a_validity": {
        RU: "3 года с даты сдачи экзамена.",
        UZ_CYRL: "Имтиҳон топширилган кундан бошлаб 3 йил.",
        UZ_LATN: "Imtihon topshirilgan kundan boshlab 3 yil.",
    },
    "faq_q_when_issued": {
        RU: "Когда выдают",
        UZ_CYRL: "Қачон берилади",
        UZ_LATN: "Qachon beriladi",
    },
    "faq_a_when_issued": {
        RU: (
            "В день экзамена.\n\n"
            "Результаты тестовой части — примерно в 13:00, "
            "устной — примерно в 16:00.\n\n"
            "При успешной сдаче обеих частей сертификат выдают примерно к 18:00."
        ),
        UZ_CYRL: (
            "Имтиҳон кунида.\n\n"
            "Тест қисми натижалари — тахминан 13:00 да, "
            "оғзаки қисми — тахминан 16:00 да.\n\n"
            "Иккала қисм муваффақиятли топширилса, сертификат тахминан "
            "18:00 га берилади."
        ),
        UZ_LATN: (
            "Imtihon kunida.\n\n"
            "Test qismi natijalari — taxminan 13:00 da, "
            "og'zaki qismi — taxminan 16:00 da.\n\n"
            "Ikkala qism muvaffaqiyatli topshirilsa, sertifikat taxminan "
            "18:00 ga beriladi."
        ),
    },

    # --- Другое ---
    "faq_q_documents": {
        RU: "Какие документы нужны",
        UZ_CYRL: "Қандай ҳужжатлар керак",
        UZ_LATN: "Qanday hujjatlar kerak",
    },
    "faq_a_documents": {
        RU: (
            "Только фото загранпаспорта и чек об оплате.\n\n"
            "Больше ничего не требуется."
        ),
        UZ_CYRL: (
            "Фақат чет эл паспорти расми ва тўлов чеки.\n\n"
            "Бошқа ҳеч нарса талаб қилинмайди."
        ),
        UZ_LATN: (
            "Faqat chet el pasporti rasmi va to'lov cheki.\n\n"
            "Boshqa hech narsa talab qilinmaydi."
        ),
    },
    "faq_q_friend": {
        RU: "Можно ли записать друга",
        UZ_CYRL: "Дўстимни ёздирсам бўладими",
        UZ_LATN: "Do'stimni yozdirsam bo'ladimi",
    },
    "faq_a_friend": {
        RU: (
            "Да. С одного аккаунта можно оформить несколько записей.\n\n"
            "Для каждого человека нужен свой паспорт."
        ),
        UZ_CYRL: (
            "Ҳа. Бир аккаунтдан бир нечта ёзилишни расмийлаштириш мумкин.\n\n"
            "Ҳар бир одам учун ўз паспорти керак."
        ),
        UZ_LATN: (
            "Ha. Bir akkauntdan bir nechta yozilishni rasmiylashtirish mumkin.\n\n"
            "Har bir odam uchun o'z pasporti kerak."
        ),
    },
    "faq_q_buy": {
        RU: "Можно ли купить без экзамена",
        UZ_CYRL: "Имтиҳонсиз сотиб олса бўладими",
        UZ_LATN: "Imtihonsiz sotib olsa bo'ladimi",
    },
    "faq_a_buy": {
        RU: (
            "Нет. Такой возможности не существует.\n\n"
            "Сертификат выдаётся только после личной сдачи экзамена."
        ),
        UZ_CYRL: (
            "Йўқ. Бундай имконият мавжуд эмас.\n\n"
            "Сертификат фақат шахсан имтиҳон топширилгандан кейин берилади."
        ),
        UZ_LATN: (
            "Yo'q. Bunday imkoniyat mavjud emas.\n\n"
            "Sertifikat faqat shaxsan imtihon topshirilgandan keyin beriladi."
        ),
    },
    "faq_q_manager": {
        RU: "Задать вопрос менеджеру",
        UZ_CYRL: "Менежерга савол бериш",
        UZ_LATN: "Menejerga savol berish",
    },
    "faq_a_manager": {
        RU: (
            "Напишите нашим менеджерам: @Izzatsiddikov или @sardorrazzakoff.\n\n"
            "Они ответят на любой вопрос."
        ),
        UZ_CYRL: (
            "Менежерларимизга ёзинг: @Izzatsiddikov ёки @sardorrazzakoff.\n\n"
            "Улар ҳар қандай саволга жавоб беради."
        ),
        UZ_LATN: (
            "Menejerlarimizga yozing: @Izzatsiddikov yoki @sardorrazzakoff.\n\n"
            "Ular har qanday savolga javob beradi."
        ),
    },
}


# Разделы FAQ и порядок вопросов внутри. Ключи собираются как
# faq_q_<id> для кнопки и faq_a_<id> для ответа.
FAQ_SECTIONS = (
    ("exam", ("dates", "address", "bring", "duration", "online", "failed")),
    ("pay", ("price", "how_pay", "refund", "training", "housing")),
    ("cert", ("patent", "residence", "where", "validity", "when_issued")),
    ("other", ("documents", "friend", "buy", "manager")),
)

# id вопроса -> id раздела, чтобы «Назад» знала, куда возвращать
FAQ_PARENT = {q: sec for sec, qs in FAQ_SECTIONS for q in qs}

# Нажатие на этот вопрос дополнительно уведомляет администраторов
FAQ_MANAGER = "manager"



def lang_or_default(lang: str | None) -> str:
    """Приводит что угодно к поддерживаемому языку."""
    return lang if lang in LANGUAGES else DEFAULT_LANG


def t(key: str, lang: str, **kwargs) -> str:
    translations = TEXTS[key]
    text = translations.get(lang) or translations[DEFAULT_LANG]
    return text.format(**kwargs) if kwargs else text
