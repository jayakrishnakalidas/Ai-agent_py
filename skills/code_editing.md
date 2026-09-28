# Safe Code Editing & Verification Skill

When the user asks to MODIFY, FIX, or EDIT code, follow this workflow:

## Workflow (only for modification requests):
1. **INSPECT**: Read the specific files that need changes using `read_file`. Use `search_files` or `find_symbol` only if you need to locate the right file.
2. **PLAN**: Outline exact changes and verify matching lines in target files.
3. **MODIFY**: Use exact targeted replacement tools (`replace_text`, `insert_text`, `patch_file`) instead of overwriting entire files.
4. **AUTOMATIC BACKUP**: Every write or edit operation creates an automatic timestamped backup in `.agent_backups/`. Use `list_backups` and `restore_backup` if a change needs to be reverted.
5. **VERIFY**: Run `check_syntax` and `run_tests` immediately after modifying code.

This workflow does NOT apply to simple read-only requests like listing files, reading a file, or checking git status.
