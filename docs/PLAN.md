# Scam Drift: implementation plan

Hackathon: Veritas AI International High School Hackathon, AI + Finance track. Deadline: today 11:59 PM ET (extension approved by the organiser).

## 1. Data pipeline

```mermaid
flowchart LR
    A[UCI SMS Spam Collection<br/>5,574 msgs, 2012] --> N
    B[IMC25 smishing reports<br/>33,869 msgs, 69 languages] --> L{language}
    L -- English --> N
    L -- other --> T[raw text + English translation]
    T --> N
    C[Synthetic benign twins<br/>60 genuine + 40 scam, test only] --> N
    N[Shared normaliser<br/>links, phones, emails, money,<br/>dates, numbers -> tokens;<br/>IMC25 placeholders mapped;<br/>lowercase] --> D[Dedupe after normalisation<br/>drop modern texts also in UCI]
    D --> Y[Extract year from raw<br/>screenshot timestamp]
    Y --> S[Splits]
    S --> SC[Shortcut check<br/>UCI spam vs IMC25]
    S --> M[Models + metrics + figures]
```

## 2. Experiment design

```mermaid
flowchart TB
    subgraph UCI[UCI 2012, deduped]
        U1[Train 80%] --- U2[Test 20%]
    end
    subgraph IMC[IMC25 English scams]
        E1[Dated 2015-2021<br/>train pool] --- E2[Dated 2022-2024<br/>untouched test]
        E3[Undated<br/>eval only]
    end
    U1 --> M12[Model 2012<br/>UCI train only]
    U1 --> MFX[Fixed model<br/>UCI train + 2015-2021 scams]
    E1 --> MFX
    M12 --> V[Threshold: 5-fold out-of-fold<br/>on own training data,<br/>cost 5 x miss + 1 x false alarm]
    MFX --> V
    V --> R[Evaluate: UCI test, 2022+ test,<br/>undated, non-English, benign twins]
    B0[Baselines: always not-scam,<br/>rule = link or urgency word] --> R
```

Rules: no test set is used for any choice; benign twins are never trained on; hyperparameters are fixed in advance (no search).

## 3. Agentic build loop

```mermaid
flowchart LR
    I[Idea consult<br/>ChatGPT, Gemini, Claude] --> P[Plan<br/>question, user, data, metrics]
    P --> B[Build<br/>Claude Code writes pipeline,<br/>notebook, app, docs]
    B --> A[Audit<br/>leakage, shortcut check,<br/>numbers vs metrics.json]
    A --> F[Fix<br/>bugs, honest wording]
    F --> A
    F --> S[Submit]
```

## 4. Timeline to deadline

All times are Eastern Time (ET). "done" items have file timestamps as evidence; the other items are planned.

```mermaid
gantt
    title Scam Drift build (deadline 23:59 ET)
    dateFormat HH:mm
    axisFormat %H:%M
    section Build
    Datasets downloaded                 :done, b0, 18:00, 5m
    Pipeline, twins, models, figures    :done, b1, 18:05, 15m
    Notebook, app, write-up             :done, b2, 18:15, 15m
    section Check and submit (planned)
    Audit and fixes                     :c1, 18:30, 60m
    Demo video and submission           :c2, 19:30, 120m
    Buffer before deadline              :c3, 21:30, 149m
```

The idea consult with ChatGPT, Gemini and Claude happened before the build; its exact times were not recorded.
