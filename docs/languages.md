# Language support

Measured on **Oct 26, 2026** (six languages) and **Oct 27** (ten more: see [Ten more languages](#ten-more-languages-oct-27)). "Any language" means you can type a word list in any language and Test Studio will try it. This page lists what we have actually measured. The same numbers, with every transcript, are in [`public_data/language_support.json`](../public_data/language_support.json).

## At a glance

| Language | Picture set (kept/20) | Named by Muse Spark (/20) | Spoken, bare word (/20, per voice) | Spoken, recommended form (/20, per voice or run) | Status |
|---|---|---|---|---|---|
| English | 20 | 20 | 20, 17 | bare word: 20, 17 | **verified** |
| Spanish | 19 | 19 | 13, 18 | with the article: 19, 20 | **verified** (name with the article) |
| French | 20 | 20 | 16, 15 | with the article: 19, 20 | **verified** (name with the article) |
| Brazilian Portuguese | 20 | 20 | 17 | with the article: 19, 18 | **verified** (name with the article) |
| Mandarin Chinese | 18 | 19 | 14, 14 | with a measure word: 18, 17 | **works with review** |
| Hindi | 18 | 18 | 14, 11 | bare word: 14, 11 | **experimental** |
| German | 20 | 20 | 16, 15 | *Das ist eine Katze*: 20, 19 | **verified** (answer in a short sentence) |
| Turkish | 20 | 20 | 17, 15 | with *bir*: 18, 19 | **verified** (name with *bir*) |
| Polish | 19 | 19 | 14, 15 | *To jest kot*: 20, 19 | **verified** (answer in a short sentence) |
| Indonesian | 19 | 19 | 19, 18 | *Ini kucing*: 20, 20 | **verified** |
| Italian | 19 | 19 | 17, 17 | with the article: 18, 17 | **works with review** |
| Arabic | 19 | 19 | 14, 14 | with al-: 16, 17 | **works with review** |
| Vietnamese | 20 | 20 | 14, 15 | with a classifier: 15, 18 | **works with review** |
| Dutch | 20 | 20 | 14, 13 | with the article: 16, 16 | **works with review** |
| Japanese | 19 | 19 | 13, 15 | with *です*: 16, 15 | **experimental** |
| Korean | 20 | 20 | 13, 14 | bare word: 13, 14 | **experimental** |
| Any other language | not measured | not measured | not measured | not measured | **experimental** |

The ten languages added on Oct 27 reuse the English demo set's pictures, so their picture-set column counts pictures that Muse Spark named correctly in the language; SAM's checks come from the English set. See [Ten more languages](#ten-more-languages-oct-27).

- **Picture set:** words with at least one picture that passed both checks: SAM 3.1 sees one clear object, and Muse Spark's name for it is coded Correct. These are first-pass numbers, before any reviewer edits.
- **Named by Muse Spark:** words for which Muse Spark gave a Correct name to at least one of the two candidate pictures.
- **Spoken:** each word was spoken by a synthesized macOS voice, transcribed by Muse Voice Transcribe with the language hint, then coded by the Scorer's rules with the set's accepted alternates. The count is responses coded Correct.

  | Language | Voices |
  |---|---|
  | English | Samantha (US), Daniel (UK) |
  | Spanish | Mónica (Spain), Paulina (Mexico) |
  | French | Thomas (France), Amélie (Canada) |
  | Brazilian Portuguese | Luciana, two runs; macOS has no second Brazilian voice |
  | Mandarin | Tingting (mainland), Meijia (Taiwan) |
  | Hindi | Lekha, two runs; the only Hindi voice |
  | Dutch | Xander (Netherlands), Ellen (Belgium) |
  | German, Italian, Japanese, Korean, Arabic, Turkish, Polish, Indonesian, Vietnamese | Anna, Alice, Kyoko, Yuna, Majed, Yelda, Zosia, Damayanti, Linh: two runs each; each is the only natural voice for its language on macOS |

- Each number is one run of 20. Expect a couple of points of run-to-run variation: two identical Hindi runs gave 14 and 11.

### Status levels

- **verified:**
  - picture set and Muse Spark naming are at least 19/20;
  - spoken naming averages at least 18/20 over two voices or runs, in the recommended answer form;
  - the language's scoring rules have unit tests and a live check.

  As in every language, a person still reviews the codes.
- **works with review:** pictures and naming work, and spoken naming is mostly right in the recommended form. Known gaps mean a person should check every code that isn't Correct. For the Oct 27 languages, "mostly right" meant at least 16/20 averaged over two runs.
- **experimental:** measured below that, or not measured. Fine for building picture sets; don't rely on automatic spoken scoring yet.

## What to tell test-takers

- **Spanish, French, Portuguese:** "Say the name with *un/una*, *un/une* or *um/uma*" (*un gato*, *un chat*, *um gato*). With bare words, short names are often heard as other words: *banc* → "Dans", *ancla* → "Acla".
- **Mandarin:** "Say it with a measure word" (*一只猫*, *一把剪刀*). Bare one-syllable names come back as homophones (*锚* → 毛).
- **English, Hindi:** the bare word. For both, the article or a frame (*यह … है*) didn't help.
- **German:** "Answer with *Das ist ein …* or *Das ist eine …*". *Der/die/das* alone gave 17/20 twice.
- **Polish:** "Answer with *To jest …*". **Indonesian:** "Answer with *Ini …*" (bare words also work: 19 and 18).
- **Turkish:** "Say the name with *bir*" (*bir kedi*). **Italian, Dutch:** with *un/una/un'* or *een*. **Arabic:** with *al-* (*القطة*).
- **Vietnamese:** "Say it with its classifier" (*con mèo*, *cái ô*). **Japanese:** with *です* (*猫です*). **Korean:** the bare word; *예요/이에요* didn't help.
- In every language, a reviewer should listen to or re-record any response that comes back empty. The Scorer codes an empty transcript as No response.

## What the landing page can claim

> Build picture tests in any language: picture sets are checked in 16. Automatic spoken scoring is verified in English, Spanish, French, Brazilian Portuguese, German, Turkish, Polish and Indonesian, works with a reviewer in Mandarin, Italian, Dutch, Arabic and Vietnamese, and is experimental in Hindi, Japanese, Korean and other languages.

Don't claim "scores speech in any language". Pictures and typed scoring travel well. Spoken scoring has been measured in 16 languages, with synthesized voices only (one voice for most of them), and depends on how people answer. Muse Voice Transcribe takes a language hint for 25 languages; the other nine (Bengali, Hebrew, Kannada, Malay, Marathi, Tagalog, Tamil, Telugu, Thai) and every other language are not measured.

## Method

**Word lists.** The 20-word English demo list, translated, with ambiguous words pinned as `word: meaning`.

| English | French | Brazilian Portuguese | Hindi | Mandarin |
|---|---|---|---|---|
| cat | chat | gato | बिल्ली | 猫 |
| umbrella | parapluie | guarda-chuva | छाता | 雨伞 |
| anchor | ancre: anchor | âncora | लंगर: anchor | 锚 |
| kettle | bouilloire | chaleira | केतली | 水壶: kettle |
| ladder | échelle: ladder | escada: ladder | सीढ़ी: ladder | 梯子 |
| bench | banc: bench | banco: bench | बेंच | 长椅 |
| glove | gant | luva | दस्ताना | 手套 |
| spoon | cuillère | colher: spoon | चम्मच | 勺子 |
| carrot | carotte | cenoura | गाजर | 胡萝卜 |
| bicycle | vélo | bicicleta | साइकिल | 自行车 |
| scissors | ciseaux | tesoura | कैंची | 剪刀 |
| candle | bougie: candle | vela: candle | मोमबत्ती | 蜡烛 |
| helicopter | hélicoptère | helicóptero | हेलीकॉप्टर | 直升机 |
| pineapple | ananas | abacaxi | अनानास | 菠萝 |
| snail | escargot | caracol | घोंघा | 蜗牛 |
| saw | scie: saw | serrote: hand saw | आरी: saw | 锯子 |
| cactus | cactus | cacto | कैक्टस | 仙人掌 |
| whistle | sifflet | apito | सीटी: whistle | 哨子 |
| harp | harpe | harpa | हार्प | 竖琴 |
| igloo | igloo | iglu | इग्लू | 冰屋 |

Portuguese uses Brazilian words: *abacaxi* (not *ananás*) and *serrote* (a hand saw). The Spanish list is in `runs/wordlists/demo_es.txt`.

**Picture sets.** `python scripts/build_test_set.py demo_<lang> <lang> <list>`, in line style with two candidates per word, costing about $0.55 per set. The sets are in `runs/sets/demo_<lang>/` and appear in the web app's Test Studio.

**Spoken naming.** Synthesized speech only, never recordings of people.
1. Each word (or phrase, such as *un chat*) was synthesized on its own with `say -v <voice>`.
2. The clip was converted to 16 kHz mono WAV and padded with 0.7 s of silence, as the Scorer does.
3. It was transcribed with the language hint.
4. The transcript was coded by `naming_errors.classify` with the set's alternates.

Transcripts from early runs were re-coded with the final rules; the JSON keeps both counts.

Extra runs:
- 1.5 s padding. This changed nothing.
- A European Portuguese voice saying the Brazilian words: 14 bare, 16 with the article.
- The "Eloquence" voices (Eddy, Flo, Jacques and others) were set aside. They are robotic formant synthesis, and Muse Voice Transcribe returned empty transcripts for up to half of their clips, with or without extra gain or padding. Treat that as a warning for very atypical speech, not as a measure of normal speech.

## Picture sets: what the checks caught

- **Spanish *sierra*:** both pictures were named *serrucho* (hand saw). *Sierra* is also a mountain range. Flagged for review.
- **Hindi *हार्प* (harp):**
  - Both pictures were named *वीणा* (veena, an Indian string instrument), and SAM found no harp.
  - The harp is unfamiliar in India, and the loanword is rarely used.
  - Replace this item in a Hindi test.
- **Hindi *सीटी* (whistle):** the drawings were read as a microphone (*माइक्रोफोन*) and, on a retry, as an ektara (*इकतारा*). Whistle drawings were weak everywhere. French, Portuguese and Chinese each kept one candidate that passed.
- **Kettle or teapot:**
  - In French and Hindi, one of the two kettle drawings was named *théière* / *चायदानी* (teapot), and the other candidate was kept.
  - In Chinese, both *水壶* drawings looked like teapots and were named *茶壶*, even with the meaning pinned, so the item went to review.
  - *水壶* also means a water bottle or canteen. *烧水壶* or *电水壶* may draw better.
- **Native names and short names:** one Hindi cactus picture was named *नागफनी* (the native name for prickly pear) instead of *कैक्टस*. One Chinese umbrella was named *伞* instead of *雨伞*. Both are good alternates to accept in review.
- **Chinese *手套* (glove):**
  - Chinese nouns don't mark number, so the plan asked for "a pair of winter gloves", and SAM rightly counted two objects.
  - Fixed: the plan now asks for exactly one object.
  - A retry kept a single glove.
- **Color in line drawings:**
  - "An orange carrot" and "a green cactus" gave colored pictures in a line-style set, and the Chinese carrot and Portuguese cactus were kept that way.
  - A reviewer swapped in the line-drawn candidate (noted as `review_note` in the manifests).
  - The plan now leaves colors out. A retry drew all three items in black and white.
- **Ambiguous words were flagged, as intended:**
  - French: *banc* (sandbank, shoal), *bougie* (spark plug).
  - Portuguese: *escada* (stairs), *banco* (bank), *vela* (sail), *caracol* (curl).
  - Hindi: *लंगर* (the Sikh community kitchen), *सीढ़ी* (stairs).
  - Chinese: *水壶* (water bottle, canteen).
- The `contact_sheet.png` labels use PIL's default font, so accented letters, Devanagari and Chinese show as boxes there. The web app shows them correctly.

## Spoken naming: what went wrong

| Language | Failures (transcript → code) |
|---|---|
| English | **Daniel, bare word:**<ul><li>*saw* → "So"</li><li>*harp* → "huh"</li><li>*igloo* → "Hey, Blue"</li></ul>**With the article:**<ul><li>*a harp* → "A heart"</li><li>*an igloo* → "Enigloo"</li></ul> |
| Spanish | **Mónica, bare word:**<ul><li>*cuchara* → "Kuchara"</li><li>*sierra* → "Cierra"</li><li>*paraguas* → "Paraguás"</li><li>*ancla* → "Acla"</li><li>*banco* → "Baco"</li><li>*zanahoria* → "Janahoria"</li><li>*arpa* → "Arba"</li></ul>**With the article:**<ul><li>*una ancla* → "Una cla"</li></ul> |
| French | **Thomas, bare word:**<ul><li>*ancre* → "Entre"</li><li>*banc* → "Dans"</li><li>*gant* → "Dans"</li><li>*harpe* → "Arp"</li></ul>**With the article:**<ul><li>*un banc* → "Un dent"</li></ul> |
| Brazilian Portuguese | **Bare word:**<ul><li>*guarda-chuva* → "Guarda a chuva"</li><li>*tesoura* → "Cisoura"</li><li>*apito* → "Capítulo"</li></ul>**With the article:**<ul><li>*um guarda-chuva* → "Quando ar da chuva"</li><li>*uma chaleira* → "O Machaleira"</li><li>*um iglu* → "Miglo"</li></ul> |
| Mandarin | **Homophones:**<ul><li>*锚* → 毛 (both máo)</li><li>*锯子* → 句子 (both jùzi)</li><li>*竖琴* → 树禽</li><li>*哨子* → 少子</li><li>*冰屋* → 冰无</li></ul>**Latin letters:**<ul><li>*梯子* → "Teez"</li><li>*猫* → "Mom"</li></ul>**With a measure word:**<ul><li>*一个锚* → 一个毛</li><li>*一架竖琴* → 一架漱琴</li></ul> |
| Hindi | **Empty:** *बेंच*.<br>**Latin letters:**<ul><li>*कैंची* → "Patty"</li><li>*केतली* → "Kaitly"</li></ul>**Bengali script:** *इग्लू* → এগুলো.<br>**Other words:**<ul><li>*घोंघा* → घूमता</li><li>*हार्प* → हाँ ("yes")</li><li>*बिल्ली* → बिली</li></ul>**In the frame:**<ul><li>*बिल्ली* → बिल ("bill")</li><li>*आरी* → आ रही ("coming")</li><li>*हार्प* → हार्ट ("heart")</li></ul> |

Patterns:

- **Short words said on their own fail most, in every language.** The transcriber has no context, so it picks a common word that sounds alike. An article or measure word gives it context:

  | Language | Bare word | With article or measure word |
  |---|---|---|
  | Spanish | 13–18 | 19–20 |
  | French | 15–16 | 19–20 |
  | Portuguese | 17 | 18–19 |
  | Mandarin | 14 | 17–18 |

  English and Hindi didn't improve.
- **Right sounds, wrong spelling.**
  - *une encre* (ink) for *ancre*, *Si* for *scie*, *cerrote* for *serrote*: the speaker said the target.
  - French and Portuguese now count a response that sounds exactly like the target as Correct.
  - Spanish *Kuchara*, *Cierra* and *Silvato* are the same case. The rule isn't applied to Spanish, because the brief keeps English and Spanish codes unchanged. Applying it would turn Spanish bare words into 15/20 (Mónica) and 20/20 (Paulina). It's a one-line change (`HOMOPHONE_LANGS`) if the lead approves.
- **Mandarin homophones can't be fixed by the rules.** Telling 锚 from 毛 needs pinyin, which we don't have offline. A measure word fixed most of them.
- **Hindi is the weakest.**
  - The transcriber switches script: English loanwords come back in Latin letters, and *इग्लू* came back in Bengali.
  - Test Studio now stores loanword spellings ("cactus", "bench", "helicopter") as accepted alternates, so those score Correct.
  - Lekha is the only Hindi voice on macOS, so part of the problem may be the voice.
- **Transcript artifacts.** The transcriber sometimes writes the first word twice ("umbrellaumbrella", "UnUn", "यहयह") or fuses the article onto the name ("Uniglú"). The Scorer now undoes both, but only for articles, frame words and accepted names.
- **Empty transcripts.** 5 of 580 clips from natural voices came back empty.

## Scoring rules added for these languages

All in `metalesionlab/naming_errors.py`, tested in `tests/test_naming_errors.py` (176 tests pass, including all earlier ones).

**English and Spanish:** codes are unchanged, except that a transcript artifact (a doubled article or name, or an article fused onto the name) now reads as the word.

**Hindi text was being broken apart.** The tokenizer dropped Devanagari vowel signs (`बिल्ली` became `ब ल ल`), so no Hindi response could be scored Correct. Combining marks now count as letters.

**Chinese crashed.** wordfreq needs `jieba` to look up Chinese words, and it isn't installed. Chinese now has its own path:
1. Traditional characters are mapped to simplified.
2. Fillers and frames are dropped: 这是, a numeral or demonstrative plus a measure word (一只, 一把, 这个), and final particles.
3. The rest is split into words by greedy longest match against wordfreq's Chinese word list.
4. Correct allows:
   - the 子/儿 suffixes (锯 = 锯子);
   - a one-character modifier on a one-character name (小猫 and 黑猫, but not 熊猫 "panda");
   - a longer name anywhere in the response (电水壶 for 水壶).
5. Description means three or more words, or a phrase ending in 的 (下雨用的), instead of three space-separated words.
6. Chinese gets no sound-based codes (Formal, Mixed, Nonword), because characters don't spell sounds. The Muse Spark second rater covers those.

**Correct with articles, frames and plurals:**
- French: *le chat*, *l'ancre*, *c'est un chat*, *chats*, *chevaux*.
- Portuguese: *o gato*, *é um gato*, *gatos*, *colheres*, *aviões*.
- Hindi: *एक बिल्ली*, *यह बिल्ली है*, *बिल्ली को*, *बिल्लियाँ*/*बिल्लियां*, *छाते*, and chandrabindu or anusvara spellings.

The head noun is last in Hindi (after postpositions) and first in French and Portuguese. Hyphenated targets match with or without the hyphen (*guarda-chuva*, "guarda chuva", *guarda-chuvas*).

**Sound for French and Portuguese.** Both now have rough spelling-to-sound rules, like the existing Spanish ones. Before, letters were compared, so:
- *chat* and *carotte* shared a "first sound" (*c*);
- *chat* and *lit* shared a silent final *t*.

A response with exactly the target's sounds and stressed vowel counts as Correct (*encre*/*ancre*, *si*/*scie*, *cerrote*/*serrote*).

**Hindi words missing from wordfreq.** Its Hindi list is small and misses words like *घोंघा* and *केतली*. An unknown Hindi string still counts as a real word when Muse Spark relates it to the target in meaning.

**Refusals** such as *je ne sais pas*, *não sei*, *पता नहीं* and *不知道* code as No response.

**Live check.** I ran 33 hand-written cases through the real Muse Spark judge, across the four languages. 30 got the code I expected, and the other 3 are defensible under the PNT sound rule:
- *pluie* for *parapluie* and *chuva* for *guarda-chuva* are Mixed, because the response is part of the target;
- *janela* for *vela* is Formal, because both stress the same vowel.

**Test Studio** (`metalesionlab/test_studio.py`):
- Word lists are NFC-normalized, and the plan falls back to item order when Muse Spark respells a word.
- The plan asks for exactly one object and no colors.
- The plan returns other spellings of the same word, which become the item's accepted alternates (Hindi *कैक्टस* → "cactus", French *igloo* → "iglou", Portuguese *âncora* → "ancora").
- Alternates are shown in review and can be edited. They were added to the four demo sets after the build.

**Scorer** (`metalesionlab/scorer.py`): category-fluency transcripts are also split at Chinese and Hindi punctuation (，。、।).

## Known gaps

- Spoken checks use synthesized voices, one speaker per voice and 20 words per run. Real speakers, accents, noise and speech from people with aphasia will differ. In particular, the robotic voices suggest that the transcriber may return nothing for very atypical speech.
- Error codes other than Correct, in French, Portuguese, Hindi and Chinese, were checked only on hand-written cases, not on responses coded by human raters.
- Chinese: no sound-based codes.
- Hindi: sound is compared letter by letter.
- Swahili is listed in the app's language menu but hasn't been measured beyond one picture named correctly (*paka*).

## Ten more languages (Oct 27)

German, Italian, Dutch, Japanese, Korean, Arabic, Turkish, Polish, Indonesian and Vietnamese. They were picked from the 25 languages Muse Voice Transcribe takes a hint for, by number of speakers and by whether macOS has a natural voice for them. Russian and Swedish have voices but no transcription hint, so they were left out.

### Method

**No new pictures.** Each language reuses the English demo set's 20 pictures (`scripts/reuse_test_set.py`, about $0.03 per language):
1. The English list was translated, with ambiguous words pinned as `word: meaning`.
2. Muse Spark planned the list as Test Studio does. Its other spellings became accepted alternates: kana for Japanese kanji (*猫* → *ねこ*, *ネコ*), and unaccented Turkish and Polish spellings.
3. Muse Spark named the English set's kept picture in the language, and the name was coded by the classifier. The second picture was named only when the first wasn't coded Correct.
4. SAM's checks were copied from the English set, since SAM checks the English gloss.

The sets are in `runs/sets/demo_<lang>/`, and the lists in `runs/wordlists/demo_<lang>.txt`.

**Spoken naming:** the same method as Oct 26. Each item was synthesized with `say`, converted to 16 kHz mono 16-bit WAV, padded with 0.7 s of silence, transcribed with the language hint, and coded with the set's alternates. Each language got:
- the bare word;
- its citation form: an article (*der/die/das*, *un/una*, *een*, *bir*, *al-*) or a classifier (*con mèo*).

Where the citation form wasn't enough, or the language has none, a short frame was also tried: *Das ist eine …*, *To jest …*, *Ini …*, *…です*, *…예요*.

Most languages have one natural macOS voice, so they got two runs of it. That's the same as Portuguese and Hindi; expect a point or two of run-to-run variation. All counts use the final rules; the JSON also keeps each run's count at the time (`correct_at_run`).

| English | German | Italian | Dutch | Turkish | Polish |
|---|---|---|---|---|---|
| cat | Katze | gatto | kat | kedi | kot |
| umbrella | Regenschirm | ombrello | paraplu | şemsiye | parasol |
| anchor | Anker | ancora | anker | çapa | kotwica |
| kettle | Kessel | bollitore | ketel | çaydanlık | czajnik |
| ladder | Leiter | scala | ladder | merdiven | drabina |
| bench | Bank | panchina | bank | bank | ławka |
| glove | Handschuh | guanto | handschoen | eldiven | rękawiczka |
| spoon | Löffel | cucchiaio | lepel | kaşık | łyżka |
| carrot | Karotte | carota | wortel | havuç | marchewka |
| bicycle | Fahrrad | bicicletta | fiets | bisiklet | rower |
| scissors | Schere | forbici | schaar | makas | nożyczki |
| candle | Kerze | candela | kaars | mum | świeczka |
| helicopter | Hubschrauber | elicottero | helikopter | helikopter | helikopter |
| pineapple | Ananas | ananas | ananas | ananas | ananas |
| snail | Schnecke | lumaca | slak | salyangoz | ślimak |
| saw | Säge | sega | zaag | testere | piła |
| cactus | Kaktus | cactus | cactus | kaktüs | kaktus |
| whistle | Pfeife | fischietto | fluitje | düdük | gwizdek |
| harp | Harfe | arpa | harp | arp | harfa |
| igloo | Iglu | igloo | iglo | iglo | igloo |

| English | Japanese | Korean | Arabic | Indonesian | Vietnamese |
|---|---|---|---|---|---|
| cat | 猫 | 고양이 | قطة | kucing | mèo |
| umbrella | 傘 | 우산 | مظلة | payung | ô |
| anchor | 錨 | 닻 | مرساة | jangkar | mỏ neo |
| kettle | やかん | 주전자 | غلاية | ketel | ấm |
| ladder | はしご | 사다리 | سلم | tangga | thang |
| bench | ベンチ | 벤치 | مقعد | bangku | ghế dài |
| glove | 手袋 | 장갑 | قفاز | sarung tangan | găng tay |
| spoon | スプーン | 숟가락 | ملعقة | sendok | thìa |
| carrot | にんじん | 당근 | جزرة | wortel | cà rốt |
| bicycle | 自転車 | 자전거 | دراجة | sepeda | xe đạp |
| scissors | はさみ | 가위 | مقص | gunting | kéo |
| candle | ろうそく | 양초 | شمعة | lilin | nến |
| helicopter | ヘリコプター | 헬리콥터 | مروحية | helikopter | trực thăng |
| pineapple | パイナップル | 파인애플 | أناناس | nanas | dứa |
| snail | カタツムリ | 달팽이 | حلزون | siput | ốc sên |
| saw | のこぎり | 톱 | منشار | gergaji | cưa |
| cactus | サボテン | 선인장 | صبار | kaktus | xương rồng |
| whistle | 笛 | 호루라기 | صفارة | peluit | còi |
| harp | ハープ | 하프 | قيثارة | harpa | đàn hạc |
| igloo | イグルー | 이글루 | إغلو | iglo | lều tuyết |

Vietnamese uses northern words (*ô*, *thìa*, *dứa*, *nến*), matching the voice.

### Pictures: what Muse Spark called them

- **The kettle drawing** is a stovetop kettle, and its second candidate looks like a teapot. It was named:
  - *Teekessel* in German, which counts under the compound rule;
  - *teiera* (teapot) in Italian, *teko* in Indonesian and *إبريق* in Arabic, so those items went to review;
  - correctly in Dutch, Japanese, Korean, Turkish, Polish and Vietnamese.
- **The stepladder** was named *脚立* (a stepladder) in Japanese, so *はしご* went to review. In Dutch it was *trap* (stairs) and then *trapladder*, which counts.
- **Polish *świeczka*:** both candle pictures were named *świeca*, the base word that *świeczka* is the diminutive of. Accept it in a Polish test.
- **Vietnamese**, asked for "exactly one word":
  - Muse Spark cut names to one syllable (*mỏ neo* → *neo*, *ghế dài* → *ghế*) or ran them together (*càrốt*, *xeđạp*).
  - 11 of 20 were kept.
  - Test Studio now asks for every syllable in Vietnamese, and for both words of a two-word Indonesian name (*sarung tangan*). With that prompt, Vietnamese kept 20 of 20.
- **Before the final rules**, the first pass kept 19 German, 19 Dutch and 18 Indonesian items: *Teekessel*, *trapladder* and *sarungtangan* were coded as errors.
- **Ambiguity flags**, as intended:
  - German: *Bank* (bank), *Pfeife* (pipe), *Leiter* (leader).
  - Italian: *scala* (stairs, scale), *candela* (spark plug).
  - Dutch: *bank* (sofa), *wortel* (root).
  - Turkish: *çapa* (hoe).
  - Arabic: *سلم* (stairs), *مقعد* (seat).
  - Korean: *톱* (top).

### Spoken naming: what went wrong

| Language | Failures in the recommended form (transcript) | Bare words |
|---|---|---|
| German | *Das ist eine Harfe* → "Das ist eine Hafe" (second run only) | Kessel → "Fessel", Kerze → "Herze", Harfe → "Hafe", Iglu → nothing. *Der/die/das* fixed Kessel but not the others (17, 17) |
| Turkish | *bir salyangoz* → "bir sağ yalnız"; *bir arp* → "Bir", "Birer" | düdük, iglo, mum → nothing; salyangoz → "Sağ yangoz" |
| Polish | *To jest kot* → "To jest kod" | kot → "Kup", ławka → "UFK", łyżka → "Półyszka", piła → "Iła", igloo → nothing |
| Indonesian | none | tangga → "Tanggal", iglo → "iglow" |
| Italian | *un bollitore* → "Un bolitore" (one l), *un'arpa* → "Un'arta", *un igloo* → "unigro" | igloo → nothing; arpa → "Art" |
| Arabic | *المقص* → "الميقصي"; *الأناناس* → "أنا الناس"; *الصفارة* → "السفارة" ("the embassy"); *الإغلو* → "قالوا", "Alhulo" | قطة → "قطع", مرساة → "مرسى" (harbor), قفاز → "خفاز", إغلو → nothing or "Hirou!" |
| Vietnamese | *cái cưa* → "cái cơ" (twice); *cây xương rồng* → "xuông/suông rồng"; *chiếc trực thăng* → "trục thăng" | dứa → "giữa"/"Rửa", ốc sên → "observe"/"Upsend", cưa → nothing, thang → "Hang" |
| Dutch | *een lepel* → "een label", *een kaars* → "een kaas", *een zaag* → "een zag", *een slak* → "Een slok", *een harp* → "Z'n hart" | kat → "God", plus the same vowel confusions |
| Japanese | *錨です* → "怒りりです"; *ベンチです* → "ベンチンチです"; *パイナップルです* → "バイナップルです"; *ハープです* → "ワープです" | 猫 → "でこ", スプーン → nothing, やかん → "夜間、間" |
| Korean | (bare) 닻 → "탁", 톱 → nothing, 가위 → "카위", 호루라기 → "고루라기", 하프 → "해프", 이글루 → "이 글로" | the copula (*예요*) gave 15 and 12 |

Patterns:
- **A short sentence helps where an article doesn't.** For German, *Das ist eine …* gave 20 and 19, against 17 and 17 with *der/die/das*. Polish went from 14–15 bare to 20 and 19 with *To jest …*, and Indonesian *Ini …* gave 20 twice. The frame gives the transcriber context, as articles did for Spanish and French.
- **Japanese and Korean didn't reach the bar.** Their failures are mostly the transcriber hearing a nearby word, not scoring rules. Both have one voice on macOS, so the voice may be part of it, as with Hindi.
- **Transcript artifacts:**
  - a doubled first syllable or word ("xexe đạp", "concon", "sarungsarung tangan", "Fesselfessel");
  - a name split in two ("أنا ناس") or run together;
  - an apostrophe inside the name ("L'umaca");
  - every Vietnamese tone mark dropped ("thia", "coi").

  The rules below undo the ones they safely can.
- **Empty transcripts:** 18 of 840 clips came back empty, all of them bare words, mostly short ones such as *igloo*, *düdük*, *톱* and *cưa*. No clip in an article, classifier or frame form came back empty.

### Scoring rules added

All in `metalesionlab/naming_errors.py`, tested in `tests/test_naming_errors.py`. Earlier languages keep their codes: the new rules are per language, and the full suite passes.

- **Articles, classifiers and frames:**
  - *der/die/das/ein/eine*, *il/la/un/uno/una/l'/un'*, *de/het/een*, Turkish *bir*;
  - Indonesian *seekor/sebuah*, Vietnamese *con/cái/chiếc/quả/cây*;
  - frames: *das ist*, *è*, *dit is*, *bu*, *to jest*, *ini*, *đây là*, *هذه*, *이것은*.

  Italian elides like French (*l'ancora*, *un'arpa*).
- **Plurals:**
  - German *-n/-en/-e/-er*, with or without an umlaut (*Bänke*, *Fahrräder*);
  - Dutch *-en/-'s*, doubled consonants (*katten*), and diminutives as the name (*bankje*);
  - Italian *gatti*, *carote*, *lumache*;
  - Turkish *-ler/-lar*;
  - Indonesian doubling (*kucing-kucing*);
  - Arabic *-ات* and the collective (*جزر* for *جزرة*).
- **German and Dutch compounds:** the head comes last, so a word ending in the name counts (*Teekessel*, *fluitketel*, *trapladder*). So does the name split by the transcript ("Regen Schirm").
- **Arabic:** short-vowel marks and tatweel are dropped. Alef forms are folded together, and so are ta marbuta, ha and a final alef maqsura ("القطى" for *القطة*). The article *al-* may be attached, also after *wa-* or *bi-*.
- **Korean:**
  - Particles and the copula are allowed (*고양이가*, *우산이에요*).
  - A compound ending in a name of two or more syllables counts (*고무장갑*).
  - Sound comes from the jamo, with liaison and the ㅐ/ㅔ merger. A spelling with the same sounds counts as the name, as in French and Portuguese (*파이네플* for *파인애플*, *다치에요* for *닻이에요*).
- **Japanese has its own path, like Chinese:**
  - katakana equals hiragana (*ネコ* = *ねこ*), and half-width forms are normalized;
  - kanji spellings count through the alternates;
  - *これは* and *です* are dropped;
  - a word ending in the name counts (*子猫*, *雨傘*);
  - sound is compared in kana only.
- **Japanese homophones:** a transcript in kanji that doesn't match is read aloud by Muse Spark in hiragana (cached in `runs/cache/ja_readings.json`), and the reading is compared with the target's kana. So *怒り* (anger, *いかり*) counts for *錨* (anchor, *いかり*), and *片つむり* for *カタツムリ*. This is the "same sounds" rule, needing one Muse Spark call per new kanji transcript. Any caller that passes `spark_semantic_judge` gets it.
- **Vietnamese:**
  - Marks aren't folded, because they are tones and vowels (*mèo* "cat", *méo* "bent").
  - A transcript with no marks at all still matches (*thia* for *thìa*).
  - Syllables run together count (*càrốt*).
- **Turkish:** the dotted capital *İ* is lowercased to *i* (it used to turn *İglo* into an error).
- **Transcript artifacts, for the new languages:**
  - a name split in two or run together;
  - a doubled first word of a several-word name ("xexe đạp");
  - an apostrophe inside an Italian or French name ("L'umaca").
- **Refusals** in every new language (*ich weiß nicht*, *non lo so*, *わかりません*, *모르겠어요*, *لا أعرف*, *bilmiyorum*, *nie wiem*, *tidak tahu*, *không biết*).
- **Word lists:** wordfreq needs MeCab for Japanese and Korean, which isn't installed. Their words are now looked up directly in wordfreq's lists.

**English (Oct 27):** a real word that wordfreq rates rare and the CMU dictionary lacks used to come out Neologism. Now it is a real word if:
- WordNet lists it (*footstool*);
- or it is a closed compound of two real words of three or more letters (*kiwifruit* = *kiwi* + *fruit*).

Each part must also be a WordNet lemma, so *Caraloon* (*cara* + *loon*) stays a nonword.

**Live check.** 23 hand-written error responses, two or three per new language (Semantic, Formal, Description), went through the real Muse Spark judge (and reader for Japanese). All 23 got the expected code.

### Known gaps

- One synthesized voice for nine of the ten languages. Real speakers, accents, noise and speech from people with aphasia will differ.
- No spelling-to-sound rules for German, Italian, Dutch, Turkish, Polish, Indonesian, Vietnamese or Arabic. Sound is compared letter by letter, like Hindi, so "bolitore" for *bollitore* is a Nonword.
- Accents still fold for Latin-script languages other than Vietnamese. So a German umlaut, or a Turkish or Polish letter, can be missed: *Sage* (legend) would count for *Säge*. No transcript needed it.
- The compound rule can accept a different word with the same head (*Bauleiter*, a site manager, for *Leiter*); a reviewer should check.
- Japanese homophone matching depends on Muse Spark's reading. Without the reader (offline), a kanji homophone is an error.
- Korean and Japanese one-syllable or short names (*닻*, *톱*, *猫*) are the least reliable; consider longer items in a test.

## Reproduce

```bash
export MLL_LEDGER=runs/costs.jsonl
python scripts/build_test_set.py demo_fr fr runs/wordlists/demo_fr.txt
# Oct 27 languages: the English demo set's pictures, named in the language (no new images)
python scripts/reuse_test_set.py demo_de de runs/wordlists/demo_de.txt
```

The speech check is a short loop per word:
1. Synthesize the word: `say -v Thomas -o clip.aiff "un chat"`.
2. Convert and pad it: `audio.to_wav16k`, then `audio.pad_silence(wav, 0.7)`.
3. Transcribe: `MetaAPI().transcribe(wav, language="fr")`.
4. Code the transcript: `naming_errors.classify(target, transcript, "fr", alternates=item["alternates"], judge=...)`.

The whole check cost under $0.10 per language. The picture sets cost about $0.55 each. For the ten Oct 27 languages, everything (sets, 42 runs of 20 clips, re-coding and the live check) cost about $0.65 in all.
