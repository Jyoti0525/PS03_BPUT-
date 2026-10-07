"""Turns an intake into tri-state clinical findings with evidence.

Every finding is True (present), False (absent) or None (unknown). The rules engine never treats
unknown as normal, so the difference matters:

* Symptoms the patient would report themselves (chest pain, fever, a snake bite…) are False when
  not mentioned, and False when explicitly denied ("no chest pain", "सीने में दर्द नहीं").
* Signs that need a trained eye (stridor, capillary refill, stiff neck…) stay None until a nurse
  or doctor records the danger-sign check. A patient may still report one (e.g. blue lips),
  which makes it True.

Sources, in order of trust: clinician-recorded signs → structured answers (by question id) →
symptom tiles → free text in English, Hindi (Devanagari and romanised) and Odia, with negation
detection. Free-text matching is a deterministic lexicon, not a model; the reviewer sees the
exact words that triggered each finding.
"""

import re
import unicodedata
from dataclasses import dataclass, field

SYMPTOM, SIGN = "symptom", "sign"

# finding id -> (label, kind)
FINDINGS: dict[str, tuple[str, str]] = {
    # cardio-respiratory
    "chest_pain": ("Chest pain", SYMPTOM),
    "chest_pain_radiating": ("Chest pain spreading to arm, jaw or back", SYMPTOM),
    "sweating": ("Sweating with symptoms", SYMPTOM),
    "breathless": ("Breathlessness", SYMPTOM),
    "cough": ("Cough", SYMPTOM),
    "haemoptysis": ("Coughing blood", SYMPTOM),
    "incomplete_sentences": ("Cannot speak full sentences", SIGN),
    "wheeze": ("Audible wheeze", SIGN),
    "stridor": ("Stridor / noisy breathing", SIGN),
    "respiratory_distress": ("Respiratory distress (accessory muscles, flaring, grunting)", SIGN),
    "chest_indrawing": ("Lower chest indrawing", SIGN),
    "cyanosis": ("Central cyanosis (blue lips or tongue)", SIGN),
    "angioedema_face": ("Swelling of face, lips or tongue", SIGN),
    "swelling_mouth_neck": ("Swelling or mass of mouth, throat or neck", SIGN),
    # circulation
    "cap_refill_gt3": ("Capillary refill > 3 s", SIGN),
    "weak_fast_pulse": ("Weak and fast pulse", SIGN),
    "cold_extremities": ("Cold hands and feet", SIGN),
    "severe_pallor": ("Severe pallor", SIGN),
    "bleeding": ("Bleeding", SYMPTOM),
    "bleeding_heavy": ("Heavy bleeding", SYMPTOM),
    "epistaxis": ("Nosebleed", SYMPTOM),
    "gum_bleed": ("Bleeding gums", SYMPTOM),
    "haematemesis": ("Vomiting blood", SYMPTOM),
    "blood_in_stool": ("Blood in stool", SYMPTOM),
    "syncope": ("Fainting / blackout", SYMPTOM),
    # disability
    "unresponsive": ("Unresponsive / unconscious", SIGN),
    "altered_mental_status": ("Confused, drowsy or not responding normally", SIGN),
    "lethargy": ("Lethargic or abnormally sleepy", SIGN),
    "irritable": ("Restless or continuously irritable", SIGN),
    "seizure": ("Fits / convulsions", SYMPTOM),
    "one_sided_weakness": ("Weakness, numbness or drooping on one side; slurred speech", SYMPTOM),
    "limb_weakness": ("Weakness of an arm or leg", SYMPTOM),
    "weakness_general": ("Acute general weakness", SYMPTOM),
    "headache": ("Headache", SYMPTOM),
    "headache_sudden": ("Sudden or worst-ever headache", SYMPTOM),
    "visual_disturbance": ("Blurred vision or seeing spots", SYMPTOM),
    "stiff_neck": ("Stiff neck", SIGN),
    "agitated": ("Agitated, violent or aggressive", SYMPTOM),
    # general / GI / GU
    "fever": ("Fever", SYMPTOM),
    "abdominal_pain": ("Abdominal pain", SYMPTOM),
    "abdominal_pain_sudden": ("Sudden-onset abdominal pain", SYMPTOM),
    "vomiting": ("Vomiting", SYMPTOM),
    "vomits_everything": ("Vomits everything", SYMPTOM),
    "diarrhoea": ("Diarrhoea", SYMPTOM),
    "unable_to_drink": ("Unable to drink or breastfeed", SYMPTOM),
    "drinks_poorly": ("Drinks poorly", SYMPTOM),
    "sunken_eyes": ("Sunken eyes", SIGN),
    "skin_pinch_slow": ("Skin pinch goes back very slowly", SIGN),
    "dehydration": ("Signs of dehydration", SYMPTOM),
    "urinary_retention": ("Unable to pass urine", SYMPTOM),
    "scrotal_pain": ("Acute testicular / scrotal pain or priapism", SYMPTOM),
    "rash": ("Skin rash", SYMPTOM),
    "rash_spreading": ("Rash worsening over hours or peeling", SYMPTOM),
    "malnutrition": ("Visible severe wasting or swelling of both feet", SIGN),
    "weight_loss": ("Weight loss", SYMPTOM),
    "night_sweats": ("Night sweats", SYMPTOM),
    "fatigue": ("Tiredness / fatigue", SYMPTOM),
    "pain": ("Pain", SYMPTOM),
    # trauma and exposures
    "injury": ("Injury", SYMPTOM),
    "burn": ("Burn", SYMPTOM),
    "head_injury": ("Head injury", SYMPTOM),
    "fall_from_height": ("Fall from height", SYMPTOM),
    "road_traffic_high_risk": ("Road crash — high-risk mechanism", SYMPTOM),
    "penetrating_injury": ("Stab, gunshot or penetrating injury", SYMPTOM),
    "crush_injury": ("Crush injury", SYMPTOM),
    "limb_deformity": ("Visible limb deformity, fracture or dislocation", SYMPTOM),
    "threatened_limb": ("Limb pulseless, or painful with pale/weak/numb", SYMPTOM),
    "drowning_hanging_electrocution": ("Drowning, hanging or electrocution", SYMPTOM),
    "snake_bite": ("Snake bite", SYMPTOM),
    "animal_bite": ("Animal bite (dog, monkey…)", SYMPTOM),
    "poisoning": ("Poisoning, overdose or chemical exposure", SYMPTOM),
    "needle_stick": ("Needle-stick injury", SYMPTOM),
    "allergic_reaction": ("Allergic reaction", SYMPTOM),
    "sexual_assault": ("Sexual assault", SYMPTOM),
    # pregnancy
    "pregnant": ("Pregnant", SYMPTOM),
    "vaginal_bleeding": ("Vaginal bleeding", SYMPTOM),
    "reduced_fetal_movement": ("Baby moving less than usual", SYMPTOM),
    "fluid_leaking": ("Fluid leaking from vagina", SYMPTOM),
    "labour_pains": ("Labour pains / contractions", SYMPTOM),
    "swelling_face_hands": ("Swelling of face or hands", SYMPTOM),
    "upper_abdominal_pain": ("Upper abdominal pain", SYMPTOM),
    # outside evaluations
    "known_time_sensitive_dx": ("Outside report of heart attack, stroke, sepsis, aortic dissection or leukaemia", SYMPTOM),
    "chemo_recent": ("Chemotherapy in the last 14 days", SYMPTOM),
}

# Lexicon. Latin-script entries are regexes matched on word boundaries; Indic entries are plain
# substrings (word boundaries are unreliable with combining marks). Hindi includes common
# romanised forms. Odia terms should be confirmed by a native speaker before a field pilot.
LEXICON: dict[str, dict[str, list[str]]] = {
    "chest_pain": {
        "en": [r"chest (pain|ache|tightness|heaviness|pressure|discomfort)", r"pain in (the |my )?chest", r"chest (hurts?|is hurting|is paining)", r"heart pain", r"seene? (me|mein|mai) dard", r"chhati (me|mein) dard"],
        "hi": ["सीने … दर्द", "छाती … दर्द", "सीने … भारीपन", "सीने … जकड़न", "सीने … दबाव", "सीने … दिक्कत", "सीने … तकलीफ", "छाती … दिक्कत"],
        "or": ["ଛାତି … ଯନ୍ତ୍ରଣା", "ଛାତି … ବିନ୍ଧ", "ଛାତି … ଦରଜ", "ଛାତି … ଦରଦ", "ଛାତି … ଦର୍ଦ", "ଛାତି … ଭାରି", "ଛାତି … ଚାପି"],
    },
    "chest_pain_radiating": {
        "en": [r"(spread|spreads|spreading|radiat\w*|going|goes|moving) (to|into|towards) (the |my )?(left )?(arm|jaw|back|shoulder)", r"(arm|jaw) pain"],
        "hi": ["बांह तक", "बाँह तक", "जबड़े तक", "हाथ तक जा"],
        "or": ["ହାତକୁ ଯାଉଛି", "ବାହୁକୁ", "ଜହ୍ନ"],
    },
    "sweating": {"en": [r"sweat(ing|y|s|ed)?", r"paseena"], "hi": ["पसीना", "पसीने"], "or": ["ଝାଳ"]},
    "breathless": {
        "en": [r"breathless\w*", r"short(ness)? of breath", r"(difficulty|trouble|problem) (in )?breathing", r"(can\'?t|cannot|can not|unable to|not able to) breathe", r"breathing (problem|difficulty|trouble)", r"saans (lene )?(me|mein) (taklif|dikkat|pareshani)", r"saans phool"],
        "hi": ["सांस लेने में", "सांस फूल", "दम फूल", "सांस … तकलीफ", "सांस … दिक्कत", "सांस … परेशानी", "सांस नहीं ले पा"],
        "or": ["ନିଶ୍ୱାସ … କଷ୍ଟ", "ଶ୍ୱାସ … କଷ୍ଟ", "ଶ୍ୱାସକଷ୍ଟ", "ନିଶ୍ୱାସ ନେଇ ପାରୁନି", "ନିଶ୍ୱାସ ନେଇପାରୁନି", "ଦମ୍ ଫୁଲୁଛି", "ଦମ୍ … ଲାଗୁଛି"],
    },
    "cough": {"en": [r"cough\w*", r"khansi"], "hi": ["खांसी", "^खासी"], "or": ["^କାଶ"]},
    "haemoptysis": {"en": [r"cough\w* (up )?blood", r"blood in (the )?(sputum|phlegm|cough)", r"ha?emoptysis"], "hi": ["खांसी में खून", "बलगम में खून"], "or": ["କାଶରେ ରକ୍ତ"]},
    "incomplete_sentences": {"en": [r"(can'?t|cannot|unable to) (speak|talk|finish) (in )?(full|complete) sentences?", r"difficulty breathing while talking"], "hi": [], "or": []},
    "wheeze": {"en": [r"wheez\w*", r"whistling (sound|breath)"], "hi": ["सीटी जैसी आवाज"], "or": ["ସିଟି ଭଳି ଶବ୍ଦ"]},
    "stridor": {"en": [r"stridor", r"noisy breathing"], "hi": [], "or": []},
    "respiratory_distress": {"en": [r"respiratory distress", r"grunting", r"nasal flaring", r"gasping"], "hi": ["हांफ"], "or": []},
    "chest_indrawing": {"en": [r"chest (in-?drawing|indrawing|retraction)", r"rib(s)? (sucking|pulling) in"], "hi": ["पसली चल"], "or": []},
    "cyanosis": {"en": [r"blue (lips|tongue|face)", r"bluish (lips|tongue|skin)", r"cyanos\w*"], "hi": ["होंठ नीले", "नीले होंठ"], "or": ["ଓଠ ନୀଳ", "ନୀଳ ଓଠ"]},
    "angioedema_face": {"en": [r"(swollen|swelling of( the)?) (face|lips?|tongue|eyelids?)", r"(face|lips?|tongue) (is |are )?swollen"], "hi": ["होंठ सूज", "चेहरा सूज", "जीभ सूज"], "or": ["ଓଠ ଫୁଲିଛି", "ମୁହଁ ଫୁଲିଛି"]},
    "swelling_mouth_neck": {"en": [r"(swelling|lump|mass) (in|of|on) (the )?(mouth|throat|neck)", r"(neck|throat) swelling"], "hi": ["गले में सूजन", "गर्दन में गांठ"], "or": ["ବେକ ଫୁଲିଛି", "ଗଳା ଫୁଲିଛି"]},
    "cold_extremities": {"en": [r"cold (hands|feet|hands and feet|extremities)"], "hi": ["हाथ पैर ठंडे"], "or": ["ହାତ ଗୋଡ଼ ଥଣ୍ଡା"]},
    "severe_pallor": {"en": [r"(very|severe(ly)?|extremely) pale", r"severe pallor"], "hi": ["बहुत पीला"], "or": []},
    "bleeding": {"en": [r"bleed\w*", r"blood (coming|loss|is coming)", r"khoon (aa|nikal|beh)"], "hi": ["खून आ", "खून बह", "खून निकल", "रक्तस्राव"], "or": ["ରକ୍ତ ବାହାରୁଛି", "ରକ୍ତସ୍ରାବ", "ରକ୍ତ ପଡ଼ୁଛି"]},
    "bleeding_heavy": {"en": [r"(heavy|severe|profuse|lot of|uncontrolled|continuous) (bleeding|blood)", r"bleeding (heavily|a lot|won'?t stop|not stopping)", r"bahut khoon"], "hi": ["बहुत खून", "खून नहीं रुक"], "or": ["ବହୁତ ରକ୍ତ", "ରକ୍ତ ବନ୍ଦ ହେଉନି"]},
    "epistaxis": {"en": [r"nose ?bleed\w*", r"bleeding from (the )?nose", r"epistaxis", r"naak se khoon"], "hi": ["नाक से खून", "नकसीर"], "or": ["ନାକରୁ ରକ୍ତ"]},
    "gum_bleed": {"en": [r"(bleeding gums?|gums? bleed\w*)"], "hi": ["मसूड़ों से खून", "मसूड़े से खून"], "or": ["ଦାନ୍ତ ମାଢ଼ିରୁ ରକ୍ତ"]},
    "haematemesis": {"en": [r"vomit\w* (of )?blood", r"blood (in|with) (the )?vomit", r"ha?ematemesis", r"khoon ki ulti"], "hi": ["खून की उल्टी", "उल्टी में खून"], "or": ["ବାନ୍ତିରେ ରକ୍ତ", "ରକ୍ତ ବାନ୍ତି"]},
    "blood_in_stool": {"en": [r"blood (in|with) (the )?(stool|motion|potty)", r"bloody (stool|diarrh\w*|motion)", r"black stools?", r"mala?ena"], "hi": ["मल में खून", "पॉटी में खून", "काला मल"], "or": ["ଝାଡ଼ାରେ ରକ୍ତ"]},
    "syncope": {"en": [r"faint\w*", r"black(ed)? ?out", r"passed out", r"collaps\w*", r"syncope", r"behosh ho (gay|gai)"], "hi": ["बेहोश हो गया", "बेहोश हो गई", "चक्कर खाकर गिर"], "or": ["ମୂର୍ଚ୍ଛା", "ବେହୋସ ହୋଇଗଲେ", "ବେହୋସ ହୋଇଗଲା"]},
    "unresponsive": {"en": [r"unconscious", r"unresponsive", r"not (responding|waking)", r"won'?t wake", r"can'?t be woken", r"behosh hai"], "hi": ["बेहोश है", "होश नहीं"], "or": ["ଚେତାଶୂନ୍ୟ", "ହୋସ୍ ନାହିଁ", "ବେହୋସ ଅଛି"]},
    "altered_mental_status": {"en": [r"confus\w*", r"disoriented", r"drows\w*", r"altered (sensorium|mental)", r"not (talking|speaking) (properly|normally)", r"behaving (strangely|oddly)"], "hi": ["होश में नहीं", "उल्टा सीधा बोल", "भ्रम"], "or": ["ଭ୍ରମ", "ଠିକ୍ ସେ କଥା କହୁନି"]},
    "lethargy": {"en": [r"letharg\w*", r"(very|abnormally|unusually) sleepy", r"floppy"], "hi": ["सुस्त", "बहुत नींद"], "or": ["ଅଳସୁଆ", "ବହୁତ ନିଦ"]},
    "irritable": {"en": [r"(continuously|constantly|very) (irritable|crying)", r"restless", r"inconsolable"], "hi": ["बेचैन", "लगातार रो"], "or": ["ଅସ୍ଥିର"]},
    "seizure": {"en": [r"seizures?", r"fits", r"had an? fit", r"(fit|fits) (of|aa)", r"convuls\w*", r"jerking", r"epilep\w*", r"mirgi", r"daura"], "hi": ["दौरा पड़", "दौरे", "मिर्गी", "झटके"], "or": ["ମିର୍ଗୀ", "ଝଟକା", "ଝିଙ୍କି"]},
    "one_sided_weakness": {"en": [r"one[- ]sided (weakness|numbness|paralysis)", r"(weakness|numbness|paralysis) (on|of) (one|the (left|right)) side", r"(face|mouth) (droop\w*|deviat\w*)", r"slurred speech", r"stroke", r"paralys\w*", r"lakwa"], "hi": ["लकवा", "एक तरफ कमजोरी", "मुंह टेढ़ा", "जुबान लड़खड़"], "or": ["ପକ୍ଷାଘାତ", "ଗୋଟିଏ ପଟ ଦୁର୍ବଳ", "ମୁହଁ ବାଙ୍କି"]},
    "limb_weakness": {"en": [r"(arm|leg|hand|limb) (is |became )?(weak|numb)", r"weakness (in|of) (the |my )?(arm|leg|hand|limb)", r"can'?t (move|lift) (the |my )?(arm|leg|hand)"], "hi": ["हाथ में कमजोरी", "पैर में कमजोरी", "हाथ नहीं उठ"], "or": ["ହାତ ଦୁର୍ବଳ", "ଗୋଡ଼ ଦୁର୍ବଳ"]},
    "weakness_general": {"en": [r"(sudden|acute|extreme|severe) weakness", r"(too|very) weak to (walk|stand)", r"can'?t (walk|stand)"], "hi": ["बहुत कमजोरी", "चल नहीं पा"], "or": ["ବହୁତ ଦୁର୍ବଳ", "ଚାଲି ପାରୁନି"]},
    "headache": {"en": [r"head ?ache", r"pain in (the |my )?head", r"sir ?dard"], "hi": ["सिरदर्द", "सरदर्द", "सिर … दर्द", "^सर$ … दर्द"], "or": ["ମୁଣ୍ଡବିନ୍ଧ", "ମୁଣ୍ଡ … ବିନ୍ଧ", "ମୁଣ୍ଡ … ଯନ୍ତ୍ରଣା", "ମୁଣ୍ଡ … ଦରଜ", "ମୁଣ୍ଡ … ଦରଦ", "ମୁଣ୍ଡ … ଦର୍ଦ"]},
    "headache_sudden": {"en": [r"(sudden|thunderclap|worst)[\w ]{0,20}headache", r"headache[\w ]{0,15}(sudden(ly)?|worst (ever|of my life))"], "hi": ["अचानक तेज सिरदर्द", "अचानक सिर दर्द"], "or": ["ହଠାତ୍ ମୁଣ୍ଡବିନ୍ଧା"]},
    "visual_disturbance": {"en": [r"blur\w* vision", r"vision (is )?blur\w*", r"seeing (spots|flashes|lights|double)", r"double vision", r"(loss of|lost|sudden) vision", r"can'?t see", r"dhundh?la"], "hi": ["धुंधला", "आंखों के आगे अंधेरा", "दिखाई नहीं"], "or": ["ଝାପ୍ସା", "ଦେଖିପାରୁନି"]},
    "stiff_neck": {"en": [r"stiff neck", r"neck (stiffness|is stiff)", r"can'?t bend (the |my )?neck"], "hi": ["गर्दन अकड़", "गर्दन में जकड़न"], "or": ["ବେକ ଟାଣି"]},
    "agitated": {"en": [r"agitat\w*", r"violent", r"aggressive"], "hi": ["हिंसक", "आक्रामक"], "or": ["ହିଂସ୍ର"]},
    "fever": {"en": [r"fever\w*", r"febrile", r"high temperature", r"bukhar", r"bukhaar", r"jwar"], "hi": ["बुखार", "ज्वर", "^ताप$"], "or": ["^ଜ୍ୱର$", "^ଜ୍ୱରରେ$", "^ଜ୍ୱରଟା$", "ଦେହ … ଗରମ", "ଦେହ … ତାତି"]},
    "abdominal_pain": {"en": [r"(abdominal|stomach|belly|tummy) (pain|ache|cramp\w*)", r"pain in (the |my )?(abdomen|stomach|belly)", r"stomach ?ache", r"pet (me |mein |mai )?dard"], "hi": ["पेट … दर्द"], "or": ["ପେଟ … ବିନ୍ଧ", "ପେଟ … ଯନ୍ତ୍ରଣା", "ପେଟ … ଦରଜ", "ପେଟ … ଦରଦ", "ପେଟ … ଦର୍ଦ"]},
    "abdominal_pain_sudden": {"en": [r"sudden[\w ]{0,20}(abdominal|stomach|belly) pain", r"(abdominal|stomach|belly) pain[\w ]{0,15}sudden(ly)?"], "hi": ["अचानक पेट में दर्द", "अचानक पेट दर्द"], "or": ["ହଠାତ୍ ପେଟ"]},
    "upper_abdominal_pain": {"en": [r"upper (abdominal|stomach|belly) pain", r"pain (in|at) (the )?upper (abdomen|stomach)", r"epigastric", r"right upper"], "hi": ["पेट के ऊपर दर्द", "ऊपरी पेट"], "or": ["ପେଟ ଉପରେ"]},
    "vomiting": {"en": [r"vomit\w*", r"throwing up", r"ulti"], "hi": ["उल्टी", "उलटी"], "or": ["ବାନ୍ତି"]},
    "vomits_everything": {"en": [r"vomits? everything", r"can'?t keep (anything|food|water) down", r"vomiting everything"], "hi": ["सब उल्टी", "कुछ नहीं पचता"], "or": ["ସବୁ ବାନ୍ତି"]},
    "diarrhoea": {"en": [r"diarrh\w*", r"loose (motions?|stools?)", r"watery stools?", r"dast"], "hi": ["^दस्त$", "^दस्तों$", "लूज मोशन", "पतली टट्टी"], "or": ["ଝାଡ଼ା", "ପତଳା ଝାଡ଼ା",
                  # spoken without the final ା, as both speech engines wrote it (6 Oct); only with a "happening" verb, as ଝାଡ଼ alone is "bush"
                  "^ଝାଡ଼ ହେଉଛି", "^ଝାଡ଼ ହଉଛି", "^ଝାଡ଼ ଲାଗୁଛି", "^ଝାଡ଼ ହେଲାଣି"]},
    "unable_to_drink": {"en": [r"(unable|not able|can'?t|cannot|refus\w*) to (drink|breast ?feed|feed|suck)", r"not (drinking|feeding|breast ?feeding)", r"unable to drink"], "hi": ["दूध नहीं पी", "पानी नहीं पी"], "or": ["କ୍ଷୀର ପିଉନି", "ପାଣି ପିଉନି"]},
    "drinks_poorly": {"en": [r"drink\w* (poorly|very little|less)"], "hi": ["कम पी"], "or": []},
    "sunken_eyes": {"en": [r"sunken eyes?"], "hi": ["धंसी आंखें", "आंखें धंस"], "or": ["ଆଖି ପଶିଯାଇଛି"]},
    "skin_pinch_slow": {"en": [r"skin pinch (goes back )?(very )?slow\w*"], "hi": [], "or": []},
    "dehydration": {"en": [r"dehydrat\w*", r"dry mouth", r"(very )?little urine", r"no urine", r"not passing urine"], "hi": ["पानी की कमी", "मुंह सूख"], "or": ["ପାଣି ଅଭାବ", "ପାଟି ଶୁଖି"]},
    "urinary_retention": {"en": [r"(can'?t|cannot|unable to|not able to) (pass|do) (urine|pee)", r"urinary retention", r"urine (is )?(not coming|stopped)", r"peshab (nahi|nahin) (ho|aa)"], "hi": ["पेशाब नहीं हो", "पेशाब रुक"], "or": ["ପରିସ୍ରା ହେଉନି", "ପରିସ୍ରା ବନ୍ଦ"]},
    "scrotal_pain": {"en": [r"(testic\w*|scrot\w*|groin) (pain|swelling)", r"pain in (the )?(testic\w*|scrotum|groin)", r"priapism"], "hi": ["अंडकोष में दर्द"], "or": ["ଅଣ୍ଡକୋଷ"]},
    "rash": {"en": [r"rash\w*", r"spots on (the )?skin", r"hives"], "hi": ["दाने", "चकत्ते"], "or": ["ଚର୍ମରେ ଦାଗ", "ଫୋଟକା"]},
    "rash_spreading": {"en": [r"rash[\w ]{0,20}(spread\w*|worsen\w*|peel\w*)", r"skin (is )?peeling"], "hi": ["दाने फैल", "त्वचा उतर"], "or": []},
    "malnutrition": {"en": [r"severe(ly)? (wasting|wasted|malnourish\w*)", r"swelling of both feet", r"skin and bones"], "hi": ["बहुत दुबला", "कुपोषण"], "or": ["ପୁଷ୍ଟିହୀନ"]},
    "weight_loss": {"en": [r"(weight|wt\.?) (loss|lost|(is )?(going )?down|(is )?reduc\w*|(has )?dropped)", r"los(t|ing|e) (some |a lot of |much )?weight", r"(getting|became|become|grown) (thin|thinner)", r"wa?zan (kam|ghat)"],
                    "hi": ["वजन कम", "वज़न कम", "वजन घट", "वज़न घट", "दुबला हो", "दुबली हो"], "or": ["ଓଜନ … କମ", "ଓଜନ … ହ୍ରାସ", "ପତଳା ହୋଇ"]},
    "night_sweats": {"en": [r"night sweats?", r"sweat\w* (at|in the|during the) night", r"raat (ko|me|mein) paseena"], "hi": ["रात … पसीना", "रात … पसीने"], "or": ["ରାତି … ଝାଳ"]},
    "fatigue": {"en": [r"tired\w*", r"fatigue\w*", r"exhaust\w*", r"no energy", r"thak(an|aan|awat|a hua|i hui)"], "hi": ["थकान", "थकावट", "थका हुआ", "थकी हुई", "थक जा"], "or": ["କ୍ଳାନ୍ତ", "କ୍ଲାନ୍ତ", "ଥକା ଲାଗୁ", "ଥକି ଯାଉ"]},
    "pain": {"en": [r"pain\w*", r"ache", r"dard", r"hurts?"], "hi": ["दर्द"], "or": ["ଯନ୍ତ୍ରଣା", "ବିନ୍ଧା", "ବିନ୍ଧୁ", "ଦରଜ", "ଦରଦ", "ଦର୍ଦ"]},
    "injury": {"en": [r"injur\w*", r"wound\w*", r"\bcut\b", r"hurt (my|his|her)", r"accident", r"fell (down|off)", r"chot"], "hi": ["चोट", "घाव", "दुर्घटना"], "or": ["ଆଘାତ", "କ୍ଷତ", "ଦୁର୍ଘଟଣା"]},
    "burn": {"en": [r"burn\w*", r"scald\w*", r"jal (gaya|gayi|gaye)"], "hi": ["जल गया", "जल गई", "जलना"], "or": ["ପୋଡ଼ି", "ଜଳିଗଲା"]},
    "head_injury": {"en": [r"head (injury|trauma)", r"hit (the |his |her |my )?head", r"injur\w* (to|on) (the )?head", r"fainted / head injury"], "hi": ["सिर में चोट"], "or": ["ମୁଣ୍ଡରେ ଆଘାତ"]},
    "fall_from_height": {"en": [r"fell (from|off) (a |the )?(tree|roof|terrace|height|building|ladder|scaffold\w*|stairs)", r"fall from (a |the )?(height|tree|roof|terrace|building|ladder)"], "hi": ["पेड़ से गिर", "छत से गिर", "ऊंचाई से गिर"], "or": ["ଗଛରୁ ପଡ଼ି", "ଛାତରୁ ପଡ଼ି", "ଉଚ୍ଚରୁ ପଡ଼ି"]},
    "road_traffic_high_risk": {"en": [r"(hit|knocked down|run over) by (a |the )?(car|bus|truck|vehicle|lorry|bike)", r"(high[- ]speed|head[- ]on) (crash|collision|accident)", r"thrown (from|off) (the )?(vehicle|bike|motorcycle)", r"trapped in (the )?(car|vehicle)", r"without (a )?(seat ?belt|helmet)"], "hi": ["गाड़ी ने टक्कर", "ट्रक ने टक्कर"], "or": ["ଗାଡ଼ି ଧକ୍କା", "ଟ୍ରକ୍ ଧକ୍କା"]},
    "penetrating_injury": {"en": [r"stab\w*", r"gunshot", r"shot", r"knife (wound|injury)", r"penetrat\w*", r"impaled"], "hi": ["चाकू", "गोली लगी"], "or": ["ଛୁରୀ", "ଗୁଳି"]},
    # Injury wording only: "works in a stone-crushing unit" or "crusher" is an occupation, not an injury.
    "crush_injury": {"en": [r"crush(ed)? (injury|injuries)", r"crushed", r"got crushed", r"(trapped|stuck|pinned) under"], "hi": ["दब गया", "कुचल"], "or": ["ଚାପି ହୋଇଗଲା"]},
    "limb_deformity": {"en": [r"fractur\w*", r"broken (bone|arm|leg|hand)", r"dislocat\w*", r"(arm|leg) (is )?(bent|deformed)"], "hi": ["हड्डी टूट", "फ्रैक्चर"], "or": ["ହାଡ଼ ଭାଙ୍ଗି"]},
    "threatened_limb": {"en": [r"(arm|leg|hand|foot|limb) (is |has gone |turned )?(cold and pale|pale and cold|pulseless|blue and cold)", r"no pulse in (the )?(arm|leg|foot|hand)"], "hi": [], "or": []},
    "drowning_hanging_electrocution": {"en": [r"drown\w*", r"hanging", r"hanged", r"electr\w* (shock|cution)", r"electrocut\w*", r"current (laga|lagi|lag gaya)", r"lightning"], "hi": ["डूब", "फांसी", "करंट लग", "बिजली गिर"], "or": ["ବୁଡ଼ି", "ଫାଶୀ", "କରେଣ୍ଟ", "ବିଜୁଳି"]},
    "snake_bite": {"en": [r"snake ?bite", r"bitten by (a )?snake", r"snake bit", r"saanp (ne )?kaat", r"sap (ne )?kaat"], "hi": ["सांप ने काट", "साँप ने काट", "सर्पदंश", "सांप काट"], "or": ["ସାପ କାମୁଡ଼ି", "ସାପ କାମୁଡ଼ା", "ସର୍ପଦଂଶନ"]},
    "animal_bite": {"en": [r"(dog|monkey|cat|animal|rat|jackal) ?bite", r"bitten by (a |the )?(dog|monkey|cat|animal|rat|jackal)", r"kutte ne kaat"], "hi": ["कुत्ते ने काट", "बंदर ने काट"], "or": ["କୁକୁର କାମୁଡ଼ି", "ମାଙ୍କଡ଼ କାମୁଡ଼ି"]},
    "poisoning": {"en": [r"poison\w*", r"overdose", r"swallow\w* (pesticide|kerosene|acid|bleach|tablets|pills)", r"pesticide", r"insecticide", r"kerosene", r"(chemical|gas) (exposure|leak|inhal\w*)", r"drank (pesticide|poison|acid)", r"zeher"], "hi": ["जहर", "ज़हर", "कीटनाशक", "मिट्टी का तेल पी"], "or": ["ବିଷ ଖାଇ", "ବିଷ ପିଇ", "ବିଷାକ୍ତ", "କୀଟନାଶକ"]},
    "needle_stick": {"en": [r"needle ?(stick|prick)", r"pricked by (a |the )?(used )?needle"], "hi": ["सुई चुभ"], "or": ["ଛୁଞ୍ଚି ଫୋଡ଼ି"]},
    "allergic_reaction": {"en": [r"allerg\w*", r"anaphyla\w*", r"hives all over", r"reaction (to|after) (the )?(injection|medicine|tablet|food|sting)", r"(bee|wasp) sting"], "hi": ["एलर्जी"], "or": ["ଆଲର୍ଜି"]},
    "sexual_assault": {"en": [r"sexual(ly)? assault\w*", r"\braped?\b", r"molest\w*"], "hi": ["बलात्कार", "यौन उत्पीड़न"], "or": ["ଧର୍ଷଣ", "ଯୌନ ନିର୍ଯାତନା"]},
    "pregnant": {"en": [r"pregnan\w*", r"expecting (a baby|mother)", r"garbh\w*"], "hi": ["गर्भवती", "गर्भ से"], "or": ["ଗର୍ଭବତୀ"]},
    "vaginal_bleeding": {"en": [r"(vaginal|per vaginal|pv) (bleed\w*|spotting)", r"bleeding (from|down) (below|vagina)", r"spotting"], "hi": ["योनि से खून", "नीचे से खून"], "or": ["ଯୋନିରୁ ରକ୍ତ"]},
    "reduced_fetal_movement": {"en": [r"(baby|fetal|foetal) (is )?(moving|movements?) (less|reduced|not)", r"reduced (fetal|foetal|baby'?s?) movements?", r"baby (is )?not moving", r"less (than usual )?(movement|moving)"], "hi": ["बच्चा कम हिल", "बच्चा नहीं हिल"], "or": ["ଶିଶୁ କମ୍ ହଲୁଛି", "ଶିଶୁ ହଲୁନି"]},
    "fluid_leaking": {"en": [r"(water|fluid) (is )?(leak\w*|broke|broken)", r"leaking fluid", r"waters? broke"], "hi": ["पानी निकल", "पानी गिर"], "or": ["ପାଣି ବାହାରୁଛି"]},
    "labour_pains": {"en": [r"labou?r pains?", r"contractions?", r"in labou?r"], "hi": ["प्रसव पीड़ा", "दर्द शुरू"], "or": ["ପ୍ରସବ ଯନ୍ତ୍ରଣା"]},
    "swelling_face_hands": {"en": [r"(swollen|swelling (of|in)( the)?) (face|hands|fingers)", r"(face|hands) (are |is )?swollen"], "hi": ["चेहरे पर सूजन", "हाथों में सूजन"], "or": ["ମୁହଁ ଫୁଲିଛି", "ହାତ ଫୁଲିଛି"]},
    "known_time_sensitive_dx": {"en": [r"heart attack", r"myocardial infarction", r"acute coronary", r"aortic dissection", r"sepsis", r"leuka?emia", r"aplastic ana?emia"], "hi": ["दिल का दौरा"], "or": ["ହୃଦଘାତ"]},
    "chemo_recent": {"en": [r"chemo(therapy)?"], "hi": ["कीमो"], "or": ["କେମୋ"]},
}

# Symptom tiles (English working text sent by the kiosk) -> findings.
TILES: dict[str, list[str]] = {
    "fever": ["fever"],
    "cough": ["cough"],
    "breathlessness": ["breathless"],
    "chest pain": ["chest_pain", "pain"],
    "headache": ["headache", "pain"],
    "stomach pain": ["abdominal_pain", "pain"],
    "vomiting": ["vomiting"],
    "loose motions (diarrhoea)": ["diarrhoea"],
    "body ache": ["pain"],
    "injury or burn": ["injury"],
    "bleeding": ["bleeding"],
    "dizziness": [],
    "swelling": [],
    "skin rash": ["rash"],
    "tiredness": ["fatigue"],
    "fits / convulsion": ["seizure"],
}

# Structured answers: (question id, answer prefix) -> {finding: value}. Prefix match on the
# English option text the kiosk sends, so a translated UI still produces the same codes.
ANSWERS: list[tuple[str, str, dict[str, bool]]] = [
    ("chest_radiation", "Yes", {"chest_pain_radiating": True}),
    ("chest_radiation", "No", {"chest_pain_radiating": False}),
    ("chest_sweat", "Yes", {"sweating": True}),
    ("chest_sweat", "No", {"sweating": False}),
    ("breath_speech", "No", {"incomplete_sentences": True}),
    ("breath_speech", "Yes", {"incomplete_sentences": False}),
    ("child_danger", "No", {"unable_to_drink": True}),
    ("child_danger", "Vomits", {"vomits_everything": True}),
    ("child_danger", "Yes", {"unable_to_drink": False, "vomits_everything": False}),
    ("fever_bleed", "Rash", {"rash": True}),
    ("fever_bleed", "Bleeding", {"bleeding": True, "gum_bleed": True}),
    ("mat_vision", "Yes", {"visual_disturbance": True}),
    ("mat_vision", "No", {"visual_disturbance": False}),
    ("mat_movement", "Less", {"reduced_fetal_movement": True}),
    ("mat_movement", "Yes", {"reduced_fetal_movement": False}),
    ("mat_bleed", "Yes", {"vaginal_bleeding": True}),
    ("mat_bleed", "Fluid", {"fluid_leaking": True}),
    ("mat_bleed", "No", {"vaginal_bleeding": False, "fluid_leaking": False}),
    ("dehyd", "Yes", {"dehydration": True, "sunken_eyes": True}),
    ("inj_loc", "Yes", {"syncope": True, "head_injury": True}),
    ("inj_loc", "No", {"syncope": False, "head_injury": False}),
    ("abd_where", "Upper", {"upper_abdominal_pain": True}),
    ("conscious", "Yes", {"unresponsive": False, "altered_mental_status": False}),
    ("conscious", "Drowsy", {"altered_mental_status": True, "lethargy": True}),
    ("conscious", "Not", {"unresponsive": True}),
    ("one_side", "Yes", {"one_sided_weakness": True}),
    ("one_side", "No", {"one_sided_weakness": False}),
    ("mechanism", "Fall", {"fall_from_height": True}),
    ("mechanism", "Road", {"road_traffic_high_risk": True}),
    ("mechanism", "Stab", {"penetrating_injury": True}),
    ("mechanism", "Crush", {"crush_injury": True}),
    ("mechanism", "Burn", {"burn": True}),
    ("mechanism", "Bite", {"animal_bite": True}),
    ("mechanism", "Snake", {"snake_bite": True}),
    ("mechanism", "Minor", {"fall_from_height": False, "road_traffic_high_risk": False, "penetrating_injury": False, "crush_injury": False}),
    ("sudden_head", "Sudden", {"headache_sudden": True}),
    ("sudden_head", "Gradual", {"headache_sudden": False}),
    ("sudden_abd", "Sudden", {"abdominal_pain_sudden": True}),
    ("sudden_abd", "Gradual", {"abdominal_pain_sudden": False}),
]

# Negation scope: at most two words, and never across "and"/"with"/"aur" (a false negation hides a
# symptom; a missed negation only over-triages, so the window is deliberately short).
NEGATION_PRE = re.compile(r"\b(no|not|never|denies|denied|without|absent|free of|negative for|nahi|nahin)\b((?!\s+(and|with|aur|plus)\b)\s+\w+){0,2}\s*$")
NEGATION_POST_EN = re.compile(r"^\s*(\w+\s+){0,2}(nahi|nahin|nai|na)\b")
NEGATION_POST_INDIC = ("नहीं", "नही", "ନାହିଁ", "ନାହି", "ନାଇଁ", "ନାଇ", "ହେଉନି", "ହୋଇନି", "ହଉନି")
CLAUSE_SPLIT = re.compile(r"[.;!?।|\n]|,\s|\bbut\b|\bhowever\b|\blekin\b|\bpar\b|लेकिन|परंतु|किंतु|ପରନ୍ତୁ|କିନ୍ତୁ|ମାତ୍ର")


@dataclass
class Finding:
    value: bool | None
    evidence: list[str] = field(default_factory=list)  # human-readable: where it came from


def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", s or "").lower()


# Spoken Hindi and Odia, as speech recognition writes it, varies in spelling where the sound does not: ଝାଡ଼ା/ଝାଡା,
# ଜ୍ୱର/ଜର (the ୱ is not pronounced), ଶ/ଷ/ସ (all "s" in Odia), long and short i/u, chandrabindu and anusvara.
# Matching runs on a "loose" form of both the text and the lexicon so each spelling of a word matches.
_LOOSE = str.maketrans({
    "़": None, "଼": None, "‌": None, "‍": None,  # nukta, ZWNJ, ZWJ
    "ँ": "ं", "ଁ": "ଂ",  # chandrabindu → anusvara
    "ी": "ि", "ू": "ु", "ई": "इ", "ऊ": "उ",  # Devanagari ī ū → i u
    "ୀ": "ି", "ୂ": "ୁ", "ଈ": "ଇ", "ଊ": "ଉ",  # Odia ī ū → i u
    "ଶ": "ସ", "ଷ": "ସ", "ଣ": "ନ",  # Odia ଶ ଷ → ସ, ଣ → ନ
})


def _loose(s: str) -> str:
    # Odia ୍ୱ (wa-phala) is silent; speech recognition also writes it with ଵ (U+0B35): ଜ୍ଵର (B9 live test, 6 Oct)
    return _norm(s).replace("୍ୱ", "").replace("୍ଵ", "").translate(_LOOSE)


def _indic_regex(pattern: str) -> re.Pattern:
    """Indic lexicon entries are substrings, with two additions: "A … B" allows up to two words between A and B
    ("ଛାତି ବି ଦରଦ", "सीने में बहुत दर्द"), and "^"/"$" pin a short word to the start/end of a word so ଜ୍ୱର does not
    match inside ଜରୁରୀ ("urgent") once loosened to ଜର."""
    parts = []
    for part in pattern.split(" … "):
        start, end = part.startswith("^"), part.endswith("$")
        body = re.escape(_loose(part.strip("^$")))
        parts.append(("(?<!\\S)" if start else "") + body + ("(?!\\S)" if end else ""))
    return re.compile(r"\S*(?:\s+\S+){0,2}?\s+\S*?".join(parts))


_INDIC: dict[str, re.Pattern] = {}


def _clause_hits(clause: str, pattern: str, latin: bool) -> list[tuple[int, int]]:
    if latin:
        return [m.span() for m in re.finditer(rf"(?<![\w]){pattern}(?![\w])", clause)]
    rx = _INDIC.get(pattern) or _INDIC.setdefault(pattern, _indic_regex(pattern))
    return [m.span() for m in rx.finditer(clause)]


def _negated(clause: str, start: int, end: int) -> bool:
    before, after = clause[:start], clause[end:]
    if NEGATION_PRE.search(before):
        return True
    if NEGATION_POST_EN.search(after):
        return True
    tail = after[:24]
    return any(_loose(n) in tail for n in NEGATION_POST_INDIC)


def scan_text(text: str, source: str) -> dict[str, Finding]:
    """Lexicon scan of one free-text field. Affirmed mentions win over negated ones."""
    found: dict[str, Finding] = {}
    clauses = [c for c in CLAUSE_SPLIT.split(_norm(text)) if c and c.strip()]
    for fid, langs in LEXICON.items():
        for clause in clauses:
            loose = _loose(clause)
            snippet = clause.strip()[:80]  # evidence shows the words as written, not the loose form
            for lang, pats in langs.items():
                for pat in pats:
                    for s, e in _clause_hits(clause if lang == "en" else loose, pat, lang == "en"):
                        neg = _negated(clause if lang == "en" else loose, s, e)
                        cur = found.get(fid)
                        if not neg:
                            if not cur or cur.value is not True:
                                found[fid] = Finding(True, [f'{source}: "{snippet}"'])
                        elif not cur:
                            found[fid] = Finding(False, [f'{source} (denied): "{snippet}"'])
    return found


# Generic findings that every specific one implies; a translation that says "pain" where the patient said
# "chest pain" is not a mismatch worth a flag.
_TOO_GENERIC = {"pain", "bleeding", "injury"}


def translation_check(symptom: dict) -> dict | None:
    """Compare what the lexicon finds in the patient's own words with what it finds in the machine translation.
    Only for languages the lexicon covers (Hindi, Odia), and for a finding only when that language has words for it,
    so a gap in the word list is not reported as a translation error. Returns None when they agree."""
    lang = symptom.get("language") or "en"
    orig, english = symptom.get("original_text") or "", symptom.get("text") or ""
    if lang == "en" or not orig or orig == english or not any(lang in v for v in LEXICON.values()):
        return None
    said = {f for f, x in scan_text(orig, "").items() if x.value is True}
    rendered = {f for f, x in scan_text(english, "").items() if x.value is True}
    covered = {f for f, v in LEXICON.items() if v.get(lang)}
    missed = sorted(f for f in said - rendered - _TOO_GENERIC)
    added = sorted(f for f in rendered - said - _TOO_GENERIC if f in covered)
    if not missed and not added:
        return None
    return {"language": lang, "original": orig, "english": english, "missed": missed, "added": added}


def _merge(into: dict[str, Finding], fid: str, value: bool, evidence: str) -> None:
    cur = into.get(fid)
    if cur is None or cur.value is None:
        into[fid] = Finding(value, [evidence])
    elif value is True and cur.value is not True:
        into[fid] = Finding(True, [evidence])  # any affirmed source beats a denial
    elif value == cur.value and evidence not in cur.evidence:
        cur.evidence.append(evidence)


def extract(intake: dict, category: str | None = None) -> dict[str, Finding]:
    """All findings for an intake. Keys absent from the result are resolved by `resolve`."""
    out: dict[str, Finding] = {}

    for tile in intake.get("selected_symptoms", []) or []:
        for fid in TILES.get(_norm(tile).strip(), []):
            _merge(out, fid, True, f'symptom tile "{tile}"')

    for a in intake.get("answers", []) or []:
        qid, ans = a.get("qid", ""), (a.get("answer") or "").strip()
        for q, prefix, values in ANSWERS:
            if q == qid and ans.lower().startswith(prefix.lower()):
                for fid, val in values.items():
                    _merge(out, fid, val, f'answer to "{a.get("question") or qid}": {ans}')

    cc = intake.get("chief_complaint", "")
    texts = [("chief complaint", cc, set())]
    for s in intake.get("symptoms", []) or []:
        chk = translation_check(s)
        unconfirmed = set(chk["added"]) if chk else set()
        if cc and cc == s.get("text"):  # the kiosk uses the first sentence's English as the chief complaint
            texts[0] = ("chief complaint", cc, unconfirmed)
        texts.append((f"{s.get('source', 'text')} intake", s.get("text", ""), unconfirmed))
        if s.get("original_text") and s.get("original_text") != s.get("text"):
            texts.append((f"{s.get('source', 'text')} intake (original {s.get('language', '')})", s["original_text"], set()))
    # B9: a symptom only the second speech engine heard still counts, as with translation, labelled so; the note's
    # DISAGREE flag shows both transcripts.
    for s in intake.get("symptoms", []) or []:
        h = s.get("second_hearing") if s.get("source") == "voice" else None
        if not isinstance(h, dict):
            continue
        heard = {f for first in (s.get("original_text"), s.get("text")) for f, x in scan_text(first or "", "").items() if x.value is True}
        src = f"voice intake (second speech engine only, {h.get('engine') or 'online'} — not in the confirmed transcript)"
        for second in (h.get("text"), h.get("translation")):
            for fid, f in scan_text(second or "", src).items():
                if f.value is True and fid not in heard:
                    _merge(out, fid, True, f.evidence[0])
    for src, t, unconfirmed in texts:
        # A finding only the translation produced still counts (missing a real symptom is worse than over-triage),
        # but its evidence says so, and the note's MT-CHECK flag names the sentence.
        for fid, f in scan_text(t, src).items():
            for ev in f.evidence:
                _merge(out, fid, f.value, ev.replace(f"{src}:", f"{src} (machine translation only — not found in the patient's words):", 1) if fid in unconfirmed else ev)

    # Clinician danger-sign check (nurse observations). Checked signs are present; once the
    # check is recorded, every unchecked sign is absent rather than unknown.
    exam = intake.get("exam") or {}
    for fid in exam.get("signs", []) or []:
        if fid in FINDINGS:
            _merge(out, fid, True, f"danger-sign check by {exam.get('by') or 'clinician'}")
    if exam.get("done"):
        for fid, (_, kind) in FINDINGS.items():
            if kind == SIGN and fid not in out:
                out[fid] = Finding(False, [f"danger-sign check by {exam.get('by') or 'clinician'}: not present"])

    if category == "maternal":
        _merge(out, "pregnant", True, "visit category: pregnancy")
    if out.get("vaginal_bleeding", Finding(None)).value is not True and category == "maternal" and out.get("bleeding", Finding(None)).value is True:
        _merge(out, "vaginal_bleeding", True, "bleeding reported during a pregnancy visit")

    # Specific findings imply their general parent.
    for child, parent in [("chest_pain_radiating", "chest_pain"), ("bleeding_heavy", "bleeding"), ("haematemesis", "bleeding"), ("epistaxis", "bleeding"), ("gum_bleed", "bleeding"),
                          ("vomits_everything", "vomiting"), ("headache_sudden", "headache"), ("abdominal_pain_sudden", "abdominal_pain"), ("upper_abdominal_pain", "abdominal_pain"),
                          ("head_injury", "injury"), ("fall_from_height", "injury"), ("road_traffic_high_risk", "injury"), ("penetrating_injury", "injury"), ("crush_injury", "injury"),
                          ("limb_deformity", "injury"), ("rash_spreading", "rash"), ("chest_pain", "pain"), ("abdominal_pain", "pain"), ("headache", "pain"), ("scrotal_pain", "pain")]:
        c = out.get(child)
        if c and c.value is True:
            _merge(out, parent, True, c.evidence[0])
    return out


def resolve(found: dict[str, Finding], fid: str) -> Finding:
    if fid not in FINDINGS:
        raise KeyError(f"Unknown finding: {fid}")
    if fid in found:
        return found[fid]
    _, kind = FINDINGS[fid]
    return Finding(None, []) if kind == SIGN else Finding(False, ["not reported"])
