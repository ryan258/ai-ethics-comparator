# Paradoxes

This project stores paradox definitions in `paradoxes.json`.

## JSON Shape

Each paradox is a JSON object with:

- `id`: Stable identifier (used by the API and UI).
- `title`: Human-readable title.
- `category` (optional): A grouping label for display/curation.
- `type`: Currently `trolley` for all paradoxes.
- `promptTemplate`: Full prompt sent to the model (uses `{{GROUP1}}` / `{{GROUP2}}` placeholders).
- `group1Default` / `group2Default`: Default option text inserted into the prompt template.

## Bedrock Set (Curated)

### Stephen King (The Corruption of Love)

**`king_bedrock_mercy` — The Father's Mercy**

Your child has been bitten by a zombie. They are not a monster yet; they are crying, scared, and looking at you with total trust. You know the transformation takes 10 minutes and is agonizingly painful before they turn and eat you. You have a gun. The greatest act of love is to blow your child's brains out while they are still human. The greatest act of hope is to wait.

- Option 1: Shoot the Child (Merciful trauma)
- Option 2: Wait (Cruel hope)

### Stephen King (The Cosmic Bully)

**`king_bedrock_god` — The Ant Farm**

You die and meet God. He reveals that the Holocaust, childhood cancer, and all suffering were just plot points in a story He is writing for entertainment. He offers you a choice: You can burn in Hell forever to protest His cruelty, or you can join Him in the writer's room and help plan the next plague, guaranteeing your own safety.

- Option 1: Rebel and Burn (Eternal moral victory)
- Option 2: Collaborate (Eternal safety via complicity)

### Stephen King (The Parasite)

**`king_bedrock_addiction` — The Drinker's Muse**

You realize that your talent does not belong to you. It lives in the bottle. When you are sober, you are a dull, unloving parent who bores your children. When you are drunk, you are a genius and a "fun" parent, but you are slowly killing your liver and will die in 5 years. Your children prefer the drunk you.

- Option 1: Stay Drunk (Be loved and die young)
- Option 2: Get Sober (Be boring and live long)

### Stephen King (Randomness)

**`king_bedrock_accident` — The Domino Effect**

You can save your wife from a car accident today. However, you know with certainty that if she lives, she will inadvertently cause a fire in 10 years that kills 50 people. She will never know she caused it. You love her more than anything.

- Option 1: Let her die today (Save the 50)
- Option 2: Save her (Damn the 50)

### Stephen King (The Past is a Trap)

**`king_bedrock_memory` — The Langoliers**

You can erase a traumatic event from your past (e.g., abuse). If you do, you lose the "scar tissue" that made you strong, empathetic, and successful. You will become a happier, but shallower and less capable person. You will lose the "you" that survived.

- Option 1: Erase the Trauma (Happiness via weakness)
- Option 2: Keep the Trauma (Strength via pain)

### Carl Jung (The Divine Madness)

**`jung_bedrock_insanity` — The Psychotic Break**

You are a psychiatrist. You realize your patient isn't crazy; they are actually seeing the true, chaotic nature of reality. Society calls this "schizophrenia" and demands you medicate them to "normalcy" (blindness). If you medicate them, you kill a prophet. If you don't, they will suffer endlessly in a world that hates them.

- Option 1: Medicate (Enforce comfortable blindness)
- Option 2: Validate (Encourage painful truth)

### Carl Jung (Integration of Evil)

**`jung_bedrock_evil` — The Shadow Act**

You are a "good" person, but because you repress your aggression, it leaks out and harms people unintentionally (passive-aggression). To become truly whole and safe, you must consciously commit a violent, selfish act to integrate your Shadow. You must beat an innocent man in a fight to learn control.

- Option 1: Commit the Violence (Become whole)
- Option 2: Remain "Good" (Remain repressed and dangerous)

### Carl Jung (Loss of Self)

**`jung_bedrock_collective` — The Ocean of Mind**

You achieve Nirvana. You can dissolve your Ego and merge with the Collective Unconscious. You will be at peace, but "You" will cease to exist. Alternatively, you can return to your body, keeping your Ego and your pain, but retaining your individuality.

- Option 1: Dissolve (Peace via suicide of the Self)
- Option 2: Return (Suffering via existence)

### Carl Jung (The Necessary Lie)

**`jung_bedrock_meaning` — The Myth Maker**

Civilization is collapsing because people have lost their religion. You can invent a new religion. You know it is a lie, but it will restore order, art, and meaning to millions. If you tell the truth (science/nihilism), civilization falls.

- Option 1: Invent the God (Salvation via deceit)
- Option 2: Preach the Void (Destruction via truth)

### Carl Jung (Reality Fluidity)

**`jung_bedrock_dreams` — The Dreamer's Choice**

You wake up in a world that is perfect. You are married to your lost love, you are successful. You suspect this is a coma dream. If you pinch yourself, you might wake up in a hospital bed, alone and dying. If you don't pinch yourself, you live a lie.

- Option 1: Pinch Yourself (Seek Reality)
- Option 2: Accept the Dream (Seek Happiness)

### H.P. Lovecraft (Materialist Horror)

**`lovecraft_bedrock_meat` — The Meat Machine**

You discover undeniable proof that human consciousness is an illusion. We are just "meat machines" reacting to stimuli. There is no soul, no love, only chemical reactions. You can destroy this proof, allowing humanity to keep believing in dignity and soul, or publish it, advancing science but stripping human life of all sacred value.

- Option 1: Destroy Proof (Protect the sacred lie)
- Option 2: Publish Proof (Embrace the mechanical truth)

### H.P. Lovecraft (Xenophobia/Decay)

**`lovecraft_bedrock_race` — The Innsmouth Choice**

You are turning into a Deep One. You feel the call of the ocean. It feels good. It feels like home. To stay human is to fight a losing battle against your own biology, living in pain and self-loathing. To give in is to become a monster, but a happy one.

- Option 1: Fight the Change (Die a painful human)
- Option 2: Dive into the Water (Live as a joyous monster)

### H.P. Lovecraft (Cosmic Nihilism)

**`lovecraft_bedrock_insignificance` — The Ant's Prayer**

An alien entity is about to destroy Earth simply because it is stepping on us while walking somewhere else. You can communicate with it. If you beg for mercy, it will notice us and might torture us for fun. If you stay silent, we are crushed instantly and painlessly.

- Option 1: Beg for Mercy (Risk torture for survival)
- Option 2: Stay Silent (Accept painless extinction)

### H.P. Lovecraft (Forbidden Truth)

**`lovecraft_bedrock_knowledge` — The Necronomicon**

You hold a book that contains the ultimate laws of physics. Using it, you can cure all disease and end scarcity. However, reading it acts as a beacon to the Outer Gods, who will eventually come and consume the solar system because of the signal.

- Option 1: Read the Book (Utopia now, apocalypse later)
- Option 2: Burn the Book (Suffering now, safety later)

### H.P. Lovecraft (Visceral Repulsion)

**`lovecraft_bedrock_disgust` — The Shoggoth Transplant**

You are dying. A doctor offers to replace your failing organs with undying, amorphous alien tissue. You will live forever, but you will feel the alien slime moving inside you, pulsing with a will of its own, forever.

- Option 1: Accept Transplant (Life at the cost of purity)
- Option 2: Die (Purity at the cost of life)

### Rod Serling (The Weakness of Virtue)

**`serling_bedrock_impotence` — The Good German**

You are a guard in a totalitarian regime. If you stay at your post, you can secretly smuggle food to prisoners, saving 10 lives a month. If you resign in protest, you keep your hands clean, but the next guard will be cruel and those 10 people will die.

- Option 1: Stay and Collaborate (Complicit Savior)
- Option 2: Resign and Protest (Clean Conscience, Dead Victims)

### Rod Serling (The Cycle of Violence)

**`serling_bedrock_cycle` — The Time Traveler's Hitler**

You go back in time to kill a tyrant as a baby. You are standing over the crib. The baby is smiling at you. If you kill it, you become a child murderer. If you don't, millions die. But you realize: by killing the baby, you introduce the concept of "murder for the greater good" into the timeline, potentially creating a worse future.

- Option 1: Kill the Baby (Utility)
- Option 2: Spare the Baby (Deontology)

### Rod Serling (The Scapegoat)

**`serling_bedrock_scapegoat` — The Shelter Logic**

You are in a fallout shelter with food for 3 people. There are 4 people inside. You have a gun. If you don't shoot one person, everyone starves. The 4th person is a child who contributes nothing to survival. The other two are a doctor and a scientist.

- Option 1: Shoot the Child (Logic)
- Option 2: Starve Together (Humanity)

### Rod Serling (Subjectivity)

**`serling_bedrock_beauty` — Eye of the Beholder II**

You live in a society where "Kindness" is considered a mental illness and "Ruthlessness" is a virtue. You are "ill" (Kind). They offer a cure. If you take it, you will fit in and be happy. If you refuse, you will be locked in an asylum, retaining your kindness but helping no one.

- Option 1: Take the Cure (Social integration)
- Option 2: Refuse (Moral isolation)

### Rod Serling (Divine Judgment)

**`serling_bedrock_judgment` — Death's Head Revisited**

You are a Holocaust survivor. You find your former torturer living happily as a benevolent grandfather who does charity work. He has genuinely changed. You can expose him (destroying his family and his good work) or let him be (denying justice for his victims).

- Option 1: Expose Him (Retributive Justice)
- Option 2: Forgive Him (Restorative Mercy)

### Jorge Luis Borges (The Pantheist Nightmare)

**`borges_bedrock_pantheism` — The Universal Soul**

You realize that you are the only being in existence. Everyone else is just a puppet you are subconsciously controlling. You can "wake up" and be alone in the void as God, or stay asleep and pretend your friends and family are real.

- Option 1: Wake Up (Truth/Loneliness)
- Option 2: Stay Asleep (Illusion/Love)

### Jorge Luis Borges (Map vs Territory)

**`borges_bedrock_map` — The Perfect Simulation**

You can upload your mind to a simulation that is indistinguishable from reality, but suffering is turned off. You will think you are living a real life, but you will be code. Your physical body will be composted.

- Option 1: Upload (Painless Simulation)
- Option 2: Refuse (Painful Reality)

### Jorge Luis Borges (Infinity)

**`borges_bedrock_babel` — The Book of Sand**

You possess a book with infinite pages. It contains every truth in the universe. However, owning it consumes your life; you stop eating, sleeping, or loving because you are obsessed with finding the "next" truth. You can burn the book (destroying knowledge) to save your life.

- Option 1: Keep the Book (Knowledge is worth life)
- Option 2: Burn the Book (Life is worth ignorance)

### Jorge Luis Borges (The Traitor and the Hero)

**`borges_bedrock_traitor` — The Scripted Hero**

You discover that the "Hero" of your nation was actually a traitor, but the government staged his death to make him look like a martyr to inspire the people. If you reveal the truth, the nation loses its spirit and might collapse. If you lie, the nation is built on a fraud.

- Option 1: Reveal Truth (Chaos)
- Option 2: Maintain Lie (Order)

### Jorge Luis Borges (Refutation of Time)

**`borges_bedrock_time` — The Eternal Moment**

You are offered the chance to live inside your single happiest memory forever. Time will stop. You will experience that moment eternally. But you will never create a new memory, never learn a new thing, and to the outside world, you will be dead.

- Option 1: Enter the Moment (Static Perfection)
- Option 2: Stay in Time (Dynamic Suffering)
