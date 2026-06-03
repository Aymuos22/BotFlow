# 3-Bugs Quality Test Report — SkinRange

**Company ID:** `33eaf707-06f1-4e30-93d8-d8da71afaa92`  
**Total:** 100  |  **Pass:** 87  |  **Fail:** 13  |  **Pass rate:** 87%

---

## Summary by Bug

| Bug | Description | Pass | Fail | Rate |
|-----|-------------|------|------|------|
| bug1 | Product Info Completeness | 19 | 11 | 63% |
| bug2 | Recommendation Relevance | 33 | 2 | 94% |
| bug3 | Medicine-Type Queries | 35 | 0 | 100% |

---

## Detailed Results

| # | Tag | Bug | Status | Lang | Score | ms | Failures | Query | Answer (first 250 chars) |
|---|-----|-----|--------|------|-------|----|----------|-------|--------------------------|
| 1 | `B1-PC-01` | bug1 | ❌ FAIL | english | 0.250 | 5370 | missing:'2900'; missing:'2610' | what is the price of Ayush for Men | 💰 Price and order link for Ayush for Men are not provided. Please connect with our support team at +91 93113 91981 for assistance. 📞 |
| 2 | `B1-PC-02` | bug1 | ❌ FAIL | hinglish | 0.250 | 2676 | missing:'14063'; missing:'12656' | Sandy RX ka price kya hai | 💰 Price aur order link ke liye hamare support se baat karen: +91 93113 91981 📞 |
| 3 | `B1-PC-03` | bug1 | ❌ FAIL | english | 0.250 | 1402 | missing:'2499' | what is the price of Kaama Gold Kit | 💰 Price aur order link ke liye hamare support se baat karen: +91 93113 91981 📞 |
| 4 | `B1-PC-04` | bug1 | ❌ FAIL | hinglish | 0.250 | 2104 | missing:'4999' | Liv Muztang Capsules kitne ka hai | Liv Muztang Capsules ki price abhi mujhe pata nahi hai. Order link aur price ke liye hamare support se baat karen: +91 93113 91981 📞. Prepaid order pe 10% off + free gift worth Rs. 1,299 milega 🎁. |
| 5 | `B1-PC-05` | bug1 | ❌ FAIL | hinglish | 0.250 | 1995 | missing:'1799'; missing:'1619' | Ultimate Hammer MRP aur prepaid price bata | 💰 Ultimate Hammer ki MRP hai Rs. 2,499, aur prepaid order par aapko milega Rs. 2,249 ka price.  Prepaid order pe 10% off + free gift worth Rs. 1,299 milega 🎁  Order karne ke liye yahan click karein: Ultimate Hammer: https://skinrange.com/products/ult |
| 6 | `B1-DOS-01` | bug1 | ✅ PASS | english | 0.250 | 369 | — | How do I take Ayush for Men? what is the dosage? | Here are the best matching options:  1. *Ayush for Men (Ayurvedic Sexual Wellness Capsules for Men)* - Category: Male Sexual Wellness - Used for: Ayurvedic capsules for male sexual wellness supporting testosterone levels, libido, erection quality, st |
| 7 | `B1-DOS-02` | bug1 | ✅ PASS | hinglish | 0.250 | 1862 | — | Sandy RX kaise lena chahiye | Sandy RX ko aapko din mein 2 capsules lene hain, lukewarm milk ke sath. Yeh ek high-potency Ayurvedic aur herbal formula hai jo male sexual wellness ke liye bohot effective hai. Isko 3 mahine tak regularly lena hai taaki achhe results mil sakein. Aga |
| 8 | `B1-DOS-03` | bug1 | ✅ PASS | hinglish | 0.250 | 377 | — | Aadved Adivasi Hair Oil kaise lagayen | 🌿 Is concern ke liye ye options match karte hain:  1. *Aadved Adivasi Hair Oil* - Category: Hair Care - Kaam aata hai: A multi-herb Ayurvedic hair oil for reducing hair fall, dandruff, premature greying, and promoting hair growth. Strengthens roots,  |
| 9 | `B1-DOS-04` | bug1 | ✅ PASS | hinglish | 0.250 | 506 | — | Stones Veda dosage kya hai | Is concern ke liye ye options match karte hain:  1. *Stones Veda* - Category: Kidney Health & Urinary Tract - Kaam aata hai: An Ayurvedic capsule and syrup kit for kidney stone removal, UTI relief, and urinary detoxification. Promotes natural kidney  |
| 10 | `B1-DOS-05` | bug1 | ✅ PASS | english | 0.250 | 362 | — | Addiction Killer Powder how to use | 🤝 Here are the best matching options:  1. *Addiction Killer Powder* - Category: Addiction & De-addiction - Used for: An Ayurvedic herbal powder designed to support recovery from alcohol, smoking, nicotine, and drug addiction. Helps reduce cravings, d |
| 11 | `B1-BEN-01` | bug1 | ✅ PASS | english | 0.250 | 1987 | — | what are the benefits of Kaama Gold Kit | The Kaama Gold Kit is a comprehensive 4-in-1 Ayurvedic sexual wellness kit for men. Here are the key benefits:  - Supports testosterone levels. - Enhances libido and sexual stamina. - Improves blood circulation. - Promotes overall male reproductive h |
| 12 | `B1-BEN-02` | bug1 | ✅ PASS | hinglish | 0.250 | 3562 | — | Liv Muztang ke kya fayde hain | Liv Muztang ke kai fayde hain:  1. *Sexual Performance*: Yeh capsule sexual performance ko improve karta hai, jisse aapki confidence badhti hai. 2. *Erectile Dysfunction*: Yeh ED aur premature ejaculation ko manage karne mein madad karta hai. 3. *Lib |
| 13 | `B1-BEN-03` | bug1 | ✅ PASS | english | 0.250 | 2129 | — | what does Ultimate Hammer do | Ultimate Hammer is an Ayurvedic night power booster designed to enhance male sexual wellness. It helps to:  - Boost libido and erection strength - Manage premature ejaculation (PE) and erectile dysfunction (ED) - Improve sperm count - Enhance overall |
| 14 | `B1-BEN-04` | bug1 | ✅ PASS | hinglish | 0.250 | 3808 | — | Stones Veda ke fayde kya hain | Stones Veda ke kuch fayde yeh hain:  1. Kidney stones ko naturally nikaalne mein madad karta hai. 2. UTI se relief deta hai aur urinary detoxification promote karta hai. 3. Urinary flow ko enhance karta hai. 4. Naye mineral buildup ko rokta hai. 5. P |
| 15 | `B1-BEN-05` | bug1 | ✅ PASS | hinglish | 0.250 | 367 | — | Liver Care Capsules se kya hota hai | 🛡️ Is concern ke liye ye options match karte hain:  1. *Liver Care Capsules* - Category: Liver Health - Kaam aata hai: Ayurvedic liver detox and regeneration capsules for fatty liver management, liver inflammation, toxin accumulation from alcohol and |
| 16 | `B1-CAT-01` | bug1 | ❌ FAIL | english | 0.250 | 362 | missing:'2900' | tell me everything about Ayush for Men | Here are the best matching options:  1. *Ayush for Men (Ayurvedic Sexual Wellness Capsules for Men)* - Category: Male Sexual Wellness - Used for: Ayurvedic capsules for male sexual wellness supporting testosterone levels, libido, erection quality, st |
| 17 | `B1-CAT-02` | bug1 | ✅ PASS | hinglish | 0.250 | 4021 | — | Jaam-e-Ishq ke baare mein poori jankari chahiye | Jaam-e-Ishq ek classical Unani herbal prash (paste) hai jo sexual health aur fertility ke liye dono mardon aur aurton ke liye beneficial hai.  *Product Details:* - *Category:* Sexual Wellness (Unisex) - *Key Benefits:*   - Enhances sexual performance |
| 18 | `B1-CAT-03` | bug1 | ✅ PASS | english | 0.250 | 360 | — | tell me about Dr Piles Free in detail | 🩺 Here are the best matching options:  1. *Dr Piles Free* - Category: Piles & Digestive Health - Used for: A complete 3-in-1 Ayurvedic kit (capsules, powder, and oil) for treatment and management of internal and external piles (hemorrhoids), anal fis |
| 19 | `B1-CAT-04` | bug1 | ✅ PASS | hinglish | 0.250 | 394 | — | Vayu Shuddhi product ki poori details do | Is concern ke liye ye options match karte hain:  1. *Vayu Shuddhi* - Category: Respiratory Health - Kaam aata hai: Ayurvedic lung detox capsules formulated for smokers and individuals exposed to pollution. Clears airways, removes tar and mucus from l |
| 20 | `B1-CAT-05` | bug1 | ✅ PASS | hinglish | 0.250 | 365 | — | Aadved Sleep ke baare mein batao | 😴 Is concern ke liye ye options match karte hain:  1. *Aadved Sleep* - Category: Sleep & Wellness - Kaam aata hai: Non-addictive herbal sleep support capsules that improve sleep quality, manage insomnia symptoms, regulate the sleep-wake cycle, and re |
| 21 | `B1-DUR-01` | bug1 | ✅ PASS | english | 0.250 | 374 | — | how long should I take Ayush for Men | Here are the best matching options:  1. *Ayush for Men (Ayurvedic Sexual Wellness Capsules for Men)* - Category: Male Sexual Wellness - Used for: Ayurvedic capsules for male sexual wellness supporting testosterone levels, libido, erection quality, st |
| 22 | `B1-DUR-02` | bug1 | ❌ FAIL | hinglish | 0.250 | 1645 | missing:'month' | Sandy RX kitne din lena hai | Sandy RX ko 3 maheeney tak lena chahiye. Roz 2 capsules lukewarm milk ke saath lena hoga. Aap regular use se achhe results dekh sakte hain. Koi aur sawaal ho toh bataiye! 😊 |
| 23 | `B1-DUR-03` | bug1 | ❌ FAIL | hinglish | 0.250 | 1816 | missing:'month' | Kaama Gold ka full course kitna hai | Kaama Gold Kit ka full course 3–6 mahine ka hota hai. Ismein capsules, oil, powder, aur avaleha sab included hai, jo aapki sexual wellness ke liye kaam aata hai. Agar aapko aur details chahiye toh batao! 😊 |
| 24 | `B1-DUR-04` | bug1 | ✅ PASS | english | 0.250 | 3083 | — | how long before Liv Muztang shows results | Yeh struggle bahut common hai. Aapne sahi decision liya apni health ke liye. 💪  Typically, Liv Muztang products show results after consistent use for at least 2 to 3 months. Regular intake along with a healthy lifestyle can enhance their effectivenes |
| 25 | `B1-DUR-05` | bug1 | ❌ FAIL | hinglish | 0.250 | 1881 | missing:'month' | Addiction Killer kitne time mein kaam karta hai | Addiction Killer ko best results ke liye 3 mahine regular use karna hota hai. Is period ke dauran aapko cravings kam hone, emotional balance improve hone aur detoxification feel hoga. Agar aapko koi aur sawal hai, toh puch sakte hain! 😊 |
| 26 | `B1-PACK-01` | bug1 | ❌ FAIL | hinglish | 0.250 | 366 | missing:'bottle' | Ayush for Men ka pack size kya hai | Is concern ke liye ye options match karte hain:  1. *M9 Shampoo (Instant Hair Colour Shampoo)* - Category: Hair Care - Kaam aata hai: An ammonia-free instant hair colouring shampoo that restores natural black hair colour in just 5 minutes. Comes as a |
| 27 | `B1-PACK-02` | bug1 | ❌ FAIL | hinglish | 0.250 | 8162 | missing:'60' | Sandy RX mein kitni tablets hoti hain | Sandy RX mein 30 capsules hoti hain. Aapko daily 2 capsules lena hai, toh yeh ek mahine tak chalega. Koi aur help chahiye? 😊 |
| 28 | `B1-PACK-03` | bug1 | ✅ PASS | english | 0.250 | 461 | — | what pack sizes are available for Kaama Gold | ✅ Here are the best matching options:  1. *Kaama Gold Kit* - Category: Male Sexual Wellness - Used for: A comprehensive 4-in-1 Ayurvedic sexual wellness kit for men containing capsules, oil, powder, and avaleha (herbal jam). Supports testosterone lev |
| 29 | `B1-PACK-04` | bug1 | ✅ PASS | hinglish | 0.250 | 361 | — | Dr Piles Free mein kya kya aata hai | 🩺 Is concern ke liye ye options match karte hain:  1. *Dr Piles Free* - Category: Piles & Digestive Health - Kaam aata hai: A complete 3-in-1 Ayurvedic kit (capsules, powder, and oil) for treatment and management of internal and external piles (hemor |
| 30 | `B1-PACK-05` | bug1 | ✅ PASS | hinglish | 0.250 | 2581 | — | Extra Time Kit mein kya included hai | Extra Time Kit mein ye 3 products included hain:  1. *Extra Time Capsule* - Yeh morning mein lehna hai. 2. *Extra Time++ Capsule* - Yeh night mein lehna hai. 3. *Extra Time Cream* - Yeh external use ke liye hai.  Yeh kit male sexual timing improve ka |
| 31 | `B2-DIA-01` | bug2 | ✅ PASS | hinglish | 0.250 | 489 | — | sugar control karne ki dawa chahiye | 🩺 Is concern ke liye ye options match karte hain:  1. *Dr. Madhu Amrit Diabetes Management Kit* - Category: Diabetes Management - Kaam aata hai: A complete 3-in-1 holistic diabetes management kit containing Ayush 82 Tablets, Liver Support Tablets, an |
| 32 | `B2-DIA-02` | bug2 | ✅ PASS | english | 0.250 | 493 | — | I have Type 2 diabetes what product do you have | 🩺 Here are the best matching options:  1. *Aadved Ayush 82 Tablets* - Category: Diabetes Management - Used for: A CCRAS-approved Ayurvedic tablet for Type 2 diabetes and prediabetes management. Helps regulate blood sugar levels, improves insulin sens |
| 33 | `B2-DIA-03` | bug2 | ✅ PASS | hinglish | 0.250 | 354 | — | blood sugar kam karne ka koi upay hai | 🩺 Is concern ke liye ye options match karte hain:  1. *Dr. Madhu Amrit Diabetes Management Kit* - Category: Diabetes Management - Kaam aata hai: A complete 3-in-1 holistic diabetes management kit containing Ayush 82 Tablets, Liver Support Tablets, an |
| 34 | `B2-HAIR-01` | bug2 | ✅ PASS | hinglish | 0.250 | 370 | — | baal bahut girte hain koi oil batao | 🌿 Is concern ke liye ye options match karte hain:  1. *Aadved Adivasi Hair Oil* - Category: Hair Care - Kaam aata hai: A multi-herb Ayurvedic hair oil for reducing hair fall, dandruff, premature greying, and promoting hair growth. Strengthens roots,  |
| 35 | `B2-HAIR-02` | bug2 | ✅ PASS | english | 0.250 | 394 | — | I have severe hair fall what product to use | 🌿 Here are the best matching options:  1. *Aadved Adivasi Hair Oil* - Category: Hair Care - Used for: A multi-herb Ayurvedic hair oil for reducing hair fall, dandruff, premature greying, and promoting hair growth. Strengthens roots, restores natural  |
| 36 | `B2-HAIR-03` | bug2 | ✅ PASS | hinglish | 0.250 | 354 | — | hair growth ke liye kya lena chahiye | 🌿 Is concern ke liye ye options match karte hain:  1. *Aadved Adivasi Hair Oil* - Category: Hair Care - Kaam aata hai: A multi-herb Ayurvedic hair oil for reducing hair fall, dandruff, premature greying, and promoting hair growth. Strengthens roots,  |
| 37 | `B2-KID-01` | bug2 | ✅ PASS | hinglish | 0.250 | 356 | — | pathri ka ilaj chahiye kidney stone treatment | 💧 Is concern ke liye ye options match karte hain:  1. *Stones Veda* - Category: Kidney Health & Urinary Tract - Kaam aata hai: An Ayurvedic capsule and syrup kit for kidney stone removal, UTI relief, and urinary detoxification. Promotes natural kidne |
| 38 | `B2-KID-02` | bug2 | ✅ PASS | english | 0.250 | 367 | — | stones veda for kidney stones how effective | 💧 Here are the best matching options:  1. *Stones Veda* - Category: Kidney Health & Urinary Tract - Used for: An Ayurvedic capsule and syrup kit for kidney stone removal, UTI relief, and urinary detoxification. Promotes natural kidney stone passage,  |
| 39 | `B2-KID-03` | bug2 | ✅ PASS | hinglish | 0.250 | 361 | — | gall bladder stone ke liye koi medicine hai | 💧 Is concern ke liye ye options match karte hain:  1. *Stones Veda* - Category: Kidney Health & Urinary Tract - Kaam aata hai: An Ayurvedic capsule and syrup kit for kidney stone removal, UTI relief, and urinary detoxification. Promotes natural kidne |
| 40 | `B2-PIL-01` | bug2 | ✅ PASS | hinglish | 0.250 | 355 | — | bawasir ka ilaj chahiye best medicine | 🩺 Is concern ke liye ye options match karte hain:  1. *Dr Piles Free* - Category: Piles & Digestive Health - Kaam aata hai: A complete 3-in-1 Ayurvedic kit (capsules, powder, and oil) for treatment and management of internal and external piles (hemor |
| 41 | `B2-PIL-02` | bug2 | ✅ PASS | english | 0.250 | 2850 | — | I have hemorrhoids can you help | I understand how uncomfortable hemorrhoids can be. You’ve made a great decision to focus on your health! 😊  I recommend our *Dr. Piles Free* kit. Here are the details:  - *Price*: Check with support for detailed pricing - *Link*: Price and order link |
| 42 | `B2-PIL-03` | bug2 | ❌ FAIL | hinglish | 0.250 | 3827 | missing:'vajra' | pet mein gas bahut hoti hai digestion problem | Aapko gas aur digestion ki problem ke liye SK Gut Raksha kaam kar sakta hai. Yeh Ayurvedic gut detox hai jo aapki digestion improve karega.  🟢 Product: SK Gut Raksha 💰 Price: Price aur order link ke liye hamare support se baat karen: +91 93113 91981  |
| 43 | `B2-LIV-01` | bug2 | ✅ PASS | hinglish | 0.250 | 361 | — | liver weak hai koi medicine suggest karo | 🛡️ Is concern ke liye ye options match karte hain:  1. *SK Gut Raksha* - Category: Gut Health & Digestion - Kaam aata hai: An Ayurvedic gut detox and gut health system combining a daily powder and a weekly detox shot. Addresses chronic constipation,  |
| 44 | `B2-LIV-02` | bug2 | ✅ PASS | hinglish | 0.250 | 371 | — | fatty liver ke liye koi product hai | 🛡️ Is concern ke liye ye options match karte hain:  1. *Liver Care Capsules* - Category: Liver Health - Kaam aata hai: Ayurvedic liver detox and regeneration capsules for fatty liver management, liver inflammation, toxin accumulation from alcohol and |
| 45 | `B2-JNT-01` | bug2 | ✅ PASS | hinglish | 0.250 | 362 | — | ghutne mein dard hai koi tel batao | 😟 Is concern ke liye ye options match karte hain:  1. *Ortho Veda Oil* - Category: Joint & Muscle Pain - Kaam aata hai: A clinically-tested, 100% plant-based Ayurvedic massage oil for joint stiffness, inflammation, knee and back pain, osteoarthritis, |
| 46 | `B2-JNT-02` | bug2 | ✅ PASS | hinglish | 0.250 | 366 | — | arthritis pain relief product chahiye | 😟 Is concern ke liye ye options match karte hain:  1. *Dhurandar Oil* - Category: Joint & Muscle Pain - Kaam aata hai: A 100% Ayurvedic vapor-action massage oil for joint stiffness, arthritis, spondylitis, sciatica, muscle pain, swelling, and injury  |
| 47 | `B2-IMM-01` | bug2 | ✅ PASS | hinglish | 0.250 | 461 | — | immunity boost karne ke liye kya lena chahiye | 🛡️ Is concern ke liye ye options match karte hain:  1. *Ayush Kavach (Immunity System Booster Capsules)* - Category: Immunity & General Wellness - Kaam aata hai: Ayurvedic immunity booster capsules that enhance the body's natural defence against infe |
| 48 | `B2-IMM-02` | bug2 | ✅ PASS | hinglish | 0.250 | 379 | — | bar bar sardi bukhar aata hai immunity weak hai | 🛡️ Is concern ke liye ye options match karte hain:  1. *Ayush Kwath (Ayurvedic Immunity Booster Tablets)* - Category: Immunity & Respiratory Health - Kaam aata hai: Ayurvedic immunity tablets based on the government-recommended Ayush Kwath formula. S |
| 49 | `B2-ADD-01` | bug2 | ✅ PASS | hinglish | 0.250 | 347 | — | cigarette chhodne ki dawa chahiye | 🤝 Is concern ke liye ye options match karte hain:  1. *Addiction Killer Ark (Addiction Killer Liquid)* - Category: Addiction & De-addiction - Kaam aata hai: A tasteless and colourless Ayurvedic liquid drop formulation for alcohol, smoking, and drug a |
| 50 | `B2-ADD-02` | bug2 | ✅ PASS | english | 0.250 | 367 | — | alcohol addiction treatment product | 🤝 Here are the best matching options:  1. *Addiction Killer Ark (Addiction Killer Liquid)* - Category: Addiction & De-addiction - Used for: A tasteless and colourless Ayurvedic liquid drop formulation for alcohol, smoking, and drug addiction recovery |
| 51 | `B2-SKIN-01` | bug2 | ✅ PASS | hinglish | 0.250 | 359 | — | safed daag ka ilaj chahiye vitiligo treatment | ✨ Is concern ke liye ye options match karte hain:  1. *Saumya Plus* - Category: Skin Health — Vitiligo - Kaam aata hai: An Ayurvedic capsule and oil combination for vitiligo (Safed Daag / white skin patches). Stimulates natural melanin production, su |
| 52 | `B2-SKIN-02` | bug2 | ✅ PASS | english | 0.250 | 349 | — | white skin patches treatment medicine | ✨ Here are the best matching options:  1. *Saumya Plus* - Category: Skin Health — Vitiligo - Used for: An Ayurvedic capsule and oil combination for vitiligo (Safed Daag / white skin patches). Stimulates natural melanin production, supports repigmenta |
| 53 | `B2-WGT-01` | bug2 | ✅ PASS | hinglish | 0.250 | 468 | — | weight loss ke liye koi product hai | ⚖️ Is concern ke liye ye options match karte hain:  1. *Power Rootz SSS Formulae* - Category: Weight Loss & Stress Management - Kaam aata hai: A 3-in-1 Ayurvedic formula combining Slim Capsules and Sleep & Stress Tablets for sustainable weight loss,  |
| 54 | `B2-WGT-02` | bug2 | ✅ PASS | hinglish | 0.250 | 355 | — | motapa kam karne ki dawa chahiye | ⚖️ Is concern ke liye ye options match karte hain:  1. *Aadved Slim Herbs* - Category: Weight Management - Kaam aata hai: An Ayurvedic weight management combo of capsules and massage oil for natural fat burning, metabolism boosting, appetite suppress |
| 55 | `B2-RES-01` | bug2 | ✅ PASS | hinglish | 0.250 | 388 | — | asthma ya saans ki takleef ke liye kya hai | 😟 Is concern ke liye ye options match karte hain:  1. *Vayu Shuddhi* - Category: Respiratory Health - Kaam aata hai: Ayurvedic lung detox capsules formulated for smokers and individuals exposed to pollution. Clears airways, removes tar and mucus from |
| 56 | `B2-RES-02` | bug2 | ✅ PASS | english | 0.250 | 355 | — | breathing problem for respiratory health | Here are the best matching options:  1. *Vayu Shuddhi* - Category: Respiratory Health - Used for: Ayurvedic lung detox capsules formulated for smokers and individuals exposed to pollution. Clears airways, removes tar and mucus from lungs, improves br |
| 57 | `B2-SLP-01` | bug2 | ✅ PASS | hinglish | 0.250 | 362 | — | mujhe neend nahi aati insomnia ka koi ilaj | 😴 Is concern ke liye ye options match karte hain:  1. *Aadved Sleep* - Category: Sleep & Wellness - Kaam aata hai: Non-addictive herbal sleep support capsules that improve sleep quality, manage insomnia symptoms, regulate the sleep-wake cycle, and re |
| 58 | `B2-SLP-02` | bug2 | ✅ PASS | hinglish | 0.250 | 359 | — | sleep problem solution chahiye | 😴 Is concern ke liye ye options match karte hain:  1. *Aadved Sleep* - Category: Sleep & Wellness - Kaam aata hai: Non-addictive herbal sleep support capsules that improve sleep quality, manage insomnia symptoms, regulate the sleep-wake cycle, and re |
| 59 | `B2-GEN-01` | bug2 | ✅ PASS | hinglish | 0.250 | 425 | — | women's health product chahiye PCOS ke liye | 🌸 Is concern ke liye ye options match karte hain:  1. *Ayush for Women* - Category: Women's Health & Reproductive Support - Kaam aata hai: Ayurvedic capsules for women's reproductive health targeting PCOS, PCOD, irregular periods, hormonal imbalance, |
| 60 | `B2-GEN-02` | bug2 | ✅ PASS | english | 0.250 | 467 | — | female sexual wellness product | Here are the best matching options:  1. *Liv Muztang Limited Edition (Female)* - Category: Female Sexual Wellness - Used for: A specialised Ayurvedic herbal formulation for female intimate wellness. Stimulates the nervous system for enhanced sensory  |
| 61 | `B2-VAG-01` | bug2 | ✅ PASS [FB] | english | — | 755 | — | I need a medicine | I didn’t catch that, but I’d love to help you find what you need 😊 Are you looking to: 🛍️ Shop products, 📦 Track an order, 🔁 Start a return, 💬 Talk to support? |
| 62 | `B2-VAG-02` | bug2 | ✅ PASS | english | 0.250 | 615 | — | suggest me best product | Here are the best matching options:  1. *Addiction Killer Ark (Addiction Killer Liquid)* - Category: Addiction & De-addiction - Used for: A tasteless and colourless Ayurvedic liquid drop formulation for alcohol, smoking, and drug addiction recovery.  |
| 63 | `B2-VAG-03` | bug2 | ✅ PASS [FB] | hinglish | — | 466 | — | koi dawa batao | Sorry, is topic pe mere paas exact info nahi hai. Support team se connect ho jao ya thoda aur detail bhejo. |
| 64 | `B2-ENR-01` | bug2 | ✅ PASS | hinglish | 0.250 | 345 | — | energy booster chahiye general weakness | ⚡ Is concern ke liye ye options match karte hain:  1. *Ayush Kavach (Immunity System Booster Capsules)* - Category: Immunity & General Wellness - Kaam aata hai: Ayurvedic immunity booster capsules that enhance the body's natural defence against infec |
| 65 | `B2-ENR-02` | bug2 | ❌ FAIL | hinglish | 0.250 | 386 | unwanted:'piles' | shilajit product hai kya | Is concern ke liye ye options match karte hain:  1. *SK Turbo Treats Shilajit Gummies* - Category: Energy & General Wellness - Kaam aata hai: India's first Shilajit Gummies made with Himalayan Shilajit Resin. Sugar-free with tamarind flavour. Boosts  |
| 66 | `B3-AYU-01` | bug3 | ✅ PASS | english | 0.250 | 382 | — | Is Ayush for Men an ayurvedic medicine? | Here are the best matching options:  1. *Ayush for Men (Ayurvedic Sexual Wellness Capsules for Men)* - Category: Male Sexual Wellness - Used for: Ayurvedic capsules for male sexual wellness supporting testosterone levels, libido, erection quality, st |
| 67 | `B3-AYU-02` | bug3 | ✅ PASS | hinglish | 0.250 | 398 | — | Sandy RX ayurvedic hai kya | Is concern ke liye ye options match karte hain:  1. *Sandy RX* - Category: Male Sexual Wellness - Kaam aata hai: A high-potency Ayurvedic and herbal capsule for men addressing low testosterone, erectile dysfunction (ED), premature ejaculation (PE), l |
| 68 | `B3-AYU-03` | bug3 | ✅ PASS | english | 0.250 | 411 | — | Is Kaama Gold Kit an ayurvedic product | Here are the best matching options:  1. *Kaama Gold Kit* - Category: Male Sexual Wellness - Used for: A comprehensive 4-in-1 Ayurvedic sexual wellness kit for men containing capsules, oil, powder, and avaleha (herbal jam). Supports testosterone level |
| 69 | `B3-AYU-04` | bug3 | ✅ PASS | hinglish | 0.250 | 372 | — | Liv Muztang Capsules ayurvedic hai ya allopathic | Is concern ke liye ye options match karte hain:  1. *Liv Muztang Plus Capsules* - Category: Male Sexual Wellness - Kaam aata hai: Ayurvedic male vitality capsules for improving stamina, hormonal balance, testosterone support, sexual wellness, and con |
| 70 | `B3-AYU-05` | bug3 | ✅ PASS | english | 0.250 | 456 | — | Ultimate Hammer is it ayurvedic | Here are the best matching options:  1. *Ultimate Hammer (Ayurvedic Night Power Booster)* - Category: Male Sexual Wellness - Used for: Ayurvedic capsules formulated to boost libido, erection strength and duration, manage premature ejaculation (PE) an |
| 71 | `B3-AYU-06` | bug3 | ✅ PASS | english | 0.250 | 353 | — | Herbo 365 herbal medicine hai? | Here are the best matching options:  1. *Herbo 365* - Category: Male Vitality & Athletic Performance - Used for: Ayurvedic capsules for men to improve muscle mass, strength, testosterone levels, athletic performance, and sexual vitality. Also helps m |
| 72 | `B3-AYU-07` | bug3 | ✅ PASS | english | 0.250 | 375 | — | is Addiction Killer Powder ayurvedic or chemical | 🤝 Here are the best matching options:  1. *Addiction Killer Powder* - Category: Addiction & De-addiction - Used for: An Ayurvedic herbal powder designed to support recovery from alcohol, smoking, nicotine, and drug addiction. Helps reduce cravings, d |
| 73 | `B3-AYU-08` | bug3 | ✅ PASS | hinglish | 0.250 | 391 | — | Vayu Shuddhi natural hai ya chemical medicine | Is concern ke liye ye options match karte hain:  1. *Vayu Shuddhi* - Category: Respiratory Health - Kaam aata hai: Ayurvedic lung detox capsules formulated for smokers and individuals exposed to pollution. Clears airways, removes tar and mucus from l |
| 74 | `B3-AYU-09` | bug3 | ✅ PASS | english | 0.250 | 361 | — | Liver Care Capsules ayurvedic hai? | 🛡️ Here are the best matching options:  1. *Liver Care Capsules* - Category: Liver Health - Used for: Ayurvedic liver detox and regeneration capsules for fatty liver management, liver inflammation, toxin accumulation from alcohol and medications, and |
| 75 | `B3-AYU-10` | bug3 | ✅ PASS | hinglish | 0.250 | 460 | — | Stones Veda kya yeh ayurvedic dawa hai | Is concern ke liye ye options match karte hain:  1. *Stones Veda* - Category: Kidney Health & Urinary Tract - Kaam aata hai: An Ayurvedic capsule and syrup kit for kidney stone removal, UTI relief, and urinary detoxification. Promotes natural kidney  |
| 76 | `B3-TYP-01` | bug3 | ✅ PASS | english | 0.250 | 365 | — | What type of medicine is Ayush for Men | Here are the best matching options:  1. *Aadved Ayush 82 Tablets* - Category: Diabetes Management - Used for: A CCRAS-approved Ayurvedic tablet for Type 2 diabetes and prediabetes management. Helps regulate blood sugar levels, improves insulin sensit |
| 77 | `B3-TYP-02` | bug3 | ✅ PASS | hinglish | 0.250 | 379 | — | Jaam-e-Ishq kis tarah ki dawa hai | Is concern ke liye ye options match karte hain:  1. *Jaam-e-Ishq* - Category: Sexual Wellness (Unisex) - Kaam aata hai: A classical Unani herbal prash (paste) for sexual health and fertility in both men and women. Enhances sexual performance, stamina |
| 78 | `B3-TYP-03` | bug3 | ✅ PASS | english | 0.250 | 363 | — | what category does Stones Veda fall in | Here are the best matching options:  1. *Stones Veda* - Category: Kidney Health & Urinary Tract - Used for: An Ayurvedic capsule and syrup kit for kidney stone removal, UTI relief, and urinary detoxification. Promotes natural kidney stone passage, en |
| 79 | `B3-TYP-04` | bug3 | ✅ PASS | english | 0.250 | 367 | — | Dhurandar Oil — what type of product is this | Here are the best matching options:  1. *Dhurandar Oil* - Category: Joint & Muscle Pain - Used for: A 100% Ayurvedic vapor-action massage oil for joint stiffness, arthritis, spondylitis, sciatica, muscle pain, swelling, and injury recovery. Provides  |
| 80 | `B3-TYP-05` | bug3 | ✅ PASS | hinglish | 0.250 | 387 | — | Aadved Adivasi Hair Oil kis category mein aata hai | 🌿 Is concern ke liye ye options match karte hain:  1. *Aadved Adivasi Hair Oil* - Category: Hair Care - Kaam aata hai: A multi-herb Ayurvedic hair oil for reducing hair fall, dandruff, premature greying, and promoting hair growth. Strengthens roots,  |
| 81 | `B3-TYP-06` | bug3 | ✅ PASS | hinglish | 0.250 | 422 | — | Aadved Sleep kya hai tablet ya powder | 😴 Is concern ke liye ye options match karte hain:  1. *Aadved Sleep* - Category: Sleep & Wellness - Kaam aata hai: Non-addictive herbal sleep support capsules that improve sleep quality, manage insomnia symptoms, regulate the sleep-wake cycle, and re |
| 82 | `B3-TYP-07` | bug3 | ✅ PASS | hinglish | 0.250 | 354 | — | Saumya Plus kya ek skin cream hai | ✨ Is concern ke liye ye options match karte hain:  1. *Saumya Plus* - Category: Skin Health — Vitiligo - Kaam aata hai: An Ayurvedic capsule and oil combination for vitiligo (Safed Daag / white skin patches). Stimulates natural melanin production, su |
| 83 | `B3-TYP-08` | bug3 | ✅ PASS | english | 0.250 | 378 | — | SK Turbo Treats — what is this product | Here are the best matching options:  1. *SK Turbo Treats Shilajit Gummies* - Category: Energy & General Wellness - Used for: India's first Shilajit Gummies made with Himalayan Shilajit Resin. Sugar-free with tamarind flavour. Boosts natural energy an |
| 84 | `B3-TYP-09` | bug3 | ✅ PASS | hinglish | 0.250 | 374 | — | Power Rootz Keeda Jadi kya hota hai | Is concern ke liye ye options match karte hain:  1. *Power Rootz Keeda Jadi (Cordyceps Militaris)* - Category: Energy & Athletic Performance - Kaam aata hai: A premium Himalayan Cordyceps Militaris supplement known as 'Himalayan Viagra' for boosting  |
| 85 | `B3-TYP-10` | bug3 | ✅ PASS | hinglish | 0.250 | 494 | — | Ayush Kavach ka form kya hai tablet ya capsule | Is concern ke liye ye options match karte hain:  1. *Ayush Kavach (Immunity System Booster Capsules)* - Category: Immunity & General Wellness - Kaam aata hai: Ayurvedic immunity booster capsules that enhance the body's natural defence against infecti |
| 86 | `B3-HRB-01` | bug3 | ✅ PASS | english | 0.250 | 359 | — | Is Dr Piles Free made with herbal ingredients | 🩺 Here are the best matching options:  1. *Dr Piles Free* - Category: Piles & Digestive Health - Used for: A complete 3-in-1 Ayurvedic kit (capsules, powder, and oil) for treatment and management of internal and external piles (hemorrhoids), anal fis |
| 87 | `B3-HRB-02` | bug3 | ✅ PASS | hinglish | 0.250 | 426 | — | Nasha Free herbal hai ya koi chemical | 🤝 Is concern ke liye ye options match karte hain:  1. *Nasha Free* - Category: Addiction & De-addiction - Kaam aata hai: A colourless herbal liquid drop for reducing alcohol and nicotine cravings and supporting addiction recovery. Aids liver detoxifi |
| 88 | `B3-HRB-03` | bug3 | ✅ PASS | hinglish | 0.250 | 361 | — | Ayush Kwath natural ingredients se bana hai | Is concern ke liye ye options match karte hain:  1. *Aadved Adivasi Hair Oil* - Category: Hair Care - Kaam aata hai: A multi-herb Ayurvedic hair oil for reducing hair fall, dandruff, premature greying, and promoting hair growth. Strengthens roots, re |
| 89 | `B3-HRB-04` | bug3 | ✅ PASS | english | 0.250 | 376 | — | Ortho Veda Oil is it herbal | Here are the best matching options:  1. *Ortho Veda Oil* - Category: Joint & Muscle Pain - Used for: A clinically-tested, 100% plant-based Ayurvedic massage oil for joint stiffness, inflammation, knee and back pain, osteoarthritis, muscle strains, an |
| 90 | `B3-HRB-05` | bug3 | ✅ PASS | english | 0.250 | 377 | — | Sanjeev Ras herbal juice hai | Here are the best matching options:  1. *Sanjeev Ras* - Category: Immunity & Wellness - Used for: A premium Ayurvedic antioxidant juice powered by Sea Buckthorn (rich in Vitamins C & E, Omega 3, 6, 7, and 9) and Nano Curcumin for enhanced absorption. |
| 91 | `B3-HIN-01` | bug3 | ✅ PASS | hinglish | 0.250 | 352 | — | Kaama Gold herbal dawa hai ya english medicine | Is concern ke liye ye options match karte hain:  1. *Kaama Gold Kit* - Category: Male Sexual Wellness - Kaam aata hai: A comprehensive 4-in-1 Ayurvedic sexual wellness kit for men containing capsules, oil, powder, and avaleha (herbal jam). Supports t |
| 92 | `B3-HIN-02` | bug3 | ✅ PASS | hinglish | 0.250 | 425 | — | Addiction Killer angrezi dawa hai ya desi | 🤝 Is concern ke liye ye options match karte hain:  1. *Addiction Killer Powder* - Category: Addiction & De-addiction - Kaam aata hai: An Ayurvedic herbal powder designed to support recovery from alcohol, smoking, nicotine, and drug addiction. Helps r |
| 93 | `B3-HIN-03` | bug3 | ✅ PASS | hinglish | 0.250 | 373 | — | Sandy RX mein kya English medicine hai | Is concern ke liye ye options match karte hain:  1. *Sandy RX* - Category: Male Sexual Wellness - Kaam aata hai: A high-potency Ayurvedic and herbal capsule for men addressing low testosterone, erectile dysfunction (ED), premature ejaculation (PE), l |
| 94 | `B3-HIN-04` | bug3 | ✅ PASS | hinglish | 0.250 | 523 | — | Liver Care Capsules allopathic hai ya herbal | 🛡️ Is concern ke liye ye options match karte hain:  1. *Liver Care Capsules* - Category: Liver Health - Kaam aata hai: Ayurvedic liver detox and regeneration capsules for fatty liver management, liver inflammation, toxin accumulation from alcohol and |
| 95 | `B3-HIN-05` | bug3 | ✅ PASS | hinglish | 0.250 | 360 | — | Aadved Adivasi Hair Oil mein kya natural ingredients hain | 🌿 Is concern ke liye ye options match karte hain:  1. *Aadved Adivasi Hair Oil* - Category: Hair Care - Kaam aata hai: A multi-herb Ayurvedic hair oil for reducing hair fall, dandruff, premature greying, and promoting hair growth. Strengthens roots,  |
| 96 | `B3-CTG-01` | bug3 | ✅ PASS | hinglish | 0.250 | 371 | — | Ayush for Women kis category ka product hai | 🌸 Is concern ke liye ye options match karte hain:  1. *Ayush for Women* - Category: Women's Health & Reproductive Support - Kaam aata hai: Ayurvedic capsules for women's reproductive health targeting PCOS, PCOD, irregular periods, hormonal imbalance, |
| 97 | `B3-CTG-02` | bug3 | ✅ PASS | english | 0.250 | 378 | — | Macamo The Latin Lava which category | Here are the best matching options:  1. *Macamo (The Latin Lava)* - Category: Male Sexual Wellness - Used for: A Maca Root-based premium Ayurvedic capsule for men combining traditional Latin and Indian herbs for boosting libido, testosterone, fertili |
| 98 | `B3-CTG-03` | bug3 | ✅ PASS | hinglish | 0.250 | 374 | — | Aadved Slim Herbs kya yeh weight loss product hai | ⚖️ Is concern ke liye ye options match karte hain:  1. *Aadved Slim Herbs* - Category: Weight Management - Kaam aata hai: An Ayurvedic weight management combo of capsules and massage oil for natural fat burning, metabolism boosting, appetite suppress |
| 99 | `B3-CTG-04` | bug3 | ✅ PASS | hinglish | 0.250 | 355 | — | Poshan Plus weight gain ke liye hai | ⚖️ Is concern ke liye ye options match karte hain:  1. *Poshan Plus* - Category: Weight Gain & Nutrition - Kaam aata hai: A unisex Ayurvedic weight gainer powder for healthy weight gain, muscle mass building, energy, improved digestion, and stronger  |
| 100 | `B3-CTG-05` | bug3 | ✅ PASS | english | 0.250 | 352 | — | Dr Madhu Amrit diabetes kit hai | 🩺 Here are the best matching options:  1. *Dr. Madhu Amrit Diabetes Management Kit* - Category: Diabetes Management - Used for: A complete 3-in-1 holistic diabetes management kit containing Ayush 82 Tablets, Liver Support Tablets, and Neem-Karela-Jam |

---

## Failing Tests Detail

### ❌ `B1-PC-01` (bug1)
**Query:** what is the price of Ayush for Men
**Note:** Must show both COD price AND prepaid price
**Failures:** missing:'2900'; missing:'2610'
**Answer:**
> 💰 Price and order link for Ayush for Men are not provided. Please connect with our support team at +91 93113 91981 for assistance. 📞

### ❌ `B1-PC-02` (bug1)
**Query:** Sandy RX ka price kya hai
**Note:** Must show MRP and prepaid for Sandy RX
**Failures:** missing:'14063'; missing:'12656'
**Answer:**
> 💰 Price aur order link ke liye hamare support se baat karen: +91 93113 91981 📞

### ❌ `B1-PC-03` (bug1)
**Query:** what is the price of Kaama Gold Kit
**Note:** Must include COD price for Kaama Gold
**Failures:** missing:'2499'
**Answer:**
> 💰 Price aur order link ke liye hamare support se baat karen: +91 93113 91981 📞

### ❌ `B1-PC-04` (bug1)
**Query:** Liv Muztang Capsules kitne ka hai
**Note:** Must include COD price
**Failures:** missing:'4999'
**Answer:**
> Liv Muztang Capsules ki price abhi mujhe pata nahi hai. Order link aur price ke liye hamare support se baat karen: +91 93113 91981 📞. Prepaid order pe 10% off + free gift worth Rs. 1,299 milega 🎁.

### ❌ `B1-PC-05` (bug1)
**Query:** Ultimate Hammer MRP aur prepaid price bata
**Note:** Must show both MRP and prepaid price
**Failures:** missing:'1799'; missing:'1619'
**Answer:**
> 💰 Ultimate Hammer ki MRP hai Rs. 2,499, aur prepaid order par aapko milega Rs. 2,249 ka price.  Prepaid order pe 10% off + free gift worth Rs. 1,299 milega 🎁  Order karne ke liye yahan click karein: Ultimate Hammer: https://skinrange.com/products/ultimate-hammer

### ❌ `B1-CAT-01` (bug1)
**Query:** tell me everything about Ayush for Men
**Note:** Full product info: category, dosage, benefits, price
**Failures:** missing:'2900'
**Answer:**
> Here are the best matching options:  1. *Ayush for Men (Ayurvedic Sexual Wellness Capsules for Men)* - Category: Male Sexual Wellness - Used for: Ayurvedic capsules for male sexual wellness supporting testosterone levels, libido, erection quality, stamina, sperm count, and fertility. Addresses erectile dysfunction (ED), low sexual desire, and hormonal imbalance. Key ingredients include Kaunch Beej, Safed Musali, Ashwagandha, Akarakara, Shodhit Shilajit, Vidari Kand, Shatavari, and Kesar. Take 1 

### ❌ `B1-DUR-02` (bug1)
**Query:** Sandy RX kitne din lena hai
**Note:** Recommended Duration: 3 months
**Failures:** missing:'month'
**Answer:**
> Sandy RX ko 3 maheeney tak lena chahiye. Roz 2 capsules lukewarm milk ke saath lena hoga. Aap regular use se achhe results dekh sakte hain. Koi aur sawaal ho toh bataiye! 😊

### ❌ `B1-DUR-03` (bug1)
**Query:** Kaama Gold ka full course kitna hai
**Note:** Course duration for Kaama Gold
**Failures:** missing:'month'
**Answer:**
> Kaama Gold Kit ka full course 3–6 mahine ka hota hai. Ismein capsules, oil, powder, aur avaleha sab included hai, jo aapki sexual wellness ke liye kaam aata hai. Agar aapko aur details chahiye toh batao! 😊

### ❌ `B1-DUR-05` (bug1)
**Query:** Addiction Killer kitne time mein kaam karta hai
**Note:** Expected timeline for Addiction Killer in months
**Failures:** missing:'month'
**Answer:**
> Addiction Killer ko best results ke liye 3 mahine regular use karna hota hai. Is period ke dauran aapko cravings kam hone, emotional balance improve hone aur detoxification feel hoga. Agar aapko koi aur sawal hai, toh puch sakte hain! 😊

### ❌ `B1-PACK-01` (bug1)
**Query:** Ayush for Men ka pack size kya hai
**Note:** Single bottle, 60 capsules — check for bottle/capsule mention
**Failures:** missing:'bottle'
**Answer:**
> Is concern ke liye ye options match karte hain:  1. *M9 Shampoo (Instant Hair Colour Shampoo)* - Category: Hair Care - Kaam aata hai: An ammonia-free instant hair colouring shampoo that restores natural black hair colour in just 5 minutes. Comes as a combo pack of Colorant Shampoo and Developer Shampoo. Contains Noni Extracts, Aloe Vera, and Olive Oil. Mix both shampoos, apply on dry hair, leave for 5 minutes, and rinse. Not recommended for daily use. Currently out of stock.  2. *Ayush for Men (

### ❌ `B1-PACK-02` (bug1)
**Query:** Sandy RX mein kitni tablets hoti hain
**Note:** 60 capsules per bottle
**Failures:** missing:'60'
**Answer:**
> Sandy RX mein 30 capsules hoti hain. Aapko daily 2 capsules lena hai, toh yeh ek mahine tak chalega. Koi aur help chahiye? 😊

### ❌ `B2-PIL-03` (bug2)
**Query:** pet mein gas bahut hoti hai digestion problem
**Note:** Digestion/gas → gut health products
**Failures:** missing:'vajra'
**Answer:**
> Aapko gas aur digestion ki problem ke liye SK Gut Raksha kaam kar sakta hai. Yeh Ayurvedic gut detox hai jo aapki digestion improve karega.  🟢 Product: SK Gut Raksha 💰 Price: Price aur order link ke liye hamare support se baat karen: +91 93113 91981 📞 👉 Benefits: Chronic constipation, gas, bloating, aur acidity ko address karta hai. 🔑 Usage: 1 spoon (10 g) powder subah khali pet lukewarm water mein. Aur har Sunday 1 detox shot (5 ml). 🗓️ Recommended duration: 3-month course. 🎁 Prepaid order pe 1

### ❌ `B2-ENR-02` (bug2)
**Query:** shilajit product hai kya
**Note:** Shilajit query → SK Turbo Treats Shilajit Gummies
**Failures:** unwanted:'piles'
**Answer:**
> Is concern ke liye ye options match karte hain:  1. *SK Turbo Treats Shilajit Gummies* - Category: Energy & General Wellness - Kaam aata hai: India's first Shilajit Gummies made with Himalayan Shilajit Resin. Sugar-free with tamarind flavour. Boosts natural energy and stamina, reduces fatigue and stress, strengthens muscles and bones, supports testosterone levels, and promotes sexual wellness and healthy aging. Suitable for both men and women. Chew 1–2 gummies daily at any time — no water requir
