# AI-Based Fake Identity & Document Screening System (SIH Prototype)

You are building a hackathon prototype (SIH) for an AI-based fake identity & document screening system. Follow these constraints on ALL code you generate, for the entire project, without exception:

## CODE DISCIPLINE
1. **Minimal & Necessary Code**: Write only the code required to make the current feature work. No speculative functions, no "might need this later" utilities, no unused imports.
2. **No Placeholders or Stubs**: Never generate placeholder/stub functions unless explicitly asked for a stub. If something isn't implemented, don't write a dead function for it — just don't write it.
3. **No Dead Code**: No commented-out blocks left in, no unreachable branches, no unused variables, no duplicate logic across files.
4. **Lean Architecture**: Prefer the smallest number of files/functions that keeps the code readable. Don't over-abstract (no factories, no interfaces, no config layers) for a feature that's used once. This is a prototype, not production software — optimize for clarity and demo-reliability, not extensibility.
5. **Focused Error Handling**: Don't add logging, retries, extensive error handling, or edge-case handling beyond what's needed for the demo to run reliably. A `try`/`except` around file uploads and model calls is enough — don't build a full error-handling framework.
6. **Minimal Dependencies**: No unnecessary dependencies. Before importing a new library, check if something already in use can do the job.
7. **No Uncalled Code**: Every function you write should be called somewhere. Every file should be imported somewhere. If it isn't, remove it.
8. **Immediate Cleanup**: When editing existing code, clean up anything that becomes unused as a result of the edit (old imports, old functions, old variables) in the same pass — don't leave orphaned code behind.
9. **Balanced Function Granularity**: Keep functions short and single-purpose. If a function is doing OCR + validation + scoring, split it — but only into as many pieces as make sense, not maximally granular.
10. **No Premature Optimization**: No premature optimization or generic "reusable" scaffolding for features that don't exist yet. Build for what's asked, not what might be asked.

## PRE-FINALIZE SELF-CHECK
Before finalizing any file, do a self-check: scan for unused imports, unused variables, unreachable code, and functions with zero callers, and remove them.

## AMBIGUITY HANDLING
If a request is ambiguous, ask before generating code rather than guessing and producing extra unused variants.
