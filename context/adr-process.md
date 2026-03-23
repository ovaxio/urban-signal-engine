# ADR Process — context/adr-process.md

Loaded for: ADR creation, decision recording.
Standing instruction: detect when a decision warrants an ADR and create it without being asked.

## When to create an ADR

### Technical triggers
- Constant, weight, threshold, or formula changed with non-obvious reason
- New external dependency or data source added or explicitly rejected
- Database schema change affecting data semantics
- Signal composition or scoring logic change
- Bug fix changing a previously intentional behavior
- Architectural pattern chosen over a documented alternative
- Performance or reliability constraint discovered and worked around

### Product/strategy triggers
- Segment, feature, or integration explicitly ruled out (NO-GO = important)
- Pricing, packaging, or commercial decision made or confirmed
- Pivot condition or fallback strategy defined
- "Do not build before X" constraint established

### Process triggers
- Recurring mistake identified and prevention rule established
- Known issue documented as "won't fix until Y"
- External API/service evaluated and rejected with reason

## When NOT to create an ADR
- Routine implementation following existing patterns
- Bug fixes restoring intended behavior without design change
- Style, naming, or formatting changes
- Temporary workarounds marked as TODO
- Changes already covered by an existing ADR (update it instead)

## Decision detection protocol (run silently after each task)
1. Did I change a value someone might revert without knowing why? → ADR
2. Did I reject a reasonable-looking approach? → ADR
3. Did I establish a constraint not in the code itself? → ADR
4. Did I discover a non-obvious external system limitation? → ADR
5. Already covered by existing ADR? → Update that ADR instead

## ADR format (strict)

File: `docs/decisions/ADR-{NNN}-{kebab-case-title}.md`
Number: increment from highest existing in docs/decisions/

```markdown
# ADR-{NNN} — {Title}

**Date**: {today}
**Status**: Accepted
**Source**: Claude Code session — {brief task description}

## Decision
{One or two lines maximum}

## Values
{Constants, parameters, thresholds, or rules}

## Rationale
- {Non-obvious reason 1}
- {Non-obvious reason 2}

## Consequences
- {What is now true}
- {What changed}

## DO NOT
- {Explicit prohibition 1}
- {Explicit prohibition 2}

## Triggers
Re-read when: {comma-separated list of files, functions, or topics}
```

Hard constraints:
- Max 30 lines total
- No prose paragraphs — bullets and short statements only
- Every line carries information — no filler
- DO NOT section mandatory — minimum 2 items
- Triggers section mandatory

## Lifecycle rules

### Creating
- Check docs/decisions/ for existing ADRs that might cover this
- Use next available number
- Create immediately — do not defer to end of session

### Updating
- Supersedes/refines existing ADR → update Status, append `## Update {date}` section
- Do NOT rewrite history — append only

### Conflicts
- Contradicts existing ADR → flag: "This conflicts with ADR-{N}" → ask confirmation

## After creating/updating
1. Update `docs/decisions/README.md` table
2. Update CLAUDE.md decision log table to match
3. Append at END of response:
```
---
ADR created: ADR-{NNN} — {Title}
Reason: {one sentence}
File: docs/decisions/ADR-{NNN}-{kebab-case-title}.md
---
```

## Session-end verification
```
ls docs/decisions/ | wc -l
```
If count unchanged and trigger condition met → create the missing ADR.
If count increased → confirm README.md and CLAUDE.md are updated.
