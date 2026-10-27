import pytest

from metalesionlab.naming_errors import (ar_norm, classify, ja_kana, phonemes, sound_related, tokens, word_zipf,
                                         zh_core, zh_segment)

ASSOCIATES = {("cat", "milk"), ("umbrella", "rain"), ("gato", "perro"), ("gato", "pato"), ("cuchara", "tenedor")}


def fake_judge(target, response, lang):
    return (target, response) in ASSOCIATES


@pytest.mark.parametrize("target,response,expected", [
    ("cat", "cat", "Correct"),
    ("cat", "Cats.", "Correct"),
    ("cat", "a black cat", "Correct"),
    ("cat", "", "NoResponse"),
    ("cat", "um, I don't know", "NoResponse"),
    ("cat", "dog", "Semantic"),
    ("cat", "milk", "Semantic"),       # association, from the judge
    ("cat", "hat", "Formal"),
    ("cat", "rat", "Mixed"),
    ("skirt", "shirt", "Mixed"),
    ("anchor", "ankle", "Formal"),
    ("cat", "chair", "Unrelated"),
    ("bench", "river", "Unrelated"),
    ("cat", "cag", "Nonword"),
    ("kettle", "kettin", "Nonword"),
    ("ladder", "blorf", "Neologism"),
    ("bench", "a seat in the park", "Description"),
    ("umbrella", "rain", "Semantic"),
])
def test_english_codes(target, response, expected):
    assert classify(target, response, "en", judge=fake_judge).code == expected


def test_alternate_names_count_as_correct():
    assert classify("couch", "sofa", alternates=("sofa",)).code == "Correct"
    assert classify("couch", "sofa").code == "Semantic"


@pytest.mark.parametrize("target,response,expected", [
    ("gato", "gato", "Correct"),
    ("gato", "el gato", "Correct"),
    ("gato", "gatos", "Correct"),
    ("gato", "no sé", "NoResponse"),
    ("gato", "perro", "Semantic"),
    ("gato", "pato", "Mixed"),
    ("gato", "silla", "Unrelated"),
    ("gato", "gapo", "Nonword"),
])
def test_spanish_codes(target, response, expected):
    assert classify(target, response, "es", judge=fake_judge).code == expected


def test_accents_do_not_count_as_errors():
    assert classify("iglú", "iglu", "es").code == "Correct"
    assert classify("helicóptero", "helicoptero", "es").code == "Correct"
    assert classify("iglu", "iglú", "es").code == "Correct"


def test_spanish_spelling_rules():
    assert phonemes("queso", "es")[0] == ("k", "e", "s", "o")
    assert phonemes("cielo", "es")[0][0] == "s"
    assert phonemes("árbol", "es") == (("a", "r", "b", "o", "l"), 0)


def test_sound_relation_uses_cmu_for_words_and_spelling_for_nonwords():
    assert phonemes("cat", "en")[0] == ("K", "AE", "T")
    assert sound_related("cat", "cag", "en")
    assert not sound_related("cat", "dog", "en")


# --- French, Brazilian Portuguese, Hindi and Mandarin Chinese (Oct 26) ----------------------

MORE_RELATED = {("chat", "chien"), ("gato", "cachorro"), ("बिल्ली", "कुत्ता"), ("घोंघा", "केकड़ा"),
                ("猫", "狗"), ("雨伞", "雨衣"), ("梯子", "楼梯"), ("长椅", "长凳")}


def more_judge(target, response, lang):
    return (target, response) in MORE_RELATED


@pytest.mark.parametrize("target,response,expected", [
    ("chat", "le chat", "Correct"),
    ("chat", "Chats.", "Correct"),
    ("chat", "c'est un chat noir", "Correct"),
    ("ancre", "L’ancre", "Correct"),           # elided article
    ("ciseaux", "des ciseaux", "Correct"),
    ("cheval", "chevaux", "Correct"),
    ("gâteau", "gâteaux", "Correct"),
    ("chat", "c'est un chien", "Mixed"),       # same category; chat and chien share the first sound
    ("chat", "chapeau", "Formal"),
    ("chat", "chab", "Nonword"),
    ("chat", "euh, je sais pas", "NoResponse"),
    ("banc", "un endroit pour s'asseoir", "Description"),
])
def test_french_codes(target, response, expected):
    assert classify(target, response, "fr", judge=more_judge).code == expected


@pytest.mark.parametrize("target,response,expected", [
    ("gato", "o gato", "Correct"),
    ("gato", "gatos", "Correct"),
    ("gato", "é um gato", "Correct"),
    ("colher", "colheres", "Correct"),
    ("avião", "aviões", "Correct"),
    ("guarda-chuva", "guarda chuva", "Correct"),   # the transcript may drop the hyphen
    ("guarda-chuva", "um guarda-chuva", "Correct"),
    ("guarda-chuva", "guarda-chuvas", "Correct"),
    ("gato", "cachorro", "Semantic"),
    ("gato", "não sei", "NoResponse"),
])
def test_portuguese_codes(target, response, expected):
    assert classify(target, response, "pt", judge=more_judge).code == expected


@pytest.mark.parametrize("target,response,expected", [
    ("बिल्ली", "बिल्ली", "Correct"),
    ("बिल्ली", "यह बिल्ली है", "Correct"),
    ("बिल्ली", "एक काली बिल्ली", "Correct"),
    ("बिल्ली", "बिल्लियाँ", "Correct"),
    ("बिल्ली", "बिल्लियां", "Correct"),
    ("बिल्ली", "बिल्ली को", "Correct"),         # with a postposition
    ("छाता", "छाते", "Correct"),
    ("सीढ़ी", "सीढ़ी", "Correct"),  # सीढ़ी: nukta precomposed vs. not
    ("बिल्ली", "यह कुत्ता है", "Semantic"),
    ("घोंघा", "केकड़ा", "Semantic"),             # missing from wordfreq's small Hindi list, still a word
    ("बिल्ली", "मुझे नहीं पता।", "NoResponse"),
    ("बेंच", "पार्क में बैठने की जगह", "Description"),
])
def test_hindi_codes(target, response, expected):
    assert classify(target, response, "hi", judge=more_judge).code == expected


def test_tokens_keep_devanagari_vowel_signs():
    assert tokens("बिल्ली, छाता। सीढ़ी") == ["बिल्ली", "छाता", "सीढ़ी"]


@pytest.mark.parametrize("target,response,expected", [
    ("猫", "猫", "Correct"),
    ("猫", "这是一只猫。", "Correct"),     # frame and measure word
    ("猫", "小猫", "Correct"),
    ("猫", "黑猫", "Correct"),
    ("猫", "猫在睡觉", "Correct"),
    ("猫", "熊猫", "Unrelated"),          # panda is not a kind of cat (and this judge says unrelated)
    ("猫", "一只狗", "Semantic"),
    ("猫", "黑色的狗", "Semantic"),
    ("猫", "我不知道啊", "NoResponse"),
    ("雨伞", "一把雨伞", "Correct"),
    ("雨伞", "雨傘", "Correct"),           # traditional characters
    ("雨伞", "雨衣", "Semantic"),          # shares 雨, which is meaning, not sound
    ("锯子", "一把锯", "Correct"),         # 子 suffix
    ("水壶", "电水壶", "Correct"),
    ("梯子", "楼梯", "Semantic"),          # stairs, not a ladder
    ("长椅", "可以坐的地方", "Description"),  # three words, though no spaces
    ("雨伞", "下雨用的", "Description"),
])
def test_chinese_codes(target, response, expected):
    assert classify(target, response, "zh", judge=more_judge).code == expected


def test_chinese_segmentation_and_frequency_need_no_jieba():
    assert zh_core("这是一只黑色的小狗") == "黑色的小狗"
    assert zh_segment("黑色的小狗") == ["黑色", "的", "小狗"]
    assert word_zipf("猫", "zh") > 4 and word_zipf("鞡鞡鞡", "zh") == 0
    assert not sound_related("雨伞", "雨衣", "zh")


@pytest.mark.parametrize("lang,target,response,expected", [
    ("fr", "bouilloire", "bouilloir", "Correct"),   # transcripts seen on Oct 26
    ("fr", "igloo", "Iglou.", "Correct"),
    ("pt", "serrote", "Cerrote.", "Correct"),
    ("pt", "harpa", "arpa", "Correct"),
    ("pt", "tesoura", "Cisoura.", "Nonword"),         # t and s differ: still an error
    ("fr", "chat", "chatte", "Mixed"),                # a real word is never respelled
    ("fr", "chat", "chab", "Nonword"),
])
def test_misspelled_target_in_a_transcript_is_correct(lang, target, response, expected):
    assert classify(target, response, lang, judge=lambda t, r, l: (t, r) == ("chat", "chatte")).code == expected


@pytest.mark.parametrize("lang,target,response,expected", [
    ("fr", "ancre", "Une encre.", "Correct"),   # homophones: the transcript chose the other spelling
    ("fr", "scie", "Si.", "Correct"),
    ("fr", "ancre", "Entre.", "Formal"),        # /ɑ̃tʁ/ is not /ɑ̃kʁ/
    ("fr", "banc", "Dans.", "Formal"),          # same nasal vowel
    ("fr", "chat", "lit", "Unrelated"),         # both end in a silent t, which isn't a shared sound
    ("pt", "serrote", "Um cerrote", "Correct"),
    ("pt", "cenoura", "Senoura.", "Correct"),
    ("pt", "apito", "Capítulo,", "Formal"),
])
def test_spoken_homophones_and_sound_relations(lang, target, response, expected):
    assert classify(target, response, lang, judge=lambda t, r, l: False).code == expected


def test_french_and_portuguese_spelling_rules():
    assert phonemes("chat", "fr")[0] == ("ʃ", "a")
    assert phonemes("bouilloire", "fr")[0] == ("b", "u", "j", "w", "a", "ʁ")
    assert phonemes("chien", "fr")[0][0] == phonemes("chat", "fr")[0][0]
    assert phonemes("scie", "fr")[0] == phonemes("si", "fr")[0]
    assert phonemes("escada", "pt") == (("e", "s", "k", "a", "d", "a"), 3)  # es-CA-da
    assert phonemes("âncora", "pt") == (("ã", "k", "o", "r", "a"), 0)
    assert phonemes("colher", "pt")[0] == ("k", "o", "ʎ", "e", "r")


@pytest.mark.parametrize("lang,target,response,expected,head", [
    ("fr", "chat", "UnUn chien.", "Mixed", "chien"),    # transcripts double a leading article
    ("pt", "gato", "OO cachorro.", "Semantic", "cachorro"),
    ("hi", "बिल्ली", "यहयह कुत्ता है।", "Semantic", "कुत्ता"),
    ("fr", "chat", "UneUne carotte.", "Unrelated", "carotte"),
])
def test_doubled_article_in_a_transcript(lang, target, response, expected, head):
    c = classify(target, response, lang, judge=more_judge)
    assert (c.code, c.head) == (expected, head)


def test_doubled_name_in_a_transcript():
    assert classify("umbrella", "umbrellaumbrella").code == "Correct"   # seen with Samantha, Oct 26
    assert classify("couscous", "couscous").code == "Correct"
    assert classify("cat", "dodo", judge=fake_judge).head == "dodo"     # only accepted names are undoubled


def test_article_fused_onto_the_name_in_a_transcript():
    assert classify("iglú", "Uniglú.", "es").code == "Correct"        # Paulina voice, "un iglú"
    assert classify("chat", "lechat", "fr").code == "Correct"
    assert classify("chat", "machat", "fr", judge=lambda *a: False).code != "Correct"  # "ma" isn't an article


def test_hindi_chandrabindu_and_anusvara_spellings_match():
    assert classify("आँख", "आंख", "hi").code == "Correct"


def test_alternate_spelling_in_another_script_is_correct():
    # Hindi transcripts may spell an English loanword in Latin letters; Test Studio stores that spelling.
    assert classify("कैक्टस", "Cactus.", "hi", alternates=("cactus",)).code == "Correct"


def test_english_and_spanish_heads_unchanged():
    assert classify("cat", "big dog", judge=fake_judge).head == "dog"
    assert classify("gato", "un perro grande", "es", judge=fake_judge).head == "perro"


@pytest.mark.parametrize("target,response,expected", [
    ("pineapple", "kiwifruit", "Semantic"),  # rare in wordfreq, not in CMU: a compound of kiwi + fruit
    ("bench", "footstool", "Semantic"),      # a WordNet lemma
    ("cat", "Caraloon", "Nonword"),          # cara + loon, but "cara" isn't a WordNet lemma
    ("ladder", "blorf", "Neologism"),
    ("cat", "cag", "Nonword"),
])
def test_rare_english_real_words_are_words(target, response, expected):
    judge = lambda t, r, l: (t, r) == ("pineapple", "kiwifruit")  # noqa: E731
    assert classify(target, response, "en", judge=judge).code == expected


@pytest.mark.parametrize("target,response", [("sierra", "Cierra."), ("cuchara", "Kuchara"), ("zanahoria", "sanahoria")])
def test_spanish_homophone_spellings_are_correct(target, response):
    # Spoken scoring: the transcript picked another spelling of the same sounds.
    assert classify(target, response, "es", judge=lambda t, r, l: False).code == "Correct"


# --- German, Italian, Dutch, Japanese, Korean, Arabic, Turkish, Polish, Indonesian, Vietnamese (Oct 27) ---

OCT27_RELATED = {("katze", "hund"), ("gatto", "cane"), ("kat", "hond"), ("猫", "犬"), ("はしご", "脚立"),
                 ("고양이", "강아지"), ("قطة", "كلب"), ("kedi", "köpek"), ("kot", "pies"), ("kucing", "anjing"),
                 ("mèo", "chó"), ("kessel", "teekanne")}


def oct27_judge(target, response, lang):
    return (target, response) in OCT27_RELATED


@pytest.mark.parametrize("target,response,expected", [
    ("katze", "Die Katze.", "Correct"),
    ("katze", "Das ist eine schwarze Katze", "Correct"),
    ("katze", "Katzen", "Correct"),
    ("bank", "Bänke", "Correct"),               # plural with an umlaut
    ("fahrrad", "Fahrräder", "Correct"),
    ("kessel", "Teekessel", "Correct"),         # compound, head last: Muse Spark's name for the kettle picture
    ("schirm", "Regenschirm", "Correct"),
    ("regenschirm", "Regen Schirm", "Correct"),  # a compound the transcript split
    ("kessel", "Teekanne", "Mixed"),            # a teapot: no shared head; letters shared, by the gendered rule
    ("katze", "Hund", "Semantic"),
    ("kerze", "Die Karte.", "Formal"),          # seen with Anna, Oct 27
    ("katze", "ich weiß nicht", "NoResponse"),
])
def test_german_codes(target, response, expected):
    assert classify(target, response, "de", judge=oct27_judge).code == expected


@pytest.mark.parametrize("target,response,expected", [
    ("gatto", "un gatto", "Correct"),
    ("gatto", "il gatto nero", "Correct"),
    ("gatto", "gatti", "Correct"),
    ("lumaca", "lumache", "Correct"),
    ("cucchiaio", "cucchiai", "Correct"),
    ("ancora", "l'ancora", "Correct"),          # elided article
    ("arpa", "Un'arpa.", "Correct"),
    ("lumaca", "L'umaca.", "Correct"),          # the transcript put an apostrophe inside the name (Alice, Oct 27)
    ("arpa", "Un'arta.", "Formal"),
    ("gatto", "cane", "Semantic"),
    ("gatto", "non lo so", "NoResponse"),
])
def test_italian_codes(target, response, expected):
    assert classify(target, response, "it", judge=oct27_judge).code == expected


@pytest.mark.parametrize("target,response,expected", [
    ("kat", "een kat", "Correct"),
    ("kat", "katten", "Correct"),               # doubled consonant
    ("schaar", "scharen", "Correct"),           # long vowel written once
    ("paraplu", "paraplu's", "Correct"),
    ("bank", "een bankje", "Correct"),          # diminutive
    ("ketel", "fluitketel", "Correct"),         # compound, head last
    ("ladder", "trapladder", "Correct"),        # Muse Spark's name for the stepladder
    ("kat", "hond", "Semantic"),
    ("lepel", "een label", "Formal"),           # seen with Xander and Ellen, Oct 27
    ("kat", "geen idee", "NoResponse"),
])
def test_dutch_codes(target, response, expected):
    assert classify(target, response, "nl", judge=oct27_judge).code == expected


def kana_reader(text):
    return {"怒り": "いかり", "片つむりです": "かたつむりです", "夜間です": "やかんです"}.get(text, text)


@pytest.mark.parametrize("target,alternates,response,expected", [
    ("猫", ("ねこ", "ネコ"), "猫", "Correct"),
    ("猫", ("ねこ", "ネコ"), "ネコ", "Correct"),
    ("猫", (), "これは猫です。", "Correct"),     # frame and copula
    ("猫", (), "子猫", "Correct"),               # head last
    ("やかん", (), "ヤカン", "Correct"),         # katakana and hiragana are the same
    ("ベンチ", (), "ﾍﾞﾝﾁ", "Correct"),           # half-width katakana
    ("自転車", (), "自転車に乗る", "Correct"),
    ("錨", ("いかり", "イカリ"), "怒り。", "Correct"),         # homophone kanji, compared by reading (Kyoko, Oct 27)
    ("カタツムリ", ("かたつむり", "蝸牛"), "片つむりです。", "Correct"),
    ("やかん", ("ヤカン", "薬缶"), "夜間です。", "Correct"),
    ("猫", ("ねこ",), "犬", "Semantic"),
    ("はしご", ("ハシゴ", "梯子"), "脚立", "Semantic"),       # stepladder: Muse Spark's name for the picture
    ("傘", ("かさ",), "雨の日に使うもの", "Description"),
    ("猫", ("ねこ",), "わかりません", "NoResponse"),
])
def test_japanese_codes(target, alternates, response, expected):
    def judge(t, r, lang):
        return oct27_judge(t, r, lang)
    judge.reading = kana_reader
    assert classify(target, response, "ja", alternates=alternates, judge=judge).code == expected


def test_japanese_homophone_needs_a_reader():
    # Without a reader, kanji can't be compared by sound: 怒り ("anger") is another word.
    assert classify("錨", "怒り", "ja", alternates=("いかり",), judge=oct27_judge).code == "Unrelated"
    assert phonemes("ねこ", "ja")[0] == ("ね", "こ") and phonemes("猫", "ja")[0] == ()


@pytest.mark.parametrize("target,response,expected", [
    ("고양이", "고양이", "Correct"),
    ("고양이", "고양이가", "Correct"),           # subject particle
    ("고양이", "이것은 고양이예요.", "Correct"),  # frame and copula
    ("우산", "우산이에요", "Correct"),
    ("장갑", "고무장갑", "Correct"),             # compound ending in a two-syllable name
    ("톱", "데스크톱", "Formal"),                # but a one-syllable name must stand alone
    ("파인애플", "파이네플", "Correct"),         # liaison spelling of the same sounds (Yuna, Oct 27)
    ("닻", "다치에요", "Correct"),               # 닻이에요 said with liaison
    ("고양이", "강아지가", "Mixed"),             # particle dropped before coding; both start with ㄱ
    ("고양이", "몰라요", "NoResponse"),
])
def test_korean_codes(target, response, expected):
    assert classify(target, response, "ko", judge=oct27_judge).code == expected


@pytest.mark.parametrize("target,response,expected", [
    ("قطة", "القطة", "Correct"),                # al-
    ("قطة", "قطّة", "Correct"),                  # with a shadda
    ("قطة", "قطه", "Correct"),                  # ta marbuta written as ha
    ("قطة", "القطى", "Correct"),                # or as a final alef maqsura (Majed, Oct 27)
    ("مرساة", "مرسى", "Formal"),                # a harbor: another word, not the anchor (Majed, Oct 27)
    ("أناناس", "اناناس", "Correct"),            # hamza left off the alef
    ("أناناس", "أنا ناس", "Correct"),           # split by the transcript (Majed, Oct 27)
    ("جزرة", "جزر", "Correct"),                 # collective: Muse Spark's name for one carrot picture
    ("شمعة", "شمعات", "Correct"),
    ("قطة", "هذه قطة", "Correct"),
    ("قطة", "الكلب", "Semantic"),
    ("صفارة", "السفارة", "Formal"),             # "the embassy"
    ("قطة", "لا أعرف", "NoResponse"),
])
def test_arabic_codes(target, response, expected):
    assert classify(target, response, "ar", judge=oct27_judge).code == expected


@pytest.mark.parametrize("lang,target,response,expected", [
    ("tr", "kedi", "bir kedi", "Correct"),
    ("tr", "kedi", "Bu bir kedi.", "Correct"),
    ("tr", "kedi", "kediler", "Correct"),
    ("tr", "kaşık", "kaşıklar", "Correct"),
    ("tr", "iglo", "İglo", "Correct"),          # dotted capital İ (Muse Spark, Oct 27)
    ("tr", "kedi", "köpek", "Mixed"),            # both start with k
    ("tr", "kedi", "bilmiyorum", "NoResponse"),
    ("pl", "kot", "To jest kot.", "Correct"),
    ("pl", "kot", "pies", "Semantic"),
    ("pl", "kot", "nie wiem", "NoResponse"),
    ("id", "kucing", "ini kucing", "Correct"),
    ("id", "kucing", "seekor kucing", "Correct"),  # classifier
    ("id", "kucing", "kucing-kucing", "Correct"),  # plural by doubling
    ("id", "sarung tangan", "sarungtangan", "Correct"),
    ("id", "sarung tangan", "sarungsarung tangan,", "Correct"),  # first word doubled (Damayanti, Oct 27)
    ("id", "kucing", "anjing", "Mixed"),         # both end in g
    ("id", "kucing", "tidak tahu", "NoResponse"),
])
def test_turkish_polish_and_indonesian_codes(lang, target, response, expected):
    assert classify(target, response, lang, judge=oct27_judge).code == expected


@pytest.mark.parametrize("target,response,expected", [
    ("mèo", "con mèo", "Correct"),              # classifier
    ("ô", "cái ô", "Correct"),
    ("cà rốt", "củ cà rốt", "Correct"),
    ("cà rốt", "càrốt", "Correct"),             # syllables run together
    ("xe đạp", "xexe đạp,", "Correct"),         # first syllable doubled (Linh, Oct 27)
    ("thìa", "thia", "Correct"),                # every mark dropped
    ("đàn hạc", "dan hac", "Correct"),
    ("mèo", "méo", "Formal"),                   # another tone is another word ("bent")
    ("mèo", "con chó", "Semantic"),
    ("mèo", "không biết", "NoResponse"),
])
def test_vietnamese_codes(target, response, expected):
    assert classify(target, response, "vi", judge=oct27_judge).code == expected


def test_new_language_helpers():
    assert tokens("İglo") == ["iglo"]
    assert ar_norm("أَنَانَاس") == "اناناس" and ar_norm("قطة") == "قطه"
    assert ja_kana("ネコ") == "ねこ" and ja_kana("ﾍﾞﾝﾁ") == "べんち"
    assert phonemes("파인애플", "ko") == phonemes("파이네플", "ko")
    assert word_zipf("猫", "ja") > 4 and word_zipf("고양이", "ko") > 3  # no MeCab needed


def test_earlier_languages_keep_their_codes():
    # The Oct 27 rules are per language: Spanish still folds accents, English doesn't join split words.
    assert classify("iglú", "iglu", "es").code == "Correct"
    assert classify("sunflower", "sun flower", "en", judge=fake_judge).code != "Correct"
    assert classify("chat", "UnUn chien.", "fr", judge=more_judge).head == "chien"
