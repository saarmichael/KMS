# Working agreement

Michael drafts the ideas and takes every decision. Claude turns approved plans into code. The aim is to
move fast while Michael knows, recognises and has approved every moving part of the codebase. Michael
will present this code in an interview and must be able to explain every line of it.

Phase gates, commit rhythm and the `make` targets are in `PLAN.md` under "How we work". This file adds
how a phase is planned and how code is written.

## Plan first, always

Nothing lands in the codebase that was not in an approved plan. No surprise files, no surprise
functions, no surprise dependencies.

1. **Start of a phase.** Read the phase section in `PLAN.md`. Split it into parts (one per feature or
   concern). Write a short plan for each part and get it approved before any code for that part.
2. **What a plan contains.** For each part: the design decisions with the alternative considered; every
   new file and what it holds; every new dependency; every new setting; every class, and every function
   with its signature, what it returns, what it does on error, and one line on what it does. Interfaces
   between parts are spelled out. Tests to be written are listed by name and what they prove.
3. **What a plan does not contain.** Line-level code. The plan is precise about the API and silent
   about the body, so that reading a function header later says exactly what to expect.
4. **Plans are approved before implementation.** Michael edits or rejects; only then does the code for
   that part start. Anything the plan left open is a question to Michael, asked before the step that
   depends on it, never resolved by assumption.

## Implementation follows the plan

- Implement the approved API exactly: same names, same parameters, same return and error behaviour.
- Do not add assumptions, handle new cases, or invent requirements while implementing. If a case comes
  up that the plan did not cover, stop and ask; if it must be handled now, the plan is amended first.
- Do not add helpers, files, dependencies or settings that the plan did not name.
- Every new construct that Michael has not met before is explained in the message that introduces it.

## Code style

- One responsibility per function, but no function sprawl: split when a function does two things, not
  to hit a size target. Aim for efficient, not tiny.
- Prefer plain, readable lines over clever one-liners. Several simple statements beat a dense
  expression. A one-liner is fine where it is the idiomatic form and reads at a glance.
- Names carry meaning. Prefer a word over an abbreviation: `file`, not `f`; `connection`, not `conn`;
  `asset_row`, not `r`. This is not a call for long names, only for names that say what the value is,
  so that reading the code feels like reading a description of what it does.
- Explicit over implicit. No hidden magic that a reader cannot trace from the call site.
- Comments say why, not what. The plan already says what.
- Follow the existing layout and naming; nothing new gets its own convention.
