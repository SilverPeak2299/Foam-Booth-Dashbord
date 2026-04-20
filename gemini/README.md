# Gemini Processing Notes

Open Gemini CLI in this worktree and point it at:

```text
gemini/TASK.md
```

The source CSV is already present:

```text
data/gemini_source/stage_1_output_no_customer.csv
```

Suggested instruction to Gemini:

```text
Read gemini/TASK.md and complete the task. Process the CSV in batches if needed. Write outputs under data/gemini_output/.
```

Expected final outputs:

```text
data/gemini_output/semantic_line_items.jsonl
data/gemini_output/semantic_summary.json
data/gemini_output/review_needed.csv
```

