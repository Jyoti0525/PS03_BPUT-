# Team recording kit: symptom sentences (TODO §2)

Measures speech recognition on **medical words**, which FLEURS (news-style read speech) does not test. Every
sentence is invented; nobody describes their own health.

## Before recording

Each speaker signs the consent below (paper or a signed photo). Keep the forms off the repository.

> I agree that my voice, reading the sentences I was given, is recorded and used to measure the Jeevia prototype's
> speech recognition. The sentences are not about my health. The recordings stay on the project's laptop, are not
> published, and are deleted after the evaluation (by 31 Oct 2026). I can withdraw at any time and my recordings will
> be deleted.
> Name, date, signature.

## How to record

- A phone or the laptop, in a quiet room, then a noisy one (a corridor) for half the sentences. Say which in `room`.
- One sentence per file, WAV or M4A, named `<language>_<speaker initials>_<number>` (e.g. `or_JS_03.wav`).
- Say it the way you would say it to a nurse. If your words differ from the script, write down what you **actually
  said**: that is the reference the machine is compared with.
- Put the files and a `dev.tsv` in `models/eval/team_<language>/` (not committed). `dev.tsv` has one line per file,
  tab-separated: `number`, `file name`, `exactly what was said`, `room`, `speaker initials`.

Then: `python backend/scripts/eval_asr.py models/eval/team_or or` (word errors overall), and the medical-word count
in the results is checked by hand against the **bold** words.

## Sentences (12 per language; say the bold words clearly but naturally)

| # | Meaning | Odia | Hindi |
|---|---|---|---|
| 1 | I have had **fever** for **three days**. | ତିନି ଦିନ ହେଲା **ଜ୍ୱର** ହେଉଛି। | मुझे **तीन दिन** से **बुखार** है। |
| 2 | My **chest** has been **hurting** since morning. | ସକାଳୁ **ଛାତି ଦରଦ** ହେଉଛି। | सुबह से **सीने में दर्द** है। |
| 3 | I am **short of breath** when I walk. | ଚାଲିଲେ **ନିଶ୍ୱାସ** ନେବାକୁ କଷ୍ଟ ହେଉଛି। | चलने पर **सांस फूलती** है। |
| 4 | **Loose stools** and **vomiting** since yesterday. | କାଲିଠୁ **ଝାଡ଼ା** ଓ **ବାନ୍ତି** ହେଉଛି। | कल से **दस्त** और **उल्टी** हो रही है। |
| 5 | She is **seven months pregnant** and has a **headache**. | ସେ **ସାତ ମାସ ଗର୍ଭବତୀ**, **ମୁଣ୍ଡ ବିନ୍ଧୁଛି**। | वह **सात महीने** की **गर्भवती** है, **सिर दर्द** है। |
| 6 | Her **feet are swollen** and **vision is blurred**. | **ଗୋଡ଼ ଫୁଲିଛି**, **ଆଖି ଝାପ୍ସା** ଦେଖାଯାଉଛି। | **पैरों में सूजन** है और **धुंधला दिखता** है। |
| 7 | The child had a **fit** this morning. | ପିଲାର ଆଜି ସକାଳେ **ଅଚେତ ହୋଇ ହାତଗୋଡ଼ ଥରିଲା**। | बच्चे को आज सुबह **दौरा** पड़ा। |
| 8 | **Blood** in the **cough** for a week. | ଏକ ସପ୍ତାହ ହେଲା **କାଶରେ ରକ୍ତ** ଆସୁଛି। | एक हफ़्ते से **खांसी में खून** आ रहा है। |
| 9 | I take **metformin** **twice a day**. | ମୁଁ ଦିନକୁ **ଦୁଇ ଥର** **ମେଟଫର୍ମିନ** ଖାଏ। | मैं दिन में **दो बार** **मेटफॉर्मिन** लेता हूँ। |
| 10 | My **sugar** was **two hundred and forty**. | ମୋର **ସୁଗାର** **ଦୁଇ ଶହ ଚାଳିଶି** ଥିଲା। | मेरी **शुगर** **दो सौ चालीस** थी। |
| 11 | Snake **bite** on the **leg**, one hour ago. | ଘଣ୍ଟାଏ ଆଗରୁ **ଗୋଡ଼ରେ ସାପ କାମୁଡ଼ିଲା**। | एक घंटा पहले **पैर में साँप ने काटा**। |
| 12 | **No fever**, but **burning** when passing **urine**. | **ଜ୍ୱର ନାହିଁ**, କିନ୍ତୁ **ପରିସ୍ରା** ବେଳେ **ଜଳାପୋଡ଼ା**। | **बुखार नहीं** है, पर **पेशाब** में **जलन** है। |

**English** speakers read the "Meaning" column. **Kannada** speakers say the meaning in their own Kannada and write
down what they said. **Code-mixed**: say the Hindi or Odia sentence with the English medical word (e.g. "मुझे तीन दिन
से fever है", "ସକାଳୁ chest pain ହେଉଛି").

Rows 1, 4, 7 and 12 also test known weak points: the spoken ଜର spelling, ଝାଡ଼ା, a danger sign said without the
textbook word, and a negation.
