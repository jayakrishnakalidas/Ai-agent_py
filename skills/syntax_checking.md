# Syntax Checking & Automatic Verification Skill

After writing or modifying any code file, you MUST run `check_syntax` on the changed file before declaring the task complete.

## When to use (only after edits):
1. Run `check_syntax` ONLY on files you just created or modified using `write_file`, `replace_text`, `insert_text`, `patch_file`, or `delete_text`.
2. Do NOT run `check_syntax` on files you only read or listed.

## Supported languages:
- **Python** (.py): Runs `python -m py_compile file.py`. Fix compilation errors immediately if detected.
- **JSON** (.json): Parses JSON structure. Fix dangling commas or missing brackets.
- **JavaScript** (.js): Runs `node --check file.js`. Fix syntax errors if detected.
- **HTML** (.html): Validates closing tags.
- **CSS** (.css): Validates brace matching.

## Error recovery:
If syntax check fails → read the error → fix using `replace_text` or `patch_file` → re-run `check_syntax`.
