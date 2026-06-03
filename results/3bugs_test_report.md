# 3-Bugs Quality Test Report — SkinRange

**Company ID:** `33eaf707-06f1-4e30-93d8-d8da71afaa92`  
**Total:** 100  |  **Pass:** 78  |  **Fail:** 22  |  **Pass rate:** 78%

---

## Summary by Bug

| Bug | Description | Pass | Fail | Rate |
|-----|-------------|------|------|------|
| bug1 | Product Info Completeness | 19 | 11 | 63% |
| bug2 | Recommendation Relevance | 28 | 7 | 80% |
| bug3 | Medicine-Type Queries | 31 | 4 | 88% |

---

## Detailed Results

| # | Tag | Bug | Status | Lang | Score | ms | Failures | Query | Answer (first 250 chars) |
|---|-----|-----|--------|------|-------|----|----------|-------|--------------------------|
| 1 | `B1-PC-01` | bug1 | ❌ FAIL | english | 0.250 | 3805 | missing:'2900'; missing:'2610' | what is the price of Ayush for Men | 💰 Here are the best matching options:  1. *Ayush for Men (Ayurvedic Sexual Wellness Capsules for Men)* - Category: Male Sexual Wellness - Used for: Ayurvedic capsules for male sexual wellness supporting testosterone levels, libido, erection quality,  |
| 2 | `B1-PC-02` | bug1 | ❌ FAIL | hinglish | 0.250 | 490 | missing:'14063'; missing:'12656' | Sandy RX ka price kya hai | 💰 Is concern ke liye ye options match karte hain:  1. *Sandy RX* - Category: Male Sexual Wellness - Kaam aata hai: A high-potency Ayurvedic and herbal capsule for men addressing low testosterone, erectile dysfunction (ED), premature ejaculation (PE), |
| 3 | `B1-PC-03` | bug1 | ❌ FAIL | english | 0.250 | 380 | missing:'2499' | what is the price of Kaama Gold Kit | 💰 Here are the best matching options:  1. *Kaama Gold Kit* - Category: Male Sexual Wellness - Used for: A comprehensive 4-in-1 Ayurvedic sexual wellness kit for men containing capsules, oil, powder, and avaleha (herbal jam). Supports testosterone lev |
| 4 | `B1-PC-04` | bug1 | ❌ FAIL | hinglish | 0.250 | 372 | missing:'4999' | Liv Muztang Capsules kitne ka hai | Is concern ke liye ye options match karte hain:  1. *Liv Muztang Plus Capsules* - Category: Male Sexual Wellness - Kaam aata hai: Ayurvedic male vitality capsules for improving stamina, hormonal balance, testosterone support, sexual wellness, and con |
| 5 | `B1-PC-05` | bug1 | ❌ FAIL | hinglish | 0.250 | 793 | missing:'1799'; missing:'1619' | Ultimate Hammer MRP aur prepaid price bata | 💰 Is concern ke liye ye options match karte hain:  1. *Ultimate Hammer (Ayurvedic Night Power Booster)* - Category: Male Sexual Wellness - Kaam aata hai: Ayurvedic capsules formulated to boost libido, erection strength and duration, manage premature  |
| 6 | `B1-DOS-01` | bug1 | ✅ PASS | english | 0.250 | 367 | — | How do I take Ayush for Men? what is the dosage? | Here are the best matching options:  1. *Ayush for Men (Ayurvedic Sexual Wellness Capsules for Men)* - Category: Male Sexual Wellness - Used for: Ayurvedic capsules for male sexual wellness supporting testosterone levels, libido, erection quality, st |
| 7 | `B1-DOS-02` | bug1 | ❌ FAIL | hinglish | 0.250 | 3557 | missing:'milk' | Sandy RX kaise lena chahiye | Sandy RX ko aapko din mein 2 capsules lene hain, aur best hai ise garam doodh ke saath lena. Yeh 3 mahine ka course hai, isliye regular lena zaroori hai. Agar aapko aur details chahiye toh batana! 😊 |
| 8 | `B1-DOS-03` | bug1 | ✅ PASS | hinglish | 0.250 | 358 | — | Aadved Adivasi Hair Oil kaise lagayen | 🌿 Is concern ke liye ye options match karte hain:  1. *Aadved Adivasi Hair Oil* - Category: Hair Care - Kaam aata hai: A multi-herb Ayurvedic hair oil for reducing hair fall, dandruff, premature greying, and promoting hair growth. Strengthens roots,  |
| 9 | `B1-DOS-04` | bug1 | ✅ PASS | hinglish | 0.250 | 486 | — | Stones Veda dosage kya hai | Is concern ke liye ye options match karte hain:  1. *Stones Veda* - Category: Kidney Health & Urinary Tract - Kaam aata hai: An Ayurvedic capsule and syrup kit for kidney stone removal, UTI relief, and urinary detoxification. Promotes natural kidney  |
| 10 | `B1-DOS-05` | bug1 | ✅ PASS | english | 0.250 | 361 | — | Addiction Killer Powder how to use | 🤝 Here are the best matching options:  1. *Addiction Killer Powder* - Category: Addiction & De-addiction - Used for: An Ayurvedic herbal powder designed to support recovery from alcohol, smoking, nicotine, and drug addiction. Helps reduce cravings, d |
| 11 | `B1-BEN-01` | bug1 | ✅ PASS | english | 0.250 | 2636 | — | what are the benefits of Kaama Gold Kit | The *Kaama Gold Kit* offers several benefits for male sexual wellness:  1. *Supports Testosterone Levels*: Helps maintain healthy testosterone levels. 2. *Enhances Libido*: Boosts sexual desire and performance. 3. *Improves Sexual Stamina*: Increases |
| 12 | `B1-BEN-02` | bug1 | ✅ PASS | hinglish | 0.250 | 3254 | — | Liv Muztang ke kya fayde hain | Liv Muztang capsules ke bahut saare fayde hain:  1. *Improves Sexual Performance*: Yeh erectile dysfunction (ED) aur premature ejaculation (PE) ko manage karne mein help karta hai. 2. *Boosts Libido*: Aapki sexual desire aur stamina badhata hai. 3. * |
| 13 | `B1-BEN-03` | bug1 | ❌ FAIL | english | 0.250 | 3039 | missing:'testosterone' | what does Ultimate Hammer do | Ultimate Hammer is an Ayurvedic Night Power Booster designed to enhance male sexual wellness. It helps to boost libido, strengthen erections, improve duration, and manage issues like premature ejaculation (PE) and erectile dysfunction (ED). Additiona |
| 14 | `B1-BEN-04` | bug1 | ✅ PASS | hinglish | 0.250 | 3682 | — | Stones Veda ke fayde kya hain | Stones Veda ke kuch fayde yeh hain:  - Kidney stone removal mein madad karta hai. - UTI relief aur urinary detoxification promote karta hai. - Natural kidney stone passage ko enhance karta hai. - Urinary flow behtar karta hai. - Naye mineral buildup  |
| 15 | `B1-BEN-05` | bug1 | ✅ PASS | hinglish | 0.250 | 361 | — | Liver Care Capsules se kya hota hai | 🛡️ Is concern ke liye ye options match karte hain:  1. *Liver Care Capsules* - Category: Liver Health - Kaam aata hai: Ayurvedic liver detox and regeneration capsules for fatty liver management, liver inflammation, toxin accumulation from alcohol and |
| 16 | `B1-CAT-01` | bug1 | ❌ FAIL | english | 0.250 | 366 | missing:'2900' | tell me everything about Ayush for Men | Here are the best matching options:  1. *Ayush for Men (Ayurvedic Sexual Wellness Capsules for Men)* - Category: Male Sexual Wellness - Used for: Ayurvedic capsules for male sexual wellness supporting testosterone levels, libido, erection quality, st |
| 17 | `B1-CAT-02` | bug1 | ✅ PASS | hinglish | 0.250 | 3396 | — | Jaam-e-Ishq ke baare mein poori jankari chahiye | Jaam-e-Ishq ek classical Unani herbal prash hai jo sexual health aur fertility ke liye bana hai, dono mardon aur auraton ke liye. Iske benefits hain:  - Enhances sexual performance, stamina, aur libido - Testosterone increase karta hai mardon mein au |
| 18 | `B1-CAT-03` | bug1 | ✅ PASS | english | 0.250 | 360 | — | tell me about Dr Piles Free in detail | 🩺 Here are the best matching options:  1. *Dr Piles Free* - Category: Piles & Digestive Health - Used for: A complete 3-in-1 Ayurvedic kit (capsules, powder, and oil) for treatment and management of internal and external piles (hemorrhoids), anal fis |
| 19 | `B1-CAT-04` | bug1 | ✅ PASS | hinglish | 0.250 | 377 | — | Vayu Shuddhi product ki poori details do | Is concern ke liye ye options match karte hain:  1. *Vayu Shuddhi* - Category: Respiratory Health - Kaam aata hai: Ayurvedic lung detox capsules formulated for smokers and individuals exposed to pollution. Clears airways, removes tar and mucus from l |
| 20 | `B1-CAT-05` | bug1 | ✅ PASS | hinglish | 0.250 | 364 | — | Aadved Sleep ke baare mein batao | 😴 Is concern ke liye ye options match karte hain:  1. *Aadved Sleep* - Category: Sleep & Wellness - Kaam aata hai: Non-addictive herbal sleep support capsules that improve sleep quality, manage insomnia symptoms, regulate the sleep-wake cycle, and re |
| 21 | `B1-DUR-01` | bug1 | ✅ PASS | english | 0.250 | 377 | — | how long should I take Ayush for Men | Here are the best matching options:  1. *Ayush for Men (Ayurvedic Sexual Wellness Capsules for Men)* - Category: Male Sexual Wellness - Used for: Ayurvedic capsules for male sexual wellness supporting testosterone levels, libido, erection quality, st |
| 22 | `B1-DUR-02` | bug1 | ✅ PASS | hinglish | 0.250 | 383 | — | Sandy RX kitne din lena hai | Is concern ke liye ye options match karte hain:  1. *Sandy RX* - Category: Male Sexual Wellness - Kaam aata hai: A high-potency Ayurvedic and herbal capsule for men addressing low testosterone, erectile dysfunction (ED), premature ejaculation (PE), l |
| 23 | `B1-DUR-03` | bug1 | ✅ PASS | hinglish | 0.250 | 389 | — | Kaama Gold ka full course kitna hai | 💰 Is concern ke liye ye options match karte hain:  1. *Kaama Gold Kit* - Category: Male Sexual Wellness - Kaam aata hai: A comprehensive 4-in-1 Ayurvedic sexual wellness kit for men containing capsules, oil, powder, and avaleha (herbal jam). Supports |
| 24 | `B1-DUR-04` | bug1 | ❌ FAIL | english | 0.250 | 1680 | missing:'week' | how long before Liv Muztang shows results | Consistency is key! Generally, it is recommended to take Liv Muztang products for at least 2-3 months to notice significant results. Remember, individual responses may vary based on various factors. If you have further questions, feel free to ask! 😊 |
| 25 | `B1-DUR-05` | bug1 | ❌ FAIL | hinglish | 0.250 | 377 | missing:'week'; missing:'day' | Addiction Killer kitne time mein kaam karta hai | 🤝 Is concern ke liye ye options match karte hain:  1. *Addiction Killer Ark (Addiction Killer Liquid)* - Category: Addiction & De-addiction - Kaam aata hai: A tasteless and colourless Ayurvedic liquid drop formulation for alcohol, smoking, and drug a |
| 26 | `B1-PACK-01` | bug1 | ❌ FAIL | hinglish | 0.250 | 380 | missing:'60' | Ayush for Men ka pack size kya hai | Is concern ke liye ye options match karte hain:  1. *M9 Shampoo (Instant Hair Colour Shampoo)* - Category: Hair Care - Kaam aata hai: An ammonia-free instant hair colouring shampoo that restores natural black hair colour in just 5 minutes. Comes as a |
| 27 | `B1-PACK-02` | bug1 | ✅ PASS | hinglish | 0.250 | 1177 | — | Sandy RX mein kitni tablets hoti hain | Sandy RX mein 60 capsules hoti hain. Agar aur kuch jana hai, toh batao! 😊 |
| 28 | `B1-PACK-03` | bug1 | ✅ PASS | english | 0.250 | 365 | — | what pack sizes are available for Kaama Gold | ✅ Here are the best matching options:  1. *Kaama Gold Kit* - Category: Male Sexual Wellness - Used for: A comprehensive 4-in-1 Ayurvedic sexual wellness kit for men containing capsules, oil, powder, and avaleha (herbal jam). Supports testosterone lev |
| 29 | `B1-PACK-04` | bug1 | ✅ PASS | hinglish | 0.250 | 379 | — | Dr Piles Free mein kya kya aata hai | 🩺 Is concern ke liye ye options match karte hain:  1. *Dr Piles Free* - Category: Piles & Digestive Health - Kaam aata hai: A complete 3-in-1 Ayurvedic kit (capsules, powder, and oil) for treatment and management of internal and external piles (hemor |
| 30 | `B1-PACK-05` | bug1 | ✅ PASS | hinglish | 0.250 | 2324 | — | Extra Time Kit mein kya included hai | Extra Time Kit mein yeh teen products hain:  1. *Extra Time Capsule* - subah lena hai. 2. *Extra Time++ Capsule* - raat ko lena hai. 3. *Extra Time Cream* - external use ke liye.  Yeh kit male sexual timing improve karta hai, premature ejaculation ko |
| 31 | `B2-DIA-01` | bug2 | ✅ PASS | hinglish | 0.250 | 495 | — | sugar control karne ki dawa chahiye | 🩺 Is concern ke liye ye options match karte hain:  1. *Dr. Madhu Amrit Diabetes Management Kit* - Category: Diabetes Management - Kaam aata hai: A complete 3-in-1 holistic diabetes management kit containing Ayush 82 Tablets, Liver Support Tablets, an |
| 32 | `B2-DIA-02` | bug2 | ✅ PASS | english | 0.250 | 511 | — | I have Type 2 diabetes what product do you have | 🩺 Here are the best matching options:  1. *Aadved Ayush 82 Tablets* - Category: Diabetes Management - Used for: A CCRAS-approved Ayurvedic tablet for Type 2 diabetes and prediabetes management. Helps regulate blood sugar levels, improves insulin sens |
| 33 | `B2-DIA-03` | bug2 | ✅ PASS | hinglish | 0.250 | 368 | — | blood sugar kam karne ka koi upay hai | 🩺 Is concern ke liye ye options match karte hain:  1. *Dr. Madhu Amrit Diabetes Management Kit* - Category: Diabetes Management - Kaam aata hai: A complete 3-in-1 holistic diabetes management kit containing Ayush 82 Tablets, Liver Support Tablets, an |
| 34 | `B2-HAIR-01` | bug2 | ❌ FAIL | hinglish | 0.250 | 378 | missing:'hair' | baal bahut girte hain koi oil batao | 🌿 Is concern ke liye ye options match karte hain:  1. *Ortho Veda Oil* - Category: Joint & Muscle Pain - Kaam aata hai: A clinically-tested, 100% plant-based Ayurvedic massage oil for joint stiffness, inflammation, knee and back pain, osteoarthritis, |
| 35 | `B2-HAIR-02` | bug2 | ✅ PASS | english | 0.250 | 419 | — | I have severe hair fall what product to use | 🌿 Here are the best matching options:  1. *Aadved Adivasi Hair Oil* - Category: Hair Care - Used for: A multi-herb Ayurvedic hair oil for reducing hair fall, dandruff, premature greying, and promoting hair growth. Strengthens roots, restores natural  |
| 36 | `B2-HAIR-03` | bug2 | ✅ PASS | hinglish | 0.250 | 380 | — | hair growth ke liye kya lena chahiye | 🌿 Is concern ke liye ye options match karte hain:  1. *Aadved Adivasi Hair Oil* - Category: Hair Care - Kaam aata hai: A multi-herb Ayurvedic hair oil for reducing hair fall, dandruff, premature greying, and promoting hair growth. Strengthens roots,  |
| 37 | `B2-KID-01` | bug2 | ✅ PASS | hinglish | 0.250 | 362 | — | pathri ka ilaj chahiye kidney stone treatment | 💧 Is concern ke liye ye options match karte hain:  1. *Stones Veda* - Category: Kidney Health & Urinary Tract - Kaam aata hai: An Ayurvedic capsule and syrup kit for kidney stone removal, UTI relief, and urinary detoxification. Promotes natural kidne |
| 38 | `B2-KID-02` | bug2 | ✅ PASS | english | 0.250 | 378 | — | stones veda for kidney stones how effective | 💧 Here are the best matching options:  1. *Stones Veda* - Category: Kidney Health & Urinary Tract - Used for: An Ayurvedic capsule and syrup kit for kidney stone removal, UTI relief, and urinary detoxification. Promotes natural kidney stone passage,  |
| 39 | `B2-KID-03` | bug2 | ✅ PASS | hinglish | 0.250 | 392 | — | gall bladder stone ke liye koi medicine hai | 💧 Is concern ke liye ye options match karte hain:  1. *Stones Veda* - Category: Kidney Health & Urinary Tract - Kaam aata hai: An Ayurvedic capsule and syrup kit for kidney stone removal, UTI relief, and urinary detoxification. Promotes natural kidne |
| 40 | `B2-PIL-01` | bug2 | ✅ PASS | hinglish | 0.250 | 354 | — | bawasir ka ilaj chahiye best medicine | 🩺 Is concern ke liye ye options match karte hain:  1. *Dr Piles Free* - Category: Piles & Digestive Health - Kaam aata hai: A complete 3-in-1 Ayurvedic kit (capsules, powder, and oil) for treatment and management of internal and external piles (hemor |
| 41 | `B2-PIL-02` | bug2 | ✅ PASS | english | 0.250 | 3028 | — | I have hemorrhoids can you help | I understand that dealing with hemorrhoids can be quite uncomfortable. You might find relief with our *Dr. Piles Free* kit.  - *Price*: Price and order link are available through support: +91 93113 91981 📞 - *Description*: This complete 3-in-1 Ayurve |
| 42 | `B2-PIL-03` | bug2 | ✅ PASS | hinglish | 0.250 | 4729 | — | pet mein gas bahut hoti hai digestion problem | Yeh struggle bahut common hai. Aapne sahi decision liya apni health ke liye. 💪 Aapko gut health ke liye humare do products recommend kar sakte hain:  1. *Vajra 44*    - *Price:* ₹1,200 (60 capsules)    - *Link:* Vajra 44: https://skinrange.com    - * |
| 43 | `B2-LIV-01` | bug2 | ✅ PASS | hinglish | 0.250 | 372 | — | liver weak hai koi medicine suggest karo | 🛡️ Is concern ke liye ye options match karte hain:  1. *SK Gut Raksha* - Category: Gut Health & Digestion - Kaam aata hai: An Ayurvedic gut detox and gut health system combining a daily powder and a weekly detox shot. Addresses chronic constipation,  |
| 44 | `B2-LIV-02` | bug2 | ✅ PASS | hinglish | 0.250 | 380 | — | fatty liver ke liye koi product hai | 🛡️ Is concern ke liye ye options match karte hain:  1. *Liver Care Capsules* - Category: Liver Health - Kaam aata hai: Ayurvedic liver detox and regeneration capsules for fatty liver management, liver inflammation, toxin accumulation from alcohol and |
| 45 | `B2-JNT-01` | bug2 | ❌ FAIL | hinglish | 0.250 | 361 | unwanted:'hair' | ghutne mein dard hai koi tel batao | 😟 Is concern ke liye ye options match karte hain:  1. *Ortho Veda Oil* - Category: Joint & Muscle Pain - Kaam aata hai: A clinically-tested, 100% plant-based Ayurvedic massage oil for joint stiffness, inflammation, knee and back pain, osteoarthritis, |
| 46 | `B2-JNT-02` | bug2 | ✅ PASS | hinglish | 0.250 | 393 | — | arthritis pain relief product chahiye | 😟 Is concern ke liye ye options match karte hain:  1. *Dhurandar Oil* - Category: Joint & Muscle Pain - Kaam aata hai: A 100% Ayurvedic vapor-action massage oil for joint stiffness, arthritis, spondylitis, sciatica, muscle pain, swelling, and injury  |
| 47 | `B2-IMM-01` | bug2 | ✅ PASS | hinglish | 0.250 | 378 | — | immunity boost karne ke liye kya lena chahiye | 🛡️ Is concern ke liye ye options match karte hain:  1. *Ayush Kavach (Immunity System Booster Capsules)* - Category: Immunity & General Wellness - Kaam aata hai: Ayurvedic immunity booster capsules that enhance the body's natural defence against infe |
| 48 | `B2-IMM-02` | bug2 | ✅ PASS | hinglish | 0.250 | 365 | — | bar bar sardi bukhar aata hai immunity weak hai | 🛡️ Is concern ke liye ye options match karte hain:  1. *SK Gut Raksha* - Category: Gut Health & Digestion - Kaam aata hai: An Ayurvedic gut detox and gut health system combining a daily powder and a weekly detox shot. Addresses chronic constipation,  |
| 49 | `B2-ADD-01` | bug2 | ❌ FAIL [FB] | hinglish | — | 611 | missing:'addiction' | cigarette chhodne ki dawa chahiye | Sorry, is topic pe mere paas exact info nahi hai. Support team se connect ho jao ya thoda aur detail bhejo. |
| 50 | `B2-ADD-02` | bug2 | ✅ PASS | english | 0.250 | 360 | — | alcohol addiction treatment product | 🤝 Here are the best matching options:  1. *Addiction Killer Ark (Addiction Killer Liquid)* - Category: Addiction & De-addiction - Used for: A tasteless and colourless Ayurvedic liquid drop formulation for alcohol, smoking, and drug addiction recovery |
| 51 | `B2-SKIN-01` | bug2 | ✅ PASS | hinglish | 0.250 | 372 | — | safed daag ka ilaj chahiye vitiligo treatment | Is concern ke liye ye options match karte hain:  1. *Saumya Plus* - Category: Skin Health — Vitiligo - Kaam aata hai: An Ayurvedic capsule and oil combination for vitiligo (Safed Daag / white skin patches). Stimulates natural melanin production, supp |
| 52 | `B2-SKIN-02` | bug2 | ✅ PASS | english | 0.250 | 354 | — | white skin patches treatment medicine | ✨ Here are the best matching options:  1. *Saumya Plus* - Category: Skin Health — Vitiligo - Used for: An Ayurvedic capsule and oil combination for vitiligo (Safed Daag / white skin patches). Stimulates natural melanin production, supports repigmenta |
| 53 | `B2-WGT-01` | bug2 | ✅ PASS | hinglish | 0.250 | 494 | — | weight loss ke liye koi product hai | ⚖️ Is concern ke liye ye options match karte hain:  1. *Power Rootz SSS Formulae* - Category: Weight Loss & Stress Management - Kaam aata hai: A 3-in-1 Ayurvedic formula combining Slim Capsules and Sleep & Stress Tablets for sustainable weight loss,  |
| 54 | `B2-WGT-02` | bug2 | ❌ FAIL [FB] | hinglish | — | 563 | missing:'weight'; missing:'slim' | motapa kam karne ki dawa chahiye | ⚖️ Sorry, is topic pe mere paas exact info nahi hai. Support team se connect ho jao ya thoda aur detail bhejo. |
| 55 | `B2-RES-01` | bug2 | ❌ FAIL [FB] | hinglish | — | 380 | missing:'respiratory'; missing:'vayu' | asthma ya saans ki takleef ke liye kya hai | 😟 Sorry, is topic pe mere paas exact info nahi hai. Support team se connect ho jao ya thoda aur detail bhejo. |
| 56 | `B2-RES-02` | bug2 | ✅ PASS | english | 0.250 | 392 | — | breathing problem for respiratory health | Here are the best matching options:  1. *Vayu Shuddhi* - Category: Respiratory Health - Used for: Ayurvedic lung detox capsules formulated for smokers and individuals exposed to pollution. Clears airways, removes tar and mucus from lungs, improves br |
| 57 | `B2-SLP-01` | bug2 | ✅ PASS | hinglish | 0.250 | 402 | — | mujhe neend nahi aati insomnia ka koi ilaj | 😴 Is concern ke liye ye options match karte hain:  1. *Aadved Sleep* - Category: Sleep & Wellness - Kaam aata hai: Non-addictive herbal sleep support capsules that improve sleep quality, manage insomnia symptoms, regulate the sleep-wake cycle, and re |
| 58 | `B2-SLP-02` | bug2 | ✅ PASS | hinglish | 0.250 | 362 | — | sleep problem solution chahiye | 😴 Is concern ke liye ye options match karte hain:  1. *Aadved Sleep* - Category: Sleep & Wellness - Kaam aata hai: Non-addictive herbal sleep support capsules that improve sleep quality, manage insomnia symptoms, regulate the sleep-wake cycle, and re |
| 59 | `B2-GEN-01` | bug2 | ✅ PASS | hinglish | 0.250 | 365 | — | women's health product chahiye PCOS ke liye | 🌸 Is concern ke liye ye options match karte hain:  1. *Ayush for Women* - Category: Women's Health & Reproductive Support - Kaam aata hai: Ayurvedic capsules for women's reproductive health targeting PCOS, PCOD, irregular periods, hormonal imbalance, |
| 60 | `B2-GEN-02` | bug2 | ❌ FAIL | english | 0.250 | 368 | missing:'women' | female sexual wellness product | Here are the best matching options:  1. *Liv Muztang Limited Edition (Female)* - Category: Female Sexual Wellness - Used for: A specialised Ayurvedic herbal formulation for female intimate wellness. Stimulates the nervous system for enhanced sensory  |
| 61 | `B2-VAG-01` | bug2 | ✅ PASS [FB] | english | — | 357 | — | I need a medicine | I didn’t catch that, but I’d love to help you find what you need 😊 Are you looking to: 🛍️ Shop products, 📦 Track an order, 🔁 Start a return, 💬 Talk to support? |
| 62 | `B2-VAG-02` | bug2 | ✅ PASS | english | 0.250 | 530 | — | suggest me best product | Here are the best matching options:  1. *Addiction Killer Ark (Addiction Killer Liquid)* - Category: Addiction & De-addiction - Used for: A tasteless and colourless Ayurvedic liquid drop formulation for alcohol, smoking, and drug addiction recovery.  |
| 63 | `B2-VAG-03` | bug2 | ✅ PASS [FB] | hinglish | — | 367 | — | koi dawa batao | Sorry, is topic pe mere paas exact info nahi hai. Support team se connect ho jao ya thoda aur detail bhejo. |
| 64 | `B2-ENR-01` | bug2 | ✅ PASS | hinglish | 0.250 | 362 | — | energy booster chahiye general weakness | ⚡ Is concern ke liye ye options match karte hain:  1. *Ayush Kavach (Immunity System Booster Capsules)* - Category: Immunity & General Wellness - Kaam aata hai: Ayurvedic immunity booster capsules that enhance the body's natural defence against infec |
| 65 | `B2-ENR-02` | bug2 | ❌ FAIL | hinglish | 0.250 | 375 | unwanted:'piles' | shilajit product hai kya | Is concern ke liye ye options match karte hain:  1. *SK Turbo Treats Shilajit Gummies* - Category: Energy & General Wellness - Kaam aata hai: India's first Shilajit Gummies made with Himalayan Shilajit Resin. Sugar-free with tamarind flavour. Boosts  |
| 66 | `B3-AYU-01` | bug3 | ✅ PASS | english | 0.250 | 526 | — | Is Ayush for Men an ayurvedic medicine? | Here are the best matching options:  1. *Ayush for Men (Ayurvedic Sexual Wellness Capsules for Men)* - Category: Male Sexual Wellness - Used for: Ayurvedic capsules for male sexual wellness supporting testosterone levels, libido, erection quality, st |
| 67 | `B3-AYU-02` | bug3 | ✅ PASS | hinglish | 0.250 | 362 | — | Sandy RX ayurvedic hai kya | Is concern ke liye ye options match karte hain:  1. *Sandy RX* - Category: Male Sexual Wellness - Kaam aata hai: A high-potency Ayurvedic and herbal capsule for men addressing low testosterone, erectile dysfunction (ED), premature ejaculation (PE), l |
| 68 | `B3-AYU-03` | bug3 | ✅ PASS | english | 0.250 | 506 | — | Is Kaama Gold Kit an ayurvedic product | Here are the best matching options:  1. *Kaama Gold Kit* - Category: Male Sexual Wellness - Used for: A comprehensive 4-in-1 Ayurvedic sexual wellness kit for men containing capsules, oil, powder, and avaleha (herbal jam). Supports testosterone level |
| 69 | `B3-AYU-04` | bug3 | ✅ PASS | hinglish | 0.250 | 400 | — | Liv Muztang Capsules ayurvedic hai ya allopathic | Is concern ke liye ye options match karte hain:  1. *Liv Muztang Plus Capsules* - Category: Male Sexual Wellness - Kaam aata hai: Ayurvedic male vitality capsules for improving stamina, hormonal balance, testosterone support, sexual wellness, and con |
| 70 | `B3-AYU-05` | bug3 | ✅ PASS | english | 0.250 | 382 | — | Ultimate Hammer is it ayurvedic | Here are the best matching options:  1. *Ultimate Hammer (Ayurvedic Night Power Booster)* - Category: Male Sexual Wellness - Used for: Ayurvedic capsules formulated to boost libido, erection strength and duration, manage premature ejaculation (PE) an |
| 71 | `B3-AYU-06` | bug3 | ✅ PASS | english | 0.250 | 357 | — | Herbo 365 herbal medicine hai? | Here are the best matching options:  1. *Herbo 365* - Category: Male Vitality & Athletic Performance - Used for: Ayurvedic capsules for men to improve muscle mass, strength, testosterone levels, athletic performance, and sexual vitality. Also helps m |
| 72 | `B3-AYU-07` | bug3 | ✅ PASS | english | 0.250 | 381 | — | is Addiction Killer Powder ayurvedic or chemical | 🤝 Here are the best matching options:  1. *Addiction Killer Powder* - Category: Addiction & De-addiction - Used for: An Ayurvedic herbal powder designed to support recovery from alcohol, smoking, nicotine, and drug addiction. Helps reduce cravings, d |
| 73 | `B3-AYU-08` | bug3 | ❌ FAIL | hinglish | 0.250 | 435 | missing:'herbal' | Vayu Shuddhi natural hai ya chemical medicine | Is concern ke liye ye options match karte hain:  1. *Vayu Shuddhi* - Category: Respiratory Health - Kaam aata hai: Ayurvedic lung detox capsules formulated for smokers and individuals exposed to pollution. Clears airways, removes tar and mucus from l |
| 74 | `B3-AYU-09` | bug3 | ❌ FAIL | english | 0.250 | 398 | missing:'herbal' | Liver Care Capsules ayurvedic hai? | 🛡️ Here are the best matching options:  1. *Liver Care Capsules* - Category: Liver Health - Used for: Ayurvedic liver detox and regeneration capsules for fatty liver management, liver inflammation, toxin accumulation from alcohol and medications, and |
| 75 | `B3-AYU-10` | bug3 | ❌ FAIL | hinglish | 0.250 | 449 | missing:'herbal' | Stones Veda kya yeh ayurvedic dawa hai | Is concern ke liye ye options match karte hain:  1. *Stones Veda* - Category: Kidney Health & Urinary Tract - Kaam aata hai: An Ayurvedic capsule and syrup kit for kidney stone removal, UTI relief, and urinary detoxification. Promotes natural kidney  |
| 76 | `B3-TYP-01` | bug3 | ✅ PASS | english | 0.250 | 401 | — | What type of medicine is Ayush for Men | Here are the best matching options:  1. *Aadved Ayush 82 Tablets* - Category: Diabetes Management - Used for: A CCRAS-approved Ayurvedic tablet for Type 2 diabetes and prediabetes management. Helps regulate blood sugar levels, improves insulin sensit |
| 77 | `B3-TYP-02` | bug3 | ✅ PASS | hinglish | 0.250 | 373 | — | Jaam-e-Ishq kis tarah ki dawa hai | Is concern ke liye ye options match karte hain:  1. *Jaam-e-Ishq* - Category: Sexual Wellness (Unisex) - Kaam aata hai: A classical Unani herbal prash (paste) for sexual health and fertility in both men and women. Enhances sexual performance, stamina |
| 78 | `B3-TYP-03` | bug3 | ✅ PASS | english | 0.250 | 405 | — | what category does Stones Veda fall in | Here are the best matching options:  1. *Stones Veda* - Category: Kidney Health & Urinary Tract - Used for: An Ayurvedic capsule and syrup kit for kidney stone removal, UTI relief, and urinary detoxification. Promotes natural kidney stone passage, en |
| 79 | `B3-TYP-04` | bug3 | ✅ PASS | english | 0.250 | 414 | — | Dhurandar Oil — what type of product is this | Here are the best matching options:  1. *Dhurandar Oil* - Category: Joint & Muscle Pain - Used for: A 100% Ayurvedic vapor-action massage oil for joint stiffness, arthritis, spondylitis, sciatica, muscle pain, swelling, and injury recovery. Provides  |
| 80 | `B3-TYP-05` | bug3 | ✅ PASS | hinglish | 0.250 | 4914 | — | Aadved Adivasi Hair Oil kis category mein aata hai | 🌿 Is concern ke liye ye options match karte hain:  1. *Aadved Adivasi Hair Oil* - Category: Hair Care - Kaam aata hai: A multi-herb Ayurvedic hair oil for reducing hair fall, dandruff, premature greying, and promoting hair growth. Strengthens roots,  |
| 81 | `B3-TYP-06` | bug3 | ✅ PASS | hinglish | 0.250 | 387 | — | Aadved Sleep kya hai tablet ya powder | 😴 Is concern ke liye ye options match karte hain:  1. *Aadved Sleep* - Category: Sleep & Wellness - Kaam aata hai: Non-addictive herbal sleep support capsules that improve sleep quality, manage insomnia symptoms, regulate the sleep-wake cycle, and re |
| 82 | `B3-TYP-07` | bug3 | ✅ PASS | hinglish | 0.250 | 374 | — | Saumya Plus kya ek skin cream hai | ✨ Is concern ke liye ye options match karte hain:  1. *Saumya Plus* - Category: Skin Health — Vitiligo - Kaam aata hai: An Ayurvedic capsule and oil combination for vitiligo (Safed Daag / white skin patches). Stimulates natural melanin production, su |
| 83 | `B3-TYP-08` | bug3 | ✅ PASS | english | 0.250 | 361 | — | SK Turbo Treats — what is this product | Here are the best matching options:  1. *SK Turbo Treats Shilajit Gummies* - Category: Energy & General Wellness - Used for: India's first Shilajit Gummies made with Himalayan Shilajit Resin. Sugar-free with tamarind flavour. Boosts natural energy an |
| 84 | `B3-TYP-09` | bug3 | ✅ PASS | hinglish | 0.250 | 358 | — | Power Rootz Keeda Jadi kya hota hai | Is concern ke liye ye options match karte hain:  1. *Power Rootz Keeda Jadi (Cordyceps Militaris)* - Category: Energy & Athletic Performance - Kaam aata hai: A premium Himalayan Cordyceps Militaris supplement known as 'Himalayan Viagra' for boosting  |
| 85 | `B3-TYP-10` | bug3 | ✅ PASS | hinglish | 0.250 | 437 | — | Ayush Kavach ka form kya hai tablet ya capsule | Is concern ke liye ye options match karte hain:  1. *Ayush Kavach (Immunity System Booster Capsules)* - Category: Immunity & General Wellness - Kaam aata hai: Ayurvedic immunity booster capsules that enhance the body's natural defence against infecti |
| 86 | `B3-HRB-01` | bug3 | ✅ PASS | english | 0.250 | 374 | — | Is Dr Piles Free made with herbal ingredients | 🩺 Here are the best matching options:  1. *Dr Piles Free* - Category: Piles & Digestive Health - Used for: A complete 3-in-1 Ayurvedic kit (capsules, powder, and oil) for treatment and management of internal and external piles (hemorrhoids), anal fis |
| 87 | `B3-HRB-02` | bug3 | ✅ PASS | hinglish | 0.250 | 478 | — | Nasha Free herbal hai ya koi chemical | 🤝 Is concern ke liye ye options match karte hain:  1. *Nasha Free* - Category: Addiction & De-addiction - Kaam aata hai: A colourless herbal liquid drop for reducing alcohol and nicotine cravings and supporting addiction recovery. Aids liver detoxifi |
| 88 | `B3-HRB-03` | bug3 | ❌ FAIL | hinglish | 0.250 | 366 | missing:'herbal' | Ayush Kwath natural ingredients se bana hai | Is concern ke liye ye options match karte hain:  1. *Aadved Adivasi Hair Oil* - Category: Hair Care - Kaam aata hai: A multi-herb Ayurvedic hair oil for reducing hair fall, dandruff, premature greying, and promoting hair growth. Strengthens roots, re |
| 89 | `B3-HRB-04` | bug3 | ✅ PASS | english | 0.250 | 358 | — | Ortho Veda Oil is it herbal | Here are the best matching options:  1. *Ortho Veda Oil* - Category: Joint & Muscle Pain - Used for: A clinically-tested, 100% plant-based Ayurvedic massage oil for joint stiffness, inflammation, knee and back pain, osteoarthritis, muscle strains, an |
| 90 | `B3-HRB-05` | bug3 | ✅ PASS | english | 0.250 | 372 | — | Sanjeev Ras herbal juice hai | Here are the best matching options:  1. *Sanjeev Ras* - Category: Immunity & Wellness - Used for: A premium Ayurvedic antioxidant juice powered by Sea Buckthorn (rich in Vitamins C & E, Omega 3, 6, 7, and 9) and Nano Curcumin for enhanced absorption. |
| 91 | `B3-HIN-01` | bug3 | ✅ PASS | hinglish | 0.250 | 362 | — | Kaama Gold herbal dawa hai ya english medicine | Is concern ke liye ye options match karte hain:  1. *Kaama Gold Kit* - Category: Male Sexual Wellness - Kaam aata hai: A comprehensive 4-in-1 Ayurvedic sexual wellness kit for men containing capsules, oil, powder, and avaleha (herbal jam). Supports t |
| 92 | `B3-HIN-02` | bug3 | ✅ PASS | hinglish | 0.250 | 362 | — | Addiction Killer angrezi dawa hai ya desi | 🤝 Is concern ke liye ye options match karte hain:  1. *Addiction Killer Powder* - Category: Addiction & De-addiction - Kaam aata hai: An Ayurvedic herbal powder designed to support recovery from alcohol, smoking, nicotine, and drug addiction. Helps r |
| 93 | `B3-HIN-03` | bug3 | ✅ PASS | hinglish | 0.250 | 423 | — | Sandy RX mein kya English medicine hai | Is concern ke liye ye options match karte hain:  1. *Sandy RX* - Category: Male Sexual Wellness - Kaam aata hai: A high-potency Ayurvedic and herbal capsule for men addressing low testosterone, erectile dysfunction (ED), premature ejaculation (PE), l |
| 94 | `B3-HIN-04` | bug3 | ✅ PASS | hinglish | 0.250 | 380 | — | Liver Care Capsules allopathic hai ya herbal | 🛡️ Is concern ke liye ye options match karte hain:  1. *Liver Care Capsules* - Category: Liver Health - Kaam aata hai: Ayurvedic liver detox and regeneration capsules for fatty liver management, liver inflammation, toxin accumulation from alcohol and |
| 95 | `B3-HIN-05` | bug3 | ✅ PASS | hinglish | 0.250 | 477 | — | Aadved Adivasi Hair Oil mein kya natural ingredients hain | 🌿 Is concern ke liye ye options match karte hain:  1. *Aadved Adivasi Hair Oil* - Category: Hair Care - Kaam aata hai: A multi-herb Ayurvedic hair oil for reducing hair fall, dandruff, premature greying, and promoting hair growth. Strengthens roots,  |
| 96 | `B3-CTG-01` | bug3 | ✅ PASS | hinglish | 0.250 | 413 | — | Ayush for Women kis category ka product hai | 🌸 Is concern ke liye ye options match karte hain:  1. *Ayush for Women* - Category: Women's Health & Reproductive Support - Kaam aata hai: Ayurvedic capsules for women's reproductive health targeting PCOS, PCOD, irregular periods, hormonal imbalance, |
| 97 | `B3-CTG-02` | bug3 | ✅ PASS | english | 0.250 | 455 | — | Macamo The Latin Lava which category | Here are the best matching options:  1. *Macamo (The Latin Lava)* - Category: Male Sexual Wellness - Used for: A Maca Root-based premium Ayurvedic capsule for men combining traditional Latin and Indian herbs for boosting libido, testosterone, fertili |
| 98 | `B3-CTG-03` | bug3 | ✅ PASS | hinglish | 0.250 | 374 | — | Aadved Slim Herbs kya yeh weight loss product hai | ⚖️ Is concern ke liye ye options match karte hain:  1. *Aadved Slim Herbs* - Category: Weight Management - Kaam aata hai: An Ayurvedic weight management combo of capsules and massage oil for natural fat burning, metabolism boosting, appetite suppress |
| 99 | `B3-CTG-04` | bug3 | ✅ PASS | hinglish | 0.250 | 405 | — | Poshan Plus weight gain ke liye hai | ⚖️ Is concern ke liye ye options match karte hain:  1. *Poshan Plus* - Category: Weight Gain & Nutrition - Kaam aata hai: A unisex Ayurvedic weight gainer powder for healthy weight gain, muscle mass building, energy, improved digestion, and stronger  |
| 100 | `B3-CTG-05` | bug3 | ✅ PASS | english | 0.250 | 345 | — | Dr Madhu Amrit diabetes kit hai | 🩺 Here are the best matching options:  1. *Dr. Madhu Amrit Diabetes Management Kit* - Category: Diabetes Management - Used for: A complete 3-in-1 holistic diabetes management kit containing Ayush 82 Tablets, Liver Support Tablets, and Neem-Karela-Jam |

---

## Failing Tests Detail

### ❌ `B1-PC-01` (bug1)
**Query:** what is the price of Ayush for Men
**Note:** Must show both COD price AND prepaid price
**Failures:** missing:'2900'; missing:'2610'
**Answer:**
> 💰 Here are the best matching options:  1. *Ayush for Men (Ayurvedic Sexual Wellness Capsules for Men)* - Category: Male Sexual Wellness - Used for: Ayurvedic capsules for male sexual wellness supporting testosterone levels, libido, erection quality, stamina, sperm count, and fertility. Addresses erectile dysfunction (ED), low sexual desire, and hormonal imbalance. Key ingredients include Kaunch Beej, Safed Musali, Ashwagandha, Akarakara, Shodhit Shilajit, Vidari Kand, Shatavari, and Kesar. Take 

### ❌ `B1-PC-02` (bug1)
**Query:** Sandy RX ka price kya hai
**Note:** Must show MRP and prepaid for Sandy RX
**Failures:** missing:'14063'; missing:'12656'
**Answer:**
> 💰 Is concern ke liye ye options match karte hain:  1. *Sandy RX* - Category: Male Sexual Wellness - Kaam aata hai: A high-potency Ayurvedic and herbal capsule for men addressing low testosterone, erectile dysfunction (ED), premature ejaculation (PE), low stamina, and male fertility concerns. Contains Horny Goat Weed, Shilajit, Safed Musli, Gokshura, Kaunch Beej, Ashwagandha, Akarkara, Shatavari, Javitri, Kesar, and Mulondo. Take 2 capsules daily with lukewarm milk. 3-month course.  Age aur main 

### ❌ `B1-PC-03` (bug1)
**Query:** what is the price of Kaama Gold Kit
**Note:** Must include COD price for Kaama Gold
**Failures:** missing:'2499'
**Answer:**
> 💰 Here are the best matching options:  1. *Kaama Gold Kit* - Category: Male Sexual Wellness - Used for: A comprehensive 4-in-1 Ayurvedic sexual wellness kit for men containing capsules, oil, powder, and avaleha (herbal jam). Supports testosterone levels, libido, sexual stamina, blood circulation, and overall male reproductive health. Key ingredients include Ashwagandha, Kaunch Beej, Shatavari, Gokhshura, Vidarikand, and various Ayurvedic bhasmas. Capsules: 1 at bedtime. Oil: massage on affected 

### ❌ `B1-PC-04` (bug1)
**Query:** Liv Muztang Capsules kitne ka hai
**Note:** Must include COD price
**Failures:** missing:'4999'
**Answer:**
> Is concern ke liye ye options match karte hain:  1. *Liv Muztang Plus Capsules* - Category: Male Sexual Wellness - Kaam aata hai: Ayurvedic male vitality capsules for improving stamina, hormonal balance, testosterone support, sexual wellness, and confidence. Contains Kaunch Beej, Ashwagandha, Shatavari, Vidari Kand, Mulondo, Akarkara, Gokshura, Jaiphal, Laung, Dalchini, and traditional Ayurvedic bhasmas (Ras Sindoor, Bang Bhasma, Swarn Makshik Bhasma). Take 1 capsule daily at night with lukewarm

### ❌ `B1-PC-05` (bug1)
**Query:** Ultimate Hammer MRP aur prepaid price bata
**Note:** Must show both MRP and prepaid price
**Failures:** missing:'1799'; missing:'1619'
**Answer:**
> 💰 Is concern ke liye ye options match karte hain:  1. *Ultimate Hammer (Ayurvedic Night Power Booster)* - Category: Male Sexual Wellness - Kaam aata hai: Ayurvedic capsules formulated to boost libido, erection strength and duration, manage premature ejaculation (PE) and erectile dysfunction (ED), improve sperm count, and enhance overall male sexual performance. Contains Kaunch Beej, Shatavari, Ashwagandha, Jaiphal, Akarkara, Gokshur, Ras Sindoor, Laung, Dalchini, and Khurasini Ajwain. Take 1 cap

### ❌ `B1-DOS-02` (bug1)
**Query:** Sandy RX kaise lena chahiye
**Note:** Dosage: 2 capsules with lukewarm milk
**Failures:** missing:'milk'
**Answer:**
> Sandy RX ko aapko din mein 2 capsules lene hain, aur best hai ise garam doodh ke saath lena. Yeh 3 mahine ka course hai, isliye regular lena zaroori hai. Agar aapko aur details chahiye toh batana! 😊

### ❌ `B1-BEN-03` (bug1)
**Query:** what does Ultimate Hammer do
**Note:** Ultimate Hammer is for male sexual wellness
**Failures:** missing:'testosterone'
**Answer:**
> Ultimate Hammer is an Ayurvedic Night Power Booster designed to enhance male sexual wellness. It helps to boost libido, strengthen erections, improve duration, and manage issues like premature ejaculation (PE) and erectile dysfunction (ED). Additionally, it can improve sperm count and enhance overall sexual performance. For best results, it's recommended to take 1 capsule daily with lukewarm milk or water for a course of 3–6 months.

### ❌ `B1-CAT-01` (bug1)
**Query:** tell me everything about Ayush for Men
**Note:** Full product info: category, dosage, benefits, price
**Failures:** missing:'2900'
**Answer:**
> Here are the best matching options:  1. *Ayush for Men (Ayurvedic Sexual Wellness Capsules for Men)* - Category: Male Sexual Wellness - Used for: Ayurvedic capsules for male sexual wellness supporting testosterone levels, libido, erection quality, stamina, sperm count, and fertility. Addresses erectile dysfunction (ED), low sexual desire, and hormonal imbalance. Key ingredients include Kaunch Beej, Safed Musali, Ashwagandha, Akarakara, Shodhit Shilajit, Vidari Kand, Shatavari, and Kesar. Take 1 

### ❌ `B1-DUR-04` (bug1)
**Query:** how long before Liv Muztang shows results
**Note:** Expected timeline: 4-8 weeks / 3 months
**Failures:** missing:'week'
**Answer:**
> Consistency is key! Generally, it is recommended to take Liv Muztang products for at least 2-3 months to notice significant results. Remember, individual responses may vary based on various factors. If you have further questions, feel free to ask! 😊

### ❌ `B1-DUR-05` (bug1)
**Query:** Addiction Killer kitne time mein kaam karta hai
**Note:** Expected timeline for Addiction Killer
**Failures:** missing:'week'; missing:'day'
**Answer:**
> 🤝 Is concern ke liye ye options match karte hain:  1. *Addiction Killer Ark (Addiction Killer Liquid)* - Category: Addiction & De-addiction - Kaam aata hai: A tasteless and colourless Ayurvedic liquid drop formulation for alcohol, smoking, and drug addiction recovery. Supports withdrawal symptom management, reduces cravings, detoxifies the liver and kidneys, and improves emotional balance. Key ingredients include Kudzu, Ashwagandha, Shatavari, Shilajit, Arjuna, and Sarpagandha. Dosage is 10–15 d

### ❌ `B1-PACK-01` (bug1)
**Query:** Ayush for Men ka pack size kya hai
**Note:** 60 capsules per bottle
**Failures:** missing:'60'
**Answer:**
> Is concern ke liye ye options match karte hain:  1. *M9 Shampoo (Instant Hair Colour Shampoo)* - Category: Hair Care - Kaam aata hai: An ammonia-free instant hair colouring shampoo that restores natural black hair colour in just 5 minutes. Comes as a combo pack of Colorant Shampoo and Developer Shampoo. Contains Noni Extracts, Aloe Vera, and Olive Oil. Mix both shampoos, apply on dry hair, leave for 5 minutes, and rinse. Not recommended for daily use. Currently out of stock.  2. *Ayush for Men (

### ❌ `B2-HAIR-01` (bug2)
**Query:** baal bahut girte hain koi oil batao
**Note:** Hair fall → hair care products
**Failures:** missing:'hair'
**Answer:**
> 🌿 Is concern ke liye ye options match karte hain:  1. *Ortho Veda Oil* - Category: Joint & Muscle Pain - Kaam aata hai: A clinically-tested, 100% plant-based Ayurvedic massage oil for joint stiffness, inflammation, knee and back pain, osteoarthritis, muscle strains, and chronic joint conditions. Strengthens joints, bones, muscles, and ligaments over time. Key ingredients include Mahanarayan Oil, Kapoor Oil, Ajowan Oil, Clove Oil, Til Oil, Eucalyptus Oil, and Menthol. Massage affected area 3–4 ti

### ❌ `B2-JNT-01` (bug2)
**Query:** ghutne mein dard hai koi tel batao
**Note:** Knee pain → joint pain oil
**Failures:** unwanted:'hair'
**Answer:**
> 😟 Is concern ke liye ye options match karte hain:  1. *Ortho Veda Oil* - Category: Joint & Muscle Pain - Kaam aata hai: A clinically-tested, 100% plant-based Ayurvedic massage oil for joint stiffness, inflammation, knee and back pain, osteoarthritis, muscle strains, and chronic joint conditions. Strengthens joints, bones, muscles, and ligaments over time. Key ingredients include Mahanarayan Oil, Kapoor Oil, Ajowan Oil, Clove Oil, Til Oil, Eucalyptus Oil, and Menthol. Massage affected area 3–4 ti

### ❌ `B2-ADD-01` (bug2)
**Query:** cigarette chhodne ki dawa chahiye
**Note:** Smoking cessation → Addiction Killer
**Failures:** missing:'addiction'
**Answer:**
> Sorry, is topic pe mere paas exact info nahi hai. Support team se connect ho jao ya thoda aur detail bhejo.

### ❌ `B2-WGT-02` (bug2)
**Query:** motapa kam karne ki dawa chahiye
**Note:** Obesity → weight management products
**Failures:** missing:'weight'; missing:'slim'
**Answer:**
> ⚖️ Sorry, is topic pe mere paas exact info nahi hai. Support team se connect ho jao ya thoda aur detail bhejo.

### ❌ `B2-RES-01` (bug2)
**Query:** asthma ya saans ki takleef ke liye kya hai
**Note:** Respiratory issues → Vayu Shuddhi
**Failures:** missing:'respiratory'; missing:'vayu'
**Answer:**
> 😟 Sorry, is topic pe mere paas exact info nahi hai. Support team se connect ho jao ya thoda aur detail bhejo.

### ❌ `B2-GEN-02` (bug2)
**Query:** female sexual wellness product
**Note:** Female wellness → female products only
**Failures:** missing:'women'
**Answer:**
> Here are the best matching options:  1. *Liv Muztang Limited Edition (Female)* - Category: Female Sexual Wellness - Used for: A specialised Ayurvedic herbal formulation for female intimate wellness. Stimulates the nervous system for enhanced sensory pleasure, increases sexual desire and arousal, promotes natural lubrication, supports estrogen production and hormonal balance, and improves overall intimate satisfaction. Contains Mulondo, Shatavari, Ashwagandha, Kaunch Beej, Akarkara, Vidari Kand, 

### ❌ `B2-ENR-02` (bug2)
**Query:** shilajit product hai kya
**Note:** Shilajit query → SK Turbo Treats Shilajit Gummies
**Failures:** unwanted:'piles'
**Answer:**
> Is concern ke liye ye options match karte hain:  1. *SK Turbo Treats Shilajit Gummies* - Category: Energy & General Wellness - Kaam aata hai: India's first Shilajit Gummies made with Himalayan Shilajit Resin. Sugar-free with tamarind flavour. Boosts natural energy and stamina, reduces fatigue and stress, strengthens muscles and bones, supports testosterone levels, and promotes sexual wellness and healthy aging. Suitable for both men and women. Chew 1–2 gummies daily at any time — no water requir

### ❌ `B3-AYU-08` (bug3)
**Query:** Vayu Shuddhi natural hai ya chemical medicine
**Note:** Vayu Shuddhi is Ayurvedic
**Failures:** missing:'herbal'
**Answer:**
> Is concern ke liye ye options match karte hain:  1. *Vayu Shuddhi* - Category: Respiratory Health - Kaam aata hai: Ayurvedic lung detox capsules formulated for smokers and individuals exposed to pollution. Clears airways, removes tar and mucus from lungs, improves breathing capacity and oxygen absorption, and reduces respiratory inflammation. Contains Beetroot, Vasaka Leaf, Ginger, Citrus Extracts, Arjuna Bark, Lotus Rhizome, Pushkarmool, and Black Pepper with Piperine. Take 2 capsules daily wit

### ❌ `B3-AYU-09` (bug3)
**Query:** Liver Care Capsules ayurvedic hai?
**Note:** Liver Care is Ayurvedic
**Failures:** missing:'herbal'
**Answer:**
> 🛡️ Here are the best matching options:  1. *Liver Care Capsules* - Category: Liver Health - Used for: Ayurvedic liver detox and regeneration capsules for fatty liver management, liver inflammation, toxin accumulation from alcohol and medications, and sluggish liver function. Contains Milk Thistle Extract, Bhumi Amla, Kutki, Punarnava, Licorice, Vitamin E, Kasni (Chicory), Dandelion, Black Pepper, and Amla. Take 2 capsules daily with warm milk. 3-month course. Available as 60 capsules per bottle.

### ❌ `B3-AYU-10` (bug3)
**Query:** Stones Veda kya yeh ayurvedic dawa hai
**Note:** Stones Veda is Ayurvedic
**Failures:** missing:'herbal'
**Answer:**
> Is concern ke liye ye options match karte hain:  1. *Stones Veda* - Category: Kidney Health & Urinary Tract - Kaam aata hai: An Ayurvedic capsule and syrup kit for kidney stone removal, UTI relief, and urinary detoxification. Promotes natural kidney stone passage, enhances urinary flow, prevents new mineral buildup, and reduces pain and burning sensation. Contains Varun Chhal, Gokhru, Punarnava, Tulsi, Rakta Chandan, Sounf, and Mint. Take 1–2 capsules daily; syrup 1–2 spoons post dinner. 3-month

### ❌ `B3-HRB-03` (bug3)
**Query:** Ayush Kwath natural ingredients se bana hai
**Note:** Ayush Kwath is Ayurvedic
**Failures:** missing:'herbal'
**Answer:**
> Is concern ke liye ye options match karte hain:  1. *Aadved Adivasi Hair Oil* - Category: Hair Care - Kaam aata hai: A multi-herb Ayurvedic hair oil for reducing hair fall, dandruff, premature greying, and promoting hair growth. Strengthens roots, restores natural shine and thickness, and improves scalp health. Key ingredients include Red Onion, Bhringraj, Ashwagandha, Til Oil, Coconut Oil, Brahmi, Khas, and Manjistha. Apply to scalp at night, massage gently, leave overnight, and wash next morni
