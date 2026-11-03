"""Consejos en español para cada sonido difícil (escritos a mano, para hispanohablantes).

Cada entrada: nombre corto del sonido, cómo producirlo y ejemplos/pares mínimos.
"""
from __future__ import annotations

TIPS: dict[str, dict[str, dict]] = {
    "en": {
        "θ": {"name": "TH sorda (think)", "how": "Saca un poco la punta de la lengua entre los dientes y sopla sin vibrar, como la 'z' de España (zapato). No la cambies por 's', 't' o 'f'.", "pairs": ["think / sink", "three / tree", "thin / tin", "mouth / mouse"]},
        "ð": {"name": "TH sonora (this)", "how": "Igual que la TH de 'think' pero haciendo vibrar la garganta, como la 'd' suave de 'nada'. No digas una 'd' fuerte.", "pairs": ["they / day", "then / den", "breathe / breeze"]},
        "ɪ": {"name": "I corta (ship)", "how": "Una 'i' relajada y corta, a medio camino hacia la 'e'. La boca casi no se estira. Si la alargas suena a 'ee' (sheep).", "pairs": ["ship / sheep", "live / leave", "fill / feel", "bit / beat"]},
        "iː": {"name": "I larga (sheep)", "how": "Una 'i' tensa y larga, sonriendo un poco. Dura casi el doble que la 'i' española.", "pairs": ["sheep / ship", "leave / live", "seat / sit"]},
        "æ": {"name": "A abierta (cat)", "how": "Abre mucho la boca como para decir 'a' pero con la lengua en posición de 'e'. Suena entre 'a' y 'e'.", "pairs": ["cat / cut", "bad / bed", "man / men", "hat / hot"]},
        "ʌ": {"name": "A corta (cup)", "how": "Una 'a' corta y relajada, con la boca a medio abrir, sin redondear. Como una 'a' dicha con desgana.", "pairs": ["cup / cap", "luck / lock", "but / bat"]},
        "ə": {"name": "Schwa (about)", "how": "La vocal más común del inglés: un sonido neutro y muy breve, como un 'eh' sin fuerza. Las sílabas sin acento casi siempre se reducen a esto.", "pairs": ["about", "banana", "the"]},
        "ɚ": {"name": "ER (water)", "how": "Una schwa con la lengua curvada hacia atrás (R americana) a la vez. No pronuncies 'e' + 'r' por separado.", "pairs": ["water", "teacher", "better"]},
        "ɜː": {"name": "ER larga (bird)", "how": "Labios neutros, lengua en el centro de la boca y alargada. Nunca 'ir' ni 'er' a la española.", "pairs": ["bird / bud", "work / walk", "word"]},
        "ɹ": {"name": "R inglesa (red)", "how": "La lengua NO toca el paladar ni vibra: se curva hacia atrás y los labios se redondean un poco. Nada de 'rr'.", "pairs": ["right / light", "red / led", "pray / play"]},
        "v": {"name": "V (very)", "how": "Los dientes de arriba tocan el labio de abajo y vibras. En inglés V y B son sonidos distintos.", "pairs": ["very / berry", "vote / boat", "van / ban"]},
        "z": {"name": "Z sonora (zoo)", "how": "Una 's' que zumba, como una abeja: zzz. Muy común en plurales (dogs) y en 'is', 'was'.", "pairs": ["zoo / sue", "eyes / ice", "prize / price"]},
        "ʃ": {"name": "SH (she)", "how": "Labios hacia adelante y sopla, como cuando pides silencio: shhh.", "pairs": ["she / see", "ship / chip", "wash / watch"]},
        "tʃ": {"name": "CH (chair)", "how": "Como la 'ch' española, pero con los labios un poco adelantados.", "pairs": ["chair / share", "watch / wash", "cheap / jeep"]},
        "dʒ": {"name": "J inglesa (job)", "how": "Como 'ch' pero vibrando, parecido a la 'y' rioplatense fuerte. Nunca la 'j' española.", "pairs": ["job / yob", "jet / yet", "jeep / cheap"]},
        "ʒ": {"name": "ZH (vision)", "how": "Como 'sh' pero vibrando, igual que la 'll/y' argentina (yo, calle).", "pairs": ["vision", "measure", "usual"]},
        "h": {"name": "H aspirada (house)", "how": "Solo aire suave desde la garganta, como empañar un espejo. Mucho más suave que la 'j' española.", "pairs": ["hat / at", "hair / air", "hold / old"]},
        "ŋ": {"name": "NG (sing)", "how": "Se hace con la parte de atrás de la lengua contra el paladar, por la nariz. No pronuncies una 'g' al final.", "pairs": ["sing / sin", "thing / thin", "running"]},
        "ʊ": {"name": "U corta (book)", "how": "Una 'u' corta y relajada, con los labios poco redondeados.", "pairs": ["full / fool", "pull / pool", "look / Luke"]},
        "uː": {"name": "U larga (food)", "how": "Una 'u' tensa y larga, labios bien redondeados.", "pairs": ["fool / full", "pool / pull"]},
        "oʊ": {"name": "O diptongo (go)", "how": "Empieza en 'o' y desliza hacia 'u': 'ou'. Una 'o' plana suena extranjera.", "pairs": ["go", "home", "coat / caught"]},
        "eɪ": {"name": "EI (day)", "how": "Diptongo 'ei' marcado, desliza claramente hacia la 'i'.", "pairs": ["late / let", "pain / pen", "date / debt"]},
        "ɑː": {"name": "A larga (father)", "how": "Una 'a' abierta, larga, con la lengua atrás y la boca bien abierta.", "pairs": ["heart / hut", "cart / cut"]},
        "ɔː": {"name": "O abierta (law)", "how": "Una 'o' muy abierta y larga, con los labios redondeados.", "pairs": ["caught / cot", "walk / work"]},
        "ɑːɹ": {"name": "AR (car)", "how": "'A' larga y abierta seguida de la R inglesa, sin vibrar.", "pairs": ["car", "heart", "park"]},
        "ɔːɹ": {"name": "OR (more)", "how": "'O' abierta seguida de la R inglesa curvada.", "pairs": ["more", "door", "four"]},
        "ɛɹ": {"name": "AIR (there)", "how": "Una 'e' abierta que se desliza hacia la R inglesa (lengua curvada, sin vibrar): 'éər'.", "pairs": ["there", "hair", "where"]},
        "ɪɹ": {"name": "EAR (here)", "how": "Una 'i' corta que se desliza hacia la R inglesa: 'íər'.", "pairs": ["here", "near", "beer"]},
        "ʊɹ": {"name": "OOR (tour)", "how": "Una 'u' corta que se desliza hacia la R inglesa.", "pairs": ["tour", "sure", "pure"]},
        "ɛ": {"name": "E abierta (bed)", "how": "Similar a la 'e' española pero un poco más abierta.", "pairs": ["bed / bad", "pen / pan", "met / mat"]},
        "s": {"name": "S (stop)", "how": "Si la palabra empieza con 's' + consonante, NO añadas una 'e' delante: 'stop', no 'estop'.", "pairs": ["school", "Spain", "street"]},
        "ɾ": {"name": "T/D suave (water)", "how": "En inglés americano la 't' entre vocales se convierte en un toque rápido, como la 'r' simple de 'pero'.", "pairs": ["water", "better", "city"]},
        "t": {"name": "T aspirada (top)", "how": "Al inicio de sílaba acentuada la 't' lleva un soplo de aire. La lengua toca detrás de los dientes, no en ellos.", "pairs": ["top", "time", "tea"]},
        "d": {"name": "D final (good)", "how": "Pronuncia la 'd' al final de palabra, no la omitas ni la conviertas en 't' o 'z'.", "pairs": ["good", "played", "bed / bet"]},
        "p": {"name": "P aspirada (pen)", "how": "Al inicio de palabra, suelta un pequeño soplo de aire después de la 'p'.", "pairs": ["pen / Ben", "pie / buy"]},
        "k": {"name": "K aspirada (cat)", "how": "Al inicio de palabra, suelta un pequeño soplo de aire después de la 'k'.", "pairs": ["cold / gold", "coat / goat"]},
        "w": {"name": "W (water)", "how": "Labios redondeados como para 'u' y luego ábrelos rápido. No añadas una 'g' delante (no 'guater').", "pairs": ["wood / good", "west / vest"]},
        "j": {"name": "Y (yes)", "how": "Una 'i' muy breve que desliza a la vocal siguiente. No la endurezcas como 'll' o 'j'.", "pairs": ["yes / Jess", "year / ear", "yet / jet"]},
        "aɪ": {"name": "AI (time)", "how": "Diptongo 'ai' completo y marcado.", "pairs": ["time", "light", "buy"]},
        "aʊ": {"name": "AU (now)", "how": "Diptongo 'au' completo.", "pairs": ["now", "house", "down"]},
        "ɔɪ": {"name": "OI (boy)", "how": "Diptongo 'oi' marcado.", "pairs": ["boy", "voice", "coin"]},
    },
    "fr": {
        "ʁ": {"name": "R francesa (rouge)", "how": "Se hace en la garganta, como una 'j' española muy suave y vibrando. Nunca 'rr' con la punta de la lengua.", "pairs": ["rouge", "Paris", "très"]},
        "y": {"name": "U francesa (tu)", "how": "Pon la lengua para decir 'i' y redondea los labios como para 'u'. Distinta de 'ou'.", "pairs": ["tu / tout", "vu / vous", "rue / roue"]},
        "u": {"name": "OU (vous)", "how": "Como la 'u' española, bien redondeada. No la confundas con la 'u' francesa (tu).", "pairs": ["vous / vu", "tout / tu", "dessous / dessus"]},
        "ø": {"name": "EU cerrada (deux)", "how": "Lengua en posición de 'e' y labios redondeados como para 'o'.", "pairs": ["deux", "peu", "feu"]},
        "œ": {"name": "EU abierta (peur)", "how": "Como 'eu' cerrada pero con la boca más abierta.", "pairs": ["peur", "sœur", "jeune / jeûne"]},
        "ə": {"name": "E muda (le)", "how": "Una vocal neutra y breve; a menudo desaparece en el habla rápida.", "pairs": ["le", "petit", "demain"]},
        "ɑ̃": {"name": "Nasal AN (temps)", "how": "Una 'a' abierta dejando salir el aire por la nariz, SIN pronunciar la 'n'.", "pairs": ["temps / ton", "sans / son", "lent / long"]},
        "ɔ̃": {"name": "Nasal ON (bon)", "how": "Una 'o' redondeada por la nariz, sin cerrar con 'n'.", "pairs": ["bon / banc", "long / lent", "son / sans"]},
        "ɛ̃": {"name": "Nasal IN (vin)", "how": "Una 'e' abierta por la nariz, sin pronunciar la 'n'.", "pairs": ["vin / vent", "pain / pont", "main"]},
        "œ̃": {"name": "Nasal UN (un)", "how": "Hoy en día casi siempre se pronuncia igual que 'in' (ɛ̃).", "pairs": ["un", "brun", "parfum"]},
        "ʒ": {"name": "J francesa (je)", "how": "Como la 'll/y' argentina (yo): un 'sh' que vibra. Nunca la 'j' española.", "pairs": ["je", "jour", "manger"]},
        "ʃ": {"name": "CH francesa (chat)", "how": "Labios adelantados y soplo: shhh. No es la 'ch' española.", "pairs": ["chat", "chose", "chercher"]},
        "z": {"name": "Z sonora (maison)", "how": "Una 's' que zumba. La 's' entre vocales suena así.", "pairs": ["maison / maçon", "poison / poisson", "désert / dessert"]},
        "v": {"name": "V (vin)", "how": "Dientes de arriba sobre el labio inferior, vibrando. Distinta de la 'b'.", "pairs": ["vin / bain", "vous / bout"]},
        "e": {"name": "É cerrada (été)", "how": "Una 'e' más cerrada y tensa que la española, sonriendo.", "pairs": ["été", "parler", "les"]},
        "ɛ": {"name": "È abierta (mère)", "how": "Una 'e' más abierta que la española.", "pairs": ["mère", "fait", "lait / les"]},
        "o": {"name": "O cerrada (beau)", "how": "Una 'o' cerrada con labios muy redondeados.", "pairs": ["beau / bol", "eau", "côte / cote"]},
        "ɔ": {"name": "O abierta (bol)", "how": "Una 'o' más abierta.", "pairs": ["bol", "porte", "école"]},
        "ɥ": {"name": "UI (huit)", "how": "La 'u' francesa (tu) muy breve deslizando a la vocal siguiente.", "pairs": ["huit", "nuit", "lui"]},
        "ɲ": {"name": "GN (montagne)", "how": "Como la 'ñ' española.", "pairs": ["montagne", "gagner"]},
    },
}

GENERIC = {
    "name": "sonido",
    "how": "Escucha el audio de referencia a velocidad lenta y repite imitando la posición de la boca.",
    "pairs": [],
}


def tip_for(lang: str, phone: str) -> dict:
    t = TIPS.get(lang, {}).get(phone)
    if t:
        return {"phone": phone, **t}
    # Prueba sin marcas de longitud (ː) por si espeak usó una variante.
    base = phone.replace("ː", "")
    t = TIPS.get(lang, {}).get(base)
    return {"phone": phone, **(t or GENERIC)}
