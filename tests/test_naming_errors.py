import pytest

from metalesionlab.naming_errors import classify, phonemes, sound_related, tokens, word_zipf, zh_core, zh_segment

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


def test_hindi_chandrabindu_and_anusvara_spellings_match():
    assert classify("आँख", "आंख", "hi").code == "Correct"


def test_alternate_spelling_in_another_script_is_correct():
    # Hindi transcripts may spell an English loanword in Latin letters; Test Studio stores that spelling.
    assert classify("कैक्टस", "Cactus.", "hi", alternates=("cactus",)).code == "Correct"


def test_english_and_spanish_heads_unchanged():
    assert classify("cat", "big dog", judge=fake_judge).head == "dog"
    assert classify("gato", "un perro grande", "es", judge=fake_judge).head == "perro"
