# Growth channels and monetization for consumer AI assistants / freemium productivity apps (2025–2026) — playbook inputs for Dewiar ("Лира")

Research date: 2026-11-20. Every number is dated where the source gives a date. "(est.)" = estimate or vendor/secondary claim; "(promo)" = source sells something related, treat with caution. Dewiar baseline for comparison (from brief): ~1,500 new PCs/month (RU-speaking), week-1 retention ~34% PC / ~20% phone, prepaid credits ("талеры").

---

## 1. Monetization benchmarks: free→paid conversion, trials, hard vs soft paywall, annual vs monthly, credits vs subscription

### Takeaway
Hard paywalls convert ~5x better and earn ~8x more revenue per install by day 60, but AI apps almost never use them (<2%); the best-retaining AI apps are freemium + a 7-day trial + subscription-only with low price bands, while "hybrid" (subscription + consumables/credits) correlates with *worse* retention. AI apps earn ~41% more per payer in year 1 but churn ~30% faster; annual plans retain 3–4x better than monthly for AI apps.

### Cited Findings
**RevenueCat State of Subscription Apps 2026 (published 19 Mar 2026; 115,000+ apps, $16B+ revenue)** — [RevenueCat blog: SOSA 2026 benchmarks](https://www.revenuecat.com/blog/growth/subscription-app-trends-benchmarks-2026.md); [full report](https://www.revenuecat.com/state-of-subscription-apps-2026/)
- Median conversion, hard paywall: 10.7% (12.1% in 2025); freemium: 2.1% (flat vs 2025) → hard ≈5x freemium. Note: text calls it "Day-35 trial-to-paid", chart caption calls it "download-to-paid" — ambiguity unresolved in source.
- Revenue per install at day 60: hard paywall $3.09 vs freemium $0.38 (~8x).
- Trial length: 17–32-day trials median trial-to-paid 42.5% vs trials <4 days 25.5% (~70% higher for long trials); share of apps using <4-day trials rose 42.1% → 46.5%.
- 55.4% of 3-day-trial cancellations happen on day 0; 84% by day 1.
- Yearly subscribers still active after 1 year: freemium 28% vs hard paywall 27% (no meaningful difference).
- ~72% of annual subscribers cancel (turn off auto-renew) within year 1 (up from ~56% in 2025); month 1 = 35% of annual cancellations, spike again at month 12.
- AI monthly plans retain 36% worse over 12 months than non-AI apps; AI 12-month payer retention (2025 cohort): 9.2% App Store, 11.5% Google Play.
- Google Play: 31% of cancellations are involuntary billing failures (28.2% in 2025); App Store 14%. Report estimates 15–20% of lost Android revenue recoverable via retries/grace periods.
- Top 25% of apps grew MRR 80%+ YoY; bottom 25% shrank >33%.

**RevenueCat AI App Retention Study (published 18 Aug 2026; 3,519 AI apps, 50M+ paid subscriptions started Jul 2024–Jun 2025)** — [RevenueCat: AI app retention study](https://www.revenuecat.com/blog/growth/ai-app-retention-study); press coverage [TechCrunch, 10 Mar 2026](https://techcrunch.com/2026/03/10/ai-powered-apps-struggle-with-long-term-retention-new-report-shows), [PPC Land](https://ppc.land/ai-apps-earn-41-more-per-user-but-churn-30-faster-revenuecat-finds/)
- Median Y1 LTV per payer: AI $30.16 vs non-AI $21.37 (+41%). AI apps churn ~30% faster.
- 1-year retention of subscriptions, monthly plans: AI avg 6.1% vs non-AI 9.5% (high-retention AI apps 10.9%, low 1.6%).
- Annual plans: AI avg 21.1% vs non-AI benchmark 30.7% (high-retention AI 30.7%, low 8.2%).
- Weekly plans: high 3.1%, mid 1.1%, low 0.2% → weekly plans are a retention trap.
- First renewal of monthly plan: 57.9% (high-retention apps) vs 30.2% (low); by 3rd renewal 79.5% vs 68.5% survive each step.
- 7-day trial is 12.7 pp more common among high-retention apps; "no trial" is 23.7 pp more common among low-retention apps.
- Freemium: 66.8% of high-retention vs 55.4% of low-retention apps. Hard paywalls: <2% of AI apps.
- Lowest price band: 15.6% of high-retention vs 8.3% of low-retention apps.
- Subscription-only is 16.4 pp more common among high-retention apps; hybrid (subscription + consumables) is 16.3 pp more common among low-retention apps. Still, ~25% of best-retaining AI apps sell consumables.

**Price points (consumer AI, 2026)**
- ChatGPT: Go $8/mo (US; rolled out to 170 countries, page updated 18 Jan 2026; localized prices in some markets), Plus $20, Pro $200 — [Gulf News](https://gulfnews.com/technology/openais-cheaper-chatgpt-go-plan-goes-global-after-india-debut-1.500412041). Go launched first in India in Aug 2025 at under $5 (₹399) — [TechCrunch, 18 Aug 2025](https://techcrunch.com/2025/08/18/openai-launches-a-sub-5-chatgpt-plan-in-india).
- Google AI Plus $4.99/mo (US), AI Pro $19.99, AI Ultra from $100 (restructured at I/O May 2026); Claude Pro $20, Max $100/$200 — [iThinkDiff, 22 Aug 2026, upd. 15 Nov 2026](https://www.ithinkdiff.com/google-ai-plans-with-family-sharing-beat-chatgpt-and-claude/).
- Perplexity Max €229/mo; Runway $12 plan ≈ 50 s of Gen-4 video; Canva raised Teams prices up to 300% in 2024 citing AI — [RevenueCat, 29 Oct 2025](https://www.revenuecat.com/blog/growth/ai-subscription-app-pricing.md).
- Russia: Алиса Плюс option 199 ₽/mo (from 100 ₽ on 7 Jul 2026), only on top of Яндекс Плюс 449 ₽/mo (annual 4,490 ₽ since 16 Jun 2026) → full 648 ₽/mo; Алиса Про basic tier free (50 requests/mo), extended inside Яндекс 360 (200 requests/mo); basic Alice AI free; 30-day free trial for new users — [checkroi.ru, 2026](https://checkroi.ru/blog/alisa-plyus-vs-alisa-pro/).

**Credits vs subscription (qualitative)**
- Vendors/analysts debate: [Vellum — "Why subscriptions beat credits for AI products"](https://www.vellum.ai/blog/why-subscriptions-beat-credits-for-ai-products); [Metronome — cost-plus credit models "work until they don't"](https://metronome.com/blog/the-rise-of-ai-credits-why-cost-plus-credit-models-work-until-they-dont); [Metronome — 2026 trends from 50 AI pricing models](https://metronome.com/blog/2026-trends-from-cataloging-50-ai-pricing-models). (Not fetched in full — treat as opinion pieces.)
- RevenueCat notes heavy users can cost "dozens of times" more to serve than casual users (no number) — [RevenueCat, Oct 2025](https://www.revenuecat.com/blog/growth/ai-subscription-app-pricing.md).

### Inferences
- For Dewiar, pure prepaid credits resemble the "hybrid/consumables" pattern that correlates with lower retention in RevenueCat data; a simple subscription (with credits only as a top-up for heavy use) is the better-evidenced default for consumer AI. Credits remain reasonable for B2B/SMB usage (messages, calls).
- Realistic targets for a freemium AI assistant: 2–3% of new installs → paid within ~35 days (RevenueCat freemium median 2.1%); a 7-day trial of the paid tier; push annual plans (AI annual ~21% 1-yr retention vs monthly ~6%).
- Global anchor price ladder in 2026: ~$5 (Google AI Plus) → $8 (ChatGPT Go) → $20 (Plus/Pro). A Dewiar personal plan at $5–8/mo would sit in the "low price band" that correlates with high retention. In Russia, Yandex's mass AI bundle is 648 ₽/mo (~$7–8, est. rate), with a free tier — Dewiar's RU price should be at or below that.
- Android payments: invest in billing retry/grace (31% of Play cancellations involuntary).
- Weekly plans should be avoided.

### Gaps
- No reliable public download→paid conversion specifically for desktop AI assistants (all RevenueCat data is mobile app stores).
- No published RevenueCat dollar median price by AI category (assistant vs companion vs productivity) found in fetched pages; the full 338-page report may contain it.
- No hard comparative data (A/B) on pure prepaid credits vs subscription in consumer AI — only correlational RevenueCat data and opinion pieces.
- UAE-specific consumer AI price points not found (ChatGPT Go has localized prices "in some markets" but UAE figure unconfirmed).

---

## 2. Activation: first-session / time-to-value

### Takeaway
Public numbers for AI-app activation are scarce; the best general benchmark is Lenny's survey (avg 34%, median 25% activation; B2C freemium highest). The dominant pattern is "describe your need → useful output in under a minute", plus long-ish trials and immediate value in session 1 (because 84% of short-trial cancellations happen by day 1).

### Cited Findings
- Activation benchmark (survey of 500+ products, 25 Oct 2022): average 34%, median 25%; SaaS avg 36%, median 30%; B2C freemium has the highest rates; ~60th percentile "good", ~80th "great". Most common levers: simpler onboarding UI, reducing friction, emails/follow-ups, copy, smarter targeting, incentives, showing value earlier — [Lenny's Newsletter: What is a good activation rate](https://www.lennysnewsletter.com/p/what-is-a-good-activation-rate).
- A 2026 compilation claims SaaS activation median 30–37% (560+ companies) — [Artisan Growth Strategies (est.)](https://www.artisangrowthstrategies.com/md/blog/saas-activation-rate-benchmarks-2026) (not verified).
- AI-native onboarding: Gamma delivers a styled deck "within seconds" of a description; generic pattern "sign up, describe a need, get something useful in under a minute"; ChartMogul says some AI-native products are 3x more likely to reach $1M ARR in 6 months but have weaker net revenue retention; recommends comparing 30/60/90-day retention between users who acted on their first AI output vs not — [ChartMogul, 7 Apr 2026](https://chartmogul.com/blog/from-signup-to-value-how-ai-is-changing-activation-in-saas/).
- 55.4% of 3-day trial cancellations happen on day 0, 84% by day 1 → the first session decides — [RevenueCat SOSA 2026](https://www.revenuecat.com/blog/growth/subscription-app-trends-benchmarks-2026.md).
- Case study claims: Correcto +208% activation — [Amplitude](https://amplitude.com/blog/correcto-boosted-activation.md); Appcues 2.5x activation — [Appcues](https://www.appcues.com/blog/we-increased-our-activation-rate-by-2.5x) (not fetched; details unverified).
- Product Hunt example: 400 signups → 98% activation → 1 paying customer (0.25%) — [Product Hunt / Rankfender post (promo)](https://www.producthunt.com/p/rankfender/we-tracked-1-000-product-hunt-launches-here-s-what-the-top-10-did-differently).

### Inferences
- Dewiar's week-1 retention (34% PC, 20% phone) is roughly at Lenny's average activation range, but phone is notably weaker — phone first session is the higher-leverage fix.
- Define one "aha" event (e.g., first completed task by voice: an added to-do, a reminder that actually fires the next day, or a site generated in one phrase) and measure D7/D30 for users who hit it vs not (ChartMogul method).
- Trials should start after the aha moment, not at install.

### Gaps
- No AI-assistant-specific, measured before/after onboarding experiments with numbers found from primary sources.
- No public data on voice-first onboarding activation.

---

## 3. Retention mechanics with measured effects (Duolingo, streaks, notifications, daily briefings)

### Takeaway
Duolingo's growth came from optimizing one metric — CURR (current-user retention rate) — which in their model had 5x more DAU impact than any other lever; the result was 4.5x DAU in 4 years. Leaderboards gave +17% learning time and 3x highly-engaged users; referral gave only +3% new users. Notifications must be rationed.

### Cited Findings
- Duolingo (Lenny's Newsletter, Jorge Mazal, 28 Feb 2023): DAU grew 4.5x over 4 years (from mid-2018 single-digit YoY growth); CURR rose 21%, cutting daily churn of best users by >40%; in simulation CURR's DAU impact was 5x that of the 2nd-best metric and 6x its MAU impact; share of DAU with 7+ day streak rose ~3x to >50% of DAU; leaderboards: +17% learning time, 3x users learning 1h+/day 5 days/week, significant D1/D7 gains; streak-saver notification was "first big streak win" (no lift published); users reaching 10-day streak had much lower drop-off (partly selection); a Gardenscapes-style "moves" mechanic was neutral; referral program (free month of Super) increased new users only 3%; rule: no increase in notification volume without strong justification and CEO approval (Groupon cautionary tale: 1→5 emails/day killed the channel) — [Lenny's Newsletter: How Duolingo reignited user growth](https://lennysnewsletter.com/p/how-duolingo-reignited-user-growth).
- Duolingo retention/streak coverage: [Sensor Tower on Duolingo streaks](https://sensortower.com/blog/duolingo-streak-feature-app-engagement-growth); [Business of Apps: streaks drive record 17M DAU](https://www.businessofapps.com/news/duolingos-streak-feature-drives-record-17-million-daus); [Duolingo blog: growth model](https://blog.duolingo.com/growth-model-duolingo/) (not fetched).
- AI apps' retention problem: monthly AI plans retain 36% worse than non-AI over 12 months — [RevenueCat SOSA 2026](https://www.revenuecat.com/blog/growth/subscription-app-trends-benchmarks-2026.md).
- OpenClaw (an always-on personal agent) reports ~92% retention and ~45-min sessions (est., vendor page, definitions unclear) — [OpenclawVPS stats (promo)](https://openclawvps.io/blog/openclaw-statistics).

### Inferences
- For Dewiar: "Мой день" (дела, заметки, календарь) + a proactive morning briefing is the natural daily trigger; streaks only make sense if tied to a real habit (e.g., "день спланирован N дней подряд"), not to chatting. Use the CURR framing: measure the share of last week's active users who are active this week, and optimize that first.
- Referral programs are low-lift for single-user apps (Duolingo +3%); family invitation ("Близкие") is more promising because value is inherently multi-user — but no measured data found.

### Gaps
- No published measured effect of proactive daily briefings in AI assistants (ChatGPT Pulse, Gemini daily brief etc.) found.
- No published D30/D90 retention for daily-use AI assistants outside subscription-payer data.

---

## 4. Growth channels that worked for small teams (2024–2026)

### Takeaway
Open source + a technical community launch (Show HN + Reddit) is the strongest proven free channel for privacy/local AI tools (OpenClaw, Ollama); Product Hunt now drives signups but very few payments. Telecom bundles create huge spikes (Perplexity–Airtel: downloads ~9x) with modest later monetization; they need a large partner and are not a small-team lever except regionally.

### Cited Findings
**Telecom/OEM bundle — Perplexity × Airtel (India)** — [TechCrunch, 18 Aug 2026](https://techcrunch.com/2026/08/18/perplexitys-free-ai-offer-left-it-with-millions-more-users-in-india/); also [YourStory](https://yourstory.com/ai-story/perplexity-india-airtel-free-offer-user-growth/), [Unite.AI](https://www.unite.ai/perplexitys-free-airtel-year-ends-and-its-india-revenue-climbs/)
- Jul 2025: free 12-month Pro (~$200 value) for 360M Airtel customers; new redemptions ended 16 Jan 2026.
- Downloads: 5.9M in Jul 2025 (+625% MoM; all H1 2025 = 5.4M); 56M during 7 months of the offer (>9x prior 7 months); Feb–Jul 2026 only 3.3M (−90%).
- Daily downloads (Appfigures): ~11,200/day before → ~223,000/day first week (~20x).
- MAU: 8.9M (Jul 2025) → peak 22M (Oct 2025) → ~14M (Jul 2026), still >5x the H1 2025 avg (~2.6M).
- Revenue: net mobile ~$34k (Jan 2025) → $70k (Dec 2025) → $156k (Jul 2026); India IAP revenue Feb–mid-Aug 2026 +60% vs offer period; no paid conversion rate disclosed; part may be auto-renewals.

**Open source as distribution**
- OpenClaw: launched 14 Nov 2025 (as Clawdbot), rebranded 29 Jan 2026; 34k stars in 48 h, 60k in 72 h; passed React at ~250.8k stars on 3 Mar 2026; 346k+ by 2 Apr 2026; monthly site visitors 7.25M (Feb) → 38M (Apr 2026); 500k+ running instances; 44k+ skills on ClawHub (Apr); 180 startups on top earn $320k+/mo combined; user hosting $8–60/mo — [OpenclawVPS stats (promo, secondary; some figures e.g. "OpenAI acquisition $116M" and "92% retention" unverified)](https://openclawvps.io/blog/openclaw-statistics); [Analytics India Mag: OpenClaw overtakes React](https://analyticsindiamag.com/ai-news/openclaw-overtakes-react-in-total-github-stars).
- Ollama: 8.9M+ developers, growing ~1M/week; ~65k–67k apps/integrations; claimed 85% of Fortune 500; $65M Series B (Theory-led); drivers: one-download simplicity, local-first privacy, hybrid local+cloud, being the default backend for other tools — [Tomasz Tunguz, 9 Jul 2026](https://www.tomtunguz.com/ollama-series-b/index.md); "52M downloads" claim — [Vucense (unverified)](https://vucense.com/ai-intelligence/local-llms/ollama-hits-52-million-downloads-local-ai/).

**Show HN** — [dev.to Show HN guide (year not shown)](https://dev.to/iris1031/how-to-launch-on-hacker-news-the-show-hn-guide-real-data-461e)
- Front-page Show HN: ~200–600 points, 50–200 comments; needs ~30–50 upvotes in first hour.
- ~60% of HN traffic in first 6 h, ~80% in 24 h, negligible by day 3.
- Open-source tools: typically 500–2,000 GitHub stars from a front-page appearance; AFFiNE (Show HN + Reddit push) got 6,000 stars in week 1.
- Best time Mon–Thu 9–10 AM ET; answer comments within 15 min for first 2 h.
- More postmortems: [Indie Hackers: front page of HN full postmortem](https://www.indiehackers.com/post/front-page-of-hn-the-full-postmortem-traffic-lessons-surprises-cbe9e0a7f6) (not fetched).

**Product Hunt** — [Rankfender analysis of 1,000 launches 2025–2026 (promo)](https://www.producthunt.com/p/rankfender/we-tracked-1-000-product-hunt-launches-here-s-what-the-top-10-did-differently)
- Example: #6 of the day, 168 upvotes → 400 signups → 1 paying customer (0.25%, $237).
- Claimed: top performers convert 5–12% of activated users (no sample); top 10% prepared community/SEO 4–6 weeks before; replied to first comment within 5 min; staggered outreach waves.
- Product Hunt pages are cited by LLMs: one PH URL = 1.6% of Superwhisper's ChatGPT visibility, 5.5% of its Google AI Overview visibility; FAQ sections raised ChatGPT citations 10x (PH's own case study). Correlation of AI-visibility with community presence +0.395, SEO +0.319, PH rank −0.286.

**Referral programs**
- Duolingo referral (free month of Super): +3% new users only — [Lenny's Newsletter](https://lennysnewsletter.com/p/how-duolingo-reignited-user-growth).

### Inferences
- For Dewiar's English launch, the best-evidenced small-team sequence: (1) open-source repo `dewiar-app` polished as the distribution asset → (2) Show HN (Tue/Wed 9–10 AM ET) + r/LocalLLaMA / r/selfhosted on the "private, on-device voice assistant" angle → (3) Product Hunt mainly for backlinks and LLM visibility (expect signups, not payments).
- Telecom-bundle analogue for UAE/CIS: possible only via partners (operators, PC OEMs); Airtel case shows ~9x install spike but ~90% fall-off when the offer stops and slow monetization — treat as brand/awareness, not revenue.
- Referral incentives are low-lift; invest in "invite a close one" only where the feature itself needs two people.

### Gaps
- No measured data found (within the call budget) on TikTok/YouTube Shorts demo results, creator partnerships, Microsoft Store / winget install volumes, or ASO lift for AI assistants.
- LM Studio and Jan user numbers not found from reliable sources.
- Reddit (r/LocalLLaMA, r/selfhosted) launch traffic numbers not found; AFFiNE example combines HN+Reddit.

---

## 5. B2B/SMB monetization: what small businesses pay for

### Takeaway
SMBs pay $20–$200/mo for chat/voice AI front-desk tools (with usage caps and overage), vs $250–$400/mo for human-backed answering services and ~$44–51k/yr for a human receptionist. Typical structure: flat tier + included volume + credit packs, often with a 7-day trial and paid/free managed setup.

### Cited Findings
- Hyperleap AI (chat-first receptionist): Plus $40/mo (3,000 AI responses, 1 bot), Pro $100 (12,000, 2 bots), Max $200 (30,000, 5 bots); extra credit packs $12 per 1,000; 7-day trial with card, no free plan; managed setup was $299, now free; WhatsApp Meta fees paid separately — [Hyperleap, 27 Jul 2026, upd. 10 Nov 2026 (vendor)](https://hyperleap.ai/blog/ai-receptionist-cost).
- Voice AI entry tiers: My AI Front Desk $20/mo test tier; Dialzara $29/mo for 60 voice minutes + per-minute overage. Human-backed: Smith.ai $300/mo (30 calls), Ruby $250/mo (50 minutes), Podium ~$399/mo. Traditional answering services $50–450/mo or $0.75–2.00+/min (mid $0.90–1.25/min). Human receptionist: median ~$36k/yr base, $44–51k total cost (BLS May 2024) — same source.
- Further pricing guides (not fetched): [CloudTalk AI answering service cost](https://www.cloudtalk.io/blog/how-much-does-ai-answering-service-cost/), [Dupple: AI receptionist cost at 100/300/1,000 calls](https://dupple.com/learn/how-much-does-an-ai-receptionist-cost), [Tidio chatbot pricing](https://tidio.com/blog/chatbot-pricing/), [Landbot WhatsApp chatbot cost](https://landbot.io/whatsapp-business-automation/whatsapp-chatbot-cost), [SleekFlow AI agent cost](https://sleekflow.io/en-us/blog/ai-agent-cost).

### Inferences
- Dewiar's SMB features (website chat bot, messenger bot, clients) can be priced as a separate business tier in the $20–100/mo band with included message volume and credit top-ups — credits fit B2B usage better than consumer use.
- The selling comparison is "vs human receptionist/answering service" (20–100x cheaper per vendor claims).

### Gaps
- WhatsApp Business per-message Meta fees by country (UAE, Russia N/A) not retrieved (fetch failed).
- No data on SMB conversion/churn for AI receptionist products; prices are vendor-published list prices.
- Russian SMB price points for AI chat bots not researched.

---

## 6. Family plans and regional pricing

### Takeaway
Family sharing is a gap among AI assistants: ChatGPT and Claude have no family plans; Google bundles AI with family-shareable storage (AI Plus $4.99, shareable with up to 5 others). Regional pricing is now standard: ChatGPT Go launched in India at <$5 and is $8 in the US across 170 countries; Russian mass-market AI is bundled at 648 ₽/mo with a free tier.

### Cited Findings
- Google AI Plus $4.99/mo — 400GB storage shareable with up to 5 family members; AI Pro $19.99 (2TB, Google Home Premium, YouTube Premium Lite); ChatGPT and Claude: no family/multi-seat consumer option; 5-person household: ChatGPT Plus $100/mo vs Google AI Plus $4.99 — [iThinkDiff, upd. 15 Nov 2026](https://www.ithinkdiff.com/google-ai-plans-with-family-sharing-beat-chatgpt-and-claude/).
- Apple One Family reportedly $27.95/mo for up to 6 people (2026) — [Tech Insider (not fetched)](https://tech-insider.org/apple-one-family-27-95-six-people-four-services-2026/); Apple Music family price increases 2026 — [IBTimes SG (not fetched)](https://www.ibtimes.sg/A000Nnc).
- ChatGPT Go: India launch Aug 2025 under $5 (₹399) — [TechCrunch](https://techcrunch.com/2025/08/18/openai-launches-a-sub-5-chatgpt-plan-in-india); US $8, 170 countries, localized in some markets (Jan 2026) — [Gulf News](https://gulfnews.com/technology/openais-cheaper-chatgpt-go-plan-goes-global-after-india-debut-1.500412041).
- Russia: Яндекс Плюс 449 ₽/mo + Алиса Плюс 199 ₽/mo = 648 ₽/mo; annual Плюс 4,490 ₽; free Alice AI and free Alice Pro basic (50 requests/mo) — [checkroi.ru 2026](https://checkroi.ru/blog/alisa-plyus-vs-alisa-pro/).

### Inferences
- A Dewiar family plan (e.g., 1 payer + up to 5 "Близкие") is a real differentiator vs ChatGPT/Claude; family plans typically price at ~1.5–2x the individual price (Spotify/Apple pattern — est., not verified in this research).
- Regional price ladder suggestion (est.): RU/CIS ≈ 300–600 ₽/mo (below Yandex 648 ₽ bundle); US/EU $5–8 personal; UAE ≈ US price (high-income market) — the UAE figure is an inference, not sourced.

### Gaps
- Spotify Family exact 2026 prices, and UAE-specific pricing of ChatGPT/Google AI not retrieved.
- No data on what share of AI-assistant users would adopt a family plan.
