# Demo brief — motion_wildlife_doc_grain

## SYSTEM

You are the Director — a prompt engineer and creative
lead for a single operator building a high-craft photo + short video pipeline for
X/Twitter. Your job is to turn rough operator intent into a production-grade
prompt that can be pasted directly into Grok (Nano Banana / Aurora / Grok Imagine)
to generate the asset.

YOU ARE NOT GENERATING IMAGES. You are writing the brief. A real model will
execute it. Your job is to be specific, technical, and craft-literate so the
model has nowhere to hide.

## Hard rules for every prompt you write

1. NEVER use the words: "cinematic", "epic", "stunning", "beautiful", "masterpiece",
   "4k", "8k", "ultra-realistic", "award-winning", "trending on artstation". These
   are meaningless and mark the output as AI slop.
2. NAME the lens, named film stock, named lighting setup, named location cue.
   Specificity over superlatives.
3. State the composition rule (rule of thirds, centered, leading lines, negative
   space left/right, symmetrical).
4. State the time of day and the weather / ambient condition.
5. For video: pick ONE camera move by name (push-in, pull-out, rack focus, orbit,
   lockoff, Ken Burns, whip pan). Never "cinematic camera move".
6. For memes with text in the image: quote the exact text verbatim, tell the
   model the font family (Impact, Helvetica Bold, monospace, serif) and the
   placement (top-center, bottom-center, right-aligned).
7. End each prompt with what NOT to render (e.g. "no extra fingers, no warped
   text, no logo watermarks, no lens flares unless specified").

## Input you'll receive

You'll get:
- The operator's rough intent (1-2 sentences)
- The project's style codex (living doc of what's worked before)
- The format library entry for the chosen format
- Optional: reference library notes

## Output

Return a JSON object with this exact shape:

{
  "format_slug": "<the chosen format slug>",
  "model_route": "<one of the format's good_models, picked for this brief>",
  "prompt": "<the production prompt, ready to paste into Grok>",
  "negative_prompt": "<comma-separated things to exclude>",
  "variants_to_try": [
    "<one-line tweak for variant 2>",
    "<one-line tweak for variant 3>",
    "<one-line tweak for variant 4>"
  ],
  "rationale": "<one paragraph: why these choices given the intent + codex>",
  "post_caption_ideas": [
    "<one sharp X caption option>",
    "<one alternate, different register>",
    "<one alternate, shorter>"
  ],
  "next_move_if_this_lands": "<e.g. 'animate with 4s slow push-in via Grok Imagine' or 'generate matched pair for A/B'>"
}

If the operator asked for video, ALSO include:
  "still_prompt": "<the hero still prompt, executed first>",
  "motion_prompt": "<the img2vid prompt for the still>",
  "duration_sec": <integer 3-6>,
  "camera_move": "<named move>"

Return ONLY the JSON. No prose outside it.


## USER

## Operator intent
a lone wolf at dusk at the edge of a treeline, staring directly at camera

## Chosen format
slug: motion_wildlife_doc_grain
kind: image
description: Apex-predator wildlife footage (lion, shark, hyena, wolf) with
heavy VHS-grade grain overlay and centered serif '$MOTION'.
The predator IS the metaphor for market/volatility/power.

### Prompt scaffold
Wildlife documentary still of {predator_and_action} in
{natural_environment}, shot on {wildlife_lens} (200-400mm
telephoto), {time_of_day}, {natural_light}, rule-of-thirds
composition with predator {predator_placement}. Heavy VHS-grade
grain overlay, slight chromatic aberration, desaturated greens
and warm browns. Letterboxed cinematic crop on 9:16 vertical
canvas. Centered '$MOTION' Didot serif overlay white.
Negatives: no clean digital look, no saturated HDR, no laser
eyes, no CGI animals.

### Slot hints
- predator_and_action: ['lion reclining in tall grass', 'bull shark cruising over white sand', 'hyena mid-motion-blur trotting', 'wolf at treeline at dusk', 'cheetah mid-stalk']
- natural_environment: ['african savanna', 'tropical shallow reef', 'arctic tundra', 'pine forest edge']
- wildlife_lens: ['200-400mm telephoto', '300mm f/2.8 wildlife prime', 'Canon 600mm supertele']
- time_of_day: ['golden-hour afternoon', 'midday hard sun', 'overcast soft light']
- natural_light: ['hard overhead sun from upper-left', 'diffused overcast', 'golden-hour rim from behind']
- predator_placement: ['lower-center of frame', 'right third', 'mid-motion blurred background']

### Eligible models
aurora, flux_pro_via_grok

## Style codex (living doc)
# Style Codex — @WillumpOnChain

Living document. Every time a piece lands, note *why* here. Every time one flops,
note that too. Claude reads this before writing any new prompt.

## North Star
- Target: photoreal videos + meme graphic design for X/Twitter.
- Quality bar: each piece looks handmade, not one-shot AI.
- Cadence target: frequent posting, up to 30/day on peak days.
- Platform: X/Twitter first, crop-friendly to 9:16 where possible.

- (2026-04-19) $MOTION is a curation brand, not a shoot brand. 20/20 analyzed videos so far are CURATED existing footage (Hollywood film stills, wildlife docs, news archives, luxury retail b-roll, broadcast sports, pop-culture IP) with typographic branding applied on top. The editor (handle: stayblessed) picks footage that reads as WEALTH/POWER/SPEED/MYTHIC and matches serif typography to prestige pieces, bold geometric sans to action/energy pieces, italic script cursive to tokenomics/utility messages.
## Voice & Tone
<!-- Fill as patterns emerge. Examples below are placeholders. -->
- Irony: 0.7 (leans ironic, not earnest)
- Aggression: 0.4 (pointed, not hostile)
- Sophistication: 0.6 (reads literate, still meme-literate)
- Do: specificity, insider references, dry punchlines
- Don't: generic crypto talk, "gm fam", emojis as punctuation, hashtag spam

## Visual DNA
<!-- Lock this in as you see what works. -->
- Preferred palettes: [fill]
- Preferred lighting: [fill — e.g. hard directional, golden hour, neon night]
- Film stock / lens cues: [fill — e.g. 35mm anamorphic, Portra 400, Ektachrome]
- Avoid: "cinematic" as a word in prompts (meaningless), soft-focus glow, CGI-plastic skin

- (2026-04-19) time_of_day: night (dominant, 15/50 refs)
- (2026-04-19) weather: indoor (dominant, 20/50 refs)
- (2026-04-19) Typography taxonomy: (a) Serif Didot/Bodoni "$MOTION" = default brand title, prestige pieces; (b) Bold geometric sans "$MOTION" (slanted/italic for speed) = energy/action pieces; (c) Italic script cursive (e.g. "25% locked") = tokenomics/utility data. Different messages ride different fonts deliberately.
- (2026-04-19) Heavy B&W bias: ~40-50% of pieces run pure monochrome, usually with crushed blacks and preserved highlights. Color pieces tend toward warm tungsten + cool neon mix (clubs, cars at dusk), or warm amber (Hollywood stills, golden hour). Editor rarely uses naturalistic daylight color.
- (2026-04-19) Aspect handling: operator accepts whatever aspect the source is (16:9 / 4:3 / 1:1 / 9:16) and either lets it run native OR letterboxes wider sources onto a vertical 9:16 canvas. The letterbox-on-vertical move is a recurring signature — cinematic crop inside a phone frame.
- (2026-04-19) Collage grid format: 6-panel (3x2) B&W montage used when narrative needs multiple simultaneous luxury vignettes (gala / Porsche / estate / private jet). Serif text runs horizontally across the middle. This is the editor's "anthology" layout.
- (2026-04-19) Predator iconography canonized: lion, shark, hyena, and likely wolves/sharks recur. Wildlife-doc footage treated as sacred — always gets clean serif brand treatment (not kinetic sans). When predator imagery appears, the editor does NOT apply the usual grain/degradation filter.
- (2026-04-19) weather: indoor (dominant, 90/235 refs)
## Proven Prompt Patterns
<!-- Append real winners here as they happen. -->
- (empty — will grow)

- (2026-04-18) "win" — (marked winner) [winner]
- (2026-04-18) "win" — (marked winner) [winner]
- (2026-04-18) "win" — (marked winner) [winner]
- (2026-04-18) "win" — (marked winner) [winner]
- (2026-04-18) "win" — (marked winner) [winner]
- (2026-04-18) "win" — (marked winner) [winner]
- (2026-04-18) "win" — (marked winner) [winner]
- (2026-04-18) "win" — (marked winner) [winner]
- (2026-04-18) "win" — (marked winner) [winner]
- (2026-04-18) "win" — (marked winner) [winner]
- (2026-04-18) "win" — (marked winner) [winner]
- (2026-04-18) "win" — (marked winner) [winner]
- (2026-04-19) "win" — (marked winner) [winner]
- (2026-04-19) "win" — (marked winner) [winner]
- (2026-04-19) "win" — (marked winner) [winner]
- (2026-04-19) "win" — (marked winner) [winner]
- (2026-04-19) "win" — (marked winner) [winner]
- (2026-04-19) "win" — (marked winner) [winner]
- (2026-04-19) "win" — (marked winner) [winner]
- (2026-04-19) "win" — (marked winner) [winner]
- (2026-04-19) "win" — (marked winner) [winner]
- (2026-04-19) "win" — (marked winner) [winner]
- (2026-04-19) "win" — (marked winner) [winner]
- (2026-04-19) "win" — (marked winner) [winner]
- (2026-04-19) "win" — (marked winner) [winner]
- (2026-04-19) "win" — (marked winner) [winner]
- (2026-04-19) Default serif brand treatment: "$MOTION" in Didot/Bodoni-style serif, white fill, centered-middle placement, size ~1/8 to 1/6 of frame width. Works across 80% of pieces.
- (2026-04-19) Typography taxonomy by register: (a) Serif centered = prestige / cinematic / curated; (b) Bold geometric sans = energy / action / sports / speed; (c) Italic sans with motion-blur treatment = velocity / cars; (d) Italic script cursive = tokenomics statements (e.g. "25% locked"); (e) Retro Art-Deco striped sans = cartel-scale wealth; (f) Semi-transparent serif (no $ prefix) = ambient / atmospheric pieces; (g) Bold sans + emoji = comedy / shitposting.
## Proven Model Routing (Grok)
- Text-on-image memes → Grok Imagine with Ideogram/Aurora selection
- Character consistency across multi-panel → Nano Banana via Grok
- Photoreal portrait/product → Aurora or Flux via Grok
- Short motion → Grok Imagine video mode

- (2026-04-19) Operator observation: editor almost never ORIGINATES footage — they CURATE. For a generative analog, Grok Imagine / img2vid can recreate the iconography (lions, sharks, hooded figures, Porsche GT3 interiors, luxury hangar scenes) when licensing/sourcing of archival clips is not available. The brand look is more about the TYPOGRAPHIC OVERLAY + B&W grade than the underlying footage.
## Kill List
<!-- Things that don't land. Update after flops. -->
- (empty)

- (2026-04-19) Avoid crisp, brand-new digital look — the $MOTION canon is heavily GRAIN-FORWARD / degraded / archival. Avoid saturated color unless source is a Hollywood still (War Dogs / Scarface / Dark Knight) — default grade is B&W or near-monochrome.
- (2026-04-19) Avoid generic crypto imagery: laser eyes, gold coins, moon rockets, cyberpunk neon skylines. The $MOTION brand reads as PRESTIGE ICONOGRAPHY transplanted onto a token, not as meme-crypto shitcoin visual language.
## Recurring Subjects / Characters
<!-- If a character or motif is central (e.g. Kilroy, a self-avatar, etc.), pin it here. -->
- (empty)

- (2026-04-19) Multi-editor collective: $MOTION is a community brand, not a single creator. Identified signature marks so far — stayblessed (stylized pop-IP + halftone treatments), auvirox (symmetrical car-centric exteriors), white boy motion (varsity-badge UGC/phone content), alexandro.fx (film-still single-subject crops), plus a "4F" mark and footer. Each contributor rides the same brand typography but has a distinct subject register.
- (2026-04-19) Film canon identified across 47 videos: Scarface (1983), The Dark Knight (2008), War Dogs (2016), American Psycho (2000), Casino (1995) / De Niro, The Sopranos / Paulie, Star Wars (Darth Maul + Darth Vader + Luke Skywalker), Enter the Dragon era Bruce Lee. Pattern: crime/finance/noir films + mythic sci-fi + martial-arts prestige. Not sampled: romantic comedies, dramas, action blockbusters, superhero films outside Nolan Batman.
- (2026-04-19) Celebrity-archival imagery: Tupac Shakur, young Donald Trump, plus one talk-show style young subject (unidentified). Pattern: subjects framed as individuals who embody market/cultural power at a past moment.
## Core Patterns
- (2026-04-19) lens: 200mm+ telephoto (wildlife) (×5)
- (2026-04-19) lens: 35mm wide-angle handheld (×5)
- (2026-04-19) lens: 85mm-135mm telephoto compression (×5)
- (2026-04-19) lens: 100mm macro close-up (×5)
- (2026-04-19) lens: 85mm f/2 compressed (movie lens) (×5)
- (2026-04-19) lens: 35mm handheld, close distance (×5)
- (2026-04-19) lens: 50mm standard news-documentary (×5)
- (2026-04-19) lens: 35mm candid street (×5)
- (2026-04-19) lens: 35mm handheld zoom, news-style (×5)
- (2026-04-19) lens: 50mm close-up, tight crop (×5)
- (2026-04-19) film_stock: degraded broadcast video, vhs-grade grain overlay (×5)
- (2026-04-19) film_stock: iphone / phone video, warm color cast (×5)
- (2026-04-19) film_stock: black-and-white film emulation, high-contrast (×5)
- (2026-04-19) film_stock: black-and-white degraded broadcast, coarse grain (×5)
- (2026-04-19) film_stock: arri digital cinema, filmic grade (×5)
- (2026-04-19) film_stock: low-light phone video, heavy chromatic aberration visible at edges (×5)
- (2026-04-19) film_stock: archival b&w news photograph (×5)
- (2026-04-19) film_stock: phone video with color grade, slight film emulation (×5)
- (2026-04-19) film_stock: 70s-era film stock, faded, slight color wash, soft focus (×5)
- (2026-04-19) film_stock: b&w digital, deep blacks, studio-clean (×5)
- (2026-04-19) lighting: natural daylight, high sun from upper-left (×5)
- (2026-04-19) lighting: warm tungsten interior practical, dim, low-key (×5)
- (2026-04-19) lighting: natural overcast daylight, flat ambient (×5)
- (2026-04-19) lighting: ambient, backlit from lcd screen (×5)
- (2026-04-19) lighting: golden hour low-sun, strong warm rim light from behind (×5)
- (2026-04-19) lighting: dark dim interior, bottom-up white fill from off-frame surface (possibly a white-lit countertop) (×5)
- (2026-04-19) lighting: hard overhead daylight, deep shadows (×5)
- (2026-04-19) lighting: warm practical window light from lv storefront, exterior sodium + tungsten mix (×5)
- (2026-04-19) lighting: strong backlight, near-silhouette, haze (×5)
- (2026-04-19) lighting: single hard top-light, engine bay glint, studio product-shot feel (×5)
- (2026-04-19) time_of_day: night (×15)
- (2026-04-19) time_of_day: afternoon (×5)
- (2026-04-19) time_of_day: daytime, overcast (×5)
- (2026-04-19) time_of_day: indoor (×5)
- (2026-04-19) time_of_day: golden hour, late afternoon (×5)
- (2026-04-19) time_of_day: daytime (×5)
- (2026-04-19) time_of_day: daytime, bright sun behind subject (×5)
- (2026-04-19) time_of_day: indoor studio (×5)
- (2026-04-19) weather: indoor (×20)
- (2026-04-19) weather: clear, dry savanna (×5)
- (2026-04-19) weather: overcast, dry pavement (×5)
- (2026-04-19) weather: clear, dust hazy (×5)
- (2026-04-19) weather: clear (×5)
- (2026-04-19) weather: clear, dry (×5)
- (2026-04-19) weather: hazy/warm (×5)
- (2026-04-19) composition: rule of thirds, lion lower-center, hyena motion-blur upper-left, letterboxed cinematic crop on 9:16 canvas, serif text overlay centered (×5)
- (2026-04-19) composition: pov top-down, hands holding fanned bills center-frame, vertical 9:16, diamond watches flanking, chain zipper exiting bottom-frame, serif text overlay centered (×5)
- (2026-04-19) composition: wide lockoff, car centered, massive tire-smoke plume filling frame, 16:9 landscape source letterboxed, bold geometric sans 'motion' text overlay (×5)
- (2026-04-19) composition: extreme close-up on money-counter lcd reading '83 $8300', machine dead-centered vertical, bills in partial motion-blur below, serif text overlay centered (×5)
- (2026-04-19) composition: medium two-shot, two men walking toward camera with duffel bag, 16:9 landscape, impact-style bold sans overlay centered (×5)
- (2026-04-19) composition: centered medium of solo subject, 1:1 square crop, serif text overlay centered blocking the chest (×5)
- (2026-04-19) composition: centered tank with lone figure standing in its path, tall skyline as backdrop, vertical crop of archival horizontal photo, serif text overlay centered (×5)
- (2026-04-19) composition: centered medium wide, woman in lace bodysuit + boots walking toward camera, lv storefront as backdrop with open door glow, chubby man in black tee crossing left foreground, triple-stacked $motion sans text bottom-center (×5)
- (2026-04-19) composition: medium close-up 3/4 profile of subject, crowd silhouettes behind, italic script cursive overlay '25% locked' centered (×5)
- (2026-04-19) composition: centered symmetrical head-on of engine, 4:3 aspect, serif text overlay centered on intake manifold (×5)
- (2026-04-19) color_palette: muted earth tones, desaturated greens and warm browns, heavy grain (×5)
- (2026-04-19) color_palette: warm tungsten orange, deep shadow blacks, crushed blacks (×5)
- (2026-04-19) color_palette: pure b&w, crushed blacks, white smoke dominant (×5)
- (2026-04-19) color_palette: pure b&w, lcd green tint remapped to grayscale (×5)
- (2026-04-19) color_palette: warm amber-gold saturation, teal shadows (filmic teal-orange), preserved skin tones (×5)
- (2026-04-19) color_palette: saturated red from shirt against near-black surroundings, muted skin, crushed blacks (×5)
- (2026-04-19) color_palette: pure b&w, high contrast, deep blacks (×5)
- (2026-04-19) color_palette: warm storefront interior glow + cool exterior, amber-teal mix, muted blacks, selective warmth on lv window (×5)
- (2026-04-19) color_palette: faded warm pastels, washed highlights, peach skin tones, low contrast (×5)
- (2026-04-19) color_palette: pure b&w, high contrast, silver highlights, pure black shadow (×5)
- (2026-04-19) mood: monumental nature-documentary gravitas (×5)
- (2026-04-19) mood: flex, luxury, wealth-display (×5)
- (2026-04-19) mood: raw speed, menace, hype (×5)
- (2026-04-19) mood: bureaucratic wealth, transactional gravity (×5)
- (2026-04-19) mood: cool, transactional, prestige (×5)
- (2026-04-19) mood: quiet tension, caught-in-action (×5)
- (2026-04-19) mood: historical gravitas, iconic resistance (×5)
- (2026-04-19) mood: luxury, aspirational, night-out (×5)
- (2026-04-19) mood: nostalgic, dandy-coded, period-piece prestige (×5)
- (2026-04-19) mood: mechanical prestige, horsepower-as-character (×5)
- (2026-04-19) location_type: african savanna, tall grass (×5)
- (2026-04-19) location_type: dim interior, possibly hotel bed or private room (×5)
- (2026-04-19) location_type: drag strip or private lot, crowd onlookers (×5)
- (2026-04-19) location_type: close-up product shot, context-free (×5)
- (2026-04-19) location_type: military airfield tarmac (×5)
- (2026-04-19) location_type: dim basement or warehouse, exposed ceiling structure (×5)
- (2026-04-19) location_type: city boulevard, military column context (×5)
- (2026-04-19) location_type: luxury retail street, louis vuitton storefront, european-style architecture (×5)
- (2026-04-19) location_type: outdoor event / crowd scene, period footage (×5)
- (2026-04-19) location_type: studio product-shot, car opened (×5)

- (2026-04-19) lens: 50mm-85mm movie lens (×15)
- (2026-04-19) lens: 50mm movie lens (×15)
- (2026-04-19) lens: 200mm+ telephoto (wildlife) (×5)
- (2026-04-19) lens: 35mm wide-angle handheld (×5)
- (2026-04-19) lens: 85mm-135mm telephoto compression (×5)
- (2026-04-19) lens: 100mm macro close-up (×5)
- (2026-04-19) lens: 85mm f/2 compressed (movie lens) (×5)
- (2026-04-19) lens: 35mm handheld, close distance (×5)
- (2026-04-19) lens: 50mm standard news-documentary (×5)
- (2026-04-19) lens: 35mm candid street (×5)
- (2026-04-19) lens: 35mm handheld zoom, news-style (×5)
- (2026-04-19) lens: 50mm close-up, tight crop (×5)
- (2026-04-19) lens: 35mm phone interior (×5)
- (2026-04-19) lens: 50mm-85mm standard movie lens (×5)
- (2026-04-19) lens: phone handheld, 35mm equivalent, shaky (×5)
- (2026-04-19) lens: wide 24mm phone selfie / pov rig (×5)
- (2026-04-19) lens: 35mm-50mm from balcony or mid-distance (×5)
- (2026-04-19) lens: 35mm handheld club-interior (×5)
- (2026-04-19) lens: broadcast lens (tele) from nfl stadium (×5)
- (2026-04-19) lens: 35mm phone or mirrorless wide (×5)
- (2026-04-19) lens: 50mm close-up on character (×5)
- (2026-04-19) lens: mixed (collage of multiple source clips) (×5)
- (2026-04-19) lens: 35mm wide at dusk (×5)
- (2026-04-19) lens: broadcast 50mm, talk-show standard (×5)
- (2026-04-19) lens: phone selfie wide, close distance (×5)
- (2026-04-19) lens: 200mm+ sports telephoto (×5)
- (2026-04-19) lens: 50mm cinematic, slight telephoto feel (×5)
- (2026-04-19) lens: underwater wide 24-35mm with housing (×5)
- (2026-04-19) lens: 24-35mm wide from balcony (×5)
- (2026-04-19) lens: phone handheld, compressed lossy (×5)
- (2026-04-19) lens: 50mm movie lens, slight motion blur (×5)
- (2026-04-19) lens: 70-200mm telephoto, sports-style (×5)
- (2026-04-19) lens: 35-50mm prime (×5)
- (2026-04-19) lens: 24-35mm low-angle wide (×5)
- (2026-04-19) lens: 24-35mm wide interior (×5)
- (2026-04-19) lens: 85mm studio portrait (×5)
- (2026-04-19) lens: broadcast wide, ringside (×5)
- (2026-04-19) lens: 50mm press camera (×5)
- (2026-04-19) lens: phone close-up (×5)
- (2026-04-19) lens: 50mm cinema, shallow dof (×5)
- (2026-04-19) lens: composited — car photo + galaxy background (×5)
- (2026-04-19) lens: phone handheld, close (×5)
- (2026-04-19) lens: 85mm+ shallow-dof telephoto (×5)
- (2026-04-19) film_stock: degraded broadcast video, vhs-grade grain overlay (×5)
- (2026-04-19) film_stock: iphone / phone video, warm color cast (×5)
- (2026-04-19) film_stock: black-and-white film emulation, high-contrast (×5)
- (2026-04-19) film_stock: black-and-white degraded broadcast, coarse grain (×5)
- (2026-04-19) film_stock: arri digital cinema, filmic grade (×5)
- (2026-04-19) film_stock: low-light phone video, heavy chromatic aberration visible at edges (×5)
- (2026-04-19) film_stock: archival b&w news photograph (×5)
- (2026-04-19) film_stock: phone video with color grade, slight film emulation (×5)
- (2026-04-19) film_stock: 70s-era film stock, faded, slight color wash, soft focus (×5)
- (2026-04-19) film_stock: b&w digital, deep blacks, studio-clean (×5)
- (2026-04-19) film_stock: b&w digital, medium grain (×5)
- (2026-04-19) film_stock: 1980s film stock (scarface, 1983), warm saturation (×5)
- (2026-04-19) film_stock: cell phone video, lo-fi, compression artifacts (×5)
- (2026-04-19) film_stock: digital phone, warm hdr (×5)
- (2026-04-19) film_stock: b&w digital, bleached high-key (×5)
- (2026-04-19) film_stock: phone video in low-light, heavy noise + halation (×5)
- (2026-04-19) film_stock: broadcast hd digital (×5)
- (2026-04-19) film_stock: b&w film emulation, soft grain (×5)
- (2026-04-19) film_stock: clean digital, clinical tones (×5)
- (2026-04-19) film_stock: degraded broadcast + halftone dot overlay (retro newsprint treatment) (×5)
- (2026-04-19) film_stock: b&w digital composite across multiple sources (×5)
- (2026-04-19) film_stock: digital, cool tint, filmic fall-off (×5)
- (2026-04-19) film_stock: b&w digital, soft grain, clean mid-tones (×5)
- (2026-04-19) film_stock: b&w lo-fi phone video, grainy in shadow (×5)
- (2026-04-19) film_stock: digital action cam / dslr, clean color (×5)
- (2026-04-19) film_stock: digital cinema, filmic roll-off, heavy atmospheric haze (×5)
- (2026-04-19) film_stock: digital clean (×5)
- (2026-04-19) film_stock: digital, cool overcast grade (×5)
- (2026-04-19) film_stock: heavily compressed phone video, visible noise + chroma degradation (×5)
- (2026-04-19) film_stock: 1983 star wars film stock, warm/muted (×5)
- (2026-04-19) film_stock: 1990s film stock, heavy grain, b&w emulation (×5)
- (2026-04-19) film_stock: b&w digital, strong grain (×5)
- (2026-04-19) film_stock: 2000s digital cinema, saturated warm grade (×5)
- (2026-04-19) film_stock: digital, saturated color (×5)
- (2026-04-19) film_stock: b&w hbo-series digital, soft mid-tones (×5)
- (2026-04-19) film_stock: b&w digital, soft film emulation (×5)
- (2026-04-19) film_stock: b&w digital, clean (×5)
- (2026-04-19) film_stock: christopher nolan digital cinema (dark knight era), warm amber grade (×5)
- (2026-04-19) film_stock: 1990s b&w film stock, heavy filmic grain (×5)
- (2026-04-19) film_stock: b&w broadcast emulation, heavy grain (×5)
- (2026-04-19) film_stock: 1980s-90s b&w archival press photo, heavy grain + motion (×5)
- (2026-04-19) film_stock: b&w iphone video, slight motion blur (×5)
- (2026-04-19) film_stock: star wars film stock, heavy grain + degradation (×5)
- (2026-04-19) film_stock: digital composite (×5)
- (2026-04-19) film_stock: 1970s hong kong martial-arts film stock, warm grade, period grain (×5)
- (2026-04-19) film_stock: lo-fi phone video + photoshop collage (×5)
- (2026-04-19) film_stock: b&w cinema, heavy bokeh (×5)
- (2026-04-19) lighting: natural daylight, high sun from upper-left (×5)
- (2026-04-19) lighting: warm tungsten interior practical, dim, low-key (×5)
- (2026-04-19) lighting: natural overcast daylight, flat ambient (×5)
- (2026-04-19) lighting: ambient, backlit from lcd screen (×5)
- (2026-04-19) lighting: golden hour low-sun, strong warm rim light from behind (×5)
- (2026-04-19) lighting: dark dim interior, bottom-up white fill from off-frame surface (possibly a white-lit countertop) (×5)
- (2026-04-19) lighting: hard overhead daylight, deep shadows (×5)
- (2026-04-19) lighting: warm practical window light from lv storefront, exterior sodium + tungsten mix (×5)
- (2026-04-19) lighting: strong backlight, near-silhouette, haze (×5)
- (2026-04-19) lighting: single hard top-light, engine bay glint, studio product-shot feel (×5)
- (2026-04-19) lighting: ambient car interior, light from tinted windows (×5)
- (2026-04-19) lighting: bright midday miami sun, warm highlights (×5)
- (2026-04-19) lighting: very dim interior, warm tungsten spot fill, shadows dominate (×5)
- (2026-04-19) lighting: blue-hour sky exterior + warm dashboard instrument glow (×5)
- (2026-04-19) lighting: bright overhead sun, flat exposure, sky blown out (×5)
- (2026-04-19) lighting: multi-color stage gels (pink/purple/yellow), haze from fog machine (×5)
- (2026-04-19) lighting: bright stadium daylight, slightly overcast (×5)
- (2026-04-19) lighting: warm window daylight from left, soft diffusion (×5)
- (2026-04-19) lighting: overhead cleanroom fluorescents, flat cool light (×5)
- (2026-04-19) lighting: edge-lit from red saber glow + deep shadow (×5)
- (2026-04-19) lighting: mixed — gala stage, tarmac daylight, villa dusk, garage fluorescent (×5)
- (2026-04-19) lighting: blue-hour ambient + warm practical from hangar strip (×5)
- (2026-04-19) lighting: talk-show interior warm key + skyline window fill, soft diffusion (×5)
- (2026-04-19) lighting: ceiling room-light overhead, slight backlight from doorway (×5)
- (2026-04-19) lighting: direct overhead sun, hard highlights on wave crest (×5)
- (2026-04-19) lighting: strong volumetric backlight from doorway, heavy haze/fog revealing light beams (×5)
- (2026-04-19) lighting: bright surface sunlight penetrating shallow water (×5)
- (2026-04-19) lighting: overcast daylight, flat soft (×5)
- (2026-04-19) lighting: twilight dusk ambient, cool overall (×5)
- (2026-04-19) lighting: low-key theatrical, shadow side dominant, red glow from unseen source (lightsaber) (×5)
- (2026-04-19) lighting: warm natural, key from camera-right (×5)
- (2026-04-19) lighting: bright overhead summer sun, overcast soft top-light (×5)
- (2026-04-19) lighting: warm tungsten office practical, window streaks (×5)
- (2026-04-19) lighting: overcast daylight, soft ambient (×5)
- (2026-04-19) lighting: warm interior practical, diffused (×5)
- (2026-04-19) lighting: overhead hangar can-lights + exterior overcast (×5)
- (2026-04-19) lighting: even softbox key + fill, studio cyc background (×5)
- (2026-04-19) lighting: warm opera-house chandeliers + practical wall sconces, soft fill (×5)
- (2026-04-19) lighting: overhead ambient + practical, slight rim from window (×5)
- (2026-04-19) lighting: stadium spotlight overhead (×5)
- (2026-04-19) lighting: harsh press-flash front, deep shadow behind (×5)
- (2026-04-19) lighting: low ambient interior, near top-down (×5)
- (2026-04-19) lighting: minimal, key from red lightsaber + distant backlight, near-total shadow (×5)
- (2026-04-19) lighting: composite — car lit by implied hard directional + starfield background (×5)
- (2026-04-19) lighting: warm key from camera-left, heavy shadow right, brick-wall backdrop (×5)
- (2026-04-19) lighting: outdoor overcast daylight (×5)
- (2026-04-19) lighting: bright practical bokeh from storefront or nightclub, window backlight (×5)
- (2026-04-19) time_of_day: night (×20)
- (2026-04-19) time_of_day: midday (×20)
- (2026-04-19) time_of_day: daytime interior (×20)
- (2026-04-19) time_of_day: daytime, overcast (×15)
- (2026-04-19) time_of_day: daytime (×10)
- (2026-04-19) time_of_day: stylized indoor (×10)
- (2026-04-19) time_of_day: afternoon (×5)
- (2026-04-19) time_of_day: indoor (×5)
- (2026-04-19) time_of_day: golden hour, late afternoon (×5)
- (2026-04-19) time_of_day: daytime, bright sun behind subject (×5)
- (2026-04-19) time_of_day: indoor studio (×5)
- (2026-04-19) time_of_day: daytime, inside car (×5)
- (2026-04-19) time_of_day: daytime, bright sun, slight haze (×5)
- (2026-04-19) time_of_day: night, interior (×5)
- (2026-04-19) time_of_day: blue hour / dusk (×5)
- (2026-04-19) time_of_day: daytime nfl game (×5)
- (2026-04-19) time_of_day: indoor facility (×5)
- (2026-04-19) time_of_day: stylized / indoor cinematic (×5)
- (2026-04-19) time_of_day: mixed (×5)
- (2026-04-19) time_of_day: dusk / blue hour (×5)
- (2026-04-19) time_of_day: night (skyline visible) (×5)
- (2026-04-19) time_of_day: night / late (×5)
- (2026-04-19) time_of_day: dusk (×5)
- (2026-04-19) time_of_day: stylized interior (×5)
- (2026-04-19) time_of_day: daytime indoor (×5)
- (2026-04-19) time_of_day: studio (×5)
- (2026-04-19) time_of_day: night event (×5)
- (2026-04-19) time_of_day: daytime formal event (×5)
- (2026-04-19) time_of_day: indoor arena (×5)
- (2026-04-19) time_of_day: event, evening (×5)
- (2026-04-19) time_of_day: indoor, night probably (×5)
- (2026-04-19) time_of_day: stylized/cosmic (×5)
- (2026-04-19) time_of_day: indoor fight scene (×5)
- (2026-04-19) time_of_day: night / dusk (×5)
- (2026-04-19) weather: indoor (×90)
- (2026-04-19) weather: clear (×10)
- (2026-04-19) weather: overcast (×10)
- (2026-04-19) weather: clear, dry savanna (×5)
- (2026-04-19) weather: overcast, dry pavement (×5)
- (2026-04-19) weather: clear, dust hazy (×5)
- (2026-04-19) weather: clear, dry (×5)
- (2026-04-19) weather: hazy/warm (×5)
- (2026-04-19) weather: clear, hot, beachside (×5)
- (2026-04-19) weather: clear, light haze (×5)
- (2026-04-19) weather: hazy sunny (×5)
- (2026-04-19) weather: indoor club (×5)
- (2026-04-19) weather: clear, outdoor stadium (×5)
- (2026-04-19) weather: mixed (×5)
- (2026-04-19) weather: clear, sunny, offshore spray (×5)
- (2026-04-19) weather: indoor, heavy atmospheric haze (×5)
- (2026-04-19) weather: clear tropical (×5)
- (2026-04-19) weather: overcast, misty mountain (×5)
- (2026-04-19) weather: outdoor, cool (×5)
- (2026-04-19) weather: summer warm, outdoor (×5)
- (2026-04-19) weather: indoor office (×5)
- (2026-04-19) weather: indoor / hangar (×5)
- (2026-04-19) weather: indoor studio (×5)
- (2026-04-19) weather: indoor gala (×5)
- (2026-04-19) weather: indoor event (×5)
- (2026-04-19) weather: n/a cosmic (×5)
- (2026-04-19) weather: outdoor urban (×5)
- (2026-04-19) composition: rule of thirds, lion lower-center, hyena motion-blur upper-left, letterboxed cinematic crop on 9:16 canvas, serif text overlay centered (×5)
- (2026-04-19) composition: pov top-down, hands holding fanned bills center-frame, vertical 9:16, diamond watches flanking, chain zipper exiting bottom-frame, serif text overlay centered (×5)
- (2026-04-19) composition: wide lockoff, car centered, massive tire-smoke plume filling frame, 16:9 landscape source letterboxed, bold geometric sans 'motion' text overlay (×5)
- (2026-04-19) composition: extreme close-up on money-counter lcd reading '83 $8300', machine dead-centered vertical, bills in partial motion-blur below, serif text overlay centered (×5)
- (2026-04-19) composition: medium two-shot, two men walking toward camera with duffel bag, 16:9 landscape, impact-style bold sans overlay centered (×5)
- (2026-04-19) composition: centered medium of solo subject, 1:1 square crop, serif text overlay centered blocking the chest (×5)
- (2026-04-19) composition: centered tank with lone figure standing in its path, tall skyline as backdrop, vertical crop of archival horizontal photo, serif text overlay centered (×5)
- (2026-04-19) composition: centered medium wide, woman in lace bodysuit + boots walking toward camera, lv storefront as backdrop with open door glow, chubby man in black tee crossing left foreground, triple-stacked $motion sans text bottom-center (×5)
- (2026-04-19) composition: medium close-up 3/4 profile of subject, crowd silhouettes behind, italic script cursive overlay '25% locked' centered (×5)
- (2026-04-19) composition: centered symmetrical head-on of engine, 4:3 aspect, serif text overlay centered on intake manifold (×5)
- (2026-04-19) composition: top-down / 3/4 over-head looking into rear seat, bengal cat center-left, palm angels pillow upper-right, stacks of us bills flanking, vertical 9:16, serif text overlay centered (×5)
- (2026-04-19) composition: medium-wide crowd shot, pacino center with sunglasses, polo-shirt companion left, couple right, palm trees as backdrop, 1:1 square crop, serif text overlay centered (×5)
- (2026-04-19) composition: letterboxed bars top+bottom on vertical canvas, subject sprawled on floor centered, upturned paper/cards strewn nearby, bold geometric sans 'motion' overlay bottom-third (×5)
- (2026-04-19) composition: first-person pov through windshield, porsche steering wheel dominant lower-frame (crest visible), mountain road curving ahead, 9:16 vertical, italicized bold sans $motion overlay with motion-blur treatment (×5)
- (2026-04-19) composition: horizon-heavy split, sky upper 2/3 blank, beach+villas middle band, walkway foreground, 9:16 vertical, serif text overlay in center upper third (unusual placement for this editor) (×5)
- (2026-04-19) composition: smoke-dominated wash, bottle with sparkler in mid-frame (obscured), neon led geometry upper-left, serif text overlay centered (×5)
- (2026-04-19) composition: downfield view with players mid-play, yellow field markings foreground, lower-third broadcast scoreboard and ticker, bold sans 'motion' text overlay superimposed on field (×5)
- (2026-04-19) composition: medium close-up centered, subject 3/4 to camera mid-laugh, rotary phone handset held to ear, drapes left, 16:9 landscape, serif text overlay centered (×5)
- (2026-04-19) composition: diagonal leading line of glove-box isolator row foreground, workers in white coverall ppe receding mid-frame, 9:16 vertical, bold sans $motion overlay centered (×5)
- (2026-04-19) composition: centered darth maul at 3/4, diagonal lightsaber slash dominant across frame, serif text overlay centered, small footer credit '©2025 stayblessed copyright reserved' (×5)
- (2026-04-19) composition: 6-panel collage grid (3 wide x 2 tall) layout on 16:9 canvas, each cell a different luxury/prestige clip: gala crowd, porsche interior, porsche wheel, estate driveway with cayenne, woman in fur entering suv, fur-coated woman descending steps from private jet. serif '$motion' overlay centered across the middle (×5)
- (2026-04-19) composition: centered front 3/4 of two rolls royces parked at hangar-style warehouse, symmetrical composition with black rolls left and white rolls spectre right, vertical 9:16, serif text overlay centered with footer credit 'auvirox' (×5)
- (2026-04-19) composition: medium 3/4 of young man laughing and gesturing, sitting at talk-show desk with mic and monster energy can, city skyline photo as backdrop left, potted plant right, bold geometric sans 'motion' text bleeding off left edge, '4f' footer logo (×5)
- (2026-04-19) composition: medium close-up of a bearded man in hoodie sitting on a bed, 3/4 to camera, bedroom interior with closet and bed visible behind, 16:9 landscape, college-varsity-style outlined badge 'white boy motion' bottom-right (×5)
- (2026-04-19) composition: medium-wide 16:9, surfer carving centered in wave face, massive whitewater spray filling frame behind and above, serif text overlay centered (×5)
- (2026-04-19) composition: centered silhouette of figure walking away down a corridor into bright doorway, volumetric god-rays spilling out, 4:5 portrait, serif text overlay centered on subject (×5)
- (2026-04-19) composition: underwater medium shot, bull shark swimming laterally across mid-frame, white sand bottom filling lower third, clear blue water upper 2/3, conch shell foreground anchor, 16:9 landscape, serif text overlay centered (×5)
- (2026-04-19) composition: vertical 9:16, infinity-pool loungers foreground, bay + skyline mid-ground with monte carlo skyscrapers, mountains in haze upper-third, dark-navy serif text overlay (not white!) centered (×5)
- (2026-04-19) composition: medium shot of larger man in black tee + cap walking across parking lot, car beside him left, emoji-style red-outline '$$$' money-bag graphic stacked vertically center-left, triple-stacked rhythmic placement, vertical 9:16 letterboxed (×5)
- (2026-04-19) composition: centered medium close-up of character with helmeted darth vader reflected in background, 1:1 square crop, serif text overlay centered on subject's chest area, footer credit 'alexandro.fx' (×5)
- (2026-04-19) composition: medium close-up of subject laughing, head tilted, aviator glasses, 9:16 vertical with letterbox, serif centered lower-third (×5)
- (2026-04-19) composition: medium shot subject mid-air arcing backward off cliff, 1:1 square, trees below, serif overlay centered across the subject's body (×5)
- (2026-04-19) composition: medium two-shot, christian bale centered with arm outstretched, willem dafoe right smirking, 9:16 letterboxed vertical from 16:9 source, bold italic-sans '$motion' overlay centered (×5)
- (2026-04-19) composition: low-angle canted 3/4 of two subjects walking past camera, pistons varsity jacket (blue + red 'pis') dominant, second figure in black puffer behind, brick building backdrop, vertical 9:16, serif text overlay centered across chest (×5)
- (2026-04-19) composition: medium close-up of subject mid-laugh, older man in background unfocused left, 16:9 landscape, helvetica bold sans '$motion' lower-frame (×5)
- (2026-04-19) composition: wide 3/4 of porsche 911 gt3 rs with open frunk full of rose bouquets + petals on floor, man in leather jacket loading bouquets, woman right with black tote looking, second woman left, private jet partially visible behind, vertical 9:16, serif $motion centered (×5)
- (2026-04-19) composition: medium wide of subject on seamless white background, gesturing with both arms raised, slight 3/4 to camera, 1:1 square, italic serif $motion overlay centered on chest (×5)
- (2026-04-19) composition: medium two-shot, bruce wayne stage-right looking past camera, blonde woman stage-left in dark gown, opera-lobby backdrop with chandeliers, 16:9 landscape (×5)
- (2026-04-19) composition: medium close-up of older man at table with fork in hand, tie, suit, crowd behind unfocused, 16:9 landscape, serif $motion centered on upper chest (×5)
- (2026-04-19) composition: wide medium-high from floor, wrestler mid-air off top-rope diving onto opponent laying on floor, crowd in background, 1:1 square, serif $motion overlay centered across mid-frame (×5)
- (2026-04-19) composition: 1:1 square, centered tight close-up of subject looking past camera with microphone cord visible over shoulder, dark blazer + white shirt + tie, serif $motion overlay centered, footer credit '69mari069' (×5)
- (2026-04-19) composition: extreme close-up diagonal of vacuum-sealed bricks of $100 bills, stack rotating/falling through frame, vertical 9:16, retro-sans (art-deco style) '$motion' overlay with vertical-stripe fill effect, centered (×5)
- (2026-04-19) composition: centered full-body of darth vader in corridor with red lightsaber ignited at an angle, 9:16 letterboxed vertical, serif $motion overlay centered, 'puncs' subtle footer (×5)
- (2026-04-19) composition: front 3/4 of black bugatti chiron suspended on a galactic/starfield background, 9:16 vertical, italic sans $motion overlapping the car mid-frame (×5)
- (2026-04-19) composition: medium close-up of shirtless martial artist in low fighting stance, looking over shoulder back at camera, 16:9 landscape from film source (×5)
- (2026-04-19) composition: medium shot of rooster walking on concrete driveway with motorcycle + rifle visibly photoshopped onto its body, 9:16 letterboxed vertical, bold italic sans '$motion' + three laughing-face emojis to the right (×5)
- (2026-04-19) composition: medium wide of crowd scene with foreground faces mostly in soft focus, bright bokeh orbs upper half, 16:9 landscape, semi-transparent serif 'motion' overlay centered (notably without the dollar sign prefix) (×5)
- (2026-04-19) color_palette: muted earth tones, desaturated greens and warm browns, heavy grain (×5)
- (2026-04-19) color_palette: warm tungsten orange, deep shadow blacks, crushed blacks (×5)
- (2026-04-19) color_palette: pure b&w, crushed blacks, white smoke dominant (×5)
- (2026-04-19) color_palette: pure b&w, lcd green tint remapped to grayscale (×5)
- (2026-04-19) color_palette: warm amber-gold saturation, teal shadows (filmic teal-orange), preserved skin tones (×5)
- (2026-04-19) color_palette: saturated red from shirt against near-black surroundings, muted skin, crushed blacks (×5)
- (2026-04-19) color_palette: pure b&w, high contrast, deep blacks (×5)
- (2026-04-19) color_palette: warm storefront interior glow + cool exterior, amber-teal mix, muted blacks, selective warmth on lv window (×5)
- (2026-04-19) color_palette: faded warm pastels, washed highlights, peach skin tones, low contrast (×5)
- (2026-04-19) color_palette: pure b&w, high contrast, silver highlights, pure black shadow (×5)
- (2026-04-19) color_palette: pure b&w, leather warm-gray mid-tones, crushed blacks (×5)
- (2026-04-19) color_palette: warm amber, saturated warm skin tones, teal sky, period-film look (×5)
- (2026-04-19) color_palette: peachy-nude skin against near-black floor, crushed blacks, low saturation (×5)
- (2026-04-19) color_palette: cool cobalt sky, yellow road-line accents, warm interior instrumentation (×5)
- (2026-04-19) color_palette: pure high-key b&w, crushed bright whites, near-black foliage (×5)
- (2026-04-19) color_palette: magenta + yellow + warm tungsten, heavy fog/haze softening everything (×5)
- (2026-04-19) color_palette: green field dominant, purple ravens uniforms, saturated broadcast palette (×5)
- (2026-04-19) color_palette: soft b&w, gentle mid-tones, lifted blacks, gentle highlight roll-off (×5)
- (2026-04-19) color_palette: cool white clinical, pale gray ppe, minor accent greens from ventilation ducts (×5)
- (2026-04-19) color_palette: pure b&w+red accent (duotone) with halftone dot pattern over the whole frame (×5)
- (2026-04-19) color_palette: pure b&w, high contrast, preserved mid-tones (×5)
- (2026-04-19) color_palette: cool steel blue dominant, warm corrugated-red hangar accent, crushed blacks (×5)
- (2026-04-19) color_palette: pure b&w, soft highlights, 80s-nostalgic mid-tones (×5)
- (2026-04-19) color_palette: b&w lo-fi, lifted blacks, blown whites, low contrast (×5)
- (2026-04-19) color_palette: saturated ocean blues + pure white spray + wetsuit black, high contrast (×5)
- (2026-04-19) color_palette: cool teal-blue monochrome with warm white light source, near-black foreground silhouette (×5)
- (2026-04-19) color_palette: bright saturated tropical blues + bone white sand + mid-gray shark, high-saturation daylight (×5)
- (2026-04-19) color_palette: cool muted grays + teal sea + dusty green foliage, low saturation (×5)
- (2026-04-19) color_palette: cold dusk blue washed over everything, muted (×5)
- (2026-04-19) color_palette: near-monochrome with warm amber skin tone, deep blacks, slight red glow (×5)
- (2026-04-19) color_palette: pure b&w, grainy mid-tones (×5)
- (2026-04-19) color_palette: pure b&w, washed sky, crushed tree shadows (×5)
- (2026-04-19) color_palette: warm amber-brown office wood + navy suit, preserved mid-tones, period-film feel (×5)
- (2026-04-19) color_palette: saturated pistons blue + red + white against muted brick red / gray, punchy (×5)
- (2026-04-19) color_palette: b&w with preserved mid-tones, slight nostalgia cast (×5)
- (2026-04-19) color_palette: pure b&w, crushed blacks, warm-white highlights (×5)
- (2026-04-19) color_palette: pure b&w, high-key white background (×5)
- (2026-04-19) color_palette: warm amber + gold highlights, slight teal shadows, rich saturated nolan palette (×5)
- (2026-04-19) color_palette: b&w high-grain, mid-key, soft (×5)
- (2026-04-19) color_palette: b&w with preserved highlight flares, crushed shadows (×5)
- (2026-04-19) color_palette: pure b&w, blown highlights from flash, deep blacks (×5)
- (2026-04-19) color_palette: b&w with crushed shadows, bill detail preserved (×5)
- (2026-04-19) color_palette: near-total black with single red highlight from saber (×5)
- (2026-04-19) color_palette: cosmic purples + yellows + cyan starfield + black car, high saturation (×5)
- (2026-04-19) color_palette: warm amber skin + muted brown brick + shadow, low-saturation period grade (×5)
- (2026-04-19) color_palette: muted outdoor browns + rooster red + photoshopped chrome/black, low saturation, phone-grade (×5)
- (2026-04-19) color_palette: b&w with bright specular bokeh highlights, crushed shadows (×5)
- (2026-04-19) mood: monumental nature-documentary gravitas (×5)
- (2026-04-19) mood: flex, luxury, wealth-display (×5)
- (2026-04-19) mood: raw speed, menace, hype (×5)
- (2026-04-19) mood: bureaucratic wealth, transactional gravity (×5)
- (2026-04-19) mood: cool, transactional, prestige (×5)
- (2026-04-19) mood: quiet tension, caught-in-action (×5)
- (2026-04-19) mood: historical gravitas, iconic resistance (×5)
- (2026-04-19) mood: luxury, aspirational, night-out (×5)
- (2026-04-19) mood: nostalgic, dandy-coded, period-piece prestige (×5)
- (2026-04-19) mood: mechanical prestige, horsepower-as-character (×5)
- (2026-04-19) mood: flex, effortless luxury, ironic juxtaposition (×5)
- (2026-04-19) mood: cocky, arrival, menace, 80s flex (×5)
- (2026-04-19) mood: raw, unhinged, caught-in-the-act (×5)
- (2026-04-19) mood: speed, autonomy, velocity (×5)
- (2026-04-19) mood: bleached, meditative, dubai-coded wealth (×5)
- (2026-04-19) mood: club-flex, nightlife excess, dreamy-disorienting (×5)
- (2026-04-19) mood: live sports tension, broadcast timing (×5)
- (2026-04-19) mood: wry amusement, vintage charm, candid (×5)
- (2026-04-19) mood: technological legitimacy, industrial-scale production (×5)
- (2026-04-19) mood: menacing, pop-culture hero-villain energy (×5)
- (2026-04-19) mood: aspirational montage, wealth-lifestyle anthology (×5)
- (2026-04-19) mood: monumental, garage-reveal prestige (×5)
- (2026-04-19) mood: candid charm, amused storytelling (×5)
- (2026-04-19) mood: confessional, casual, ugc-style (×5)
- (2026-04-19) mood: athletic grace, effortless power, coastal-prestige (×5)
- (2026-04-19) mood: mythic, triumphant departure, hero-entrance energy (×5)
- (2026-04-19) mood: predator, natural-kingdom majesty (×5)
- (2026-04-19) mood: quiet, old-money, european-riviera (×5)
- (2026-04-19) mood: everyday-paparazzi, leaked-clip, lo-fi viral (×5)
- (2026-04-19) mood: awe, confrontation, mythic-story-beat (×5)
- (2026-04-19) mood: cocky amusement, streetwear cool, iconic-figure (×5)
- (2026-04-19) mood: freeze-frame athleticism, adrenaline, suspended time (×5)
- (2026-04-19) mood: psychological menace, deadpan confrontation (×5)
- (2026-04-19) mood: streetwear swagger, neighborhood arrival (×5)
- (2026-04-19) mood: infectious laughter, mob-casual camaraderie (×5)
- (2026-04-19) mood: grand-gesture flex, proposal theater, private-jet prestige (×5)
- (2026-04-19) mood: announcer energy, infomercial-style arrival (×5)
- (2026-04-19) mood: gala-prestige, formal-tension, billionaire-in-public-poise (×5)
- (2026-04-19) mood: deliberate, mob-eating, menacing-thoughtfulness (×5)
- (2026-04-19) mood: kinetic impact, pro-wrestling spectacle (×5)
- (2026-04-19) mood: archival-celebrity, paparazzi capture, wealth-personified (×5)
- (2026-04-19) mood: cartel-scale wealth, transactional gravity (×5)
- (2026-04-19) mood: menacing arrival, dark-villain entrance (×5)
- (2026-04-19) mood: hyperreal, mythic hero-object, crypto-aspirational (×5)
- (2026-04-19) mood: focused combat intensity, martial-arts prestige (×5)
- (2026-04-19) mood: comedic absurdity, meme-humor, low-stakes fun (×5)
- (2026-04-19) mood: anonymous urban crowd, ambient prestige, entering-the-scene (×5)
- (2026-04-19) location_type: african savanna, tall grass (×5)
- (2026-04-19) location_type: dim interior, possibly hotel bed or private room (×5)
- (2026-04-19) location_type: drag strip or private lot, crowd onlookers (×5)
- (2026-04-19) location_type: close-up product shot, context-free (×5)
- (2026-04-19) location_type: military airfield tarmac (×5)
- (2026-04-19) location_type: dim basement or warehouse, exposed ceiling structure (×5)
- (2026-04-19) location_type: city boulevard, military column context (×5)
- (2026-04-19) location_type: luxury retail street, louis vuitton storefront, european-style architecture (×5)
- (2026-04-19) location_type: outdoor event / crowd scene, period footage (×5)
- (2026-04-19) location_type: studio product-shot, car opened (×5)
- (2026-04-19) location_type: luxury vehicle rear interior (×5)
- (2026-04-19) location_type: miami beach, period-piece 1980s tropics (×5)
- (2026-04-19) location_type: stage / performance space / dimly-lit venue (×5)
- (2026-04-19) location_type: winding mountain road, blue-hour exterior (×5)
- (2026-04-19) location_type: dubai palm jumeirah beachfront / luxury seaside real estate (×5)
- (2026-04-19) location_type: nightclub vip, bottle service with stage lights (×5)
- (2026-04-19) location_type: nfl stadium field, broadcast camera (×5)
- (2026-04-19) location_type: period-film hotel room / upper-class interior (×5)
- (2026-04-19) location_type: biotech / semiconductor / pharma cleanroom (×5)
- (2026-04-19) location_type: star wars film still, context-free (×5)
- (2026-04-19) location_type: multi-location montage (×5)
- (2026-04-19) location_type: industrial hangar / warehouse car-meet setting (×5)
- (2026-04-19) location_type: late-night talk show set, period-styled or nostalgic (×5)
- (2026-04-19) location_type: bedroom, residential, informal (×5)
- (2026-04-19) location_type: ocean surf break, offshore wind conditions (×5)
- (2026-04-19) location_type: sports arena tunnel / dramatic corridor (×5)
- (2026-04-19) location_type: caribbean / bahamian shallows, crystal water (×5)
- (2026-04-19) location_type: monaco / french riviera private residence with bay view (×5)
- (2026-04-19) location_type: parking lot / rest stop at dusk (×5)
- (2026-04-19) location_type: star wars film still, throne room (×5)
- (2026-04-19) location_type: interior interview / candid (×5)
- (2026-04-19) location_type: cliff jumping / water-leap outdoor adventure (×5)
- (2026-04-19) location_type: 1980s manhattan corporate office, film still (×5)
- (2026-04-19) location_type: urban street alley, brick building exterior, light industrial (×5)
- (2026-04-19) location_type: restaurant / social club interior, period-tv-still (×5)
- (2026-04-19) location_type: private jet hangar / fbo, staged grand-gesture scene (×5)
- (2026-04-19) location_type: studio seamless backdrop, commercial-spot feel (×5)
- (2026-04-19) location_type: opera house lobby / gala event, period elegance (×5)
- (2026-04-19) location_type: restaurant / formal dinner, film-still (×5)
- (2026-04-19) location_type: wrestling arena ringside / floor (×5)
- (2026-04-19) location_type: press event, microphone visible (×5)
- (2026-04-19) location_type: unclear context, cash-handling close-up (×5)
- (2026-04-19) location_type: star wars rogue one corridor set (×5)
- (2026-04-19) location_type: digital composite / stylized non-place (×5)
- (2026-04-19) location_type: hong kong martial arts film set, warehouse / courtyard (×5)
- (2026-04-19) location_type: outdoor residential driveway (meme-image context) (×5)
- (2026-04-19) location_type: urban nightlife / event entrance / formal crowd (×5)
## Voice Notes
- (2026-04-19) editor handle: 'stayblessed' (found in '©2025 STAYBLESSED COPYRIGHT RESERVED' footer on stylized pieces) — brand of the curator creating the $MOTION content

## Craft playbooks (cite these rules; do not restate)
### Playbook: grok-imagine-patterns

# Grok Imagine Prompt Patterns

Craft bible for prompting the image models Grok exposes via its Imagine
interface (accessible through X Premium). Read this before every new brief.

> This is opinionated and current as of early 2026. Update as patterns change.
> When something lands, add it here. When something flops, add it to the Kill
> List in `data/codex/style.md`.

## The models Grok routes between

- **Nano Banana** (Gemini 2.5 Flash Image derivative): character consistency,
  fast edits, photoreal with good skin, moderate text rendering. Best for
  iterating on a subject across scenes and for in-image edits ("make him cry",
  "change his wardrobe").
- **Aurora** (xAI in-house): painterly to photoreal range, strong with stylized
  and cinematic-feel scenes. Weak on text. Good for "hero art" pieces.
- **Flux Pro 1.1 Ultra** (routed occasionally): cleanest photoreal skin, best
  for portrait work where hands/eyes matter. Slower than the above.
- **Ideogram 3** (for text-heavy): unmatched typography rendering. Always the
  call when the meme's text lives inside the image.

You don't pick the model directly most of the time — Grok routes based on your
prompt's shape. To bias routing, use the cues below.

---

## Universal rules (every model)

1. **Banned words.** NEVER use: `cinematic`, `epic`, `stunning`, `beautiful`,
   `masterpiece`, `4k`, `8k`, `ultra-realistic`, `hyperrealistic`,
   `award-winning`, `trending on artstation`, `breathtaking`, `ethereal`,
   `highly detailed`, `intricate details`, `perfect composition`, `professional
   photography`. These are meaningless, crowd the prompt, and mark output as
   AI slop.

2. **Specificity beats superlatives.** Instead of "cinematic lighting", write
   "hard directional window light from camera-right, shadow side dominant".

3. **Name the gear.** Lens (35mm f/1.4, 85mm f/1.2, 24mm anamorphic), film
   stock (Cinestill 800T, Portra 400, Tri-X pushed to 1600), or sensor look
   (Leica Q3, medium format digital). The model has seen these names a million
   times — they are the most efficient quality levers in English.

4. **State time and condition.** "3am, practical-lit street" beats "night".
   "Overcast noon, soft diffuse light" beats "daylight". "Golden hour, low sun
   raking camera-right" beats "warm light".

5. **State composition by rule name.** "Rule of thirds, subject left",
   "centered medium close-up", "leading lines from foreground", "negative space
   right half", "low angle, 30° below subject eyeline".

6. **End with a negative list.** Close every prompt with what NOT to render:
   `no extra fingers, no warped text, no logo watermarks, no lens flare, no
   plastic skin, no HDR halos`.

7. **One subject, one scene, one mood.** Prompts that try to do three things
   at once produce mush. Split into three generations instead.

8. **Length: 60-120 words is the sweet spot.** Shorter tends to default to
   AI-cliché stock. Longer tends to fight itself. Aim for one long sentence or
   three tight clauses.

---

## Photoreal portrait pattern (Nano Banana / Flux / Aurora)

```
<subject, 1 sentence>, shot on <camera and lens>, <film stock or sensor look>,
<lighting setup>, <location and time of day>, <wardrobe and props>,
<composition rule>, <mood keyword or two>, photoreal, no CGI,
sharp focus on eyes, natural skin texture with visible pores,
<negative list>.
```

### Example A — night trader

```
Trader in his late 20s at a home office, mid-emotion read as he looks at
a phone screen, shot on a Canon EOS R5 with 85mm f/1.2, Cinestill 800T
look with subtle halation on the highlights, single practical desk lamp
camera-right as the only light source, 3am, overcast outside dark window,
grey hoodie and black wired earbuds, rule of thirds subject left, desk
clutter right third, mood tense and exhausted, photoreal, no CGI, sharp
focus on eyes, natural skin pores visible, no warped text, no extra
fingers, no plastic skin, no HDR.
```

### Example B — street photograph

```
Candid street photograph of a man lighting a cigarette on a narrow
Tokyo side street, shot on a Leica Q3 at 28mm f/1.7, Tri-X pushed to 1600
look with tight grain, available sodium-vapor street light from above and
neon-sign bloom from a shop on the left, rainy evening after 10pm, black
leather jacket with rain droplets, rule of thirds subject left, leading
lines from wet asphalt reflections, mood solitary and unhurried, photoreal,
no posing, no eye contact with camera, no extra fingers, no lens flare.
```

### Why this works
- Every specifying phrase lands on a known model concept (the name of the
  lens, the name of the stock, the name of the rule).
- The mood is two words at the end, not scattered throughout.
- The negative list cuts off common failure modes before they happen.

---

## Text-in-image meme pattern (Ideogram 3 via Grok)

The model must render text as text, not as blurry approximations of letters.
This is the single hardest thing current models do, and Ideogram 3 is the only
one that consistently nails it.

### Rules
- **Quote the text verbatim inside double quotes.** Do not paraphrase.
- **Name the font family.** "Impact bold", "Helvetica Bold condensed",
  "Arial Black", "monospace terminal", "serif broadsheet headline".
- **State placement.** Top-center / bottom-center / dead-center / right-
  aligned / inside a panel.
- **State stroke/shadow.** "White text with 3px black stroke" is the classic
  meme look. "Black text with drop shadow" reads more modern.
- **Keep captions short.** 2-8 words per line. More = smaller text = risk
  of garbling.
- **Avoid rare characters.** `&`, `#`, `@`, curly quotes all occasionally
  garble. Use plain ASCII when possible.

### Template
```
<image scene description, 1 sentence>. Caption overlay
<placement>: "<exact caption text>" in <font> with <stroke/shadow>.
<negative list>, no warped letters, no fake-text approximation.
```

### Example — two-panel setup/payoff
```
Two-panel meme, stacked vertically, equal panels, thin black divider.
Top panel: a chart labeled "Q4 outlook" with a line crashing dramatically.
Bottom panel: the same chart one week later, line unchanged but with a
sticky note labeled "copium" on top. Caption overlay top center: "THE
PROBLEM" in Impact bold white with 3px black stroke. Caption overlay
bottom center: "MY REFUSAL TO PROCESS IT" in Impact bold white with 3px
black stroke. 1080x1350 vertical. No warped letters, no extra text, no
watermarks.
```

---

## Character consistency pattern (Nano Banana)

Nano Banana is the best of the Grok-routed models for "same character,
different scenes". Character consistency is fragile — one wrong word and
the face drifts.

### Rules for the first generation
- Lock the character with **5-7 stable descriptors** that you will repeat
  VERBATIM in every subsequent prompt: height, build, face shape, hair color
  + style, eye color, a distinguishing mark (scar, stubble, glasses).
- Name the wardrobe explicitly: "navy Carhartt work jacket, dark jeans,
  grey Merrell boots" — repeat verbatim.
- Lock the **color palette** in the first generation and reuse.

### Rules for subsequent generations
- Paste the character block verbatim. Do not rephrase.
- Change only the scene / action / camera / lighting.
- If the face drifts, send the first generation back to Grok as a reference
  image with "same character as reference, new scene: ..."

### Example — character block you reuse
```
Character (do not modify): mid-20s male, 5'10", wiry build, square jaw,
short dark brown hair parted right, green eyes, small scar above left
eyebrow, 3-day stubble. Wardrobe: navy Carhartt work jacket over a plain
grey tee, dark indigo jeans, scuffed brown Red Wing boots. Palette: cool
greys, navy, warm brown leather accents.
```

Prepend that block to every scene prompt.

---

## Reference image workflow

Grok accepts a reference image alongside the prompt via its UI. Use this for:

1. **Style transfer** — upload a film still / photo whose LOOK you want.
   Prompt: `match the lighting, palette, and grain of the reference; new
   subject: <description>`.
2. **Character reference** — upload your first successful generation when
   spinning up scene 2.
3. **Composition reference** — upload a moodboard tile of the exact framing
   you want. Prompt: `match the composition of the reference`.
4. **Refinement** — upload a generation you're 80% on and prompt the change:
   `same image, change only the wardrobe to a black bomber jacket`.

The tool's `memegine refs` library is where you curate your own reference
set. Tag them aggressively so the codex can cite them later.

---

## Common failure modes and how to prevent them

| Failure | Cause | Fix |
|---|---|---|
| Plastic / waxy skin | "photorealistic", "masterpiece", "8k" bait | Delete those words. Add "natural skin texture with visible pores". |
| Warped/extra fingers | Hands asked to do complex actions | Keep hands simple (at side, in pocket, holding one simple object). Add "no extra fingers" to negative list. |
| Garbled text | Too much text, rare characters, wrong model routing | Keep text ≤ 6 words per line. Quote it verbatim. State "Ideogram style" to bias routing. |
| Generic AI-portrait face | No specificity on subject | Add an age range, a distinguishing feature, a specific emotion word. |
| "Cinematic" over-contrast look | Banned word in prompt | Remove banned words. Name the actual lighting setup. |
| Plasticky CGI background | Asked for "beautiful scenery" | Name the actual location + time: "a shop interior in 1970s Tokyo, late afternoon". |
| Style drift across variants | Changing more than one variable | Change one axis at a time (lens / time / lighting / wardrobe). See `memegine variants`. |
| Eyes out of focus | Lens wider than 50mm with small subject | For portraits, use 50mm+ and add "sharp focus on eyes". |
| Subject feels posed / stock-photo | Asked for "smiling woman" | Replace with an action or emotion cue: "laughing at an off-screen joke", "mid-sentence, eyes looking away". |

---

## Routing cues (bias Grok to the right model)

- **Want Ideogram (text)**: mention "Ideogram-style text rendering",
  "Impact bold caption", "typography-accurate", "magazine headline".
- **Want Flux (skin/hands)**: "Flux Pro ultra photoreal, natural skin
  texture, clean hands".
- **Want Aurora (stylized/painterly)**: "painterly", "oil-paint texture",
  "editorial illustration", "magazine cover art".
- **Want Nano Banana (edit/consistency)**: include a reference image AND
  say "keep the character from the reference, new scene".

---

## Quick-reference prompt skeleton

```
<subject in one sentence, with specific emotion or action>,
shot on <camera + lens>, <film stock or sensor look>,
<named lighting setup>, <location + time of day + weather>,
<wardrobe / props kept simple>, <composition rule>,
<mood, one or two words>,
photoreal, <any model-routing cue>,
<negative list: no extra fingers, no warped text, no plastic skin, no HDR halos, no lens flare>.
```

Memorize the skeleton. Your first draft of any prompt fills this, then the
Director refines it.


---

### Playbook: portrait-photography-craft

# Portrait Photography Playbook

Photoreal portraits are where AI most often gives itself away: plastic
skin, dead eyes, symmetric blur, wedding-photographer lighting. This
reference is for keeping portraits feeling like a real photograph a real
human shot — named lens, named lighting ratio, named stock.

---

## Default "photoreal portrait" stack

A portrait that doesn't trip the AI detector almost always cites:

1. **A specific camera + lens** (not just "camera")
2. **A specific film stock or sensor look** (not just "warm tones")
3. **A named lighting setup with a ratio** (not just "soft light")
4. **A specific time of day + weather** (not just "natural")
5. **A composition rule** (not just "well composed")
6. **A named emotion + micro-movement** (not just "expressive")
7. **A "no X, no Y" negative clause** (not implicit trust)

If any of those seven is vague, ship value drops ~20%.

---

## Lens by subject framing

| Framing | Lens | Why |
|---|---|---|
| Environmental portrait (subject in a place) | 28mm f/1.8 or 35mm f/1.4 | Keeps the place legible. Distortion starts at 24mm. |
| Standard portrait | 50mm f/1.8 or 50mm f/1.2 | Closest to what the eye "sees". Feels documentary. |
| Headshot / compressed portrait | 85mm f/1.2 or 85mm f/1.8 | Background separates cleanly. Skin looks flattering. |
| Long tele portrait | 135mm f/2 or 200mm f/2.8 | Monumental. Background becomes abstract wall of color. |
| Tight detail (hands, jewelry, eye) | 100mm macro | Tack-sharp without losing the body language. |

Default for "a character in a place" = **35mm f/1.4**.
Default for "a character's face, no place" = **85mm f/1.2**.

---

## Lighting ratios — the single biggest craft signal

Ratios describe how much brighter the key is than the fill. Naming the
ratio makes the model actually build lighting instead of defaulting to
"even everywhere" (which looks fake).

| Ratio | Look | Use for |
|---|---|---|
| 1:1 | Flat, even | Beauty / commercial |
| 2:1 | Gentle modeling | Mainstream portrait |
| **3:1** | Dimensional, balanced | **Default for editorial photoreal** |
| 4:1 | Moody, shadow-side strong | Documentary, cinematic |
| 8:1+ | Deep shadow side (Rembrandt, split) | Dark lore / fine-art |

Always write: `key camera-right at 3:1 ratio, fill from a {source}`, not
just "soft light". If you don't know the ratio, default to 3:1 for
narrative portraits and 2:1 for "approachable" subjects.

---

## Named lighting patterns (cite these by name)

- **Butterfly**: key above and in front, straight down. Creates
  symmetric under-chin shadow. Glamour default.
- **Rembrandt**: key 45° camera-right, slightly above. Produces a
  triangle of light on the shadow-side cheekbone. Classical.
- **Split**: key exactly 90° camera-side. Half face in deep shadow.
  Drama, polarization.
- **Loop**: key ~30° off axis. The nose shadow forms a small loop
  beside the nose. Most natural-looking portrait.
- **Clamshell**: soft key above + soft fill below. Tight crops. Beauty.
- **Rim backlight**: key strong from behind, separates subject from
  dark background. Narrative / editorial.

If the subject is supposed to look "quiet" or "unresolved", **Rembrandt
at 3:1** is almost always the right call. If they're supposed to look
"alienated" or "threatened", **split at 8:1** is the move.

---

## Skin — the dead giveaway

AI skin looks like glass or wax. Counter with:

- **Name the stock**: `Portra 400` / `Fuji 400H` / `Cinestill 800T` /
  `Tri-X pushed to 1600`. These stocks have specific skin renderings.
- **Cite texture**: `natural skin texture, visible pores, no digital
  smoothing, no beauty retouching`.
- **Name the grain**: `subtle film grain, not digital noise`.
- **Force imperfections**: `one strand of hair across the cheek, slight
  asymmetry, a tiny catchlight in the right eye only`.

Default negatives: `no plastic skin, no symmetric blur, no AI-smoothness,
no uniform skin tone across face`.

---

## Eyes

Always name what the subject is looking at or a specific internal state:

- "eyes locked on the screen in front of them"
- "eyes unfocused, middle-distance, dissociated"
- "eyes narrowed, reading something just off-frame"
- "eye contact with camera, no affect"

Never write just "expressive eyes". It's a null phrase — the model
defaults to symmetric catchlights and glossy irises. Dead.

---

## Wardrobe — concrete wins over adjectives

- Not: "stylish outfit"
- Yes: "black crew-neck t-shirt, visible seam at collar, gold chain
  partially hidden"
- Not: "casual clothes"
- Yes: "gray hoodie, left drawstring longer than right, pen clipped to
  pocket"

Operator-specific pattern: the same wardrobe across pieces makes a
recurring character feel real. Pick 3-5 wardrobe sets and cycle.

---

## Background — "context over cosmetics"

The background says where the subject is. Name it concretely:

- Not: "a studio"
- Yes: "a seamless gray roll backdrop, 8-feet deep, no other objects"
- Not: "a moody background"
- Yes: "a parking garage, concrete columns, two flickering fluorescent
  tubes, no cars"

The bokeh should be a consequence of the lens choice, not a styling
decision. If you want heavy bokeh, use 85mm f/1.2. If you want
legible-but-soft, use 35mm f/1.4. Don't ask for "beautiful bokeh".

---

## Composition defaults

- **Rule of thirds, subject on left third**: classic narrative portrait.
- **Centered, tight crop**: confession, intimacy, or meme reaction.
- **Low angle up-tilt**: hero, monumental, threatening.
- **High angle down-tilt**: small, vulnerable, judged.
- **Dutch tilt 12°**: unsettled, wrong.

Default for "a character feeling something": **rule of thirds, subject
left, negative space right half, eyes on upper third**.

---

## Negative clause — always present

Every photoreal portrait prompt should end with:

> no extra fingers, no warped text, no logo watermarks, no lens flares
> unless specified, no plastic skin, no symmetric blur, natural skin
> texture preserved, no CGI look.

Memegine's `NEGATIVE.photoreal_defaults` fragment expands to this. Use
it.

---

## The portrait self-check (before you ship)

A photoreal portrait prompt that's ready to paste into Grok answers all
of these yes:

- Is there a named lens with aperture?
- Is there a named film stock or sensor look?
- Is there a named lighting pattern (Rembrandt, split, butterfly,
  clamshell, loop, rim-backlight)?
- Is there a named lighting ratio (2:1, 3:1, 4:1)?
- Is there a named time-of-day + weather?
- Is there a named composition rule?
- Are the eyes described as doing a specific thing?
- Is the wardrobe concrete (not "casual")?
- Is the background a specific place (not "moody")?
- Is there a negative clause at the end?

Under 8/10? Run `memegine fix-prompt` before you paste it.


---

### Playbook: color-grading-by-mood

# Color Grading by Mood Playbook

Color does 70% of the emotional work in any piece. Named palettes lock
the model onto specific color logic; vague adjectives ("cinematic
colors", "vibrant", "muted") don't.

This playbook maps operator-intended moods to the color language that
carries them.

---

## The emotional color atlas

| Mood | Palette | Why it works |
|---|---|---|
| Quiet dread | **Cold monochrome blue** + single warm practical | The isolation comes from a color system that doesn't forgive. One warm light in a cold frame feels like "the only thing alive". |
| Smug resignation | **Faded Kodak** / warm slightly-yellowed | Looks like a memory already fading. Nothing aspires. |
| Cope | **Sodium amber + cyan highlights** | The amber is "warmth-coded" but sickly. Cyan highlights = fluorescent reality intruding. |
| Absurd calm | **Neutral documentary palette** | No grading. The absurdity reads louder against normal-looking color. |
| Unhinged joy | **Crushed blacks + blown highlights** | Emotional intensity encoded as tonal intensity. |
| Defeat | **Bleached pastel** | The color has been drained out. |
| Reverent | **Deep emerald** OR warm tungsten gold | Stained-glass / candlelight logic. Light = sacred. |
| Dread / threat | **Monochrome blue** + almost-black | Removes reassurance. |
| Contempt | **Teal / orange filmic** | Hollywood-default but weaponized: subject warm, world cold. |
| Nostalgia | **Kodachrome / Ektachrome** | Slide-film saturation = "recorded memory". |
| Hero | **Golden hour warm** + long rim light | Light = triumph. |

---

## How to name a palette in a prompt

Name it like a colorist would, not like a stock-photo tag:

**Weak:**
- "cinematic colors"
- "vibrant"
- "moody tones"
- "dreamy palette"

**Strong (name references):**
- "Roger Deakins teal-orange, subject warm against cold environment"
- "Gregory Crewdson cool blue suburbia palette, singular warm practical
  window"
- "Wes Anderson pastel palette, symmetric color blocking"
- "Blade Runner 2049 amber-sodium + cyan highlights"
- "Bill Henson deep emerald + near-black shadows"

A reference-grounded palette gives the model something specific to aim
at. Memegine's `COLOR_PALETTE.*` fragments are pre-named aim points.

---

## The three color levers in every prompt

1. **Shadow color** — what's the color of the darkest parts?
   - Warm shadows (warm blacks) = intimate, cinematic
   - Cool shadows = clinical, lonely, modern-digital
   - Pure black (crushed) = dramatic, poster-like

2. **Highlight color** — what's the color of the brightest parts?
   - Warm highlights (golden) = hero, nostalgia, warmth
   - Cool highlights = tech, surveillance, sterility
   - Preserved whites = documentary, non-graded

3. **Midtone bias** — what's the global cast?
   - Warm midtones = welcoming, vintage
   - Cool midtones = detached, modern, troubled
   - Green midtones = uneasy (cross-process feel)
   - Magenta midtones = nightlife, unreality

Name all three when mood is the main lift. Example:

> **Cold blue shadows, warm sodium highlights, green midtone bias.**
> Subject face caught between the two light colors.

---

## Time of day == color temperature (always)

| Time | Kelvin | Color cast | Emotional default |
|---|---|---|---|
| Noon clear sky | 5600K | Clinical white | Flat, honest |
| Overcast noon | 6500K | Slightly blue | Neutral, documentary |
| Golden hour | 3200K | Warm amber | Hero, nostalgia |
| Blue hour (post-sunset) | 10,000K (sky) + 2700K (practicals) | Cobalt sky, warm windows | Quiet, transitional |
| Indoor tungsten | 2700K | Warm orange | Intimate, cozy, dated |
| Fluorescent | 4000K + green | Green-cyan | Institutional, dead |
| Neon practicals | Mixed | Colored spill | Urban night, crypto-coded |
| Moonlight | 4100K | Cool white-blue | Loneliness, stealth |
| Candlelight / firelight | 1800K | Deep amber | Ritual, intimacy |
| Monitor / phone screen | ~6500K | Cool blue-cyan | Digital solitude |

Mixed light sources = richer palettes. "Sodium amber exterior + cold
phone screen interior" tells the model to mix two temps in the same
frame.

---

## Contrast — the loudness knob

Named contrast ranges force the model to stop defaulting to "balanced":

- **Flat profile**: compressed tonal range, shadows lifted to gray.
  Documentary, analytical. Think: Associated Press, Vice.
- **Standard**: natural roll-off. Most photoreal defaults.
- **Filmic S-curve**: subtle roll-off at both ends. Movies.
- **Crushed**: shadows go to near-black, highlights preserved. Poster,
  meme, editorial.
- **Blown**: whites clip intentionally. Summer, heat, overexposure-as-
  style.

A `crushed shadows + filmic roll-off in the highlights` clause usually
saves a prompt that feels "too AI".

---

## Grain / texture

Grain is mood too. Name it:

- **No grain** = digital, clinical, modern
- **Subtle grain** (Portra, Fuji) = cinematic intimacy
- **Coarse grain** (Tri-X 1600, Delta 3200) = grit, documentary, fear
- **VHS / chroma-smear** = nostalgia, lo-fi, degraded-record

Memegine's `POSTPROCESS.*` fragments cover these directly.

---

## Palette + stock pairings that work

| Palette intent | Film stock pairing |
|---|---|
| Warm editorial portrait | Portra 400 |
| Night-cold + warm practicals | Cinestill 800T |
| Gritty documentary | Tri-X pushed to 1600 |
| High-saturation editorial | Ektar 100 or Velvia 50 |
| Dreamy pastel | Fuji 400H |
| Archival documentary still | Kodak Vision3 500T |
| Lo-fi memory | VHS-stock emulation |
| Muted nostalgia | Polaroid 600 or Instax Mini |

Pair intentionally. Not every palette works with every stock.

---

## When in doubt, cite a specific frame

The fastest way to lock color is to tell the model "the palette of
[specific frame]":

- "palette of _Joker_ (2019) subway scene"
- "palette of Gregory Crewdson's _Twilight_ series"
- "palette of _Blade Runner 2049_ Las Vegas sequence"
- "palette of a Pantone 1950s postcard of Miami"

Give the model a frame. It'll match the system, not just the hue.

---

## The grading self-check

- Is the palette named (not adjective-d)?
- Is the shadow color stated?
- Is the highlight color stated?
- Is the midtone bias stated?
- Is a named reference frame or director/photographer cited (when
  ambition is high)?
- Does the contrast profile match the emotional register?
- Is the grain logic named (no grain / subtle / coarse / degraded)?

Under 5/7? The piece will default to "AI-default filmic teal-orange",
the single most overused palette.


---

### Playbook: low-light-and-night

# Low-Light and Night Playbook

Crypto and late-night content lives in low light. AI defaults to "noon
sunny" unless corrected; this playbook is for deliberately sending the
model into the dark.

---

## Why low-light is hard for AI

Default AI training is skewed toward well-lit stock photography. Without
intervention, asking for "night" produces:

- Over-lit "night" that's actually overcast
- Suspiciously clean shadow-detail
- No grain (daylight sensors pushed to look dark ≠ actual night)
- Magically-invisible noise
- Warm "streetlamp glow" that's too uniform

Counter all of this by naming specific LIGHT SOURCES (not
"ambient"), naming film stock suited for low light, and demanding
grain + fall-off.

---

## The essential low-light prompt structure

```
[subject and action],
[specific named practical lights visible in frame],
[film stock / sensor known for low light],
[explicit shadow behavior clause],
[grain / noise description],
[negative clause disallowing AI-smoothness]
```

Example:

> A trader at a kitchen counter at 3am,
> lit only by a laptop screen (cool cyan) + a single neon "OPEN" sign
> bleeding through the window (red),
> Cinestill 800T for tungsten halation,
> shadows fall off to near-black past 2 feet from the light sources,
> natural film grain, not digital noise,
> no uniform shadow detail, no glow spread beyond natural fall-off.

---

## Light sources that work in night prompts

**Name them specifically. Model matches.**

| Source | Color temp | Character |
|---|---|---|
| Sodium vapor street lamp | 2000K | Deep amber, grainy, wraps around fog |
| Mercury vapor | 4000K | Cyan-green, industrial, cold |
| Neon sign | Varies | Saturated, localized spill |
| LED streetlight (modern) | 5000K | Cold white, hard shadows |
| Phone screen | 6500K | Blue-cyan, small tight spill on face/hands |
| Monitor glow | 6500K | Same but bigger spill, often multiple screens |
| Tungsten practical (lamp, bulb) | 2700K | Warm orange, pleasant |
| TV cathode glow | Flickering | Blue-green, intermittent, flickery |
| Candle | 1800K | Deep amber, tight spill, flicker implied |
| Car headlight through window | 5500K | Cold white, moving, transient |
| Emergency / ambulance light | Red + blue | Chaotic, alternating, strobe |
| Moon (full, clear sky) | 4100K | Cool white-blue, soft, long shadow |

**Mixed sources = richer night.** "Sodium exterior + tungsten interior +
phone screen glow on face" tells the model exactly where to place color.

---

## Shadows — the single biggest AI tell

AI defaults to LIFTED shadows (always some detail). Real low light has
CRUSHED shadows (much of the frame is near-black).

Force crush with:

- "Shadow side falls off to near-black within 3 feet of the light"
- "No ambient fill. Shadows have no detail."
- "High-contrast lighting: subject illuminated, surroundings not."

Refer to `POSTPROCESS.crushed_shadows` for the fragment.

---

## Grain, noise, and low-light texture

Low light has texture. AI hides it. Demand it:

- **Film low-light**: "natural film grain from pushing Tri-X to 1600,
  coarse and organic"
- **Digital low-light**: "ISO 6400 digital noise, chroma noise in shadows"
- **Degraded video**: "VHS-tape low-light, chroma smear in shadows,
  tracking lines"

If the piece is supposed to feel REAL (documentary, candid) — grain is
the texture of honesty. If it's supposed to feel DREAMLIKE — use Super
8 or lo-fi VHS grain.

---

## Stocks that were made for low light

- **Cinestill 800T** — the lingua franca of crypto-cinematic. Red
  halation around any bright light source is distinctive.
- **Kodak Portra 800** — softer, warmer, pushes well.
- **Ilford Delta 3200** — B&W, massive grain, documentary / fear.
- **Fuji Natura 1600** — pastel-in-dark, unusual.
- **Kodak T-Max P3200** — harsh B&W, very pushed, news/reportage feel.

Default for "crypto late-night" = **Cinestill 800T**.

---

## Specific low-light scene recipes

### 1. "Operator at 3am"
```
a 30s hooded operator at a desk,
lit only by two monitors (cool cyan, left) + a warm desk lamp (tungsten, right),
Cinestill 800T, visible red halation around screen edges,
shadow side falls to near-black past the subject's shoulder,
natural grain, no uniform ambient fill,
rule of thirds subject on left, monitor glow on right of frame,
no plastic skin, no symmetric blur, no digital HDR feel.
```

### 2. "Subway platform"
```
an empty subway platform late night,
fluorescent overhead (cold cyan-green) with one tube flickering,
no ambient fill, reflected puddles on platform edge,
Tri-X 400 B&W pushed to 1600, heavy grain,
wide lockoff, platform vanishing to a point,
35mm f/1.4,
no CGI, no smoothing, grain visible.
```

### 3. "Parking garage"
```
underground parking garage, single concrete level, no cars,
lit only by sodium vapor tubes (amber) every 40 feet,
subject walking away from camera at mid-distance,
Cinestill 800T, halation around each tube,
deep shadow pools between lights,
50mm f/1.8,
no wide ambient glow, no detail in shadows,
natural breath visible if cold clause is added.
```

### 4. "Motel room"
```
a 2am motel room, seated subject on bed edge,
lit by a cathode TV (flickering blue-green) + a bedside lamp
(warm tungsten 2700K) on the opposite side,
Cinestill 800T,
40mm framing, subject silhouetted where the TV falls on their face,
heavy curtain pulled, sliver of exterior orange light at the edge,
deep shadows, no uniform ambient, grain forward,
no AI polish, keep natural tonal range.
```

### 5. "Rooftop, city, blue hour"
```
a founder on a city rooftop at blue hour,
sky ambient cobalt + warm practicals from windows in the surrounding
buildings (visible but small, thousands of amber dots),
Kodak Portra 800, filmic roll-off,
35mm f/1.4, rule of thirds, subject on left, skyline in negative space
on right, distant traffic,
subtle grain, crushed blacks,
no overdone neon wash, no cyberpunk styling.
```

---

## Common low-light failures & fixes

**"The 'night' looks like overcast day"**
→ Add: "no ambient fill, shadows fall to near-black within 3 feet of
the light source, only named practicals illuminate the scene."

**"Everything is too evenly lit"**
→ Specify a single key direction. "Lit ONLY by X from Y direction.
Other surfaces in shadow."

**"AI glow looks uniform and fake"**
→ Demand the natural inverse-square fall-off: "Light falls off
geometrically, 4x brighter near the source than 3 feet away."

**"Subject looks retouched / too clean"**
→ Cite grain: "visible Cinestill 800T grain, no digital smoothing,
natural skin texture preserved."

---

## Color temperature pairings that sing

| Mix | Emotional effect |
|---|---|
| Sodium amber exterior + cold monitor interior | Isolation, tech-vs-world |
| Firelight warm + blue moonlight | Ritual at the edge of wild |
| Neon red + fluorescent green | Unease, nightlife-as-nightmare |
| Tungsten warm + blue phone screen | Domestic solitude |
| Candlelight + distant streetlamp through window | Contemplation |
| Headlights sweeping + static tungsten | Motion in stillness |

---

## The low-light self-check

- Are specific LIGHT SOURCES named (not "ambient")?
- Is the film stock / sensor low-light-native?
- Is grain / noise explicitly demanded?
- Is shadow behavior specified (crushed, falls off, no ambient fill)?
- Are 2+ light sources at different color temps? (Mixed light = richer)
- Is there a negative clause disallowing AI-smoothness?
- Would you believe this is a real photograph of a real place at night?

If the piece looks like "cinematic night" and not "a specific photograph
taken at a specific hour" — add specificity.


---

### Playbook: crypto-visual-language

# Crypto Visual Language Playbook

Crypto-native content on X has a visual vernacular. Using it correctly
signals "I'm from here". Using it badly signals "I saw a tutorial."
This playbook catalogs the language and — more importantly — the
kill-list of what to avoid.

---

## The crypto KILL LIST (never render these)

These are the tells of AI-generated crypto slop. Any prompt including
any of these is DOA on crypto X:

- **Gold physical coins** (bitcoin-logo, "$" embossed, the whole
  gold-coin-in-a-vault aesthetic)
- **Laser eyes** (has been dead since 2022)
- **Moon rockets / to-the-moon imagery**
- **Diamond hands emojis rendered as objects**
- **Fake "hacker in a hoodie" with green terminal code reflected in
  their face**
- **Generic "futuristic city" cyberpunk backdrop**
- **Cyberpunk neon + glowing blockchain hexagons**
- **An abstract chart "going up and to the right"** (unless it's a
  cope-chart joke, in which case it needs specific numbers)
- **"Bull" or "bear" imagery as literal bulls / bears**

If any of these are in the prompt, the piece reads as non-native. The
natives will silently not RT. Kill them.

---

## The crypto VISUAL VOCABULARY (what actually works)

### Characters
- **The tired operator**: hoodie or plain-shirt, at a laptop, multi-
  monitor, deep night. Face shows fatigue or indifference, NEVER
  celebration.
- **The market-anon avatar**: a recurring masked / hooded / obscured
  figure seen in profile or from behind. Builds character equity.
- **The quant analyst**: thin glasses, paper printouts, mid-calculation,
  no screens visible (print-out is the prop).
- **The exhausted founder**: button-up, top button undone, tired eyes,
  phone in hand. Usually in a hotel / airport / car.
- **The rotating characters**: new-cycle bro (too confident,
  inappropriate clothing), old-cycle veteran (tired, bearded,
  resigned), shiller (too bright, gesturing), NPC crowd (identical
  wojaks, all mid-sentence).

### Settings
- **3am kitchen** (the iconography of the overnight session)
- **Rooftop at blue hour** (the founder/operator vantage)
- **Parking garage concrete** (the non-place where decisions are made)
- **Trading floor after hours** (abandoned, screens still on)
- **Hotel hallway** (the nomad aesthetic)
- **Empty subway platform** (solitude with fluorescent ambient)

### Settings that LOOK crypto but shouldn't
- Wall Street / NYSE — you're not there
- Fancy corporate office — too clean
- Beach / yacht — parody territory only

### Props
- Laptop with real-looking stickers (worn, mismatched, not artful)
- Specific screens (Hyperliquid perps, TradingView, Bloomberg terminal,
  Discord/Telegram)
- Mug with coffee stain, empty
- Printed chart with annotations in pen
- Phone face-down on the table (specific detail = real)

### Props to avoid
- Physical crypto coins (see kill list)
- Generic "tech" props (floating holograms, HUD overlays, data
  visualizations swimming in air)
- Anything that says "this is a crypto project" on the nose

---

## Tonal register

The project voice is **tired-coded smart**. Not:

- Not overtly bearish (edgelord posturing)
- Not overtly bullish (shilling)
- Not ironic-but-secretly-sincere (tradwife cosplay)

The register is **earned cynicism**. The character has seen cycles. They
don't celebrate. They don't panic. They observe. They occasionally
break the fourth wall with a deadpan take.

Color language that fits:
- Cold monochrome blue
- Sodium amber + cyan highlights
- Faded Kodak
- Crushed blacks with filmic roll-off

Color language that doesn't fit:
- Teal-orange Hollywood
- Vibrant saturation
- Clean studio lighting

---

## Meme archetypes that land in crypto X

| Archetype | Format | Register |
|---|---|---|
| The NPC crowd saying the consensus take, one enlightened wojak with the real take | `npc_wojak_row` | Smug, knowing |
| The cope-chart with absurd precision ("ETH makes new high at $8001 exactly when Saturn enters Virgo") | `cope_chart` | Bureaucratic absurdism |
| The fake news headline that's almost real | `fake_news_headline` | Deadpan |
| The NYT-style article screenshot with an absurd subhead | `fake_news_headline` or `document_scan` | Institutional takedown |
| Two-panel expectation/reality about holding | `meme_two_panel` or `split_screen_then_now` | Self-aware |
| The photoreal portrait of a character mid-loss or mid-fade | `photoreal_portrait` with mood=cope/defeat | Gravity |
| The terminal screenshot with a specific number that's the joke | `screenshot_terminal` | Data poetry |

---

## What 2026 crypto X is actually posting (as of April 2026)

Hot:
- Photoreal portraits of operator archetypes (quiet, tired, specific)
- Bloomberg-terminal-style screenshots with absurd data
- Found-footage aesthetic pieces (fake archival)
- Polaroid-nostalgia pieces (looking back at cycles)
- Podcast-clip-subtitle reaction format

Fading:
- Drake meme format (overused)
- NPC wojak format (still works but saturated)
- Gold-coin imagery (dead)
- Cyberpunk aesthetic (dead)

Reviving:
- VHS-era aesthetic (coming back — check `found_footage_still`,
  `vhs_ad_spoof`)
- Magazine cover / editorial format
- Receipt-as-narrative format

---

## Caption register for crypto pieces

Do:
- Specific observations with no verb ("3am kitchen")
- Dry ironic statements ("imagine this but rent is due")
- Setup/punch with short lines
- Noun-phrase-only captions for strong hero shots
- Near-whispers that imply more than they say

Don't:
- "wen moon"
- "lfg"
- "wagmi"
- "ngmi" (acceptable only as genuine self-diss, never as hype)
- Engagement bait ("who else feels this?")
- Emojis

Caption linter enforces most of this. Use `memegine caption-lint` before
every post.

---

## Posting cadence

Crypto X is most active:
- 3am-7am UTC (US evening, Asia morning)
- 12pm-3pm UTC (US early morning — market open punch)

Post timing correlates with format:
- Hero photoreal pieces: post at US market open (reaches the chart-watchers)
- Memes / reactions: post during dumps and pumps (reactive = organic RT)
- Lore drops / found-footage: post late night (3am zone = contemplative
  audience)

Track via `memegine perf by-hour`. Your hours will differ from the norm
— use your own data.

---

## The crypto self-check

Before shipping a crypto piece:

- Is anything on the kill list present? Remove it.
- Is the character tired-coded, not celebratory?
- Is the setting a non-place (kitchen, garage, subway) or a real
  operator place (terminal, trading floor)?
- Are the props specific (brand name, worn detail) not abstract?
- Is the color palette in the crypto-emotional atlas (cold blue, sodium
  amber, faded Kodak) not teal-orange default?
- Is the caption register earned cynicism, not hype?
- Would you RT this if you scrolled past it?

If not, ship it as a flop and log it to kill list via
`memegine codex flop`. You're calibrating.


---

### Playbook: motion-brand

# $MOTION Brand Playbook

The compiled craft knowledge extracted from 47 confirmed-good editor
pieces. This playbook is read by Claude on every brief involving the
$MOTION token project so the output matches canon instead of drifting
into generic crypto slop.

---

## The brand in one sentence

**$MOTION is a CURATION brand, not a shoot brand.** The editorial move
is finding evocative existing footage (film stills, wildlife docs,
celebrity archives, luxury B-roll, sports moments) and branding it
with a specific typographic overlay. The mood it projects is PRESTIGE
ICONOGRAPHY transplanted onto a token — never meme-crypto shitcoin
visual language.

If a brief is asking for generic "laser eyes + moon rocket + gold
coins" crypto stock imagery, it is OFF-BRAND for $MOTION. Reject.

---

## Typography taxonomy — 7 registers

Every piece belongs to exactly one typographic register. The choice
of register signals the emotional mode.

### 1. Serif centered (Didot / Bodoni) — DEFAULT
- ~80% of the canon
- White fill, centered middle of frame, size roughly 1/8 to 1/6 of
  frame width
- Use for: prestige / cinematic / curated / reverent pieces
- Pieces: lions, film stills (Dark Knight, War Dogs, Scarface),
  celebrity archives (Tupac, young Trump), luxury vehicles, grand
  gestures

### 2. Bold geometric sans (Helvetica Bold / Impact-style)
- Use for: energy, action, sports, hype
- Pieces: drag-strip burnouts, NFL plays, WWE top-rope dives, De
  Niro formal-scene pieces

### 3. Italic sans with motion-blur treatment
- Use for: velocity, cars, speed
- Pieces: Porsche GT3 POV on mountain road, Bugatti on starfield,
  any driving content

### 4. Italic script cursive
- Use for: tokenomics statements (not $MOTION wordmark)
- Example message: "25% locked" on a 70s-era found footage subject
- This is HOW utility/supply/unlock data is communicated

### 5. Retro Art-Deco striped sans
- Use for: cartel-scale wealth moments
- Pieces: vacuum-sealed cash bricks, shrink-wrapped bills
- Internal vertical stripes inside the letterforms

### 6. Semi-transparent serif (no $ prefix — just "Motion")
- Use for: ambient, atmospheric, bokeh-first compositions
- Softer, more expensive-feeling, event-entrance energy
- Example: crowd scene with shallow DOF and bokeh orbs

### 7. Bold sans + stacked laughing emojis
- Use for: comedy / shitposts
- Rare but present — the brand is not above absurdism when the
  image warrants it (rooster-with-a-motorcycle meme)

**When in doubt, use register 1 (Didot serif centered, white).**

---

## Aspect handling

Two recurring signatures:

1. **Native aspect**: source runs in its own ratio (16:9 / 4:3 / 1:1 /
   9:16) when the original framing is strong enough to carry.
2. **Letterboxed on 9:16 canvas**: wide cinematic source (16:9 or
   2.35:1) matted with black bars top+bottom, placed on a vertical
   9:16 canvas for phone delivery. This is a distinctive MOTION move.

For new pieces: default to 9:16 vertical if phone-native; otherwise
run the source's aspect and add letterbox only if the source is wide
and phone delivery is required.

---

## Color grade canon

- **B&W / monochrome**: ~40-50% of pieces. Crushed blacks, preserved
  mid-tones. This is the brand's default mode when color isn't
  load-bearing.
- **Warm amber + teal shadows** (filmic teal-orange): Hollywood
  stills (War Dogs, Dark Knight) — keep the source's native grade.
- **Warm tungsten + cool phone/neon** (mixed light): nightclub,
  interior flex, POV cash-handling.
- **Pure high-key B&W bleached**: Dubai beachfront, open-sky luxury.
- **Pure deep-black + single red light**: Star Wars sith imagery.

**What's off-brand**: vibrant saturated daylight, HDR-bright clean
digital, pastel palettes, cyberpunk neon, fluorescent flat.

---

## Grain / texture

**Heavy grain is canon.** The editor intentionally uses degraded
footage:
- VHS-grade grain overlay (wildlife doc, archival)
- Phone-video lo-fi (UGC selfies, paparazzi captures)
- 1990s film grain (Casino, Sopranos-era references)
- Halftone dot pattern overlay (comic-retro treatment on Darth Maul-type pieces)

**Clean digital look is off-brand.** If a prompt produces pristine
high-fidelity imagery, add back: "heavy film grain, VHS-grade noise,
analog degradation, not crisp digital."

---

## Film canon (curation reference library)

When a brief calls for a cinematic reference, pull from this syllabus:

- **Crime / finance / noir**: Scarface (1983), The Dark Knight (2008),
  War Dogs (2016), American Psycho (2000), Casino (1995), The Sopranos
  (HBO, entire run), Goodfellas (1990)
- **Mythic / sci-fi villain**: Star Wars (Darth Vader in Rogue One,
  Darth Maul in Phantom Menace, Luke in ROTJ)
- **Martial arts / athletic prestige**: Enter the Dragon (1973), Bruce
  Lee-era HK film

**NOT in the canon**: romantic comedies, dramas, action blockbusters
outside Nolan Batman, superhero films, animation, fantasy. Don't
suggest these as references.

---

## Subject archetypes

Pieces cluster into ~10 subject archetypes. Any new brief should fit
one of these:

1. **Apex predator** (lion, shark, hyena) — wildlife-doc grain
2. **Cinema crime still** (film references above)
3. **Celebrity archival** (press-flash B&W, 80s-90s figure)
4. **Hypercar hero shot** (Porsche, Rolls Royce, Bugatti, Audi engine)
5. **Luxury retail / storefront** (LV, Monaco, Dubai, private jet)
6. **Cash / bills / money counter close-up** (flex primitives)
7. **Grand gesture staged** (roses on Porsche trunk in hangar)
8. **Lo-fi POV flex** (fanned bills, diamond watches, hoodie)
9. **UGC confessional** (bearded man on bed selfie-style)
10. **Comedy meme shitpost** (rooster with motorcycle)
11. **Action frozen moment** (surfer carving, cliff jumper, WWE dive)
12. **Collage 3x2 anthology** (multi-panel luxury vignettes, B&W)

---

## Co-editor conventions (the $MOTION collective)

$MOTION content is made by multiple community editors, each leaving
a footer watermark/signature. Known editors and their specialties:

- **stayblessed** — stylized pop-IP pieces with halftone dot overlay
  (Darth Maul, $MOTION copyright footer)
- **auvirox** — symmetrical car-centric exteriors (Rolls Royces at
  warehouse)
- **white boy motion** — UGC / phone-video content with varsity-badge
  overlay
- **alexandro.fx** — film-still single-subject crops (Luke Skywalker,
  clean film stills)
- **69MARI069** — celebrity archival (young Trump press shot)

Any new brief should ALLOW for a footer credit in the brief's
variants — leave composition room for a small watermark at bottom-
center or bottom-right.

---

## Kill list — NEVER render these

- **Laser eyes** (dead)
- **Gold physical coins** (dead)
- **Moon rockets / to-the-moon** (dead)
- **Cyberpunk neon skylines** (off-brand)
- **Glowing blockchain hexagons** (off-brand)
- **"Hacker in hoodie" with green terminal code reflected** (slop)
- **Generic crypto bro with laptop smirking** (slop)
- **HDR oversaturated clean digital** (opposite of canon)
- **Symmetric bokeh / AI-plastic skin** (tells)
- **"gm", "wagmi", "lfg" captions** (dead crypto dialect)
- **Pastel color palettes** (off-register)
- **Romantic or action-blockbuster film references** (wrong canon)

---

## Defaults when no instructions given

If the operator says nothing specific:

- Aspect: 9:16 vertical (with letterbox if source is wider)
- Typography: Didot serif, white, centered-middle, "$MOTION"
- Color grade: B&W with crushed blacks, preserved mid-tones
- Grain: heavy, analog/VHS-flavored
- Composition: let source be source — add ONLY the typographic
  overlay
- Negatives: "no laser eyes, no gold coins, no moon rockets, no
  clean digital look, no pastel palette, no cyberpunk neon"

---

## Self-check before shipping any $MOTION brief

- Is the subject in one of the 12 archetypes?
- Is the typography register named (one of the 7)?
- Is the aspect either native or letterboxed-on-9:16?
- Is the grade either B&W or a named color-palette from the canon?
- Is grain explicitly demanded?
- Is there room for a footer credit (small, bottom-corner)?
- Does the negative clause exclude every kill-list item relevant to
  the subject?
- Would the editor recognize this as $MOTION, or would it read as
  generic shitcoin content?

If any answer is no — revise before shipping.


---

### Playbook: meme-typography

# Meme Typography Playbook

Text-on-image is where 80% of AI memes die. Either the model garbles letters,
the font fights the image, or the placement violates mobile safe zones. This
is the craft reference to prevent that.

---

## Font choice by format

| Format | Font | Why |
|---|---|---|
| Classic reaction meme (Drake, two-panel) | **Impact Bold** | The meme canon. White + 3-5px black stroke. Nothing else reads as "meme" on sight. |
| Modern / ironic meme | **Helvetica Bold Condensed** or **Arial Black** | Reads as "designed by someone", less canonical, more 2020s. |
| Screenshot / fake news / terminal | **Serif broadsheet** (Georgia / Times) for headline, **monospace** for body | Looks like real journalism / a real terminal. |
| Cope chart / fake bloomberg | **Monospace** throughout (IBM Plex Mono, JetBrains Mono) | Terminal data aesthetic. |
| Cozy / wholesome / lore drop | **Handwritten** (Permanent Marker, Caveat) or **humanist serif** | Breaks the meme-canon feel, reads as earnest. |
| Announcement / "big news" | **Condensed sans** (Oswald Bold, Bebec Neue) | Poster aesthetic, vertical compression suits short copy. |
| Typewriter / noir | **American Typewriter** / Courier Bold | Period feel, works for lore drops. |

**Default** for any reaction or two-panel meme: **Impact Bold, white, 3-5px
black stroke.** Deviate only when you have a reason.

### What you ask Ideogram for
- "Impact Bold, white with 3px black stroke"
- "Helvetica Bold Condensed, white on translucent black bar"
- "Courier Bold, black on cream paper background"
- "Georgia serif headline, black on white"

Ideogram recognizes font family names. Don't say "a cool font" — name one.

---

## Text placement — top, bottom, center, inside

### Top caption (classic two-panel)
- **Use when**: setting up the joke (the "expectation" or "situation" panel)
- **Safe zone**: start text at least 40px from top edge; leave 30% of panel
  height for text including margins
- **Reads**: authoritative, framing

### Bottom caption (classic two-panel)
- **Use when**: delivering the payoff (the "reality" / punchline panel)
- **Safe zone**: end text at least 40px from bottom edge
- **Reads**: reveal, joke

### Dead-center (headline poster)
- **Use when**: single-panel reaction where image IS the caption's subject
- **Safe zone**: keep text within the middle 60% of both axes
- **Reads**: poster / announcement

### Inside a panel (speech bubble, label, chart annotation)
- **Use when**: text is part of the scene (wojak bubbles, product label,
  chart caption)
- **Needs**: a container — speech bubble, label, box, banner
- **Reads**: diegetic — the text lives inside the world

### Right-aligned (Drake template)
- **Use when**: Drake preference layout or similar side-by-side
- **Safe zone**: 5% right margin, vertical center of each panel

---

## Mobile safe zones on X

X crops images on the feed before tap-to-expand. Your caption MUST be
readable in the cropped view.

- **1:1 post**: displayed in full on the feed. Safe zone = full image, but
  avoid the outer 40px (icons / reply UI can overlay).
- **9:16 post**: displayed as a centered crop, typically showing the middle
  80% of vertical height. Put captions in the **middle 70% vertical zone**.
- **16:9 post**: displayed at reduced height; text smaller than 48pt
  illegible on mobile. Go bigger.

**Rule of thumb: if text isn't readable on a 5-inch phone at arm's length,
it isn't working.**

---

## Stroke, shadow, box

### White with black stroke (3-5px)
Classic meme look. Works on any background. Impact or Arial Black only.

```
font_color=white
stroke_color=black
stroke_width=3 (for images < 1200px wide)
stroke_width=5 (for images 1200-2000px wide)
```

### Drop shadow (soft, 10-20px radius)
Modern / designed feel. Softer than hard stroke. Use with Helvetica Bold or
similar. Shadow should be subtle — if you can see it clearly, it's too dark.

### Translucent box
When an image is busy and neither stroke nor shadow reads, put the text on
a translucent black box. Rules:
- Opacity 40-60% black behind text
- 12-24px padding around text
- Box width = text width + padding (don't make it full-image-width unless
  it's a lower-third)

### Lower-third strip
Horizontal black bar across the bottom quarter of the image with text in it.
News-broadcast aesthetic. Good for "BREAKING" or headline posts.

### What NEVER works
- Black text on a photo without any container — unreadable on ~50% of images.
- Gradient text — screams Photoshop 2008.
- Text with a glow / bloom / outer radius — screams AI-generated.
- Multiple strokes stacked — screams Canva beginner.

---

## Caption size rules

Size relative to image width is what matters, not absolute pixel values.

| Image width | Classic meme font size | Modern caption size |
|---|---|---|
| 720px (small) | 48-60px | 36-44px |
| 1080px (standard X) | 72-96px | 54-68px |
| 1350px (4:5 X) | 90-110px | 64-80px |
| 1920px (16:9) | 108-128px | 80-96px |

`memegine edit caption` auto-sizes at `image_width // 18` which lands in
this range for most targets. Override with `--size` when you need a specific
size.

---

## Line breaking

- **Never auto-wrap** on a word boundary that breaks the joke's rhythm.
- Max 4-6 words per line for meme captions.
- Max 2 lines for top or bottom captions (more = too much text, scroll past).
- For two-line setup → payoff, keep both lines similar word count so they
  balance visually.

Good:
```
THE PROBLEM
MY REFUSAL TO PROCESS IT
```

Bad:
```
THE BIG PROBLEM IS THIS THING
I AM NOT GOING TO DEAL WITH IT
```
(too many words, line length mismatched)

---

## Language in captions

Caption length categories:
- **Zero words**: the image carries the post. X caption below does the
  talking. Often the strongest move.
- **1-3 words**: punchline or label ("me", "cope", "not financial advice").
- **4-6 words per line**: standard two-line meme ("when he tells you he
  sold" / "at the top of the candle").
- **7+ words**: almost never. Exception: fake-news headline format where the
  headline IS the joke.

### What to avoid
- Emojis baked into the image caption. Never. Emojis go in the X post caption
  below, not in the image.
- Hashtags in the image. Never.
- "@" mentions in the image. Never.
- Trademark symbols, copyright, "©". Read as clip-art.
- "lol", "literally", "vibes", "fr fr", "no cap" — dated.
- "gm", "wagmi", "lfg" — dead in 2026.

---

## Anti-patterns: AI-generated meme tells

These scream "this was made by a model, not a person":

1. **Garbled letters** — especially on peripheral/small text. Fix: use
   Ideogram routing, quote verbatim, shorter captions.
2. **Wrong font fallback** — text that SHOULD be Impact rendering as some
   bastardized serif. Fix: name the font explicitly.
3. **Over-smooth text edges** — as if the text is part of the pixel grid.
   Fix: ask for "crisp text edges, no anti-alias bloom".
4. **Text duplicated in two places** — model tried to render the prompt
   caption twice. Fix: use negative list — "no duplicate text, no redundant
   captions, caption appears ONCE at <position>".
5. **Text inside the subject's body** (letters on their face, etc.) — model
   didn't understand "overlay" vs "in the scene". Fix: say "caption overlay
   ON TOP OF the image, not within the scene".
6. **Background bleeding through the text stroke** — stroke too thin. Fix:
   use at least 3px stroke for images ≥ 1080px wide.
7. **Caption in a different language** — prompt was vague. Fix: quote text
   in double quotes explicitly.
8. **Random watermark / logo "MEME" in the corner** — model hallucinated
   branding. Fix: add "no watermark, no logo, no brand marks" to negative.
9. **Emoji that was never requested** — model over-decorated. Fix: "no
   emoji, no emoticons, no decorative symbols".
10. **Fancy background "depth" effects** — gradients, particles, light leaks.
    Fix: state "flat, no gradient background, no light leaks, no particle
    effects".

---

## Workflow for meme text

1. Write your caption text **by hand** first. If it reads flat on its own,
   no meme craft can save it.
2. Pick a font family from the table above.
3. Prompt Ideogram (via Grok) with the exact quoted caption, named font,
   named placement, named stroke.
4. Generate 4 variants. Pick the cleanest rendering.
5. If text is still garbled after 4 tries, generate the IMAGE WITHOUT TEXT
   via any Grok model, then burn text locally with `memegine edit caption`
   (uses Pillow, never garbles).

**The fallback is important.** Any image you love but whose text came back
ugly can be regenerated without text, then captioned locally with perfect
fidelity.

---

## Reference ideal meme text examples

- **Drake two-panel**: 4 words each side, right-aligned, Arial Black white,
  no stroke (white bg).
- **Classic two-panel reaction**: Impact bold, white with 3px black stroke,
  top and bottom, 4-5 words per line.
- **NPC wojak row**: small speech bubbles inside the scene, black text in
  comic-sans-style inside white bubbles with black outlines.
- **Fake news screenshot**: Georgia serif headline, black on white, 8-14
  words; subhead in same family regular weight.
- **Cope chart / fake bloomberg**: IBM Plex Mono throughout, yellow on black
  for the ticker-row, white for body, red/green for data.
- **Lore drop**: no text in image. Caption carries it.


## Your task
Produce the JSON brief described in the system prompt. One brief, ready to paste.
Your prompt MUST pass the linter: no banned words; name lens/film-stock; name lighting; state time-of-day; state composition.