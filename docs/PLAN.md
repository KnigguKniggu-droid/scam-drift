# Scam Drift: implementation plan

Hackathon: Veritas AI International High School Hackathon 2026, AI + Finance track. The submission closed at 11:59 PM ET on Nov 17. The judged entry is git `main` at commit `01abbc9`; it does not change. Sections 1-4 below describe the **post-deadline v2 (Nov 18)** branch. The v1 plan is kept in section 5 for the record.

Every number in the project documents comes from `results/metrics.json`, written by `src/scam_drift.py`.

## 1. Data pipeline (v2)

```mermaid
flowchart LR
    A[UCI SMS Spam Collection<br/>2012, CC BY 4.0] --> N
    B[IMC25 smishing reports<br/>English + non-English with translation] --> N
    R1[India inbox, real legit SMS<br/>1,206 rows, MIT] --> N
    R2[MOZ-Smishing legit SMS<br/>1,608 rows, Portuguese, OpenRAIL-M] --> N
    C[Synthetic benign twins<br/>60 legit + 40 scam, written with AI assistance] --> N
    N[Shared normaliser<br/>links, phones, emails, money,<br/>dates, numbers -> tokens; lowercase] --> D[Dedupe after normalisation;<br/>drop legit texts also in UCI or IMC25]
    D --> Y[Report year from the<br/>screenshot timestamp]
    Y --> S[Splits]
    S --> S1[IMC25: dated <= 2021 train pool,<br/>2022-24 untouched test, undated eval only]
    S --> S2[India: brand OR template cluster groups,<br/>GroupShuffleSplit 50/50, seed 42]
    S --> S3[Synthetic legit: split by category 30/30]
    S --> S4[Cluster-safe test: drop 2022-24 rows<br/>whose template cluster was seen <= 2021]
    S1 & S2 & S3 & S4 --> M[Models, thresholds, metrics, figures<br/>results/metrics.json]
```

The India and MOZ texts contain first names. The pipeline downloads them from pinned Hugging Face revisions into the git-ignored `data/raw/extra/`. Only aggregates are written to `results/` and `figures/`.

## 2. Experiment design (v2)

```mermaid
flowchart TB
    subgraph TRAIN[Training data only]
        U1[UCI train 80%]
        E1[English scams dated 2015-2021]
        I1[India train groups]
        Y1[Synthetic legit train half]
    end
    U1 --> W12[word_2012 / char_2012]
    U1 --> WF[word_fixed / char_fixed<br/>= naive fix]
    E1 --> WF
    WF --> FB[fix_plus_benign<br/>+ synthetic half]
    Y1 --> FB
    WF --> FR[fix_plus_real_ham<br/>word and char]
    I1 --> FR
    W12 & WF & FB & FR --> TH[Thresholds: 5-fold out-of-fold on own training data<br/>cost 5 x miss + 1 x false alarm, or 10% false-alarm budget]
    TH --> SEL[Model selection on validation only:<br/>2021 scams + half of India train groups<br/>expected cost at an ASSUMED 5% scam rate]
    SEL --> TRI[Shipped three-tier triage<br/>char_fix_plus_real_ham, threshold 0.94]
    subgraph TEST[Untouched tests]
        T1[2022-24 scams, n=1,080; cluster-safe n=927]
        T2[India held-out groups, n=608]
        T3[MOZ legit, n=1,608, never trained on]
        T4[Synthetic legit held-out half, n=30]
        T5[Non-English scams: raw vs translation = oracle]
    end
    TRI --> TEST
    W12 & WF & FB & FR --> TEST
    TEST --> X[Analyses: source confound, URL ablation, Wilson CIs,<br/>half-life by report-date cohort, learning curve,<br/>multilingual, operating curve]
```

Rules: no test set is used for any choice. MOZ is never trained on. The tiers, the rules and the strict threshold were designed after the v1 results were seen (post-hoc), then frozen and evaluated.

## 3. Agentic build loop with AI-consult iterations

```mermaid
flowchart LR
    I[Idea consult<br/>ChatGPT, Gemini, Claude:<br/>rank 4 ideas] --> P[Plan<br/>question, user, data, metrics]
    P --> B[Build v1<br/>Claude Code writes pipeline,<br/>notebook, app, docs under<br/>the team's direction]
    B --> RT[Red-team consult<br/>8 method flaws]
    RT --> A[Audit<br/>leakage, shortcut,<br/>numbers vs metrics.json]
    A --> V1[v1 results review consult<br/>naive fix = 98% false alarms]
    V1 --> D[Data scout<br/>real modern legit SMS]
    D --> RH[Real-ham consult<br/>group by brand, keep MOZ untouched]
    RH --> B2[Build v2<br/>spec items 1-10]
    B2 --> A
    A --> T[Team review<br/>re-run, read code, explain]
    T --> S[Submit v1 / document v2]
```

Each consult and what we took from it: `docs/CONSULT_LOG.md`.

## 4. Timeline

All times are Eastern Time (ET). Each milestone has evidence: a git commit time or a file modification time. Bars between milestones show work periods; their start times are approximate. The idea consult happened before 18:00 on Nov 17; its exact time was not recorded.

```mermaid
gantt
    title Scam Drift build (ET)
    dateFormat YYYY-MM-DD HH:mm
    axisFormat %H:%M
    section v1 (judged)
    Datasets downloaded (file time)          :milestone, m1, 2026-11-17 18:02, 0m
    v1 pipeline commit f7e5488               :milestone, m2, 2026-11-17 18:22, 0m
    Data scout report docs/EXTRA_DATA.md     :milestone, m3, 2026-11-17 18:25, 0m
    Consults, real legit SMS probes          :done, w1, 2026-11-17 18:25, 268m
    Audit fixes commit 2fc226e               :milestone, m4, 2026-11-17 23:37, 0m
    Judged commit 01abbc9                    :milestone, m5, 2026-11-17 23:43, 0m
    section post-deadline v2 (Nov 18)
    v2 pipeline and triage                   :done, w2, 2026-11-17 23:59, 27m
    metrics.json v2 written (file time)      :milestone, m6, 2026-11-18 00:26, 0m
    README, notebook, plan, credits          :done, w3, 2026-11-18 00:30, 30m
    App switched to triage() (file time)     :milestone, m7, 2026-11-18 00:30, 0m
    User test of warning wording (planned)   :w4, 2026-11-18 01:00, 60m
```

"done" bars are finished; the last bar is planned, not done.

## 5. v1 plan (judged entry, for the record)

v1 trained `word_2012` / `char_2012` on UCI and the naive fix on UCI + 2015-2021 scams, chose thresholds by 5-fold out-of-fold cost (5:1), and evaluated on UCI test, 2022+ scams, undated scams, non-English scams and the benign twins. Its baselines were "always not scam" and "link or urgency word". Its results are Part B of `docs/RESULTS_DETAIL.md`.
