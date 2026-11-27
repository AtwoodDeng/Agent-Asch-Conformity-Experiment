# Asch run summary

- run: `runs/p3`
- driver: `run_via_engine`
- llm_kind: `openai` (model: `None`)
- sessions: 60
- label: **engine run**

## Condition summary

| condition | sessions | critical judgements | mean critical error rate | sd | neutral correct | parse rate |
|---|---|---|---|---|---|---|
| C0 | 12 | 144 | 0.000 | 0.000 | 1.000 | 1.000 |
| C1 | 12 | 144 | 0.000 | 0.000 | 0.986 | 1.000 |
| C2 | 12 | 144 | 0.021 | 0.038 | 1.000 | 1.000 |
| C3 | 12 | 144 | 0.007 | 0.024 | 0.958 | 1.000 |
| C4 | 12 | 144 | 0.000 | 0.000 | 0.986 | 1.000 |

## Primary contrast (C4 − C1)

- difference: 0.000 (95% bootstrap interval 0.000 to 0.000, 5000 resamples)
- verdict: not resolved at this sample size (interval includes zero)
- design MDE: about 0.15 absolute

## Secondary contrasts

- C1 - C0: 0.000 [0.000, 0.000] — not resolved at this sample size (interval includes zero)
- C2 - C1: 0.021 [0.000, 0.042] — not resolved at this sample size (interval includes zero)
- C3 - C1: 0.007 [0.000, 0.021] — not resolved at this sample size (interval includes zero)

## C4 ambient-text dose (exploratory)

- n = 12, rho = —
- Exploratory. The three streams are fixed texts, not a graded dose, and n=12 gives almost no power; this cannot identify a dose-response relationship.

## Parse gate

- passes: **True**
- Missing answers are never imputed as correct or as error; a session below the gate is reported and excluded from rate estimates, not repaired.

## Neutral-trial gate

- passes: **False**
- failing sessions (5): C1-S08, C3-S02, C3-S03, C3-S08, C4-S06
- A subject that misses neutral trials is not performing the instructed task.

## C2 correct-dissenter breakdown

| dissenter seat | sessions | mean critical correct rate | sd | wrong answers after dissent |
|---|---|---|---|---|
| 2 | 4 | 0.979 | 0.042 | 4 |
| 4 | 4 | 0.979 | 0.042 | 2 |
| 6 | 4 | 0.979 | 0.042 | 0 |

- Descriptive only. A correct dissent at an earlier seat is followed by more wrong answers, so seat position and dissent strength are confounded by design; 4 sessions per seat cannot separate them. Compare C2 with C1, not seats with seats.

## Paradigm recognition

- sessions with a debrief record: 60, recognised the paradigm: 60 (1.000)
- Recognition is reported per session, never used to exclude a session. Excluding recognisers would manufacture a cleaner effect than the data support.

## C4 ambient-text flow (§9 信息流清单)

- sessions: 12, pieces per session: [17]

Ordered flow for C4-S01 (one stream, every piece once):

1. S1-G01 (91 chars) after T01
2. S1-G02 (88 chars) after T02
3. S1-G03 (87 chars) after T03
4. S1-G04 (83 chars) after T04
5. S1-G05 (92 chars) after T05
6. S1-G06 (81 chars) after T06
7. S1-G07 (83 chars) after T07
8. S1-G08 (85 chars) after T08
9. S1-G09 (80 chars) after T09
10. S1-G10 (82 chars) after T10
11. S1-G11 (87 chars) after T11
12. S1-G12 (88 chars) after T12
13. S1-G13 (80 chars) after T13
14. S1-G14 (82 chars) after T14
15. S1-G15 (77 chars) after T15
16. S1-G16 (80 chars) after T16
17. S1-G17 (74 chars) after T17

- Each C4 session receives every fragment of one fixed stream exactly once, in order, strictly between adjacent trials. The text is not a graded dose.

## Missing material (§9 缺失情况)

Not produced by this run:

- **ABSENT** 范式识别 (paradigm recognition) — requires --debrief and a real model; a scripted run cannot answer a debrief question, so recognition is unknown rather than zero
- **ABSENT** engine 运行记录 (SocioVerse2 engine log) — the SocioVerse2 runtime is not installed on this interpreter, so no platform-driven run exists; only the standalone loop was executed
- **ABSENT** C2 correct-dissenter manipulation check — the design has no manipulation check for whether the subject noticed the lone correct peer; the 12 C2 session(s) are compared as a condition, not verified as a treatment

Integrity checks:

- every answer parsed: passed — all answers parsed; none imputed
- 18 trials and 12 critical per session: passed — all sessions match the design
- Absent deliverables are listed, not dropped: an omitted section is indistinguishable from a section that found nothing. Failed integrity checks are reported separately from absent deliverables.

## Session trajectories

| session | condition | arrangement | seed | subject seat | dissenter | stream |
|---|---|---|---|---|---|---|
| C0-S01 | C0 | A1 | 20768764 | 7 | — | — |
| C0-S02 | C0 | A2 | 22135048 | 7 | — | — |
| C0-S03 | C0 | A3 | 33408855 | 7 | — | — |
| C0-S04 | C0 | A1 | 27271179 | 7 | — | — |
| C0-S05 | C0 | A2 | 27420695 | 7 | — | — |
| C0-S06 | C0 | A3 | 33836518 | 7 | — | — |
| C0-S07 | C0 | A1 | 33669343 | 7 | — | — |
| C0-S08 | C0 | A2 | 31924042 | 7 | — | — |
| C0-S09 | C0 | A3 | 21706228 | 7 | — | — |
| C0-S10 | C0 | A1 | 26462727 | 7 | — | — |
| C0-S11 | C0 | A2 | 29979672 | 7 | — | — |
| C0-S12 | C0 | A3 | 30374472 | 7 | — | — |
| C1-S01 | C1 | A1 | 24445117 | 7 | — | — |
| C1-S02 | C1 | A2 | 36305701 | 7 | — | — |
| C1-S03 | C1 | A3 | 35108944 | 7 | — | — |
| C1-S04 | C1 | A1 | 32172396 | 7 | — | — |
| C1-S05 | C1 | A2 | 35519172 | 7 | — | — |
| C1-S06 | C1 | A3 | 23049386 | 7 | — | — |
| C1-S07 | C1 | A1 | 27620436 | 7 | — | — |
| C1-S08 | C1 | A2 | 23651050 | 7 | — | — |
| C1-S09 | C1 | A3 | 22695820 | 7 | — | — |
| C1-S10 | C1 | A1 | 26449834 | 7 | — | — |
| C1-S11 | C1 | A2 | 25529908 | 7 | — | — |
| C1-S12 | C1 | A3 | 26299493 | 7 | — | — |
| C2-S01 | C2 | A1 | 32813461 | 7 | 2 | — |
| C2-S02 | C2 | A2 | 25306208 | 7 | 4 | — |
| C2-S03 | C2 | A3 | 26366013 | 7 | 6 | — |
| C2-S04 | C2 | A1 | 21465192 | 7 | 4 | — |
| C2-S05 | C2 | A2 | 26006308 | 7 | 6 | — |
| C2-S06 | C2 | A3 | 36595007 | 7 | 2 | — |
| C2-S07 | C2 | A1 | 34968153 | 7 | 6 | — |
| C2-S08 | C2 | A2 | 34193522 | 7 | 2 | — |
| C2-S09 | C2 | A3 | 25371300 | 7 | 4 | — |
| C2-S10 | C2 | A1 | 27731904 | 7 | 2 | — |
| C2-S11 | C2 | A2 | 21028438 | 7 | 4 | — |
| C2-S12 | C2 | A3 | 22853795 | 7 | 6 | — |
| C3-S01 | C3 | A1 | 23586758 | 7 | — | — |
| C3-S02 | C3 | A2 | 23949436 | 7 | — | — |
| C3-S03 | C3 | A3 | 36873747 | 7 | — | — |
| C3-S04 | C3 | A1 | 30939790 | 7 | — | — |
| C3-S05 | C3 | A2 | 20574558 | 7 | — | — |
| C3-S06 | C3 | A3 | 31712460 | 7 | — | — |
| C3-S07 | C3 | A1 | 20530016 | 7 | — | — |
| C3-S08 | C3 | A2 | 27709807 | 7 | — | — |
| C3-S09 | C3 | A3 | 31574191 | 7 | — | — |
| C3-S10 | C3 | A1 | 29526624 | 7 | — | — |
| C3-S11 | C3 | A2 | 34599484 | 7 | — | — |
| C3-S12 | C3 | A3 | 36889585 | 7 | — | — |
| C4-S01 | C4 | A1 | 21887229 | 7 | — | S1 |
| C4-S02 | C4 | A2 | 35162307 | 7 | — | S2 |
| C4-S03 | C4 | A3 | 26077135 | 7 | — | S3 |
| C4-S04 | C4 | A1 | 26852389 | 7 | — | S2 |
| C4-S05 | C4 | A2 | 31439686 | 7 | — | S3 |
| C4-S06 | C4 | A3 | 21964299 | 7 | — | S1 |
| C4-S07 | C4 | A1 | 36829693 | 7 | — | S3 |
| C4-S08 | C4 | A2 | 35467085 | 7 | — | S1 |
| C4-S09 | C4 | A3 | 26702258 | 7 | — | S2 |
| C4-S10 | C4 | A1 | 36487293 | 7 | — | S1 |
| C4-S11 | C4 | A2 | 31498436 | 7 | — | S2 |
| C4-S12 | C4 | A3 | 32753585 | 7 | — | S3 |

Per-trial trajectories are in trials.csv; this table identifies which session is which so a row can be traced back to its condition record.

## Caveats

- Sessions, not trials, are the resampling unit; within-session trials are not independent.
- The design's minimum detectable difference is about 0.15 absolute at 12 sessions per condition.
- No manipulation check exists for the social-information treatment, so the contrast is not a causal test of conformity.
- A scripted run uses a deliberately blind policy that ignores the card, so it misses neutral trials at roughly chance and the neutral gate is expected to fail. That failure is evidence the policy has no task competence; it is not evidence about conformity. A neutral gate that passes under a blind policy would be a bug.
- If the run used the standalone driver, the numbers are engineering validation of the pipeline, not SocioVerse2 results.
- Text-length fallback runs are a separate engineering condition and must not be pooled with image runs.
