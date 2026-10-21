# Urdu and Arabic: for the owner's review

> Status: **signed off by the Monarch for production, 2026-10-18;** the three newer headline words
> (COUNTER, HIGH PRESS, REF'S CALL) **signed off 2026-10-20.** The headline words and the
> translator's instructions are final; change them only with the Monarch.
> How to review: mark each line ✅ (good), or write the better wording beside it. The fixed
> headline words go into `court/localizer.py` (`LABELS`, `ON_TOP`); the translated lines are
> written live by the model each match, so a note on them becomes an instruction to the translator.

## The fixed headline words (written by Claude; used whenever a cue is in Urdu or Arabic)

| English | Urdu | Arabic | Your call |
|---|---|---|---|
| GOAL | گول | هدف | |
| BIG CHANCE | سنہری موقع | فرصة خطيرة | |
| MOMENTUM | میچ پر گرفت | السيطرة | |
| GREAT PASS | شاندار پاس | تمريرة رائعة | |
| on top (after a team code) | حاوی | يسيطر | |

## Three newer headline words (proposed by Claude 2026-10-19, signed off by the Monarch 2026-10-20)

Counterattacks, the high press and the ref's call. Live in `court/localizer.py` (`LABELS`).

| English | Urdu | Arabic | Your call |
|---|---|---|---|
| COUNTER | جوابی حملہ | هجمة مرتدة | ✅ |
| HIGH PRESS | اونچا دباؤ | ضغط عالٍ | ✅ |
| REF'S CALL | ریفری کا فیصلہ | قرار الحكم | ✅ |

## One newer headline word (proposed by Claude 2026-10-21, awaiting the Monarch)

A match broken open: the ball changing hands again and again, with a shot at each end (the
Scout's control-or-chaos call). Until it is signed off, the headline airs in English under every
language (`court/localizer.py`, `AWAITING_REVIEW`); once ✅, it moves into `LABELS`.

| English | Urdu | Arabic | Your call |
|---|---|---|---|
| END TO END | دو طرفہ حملے (attacks both ways) | كرّ وفرّ (attack and fall back) | |

## Words that mark a question as about betting (added by Claude, signed off by the Monarch 2026-10-20)

Roadmap principle 8: a question about bets, odds or gambling gets fixed words that steer away from
gambling, before any model reads it (`court/ask.py`, `BETTING`). These words are never shown; they
only decide which questions are held back. Whole words only. Mark each ✅, cross out any that would
catch an ordinary football question, and add any word a fan would use that is missing.

| Language | Word | Meaning | Your call |
|---|---|---|---|
| Urdu | جوا، جوئے | gambling (jua) |✅ |
| Urdu | سٹہ، سٹے | betting (satta) |✅ |
| Arabic | مراهنة، مراهنات (any word starting مراهن) | betting (murahana) |✅ |
| Arabic | رهان | a bet (rihan) |✅ |
| Arabic | قمار | gambling (qimar) |✅ |

## Live lines from one match (seed 21, translated by gpt-4.1-mini on Foundry)

Every number in each translation was checked against the verified English line, and every name
kept as written. Judge the language: register, accuracy, anything added or lost.

### 6' goal
- **English (verified, Urdu run):** Kai Morsen scores for Brackenfield from 8 meters, following a precise pass from Ilyas Pellby. A well-taken shot with an expected goal value of 0.33.
- **Urdu:** Kai Morsen نے Brackenfield کے لیے 8 میٹر کی دوری سے گول کیا، جو Ilyas Pellby کے درست پاس کے بعد ہوا۔ ایک اچھا شاٹ جس کی متوقع گول ویلیو 0.33 ہے۔  
  Your call: 
- **English (verified, Arabic run):** Kai Morsen scores for Brackenfield from 8 meters, a solid chance with an xG of 0.33, assisted by Ilyas Pellby.
- **Arabic:** سجل Kai Morsen لصالح Brackenfield من مسافة 8 أمتار، فرصة قوية مع xG بقيمة 0.33، بمساعدة Ilyas Pellby.  
  Your call: 

### 8' great pass
- **English (verified, Urdu run):** Zane Garsen picks out Kai Morsen with a precise 36-meter pass, difficulty 47 and 86% accurate, but Morsen's shot goes wide of the target.
- **Urdu:** Zane Garsen نے Kai Morsen کو ایک درست 36 میٹر پاس دیا، مشکل 47 اور 86% درستگی کے ساتھ، لیکن Morsen کا شاٹ ہدف سے باہر گیا۔  
  Your call: 

### 33' goal
- **English (verified, Urdu run):** Luka Dunvik fires a powerful 12-meter shot at 108 km/h to level the score for Saltmarsh Rovers, brilliantly assisted by Adem Rosmere.
- **Urdu:** Luka Dunvik نے Saltmarsh Rovers کے لیے اسکور برابر کرنے کے لیے Adem Rosmere کی شاندار اسسٹ کے ساتھ 108 km/h کی رفتار سے 12 میٹر کا زوردار شاٹ مارا۔  
  Your call: 
- **English (verified, Arabic run):** Luka Dunvik fires a powerful 12-meter shot at 108 km/h, scoring for Saltmarsh Rovers after a precise 6-meter pass from Adem Rosmere.
- **Arabic:** أطلق Luka Dunvik تسديدة قوية من مسافة 12 مترًا بسرعة 108 كم/س، مسجلاً هدفًا لـ Saltmarsh Rovers بعد تمريرة دقيقة من Adem Rosmere لمسافة 6 أمتار.  
  Your call: 

### 48' big chance
- **English (verified, Urdu run):** Luka Dunvik fires a powerful 83 km/h shot from 9 meters, set up by Adem Rosmere, but the Brackenfield keeper makes a solid save to deny Saltmarsh Rovers.
- **Urdu:** Luka Dunvik نے Adem Rosmere کی پاس پر 9 میٹر سے 83 کلومیٹر فی گھنٹہ کی طاقتور شاٹ ماری، لیکن Brackenfield کے گول کیپر نے Saltmarsh Rovers کو گول کرنے سے روک دیا۔  
  Your call: 
- **English (verified, Arabic run):** Luka Dunvik fires a powerful 83 km/h shot from 9 meters after a 15-meter pass from Adem Rosmere, but the Brackenfield keeper makes a crucial save to deny Saltmarsh Rovers a big chance.
- **Arabic:** أطلق Luka Dunvik تسديدة قوية بسرعة 83 كم/س من مسافة 9 أمتار بعد تمريرة بطول 15 مترًا من Adem Rosmere، لكن حارس Brackenfield قام بتصدي حاسم ليحرم Saltmarsh Rovers من فرصة كبيرة.  
  Your call: 

### 53' big chance
- **English (verified, Urdu run):** Luka Dunvik fires a shot from 10 meters for Saltmarsh Rovers, but it goes off target despite a promising xG of 0.25.
- **Urdu:** Luka Dunvik نے Saltmarsh Rovers کے لیے 10 میٹر سے شاٹ مارا، لیکن یہ 0.25 کے امید افزا xG کے باوجود ہدف سے باہر گیا۔  
  Your call: 
- **English (verified, Arabic run):** Luka Dunvik fires a 10-meter shot for Saltmarsh Rovers, but it sails just wide with an xG of 0.25.
- **Arabic:** يُطلق Luka Dunvik تسديدة من مسافة 10 أمتار لصالح Saltmarsh Rovers، لكنها تخرج بجوار المرمى بقيمة xG تبلغ 0.25.  
  Your call: 

### 55' goal
- **English (verified, Urdu run):** Ilyas Pellby converts a penalty with a powerful 96 km/h shot to put Brackenfield ahead 2-1.
- **Urdu:** Ilyas Pellby نے ایک طاقتور 96 km/h کی شاٹ کے ساتھ پنالٹی کو گول میں تبدیل کیا اور Brackenfield کو 2-1 کی برتری دلائی۔  
  Your call: 
- **English (verified, Arabic run):** Ilyas Pellby calmly converts the penalty for Brackenfield, sending the ball in at 96 km/h and putting his team ahead with their second goal.
- **Arabic:** Ilyas Pellby يسجل ركلة الجزاء بهدوء لفريق Brackenfield، مرسلًا الكرة بسرعة 96 كم/س ومُعطيًا فريقه التقدم بهدفهم الثاني.  
  Your call: 

### 56' goal
- **English (verified, Urdu run):** Bilal Arholm fires a 10-meter shot into the net for Saltmarsh Rovers, assisted by Adem Rosmere's precise 22-meter pass, turning a speculative chance into a crucial goal.
- **Urdu:** Bilal Arholm نے Saltmarsh Rovers کے لیے Adem Rosmere کی درست 22 میٹر پاس کی مدد سے 10 میٹر کا شاٹ نیٹ میں مارا، ایک قیاسی موقع کو اہم گول میں بدل دیا۔  
  Your call: 
- **English (verified, Arabic run):** Bilal Arholm scores from 10 meters, converting a low-probability chance with a 0.11 xG, assisted by Adem Rosmere's challenging 22-meter pass.
- **Arabic:** يسجل Bilal Arholm من مسافة 10 أمتار، محولاً فرصة منخفضة الاحتمال بقيمة 0.11 xG، بمساعدة تمريرة Adem Rosmere الصعبة من مسافة 22 متراً.  
  Your call: 

### 62' momentum swing
- **English (verified, Urdu run):** Saltmarsh Rovers dominate possession with 42 of 46 passes completed in the last five minutes, 91% accuracy, pushing deep into Brackenfield's half with 36 final-third passes, while Brackenfield has none.
- **Urdu:** Saltmarsh Rovers نے آخری پانچ منٹوں میں 46 میں سے 42 پاس مکمل کر کے گیند پر قبضہ جما لیا، 91% درستگی کے ساتھ Brackenfield کے نصف میدان میں 36 آخری تہائی پاس بھیجے، جبکہ Brackenfield کے کوئی پاس نہیں۔  
  Your call: 
- **English (verified, Arabic run):** Saltmarsh Rovers dominate with 42 of 46 passes completed in the last 5 minutes, 91% accuracy up from 81%, sending 36 balls into the final third while Brackenfield have none. Momentum clearly on SAL's side.
- **Arabic:** يسيطر فريق Saltmarsh Rovers بإكمال 42 من 46 تمريرة في الدقائق الخمس الأخيرة، بدقة 91% مرتفعة من 81%، مرسلاً 36 كرة إلى الثلث الأخير بينما لم يرسل Brackenfield أي كرة. الزخم واضح لصالح SAL.  
  Your call: 

### 73' big chance
- **English (verified, Urdu run):** Luka Dunvik nearly breaks through for Saltmarsh Rovers with a 9-meter shot, narrowly off target. Adem Rosmere set him up with a difficult 36-meter pass.
- **Urdu:** Luka Dunvik Saltmarsh Rovers کے لیے 9 میٹر کے شاٹ کے ساتھ قریب تھا، جو ہدف سے تھوڑا سا باہر تھا۔ Adem Rosmere نے اسے ایک مشکل 36 میٹر کی پاس کے ساتھ سیٹ اپ کیا۔  
  Your call: 
- **English (verified, Arabic run):** Luka Dunvik fires a 9-meter shot for Saltmarsh Rovers, but it goes off target despite a promising assist from Adem Rosmere's 36-meter pass.
- **Arabic:** Luka Dunvik يسدد كرة من مسافة 9 أمتار لصالح Saltmarsh Rovers، لكنها تخرج عن المرمى رغم تمريرة واعدة من Adem Rosmere لمسافة 36 مترًا.  
  Your call: 

### 78' momentum swing
- **English (verified, Urdu run):** Brackenfield dominate possession, completing 28 of 35 passes in the last 5 minutes with 80% accuracy, significantly up from 70% earlier, pushing 20 passes into the final third compared to just 1 from Saltmarsh Rovers.
- **Urdu:** Brackenfield نے ملکیت پر قبضہ جما لیا ہے، آخری 5 منٹوں میں 35 میں سے 28 پاسز مکمل کیے ہیں 80% درستگی کے ساتھ، جو پہلے کے 70% سے نمایاں طور پر زیادہ ہے، اور Saltmarsh Rovers کے صرف 1 کے مقابلے میں آخری تہائی میں 20 پاسز بھیجے ہیں۔  
  Your call: 
- **English (verified, Arabic run):** Brackenfield dominate the last 5 minutes with 28 of 35 passes completed, an 80% rate up from 70%, driving 20 passes into the final third compared to Saltmarsh's single entry.
- **Arabic:** تسيطر Brackenfield على آخر 5 دقائق بإكمال 28 من 35 تمريرة، بمعدل 80% مرتفعًا من 70%، مع توجيه 20 تمريرة إلى الثلث الأخير مقابل دخول واحد فقط لـ Saltmarsh.  
  Your call: 

