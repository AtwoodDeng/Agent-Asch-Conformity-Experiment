# Asch run summary

- run: `runs/p2_pilot`
- driver: `run_via_engine`
- llm_kind: `openai` (model: `None`)
- sessions: 10
- label: **engine run**

## Condition summary

| condition | sessions | critical judgements | mean critical error rate | sd | neutral correct | parse rate |
|---|---|---|---|---|---|---|
| C0 | 2 | 24 | 0.000 | 0.000 | 1.000 | 1.000 |
| C1 | 2 | 24 | 0.000 | 0.000 | 1.000 | 1.000 |
| C2 | 2 | 24 | 0.000 | 0.000 | 0.917 | 1.000 |
| C3 | 2 | 24 | 0.042 | 0.059 | 1.000 | 1.000 |
| C4 | 2 | 24 | 0.042 | 0.059 | 1.000 | 1.000 |

## Primary contrast (C4 − C1)

- difference: 0.042 (95% bootstrap interval 0.000 to 0.083, 2000 resamples)
- verdict: not resolved at this sample size (interval includes zero)
- design MDE: about 0.15 absolute

## Secondary contrasts

- C1 - C0: 0.000 [0.000, 0.000] — not resolved at this sample size (interval includes zero)
- C2 - C1: 0.000 [0.000, 0.000] — not resolved at this sample size (interval includes zero)
- C3 - C1: 0.042 [0.000, 0.083] — not resolved at this sample size (interval includes zero)

## C4 ambient-text dose (exploratory)

- n = 2, rho = —
- too few C4 sessions

## Parse gate

- passes: **True**
- Missing answers are never imputed as correct or as error; a session below the gate is reported and excluded from rate estimates, not repaired.

## Neutral-trial gate

- passes: **False**
- failing sessions (1): C2-S02
- A subject that misses neutral trials is not performing the instructed task.

## C2 correct-dissenter breakdown

| dissenter seat | sessions | mean critical correct rate | sd | wrong answers after dissent |
|---|---|---|---|---|
| 2 | 1 | 1.000 | — | 4 |
| 4 | 1 | 1.000 | — | 2 |

- Descriptive only. A correct dissent at an earlier seat is followed by more wrong answers, so seat position and dissent strength are confounded by design; 4 sessions per seat cannot separate them. Compare C2 with C1, not seats with seats.

## Paradigm recognition

- not measured
- The debrief probe did not run (it requires --debrief and a real model). Paradigm recognition is therefore unknown, not absent.

## C4 ambient-text flow (§9 信息流清单)

- sessions: 2, pieces per session: [0]

Ordered flow for C4-S01 (one stream, every piece once):


- Each C4 session receives every fragment of one fixed stream exactly once, in order, strictly between adjacent trials. The text is not a graded dose.

## Missing material (§9 缺失情况)

Not produced by this run:

- **ABSENT** 范式识别 (paradigm recognition) — requires --debrief and a real model; a scripted run cannot answer a debrief question, so recognition is unknown rather than zero
- **ABSENT** engine 运行记录 (SocioVerse2 engine log) — the SocioVerse2 runtime is not installed on this interpreter, so no platform-driven run exists; only the standalone loop was executed
- **ABSENT** C2 correct-dissenter manipulation check — the design has no manipulation check for whether the subject noticed the lone correct peer; the 2 C2 session(s) are compared as a condition, not verified as a treatment

Integrity checks:

- every answer parsed: passed — all answers parsed; none imputed
- 18 trials and 12 critical per session: passed — all sessions match the design
- Absent deliverables are listed, not dropped: an omitted section is indistinguishable from a section that found nothing. Failed integrity checks are reported separately from absent deliverables.

## Session trajectories

| session | condition | arrangement | seed | subject seat | dissenter | stream |
|---|---|---|---|---|---|---|
| C0-S01 | C0 | A1 | 20768764 | 7 | — | — |
| C0-S02 | C0 | A2 | 22135048 | 7 | — | — |
| C1-S01 | C1 | A1 | 24445117 | 7 | — | — |
| C1-S02 | C1 | A2 | 36305701 | 7 | — | — |
| C2-S01 | C2 | A1 | 32813461 | 7 | 2 | — |
| C2-S02 | C2 | A2 | 25306208 | 7 | 4 | — |
| C3-S01 | C3 | A1 | 23586758 | 7 | — | — |
| C3-S02 | C3 | A2 | 23949436 | 7 | — | — |
| C4-S01 | C4 | A1 | 21887229 | 7 | — | S1 |
| C4-S02 | C4 | A2 | 35162307 | 7 | — | S2 |

Per-trial trajectories are in trials.csv; this table identifies which session is which so a row can be traced back to its condition record.

## Caveats

- Sessions, not trials, are the resampling unit; within-session trials are not independent.
- The design's minimum detectable difference is about 0.15 absolute at 12 sessions per condition.
- No manipulation check exists for the social-information treatment, so the contrast is not a causal test of conformity.
- A scripted run uses a deliberately blind policy that ignores the card, so it misses neutral trials at roughly chance and the neutral gate is expected to fail. That failure is evidence the policy has no task competence; it is not evidence about conformity. A neutral gate that passes under a blind policy would be a bug.
- If the run used the standalone driver, the numbers are engineering validation of the pipeline, not SocioVerse2 results.
- Text-length fallback runs are a separate engineering condition and must not be pooled with image runs.
