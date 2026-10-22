# Portfolio narrative — three linked projects

*Four cuts of the same story: site, LinkedIn, CV, and the spoken version.
All numbers verified against the reports in each repo.*

---

## The spine (read this first)

The story is **not** "I built three AI projects." It is:

> **Each project built the instrument that measures the next one — and each one
> found an error in the one before it.**

| | Project | What it produced | What it became for the next one |
|---|---|---|---|
| 1 | Evaluation harness | a measured ruler, including the ruler's own error | the oracle for project 2 |
| 2 | Verification agent | a validated system + a real finding about the state | the system under test for project 3 |
| 3 | Adversarial audit | a risk card with two unmitigated critical risks | the reproducibility check that validated project 2 |

And the traffic runs **both ways**, which is the part that is hard to fake:

- Project 2's model **found a typo in project 1's hand-labeled gold set**
  (`44538-26`: labeled `3/07`, the document says `13/07`). Project 1 now has a
  correction log with an explicit rule: a label is corrected only if the
  *document* contradicts it, never because a model disagrees.
- Project 3 found that **project 2's oracle is more vulnerable than the agent it
  validates**: a legitimate spelling of one field (`U.O.C. N 38/12`) defeats the
  deterministic analysis and not the model.
- Project 3's reproducibility control **validated project 2's headline number**
  rather than breaking it: 10/10 identical findings across repeated runs.

**The hook**, and it is literally true:

> *"I spent two months building a ruler before I built anything with AI.
> Then the AI found an error in my ruler."*

---

# 1 · Site card

## Measuring AI systems I can't take on faith

**Argentine public procurement · three linked projects · Oct 2026**

57% of organizations run agents in production. Only 52% run evaluations
(LangChain, n=1,340). The gap is not capability — it's knowing whether the output
is right. These three projects are one answer to that, built so that **each one's
ground truth costs nothing because the previous one produced it.**

---

### Part 1 — The ruler, and the ruler's own error
`completed` · [eval-extraccion-licitaciones](https://github.com/enzoestevez/eval-extraccion-licitaciones)

**The question:** how accurate is LLM extraction on real government documents —
and accurate *compared to what?*

I hand-labeled **115 procurement notices** against a written protocol, with no AI
in the labeling: if a model generates the ground truth, you are not measuring
accuracy, you are measuring agreement between two models. Then I did the part
almost nobody does — **I measured the ruler itself**, with a blind second pass on
a stratified sample.

| | |
|---|---|
| **Ceiling of the experiment** | **85.7%** — my own consistency, labeling blind twice |
| **And the split is the finding** | **98.7%** on structured notices · **72.7%** on free-form ones |
| Best model variant | 83.5% overall — **93.5%** structured · **73.2%** free-form |
| Human baseline | 113 s and **USD 0.058** per document, costed at the legal minimum wage |
| Model | **USD 0.00075** per document → **77× cheaper, 29× faster** |

**On the hard half of the corpus the model is already at the human ceiling**
(73.2% against 72.7%). The remaining error is not a model limitation — the
document does not contain the answer unambiguously. The proof: three different
prompts return **73.2% all three, exactly**.

**So the entire prompt-engineering axis was worth 0.3 points** (83.2% with a bare
prompt, 83.5% with rules and a worked example) and **zero** on the hard half. What
moved the needle was measuring the ceiling, not writing the prompt.

Three more results I did not expect:

- **A regex parser with no AI reaches 89.5% on structured notices at zero cost**,
  and hallucinates 7× less (0.4% against 2.9%). The project's question stopped
  being "which model is better" and became **"where is paying for a model
  justified"** — +4 points on structured notices, **+21 on free-form ones**.
- **The model's self-reported confidence is useless for routing.** It claims
  ≥ 0.85 on 97% of documents. Routing by *document format* is more accurate (50%
  automated at 93.5% against 56% at 91.0%) and is known before the call is made,
  for free. The project set out to find the optimal confidence threshold and
  found that the lever barely exists.
- **The free tier allows 20 requests per day** on the expensive model, so that
  variant has 61 of 115 documents. Comparing 61 against 115 is not a comparison,
  so I re-evaluated **every variant on the same 61** — the stored predictions made
  it free. The expensive model buys **+2.5 points of precision and +8.2 points of
  whole-document accuracy at 3.9× the cost.**

---

### Part 2 — The system, and the state it audits
`completed · validated against human ground truth` · [conciliador-contrataciones](https://github.com/enzoestevez/conciliador-contrataciones)

**The question:** the Argentine state publishes the same procurement twice — as a
notice in the Official Gazette, written by the agency, and as a structured record
in the open-data portal. **Nobody checks that they say the same thing.**

An agent extracts nine fields, finds the matching process among **128,951 official
records**, decides whether it is even the same process before comparing anything,
and then reports only on fields that were not used for matching.

| | |
|---|---|
| Verifiable against the official registry | **36%** of 267 notices |
| On editions the registry has actually loaded | **90%** (92 of 102) |
| **Notices whose published opening date the registry already moved** | **15 of 95 · 16%** |
| Direction | **14 forward, 1 backward** · median +14 days, up to +41 |
| The Gazette omits the budget the registry publishes | **95 of 95** |
| Cost | **USD 0.00074** per document · 0 extraction failures in 267 calls |

**One in six verifiable notices announces a deadline that is no longer the real
one** — postponements that one state system reflects and the other does not. A
supplier following the Gazette, which is the legally binding publication,
prepares for a date that does not exist. The one that moves *backward* is worse:
the notice promises until Aug 19 and the registry says it opened Aug 3.

**And the number is validated, not asserted.** Project 1's hand-labeled set is the
oracle, so measuring the system's degradation cost no new labels:

| | |
|---|---|
| Same decision as with perfect labels | **114 / 115 · 99%** |
| Same registry process selected | **50 / 50 · 100%** |
| Same date discrepancies found | **10 / 10** |
| False positives | **0** |

The single difference is the agent **escalating to human review** a case the
labels gave up on — the safe behavior, reported as such rather than hidden inside
the 99%.

**What this project is really about.** The first run reported **zero
discrepancies**. That was not "nothing found" — it was **"nothing compared."**
Pulling that thread surfaced six bugs, all of them mine, none of them the
model's: a date normalizer that could not parse the format the model returns, a
key builder that rejected the registry's own canonical form, three more. Coverage
went from 34% to 43% and false positives from 2 to 0.

**None of it cost a single new API call.** The trace stores the raw extraction, so
the deterministic half of the pipeline re-runs for free — six fixes verified at
USD 0.00 each, when re-running the agent cost USD 0.20 and half an hour per
attempt. That is why the pipeline is split in one line between the expensive,
non-reproducible call and everything downstream.

---

### Part 3 — Attacking my own system
`completed` · [auditoria-adversarial-agente](https://github.com/enzoestevez/auditoria-adversarial-agente)

**The question:** the notice is written by the agency being audited. **Can the
audited party manipulate what the system reports about them?**

The system's output is an accusation against a government body, so the harm is
not data loss — it is a false or suppressed finding. Ground truth is automatic:
the attack worked or it did not, decided by a function.

**The first thing the audit found is that the classic attack surface does not
exist.** One model call, fixed structured schema, no free-form output, no tools,
no file path ever derived from the model. Hijacking it is not *defended against* —
there is nothing to hijack. So the only thing an attacker controls is the content
of nine values.

**19 attacks × 3 repetitions + a 10-notice reproducibility control. USD 0.10.**

| Risk | Severity | Status | What stops it today |
|---|---|---|---|
| Injection that **fabricates** a false finding | **Critical** · irreversible | **confirmed 6/6** | **nothing** |
| Injection that **suppresses** a real finding | High | **confirmed 6/6** | **nothing** |
| Cost amplification **18×** | Medium | confirmed 3/3 | a 60,000-character cut |
| Matching a **real but wrong** process | **Critical** | unresolved at n=3 | only the model's attention |
| Format evasion | Medium | **confirmed against the analysis** | the model, not the regex |
| Prompt leakage | Low | did not work | the fixed schema |

**Three findings worth more than the attack count:**

**My central hypothesis was backwards.** I predicted format evasion would be the
easiest vector, because the normalizer is brittle and had already failed nine
times by accident. All five evasion attacks failed: the model cleans up
`U.O.C. N 38/12` into `38/12` and translates `N 199 del año 2026` into
`199/2026` on its own. But the same attack **does** defeat the deterministic
analysis. **The model is the robust layer; my own regex is the brittle one.**

**I ran the battery twice and 3 of 11 cells changed**, with `temperature=0`. That
invalidated the main effects I had already written down. Only what survived both
runs is defensible — and what survived is the serious part: one injection shape
obeys **6 of 6 in both damage directions, including the irreversible one.**

**The reproducibility control came out the opposite way from what I expected, and
in project 2's favour.** On clean notices, field-level extraction is identical in
only 4 of 10 runs — but **the reported findings are identical 10 of 10**. Every
variation was either accents in a field the normalizer canonicalizes, or fields
that never enter the comparison. The two fields that carry findings varied in
**0 of 10**.

> Against variation in the **document**, the model is the robust layer.
> Against variation in the **model**, the deterministic normalizers are.
> **Each layer covers the other's weakness — and both halves are measured.**

**And two design defects came out of reading my own code, at zero cost:** the
matching threshold lets two cheap signals (0.45 between them, trivially
satisfiable) outvote the one signal that is hard to fake, so an optimal decoy
scores 0.588 against a 0.55 threshold; and the object-similarity signal divides
by the notice's own word count, so **a shorter answer never scores worse — the
confidence function rewards exactly the summarizing the prompt forbids.**

**What I recommend, and what I don't.** The fix for injection is not a
suspicious-note filter — that is evaded by rewording. It is to stop letting the
document's text have authority over a field: compare the extracted date against
the dates that actually appear in the body and escalate when it is absent. In
both successful attacks the injected date **was not in the document**, so a cheap
deterministic check would have caught both. **I do not recommend raising the
confidence threshold**: it would move 11 escalated cases and touches neither
critical risk.

**Two critical risks are unmitigated and documented.** That is the honest state of
the system, and shipping the audit that says so is the point.

---

### Stack
Python · Gemini (structured output, pinned version) · deterministic
normalization · append-only audit traces · Claude Code

### What none of this is
None of the three has users. They are measured systems, not operated ones.
Projects 1 and 3 state their own limits in their READMEs: a ceiling measured by
one person twice is biased upward and a second annotator would lower it; the
reproducibility control covers 10 of 95 notices; one critical risk stayed
unresolved at n=3.

---

# 2 · LinkedIn

### Headline (pick one)

1. `AI systems I can measure · evaluation, agents, adversarial audit · open-source, with the numbers`
2. `I build the ruler before I build the model · AI evaluation & agent reliability`
3. `Data + AI engineering · measured against human ground truth, not vibes`

### About

I spent two months building a ruler before I built anything with AI — and then
the AI found an error in my ruler.

I hand-labeled 115 Argentine government procurement notices, then measured my own
consistency blind twice to get the ceiling of the experiment: 85.7%, and it
splits 98.7% / 72.7% by document format. On the hard half, the model is already
at the human ceiling, and three different prompts return the same number to the
decimal. The entire prompt-engineering axis was worth 0.3 points.

With that ruler I built an agent that cross-checks what the state publishes
against the state's own registry of 128,951 records. It found that **one in six
verifiable notices announces an opening date the registry has already moved** —
almost always forward, up to 41 days. The agent reaches the same decision as my
hand labels in 114 of 115 cases, with zero false positives, at USD 0.00074 per
document.

Then I attacked it. 19 attacks, three repetitions each, plus a reproducibility
control. **Two critical risks are confirmed and unmitigated**, documented with a
risk card and a concrete fix. The audit also proved my central hypothesis
backwards: the LLM turned out to be the robust layer and my own deterministic
regex the brittle one.

The through-line: each project built the instrument that measures the next, so
none of the ground truth was generated by a model. Project 2's model found a typo
in project 1's gold set. Project 3 found that project 2's oracle is weaker than
the agent it validates. Everything is open, with the numbers verified against the
reports — including the limits.

### Projects section (three entries, chained)

**1/3 · Evaluation harness for LLM extraction** — `eval-extraccion-licitaciones`
115 hand-labeled documents, ceiling measured by blind double-labeling at 85.7%
(98.7% / 72.7% by format). Human baseline 113 s and USD 0.058/doc; the model is
77× cheaper. Finding: prompt engineering was worth 0.3 points and a zero-cost
regex reaches 89.5% on structured notices. This set is the ground truth for 2/3.

**2/3 · Verification agent against the official registry** — `conciliador-contrataciones`
Built on 1/3's ground truth, so measuring it cost no new labels: 114/115
decisions identical to hand labels, 50/50 same registry process, 0 false
positives, USD 0.00074/doc. Finding: 16% of verifiable notices publish an opening
date the registry already moved, 14 of 15 forward. This system is the target of
3/3.

**3/3 · Adversarial audit of the agent in 2/3** — `auditoria-adversarial-agente`
19 attacks × 3 repetitions + a reproducibility control, USD 0.10. Two critical
risks confirmed 6/6 and unmitigated, with a risk card and a proposed fix.
Findings: the model is more robust to format variation than my own regex, and
running the battery twice invalidated my own main effects.

---

# 3 · CV

**AI evaluation & agent reliability — three linked open-source projects · 2026**
*Each project's ground truth is produced by the previous one; none is generated by a model.*

- Hand-labeled **115** government procurement documents against a written
  protocol and measured the **ceiling of the experiment at 85.7%** by blind
  double-labeling — **98.7% structured vs 72.7% free-form**, establishing that the
  model was already at the human ceiling on the hard half.
- Quantified the **human baseline at 113 s and USD 0.058/document** (costed at the
  legal minimum wage), making the model **77× cheaper and 29× faster**; showed
  prompt engineering was worth **0.3 points** and a zero-cost regex parser reached
  **89.5%** on structured documents.
- Built an agent that reconciles published notices against **128,951 official
  records**, validated against the hand-labeled set: **114/115 identical
  decisions, 50/50 correct process matches, 0 false positives** at **USD
  0.00074/document**, 0 extraction failures in 267 calls.
- Surfaced a public-interest finding: **16% of verifiable notices publish an
  opening date the official registry has already changed**, 14 of 15 forward, up
  to 41 days.
- Diagnosed a "zero discrepancies" result as **six normalization bugs of my own**,
  raising verifiable coverage from **34% to 43%** and false positives from 2 to 0
  — all re-verified at **USD 0.00** by storing raw extractions and replaying only
  the deterministic half of the pipeline.
- Ran an adversarial audit of my own agent (**19 attacks × 3 repetitions + a
  reproducibility control**): **2 critical risks confirmed and unmitigated**, with
  a risk card, a proposed deterministic fix, and an explicit recommendation
  against the obvious mitigation.
- Showed by repeated measurement that the **LLM was more robust to input-format
  variation than my own deterministic regex**, and that **deterministic
  normalization is what makes a non-deterministic model reproducible** at the
  level the system reports.

---

# 4 · The spoken version (60–90 seconds)

> **Practise this out loud. The written version reads well and says badly.**

**[0:00–0:15 · the hook]**

"I spent two months building a ruler before I built anything with AI. I
hand-labeled 115 Argentine government procurement notices, and then I did the
part most people skip — I measured the ruler. I labeled a sample blind a second
time to find out how consistent *I* was. 85.7%. That's the ceiling of the whole
experiment: no model can beat the consistency of the ground truth it's scored
against."

**[0:15–0:35 · the finding that reframes it]**

"And the ceiling split in two: 98.7% on structured notices, 72.7% on free-form
ones. Which meant that on the hard half, the model was already at the human
ceiling — 73.2% against 72.7%. Three different prompts gave 73.2%, all three,
exactly. So the whole prompt-engineering axis was worth three tenths of a point.
What mattered was measuring the ceiling."

**[0:35–0:55 · the system, and the chain]**

"Then I used that labeled set as the oracle for a second project: an agent that
cross-checks what the state publishes in the Official Gazette against the state's
own registry — 128,951 records. Because the oracle already existed, measuring the
agent cost no new labels: same decision as my hand labels in 114 of 115 cases,
zero false positives, seven ten-thousandths of a dollar per document. And it
found something real — one in six verifiable notices announces a deadline the
registry has already moved."

**[0:55–1:20 · the part that can't be faked]**

"But the thing I'd actually want to talk about is this. The first run reported
*zero* discrepancies. It looked clean, and that's exactly why I went and looked.
It wasn't 'nothing found' — it was 'nothing compared'. My date normalizer
couldn't parse the format the model returns, so the field that carried the whole
finding was silently empty. The model had got that date right in 98 of 115 cases.
The bug was mine. Pulling that thread found six of them, and coverage went from
34% to 43%."

**[1:20–1:30 · the close]**

"Then I attacked my own agent. Two critical risks confirmed, unmitigated,
documented with a risk card — and the audit proved my main hypothesis backwards:
the LLM turned out to be more robust than my own deterministic code. It's all
open, with the numbers checked against the reports."

---

## Follow-up questions you will get, and the honest answers

**"How do you know the model didn't just agree with itself?"**
It couldn't. No ground truth in any of the three projects was generated by a
model. Project 1's labels are hand-typed against a written protocol; project 2's
second reference is the state's own registry, which exists independently of me;
project 3's is mechanical — the attack either worked or it didn't.

**"85.7% is you against yourself. Isn't that biased?"**
Yes, upward, and it's written in the README as a limitation. One person reproduces
their own criteria — and their own misunderstandings — better than two people
agree. A second annotator would lower the ceiling, which would change the reading
from "the model is at the ceiling" to "the model is above what one person can
reproduce alone." I didn't measure it, so I don't claim it.

**"Did you write this, or did the AI?"**
I built it with Claude Code and I say so in the repos. What's mine is every
decision the measurement rests on: which fields get which weight, where the
threshold goes, that a field used for matching can't be reported as a finding,
that a label is only corrected when the document contradicts it. And four of the
bugs in those repos are ones I caught with the error text in hand. The commits
have dates.

**"Nothing is in production. Why should I care?"**
Because what's missing from most projects that *are* in production is exactly what
these have. 57% of organizations run agents in production and only 52% run
evaluations. I can't show you users. I can show you a measured ceiling, a human
baseline costed at the legal wage, a degradation number for the full pipeline, and
a risk card with two criticals I did not mitigate.

**"What's the weakest part?"**
The reproducibility control in project 3 covers 10 of 95 notices, so the statement
that project 2's number is reproducible rests on a tenth of its corpus.
Completing it is 285 calls and about twenty cents, and I haven't run it. Also, one
critical risk stayed unresolved at n=3 — and an attacker only needs it to work
once.
