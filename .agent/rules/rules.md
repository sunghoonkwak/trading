---
trigger: always_on
---

# Prohibited Modifications
1. **Official API Preservation**: Do not modify the `src/kis/kis_api/` directory as it contains the official Korea Investment & Securities sample code.
2. **Mandatory Confirmation**: Always ask for user permission before making any code modifications.

# Development Workflow
1. **Understand**: Examine code structure and logs. Identify the root cause or requirement.
2. **Plan**: Propose a step-by-step plan to the user.
3. **Implement**: Execute code changes (follow Coding Rules in ~/.gemini/GEMINI.md).
4. **Verify**: 
   - Run `docker compose up -d --build` and check `docker logs my-trading-bot`.
   - **MANDATORY**: Provide a specific **Test Checklist** to the user based on the changes made.
5. **Document**: 
   - Update or create matching `.md` files using `templete/module_doc_template.md`.
   - **RULE**: Every new `.py` file MUST have a matching `.md` file (except `__init__.py`).
   - **RULE**: If a `.py` file is deleted, its matching `.md` file MUST also be deleted.
6. **Commit Confirmation**: Show the proposed commit message to the user. **Wait for explicit user confirmation** before running the `git commit` command.

# Commit Message Rules (STRICT)
1. **Structure**:
   ```text
   <type>(<scope>): <subject>

   [body]

   [footer]
   ```
2. **Length Constraints**:
   - **Subject Line**: Maximum **50 characters**.
   - **Body Lines**: Wrap at **72 characters**.
3. **Content Restrictions**:
   - **NEVER** include file names in the message. Focus on *what* and *why*.
4. **Workflow**:
   - Show the message ONLY first.
   - **DO NOT** execute the commit command until the user approves the message.

## Checklist for Commit Messages:
- [ ] Subject < 50 chars?
- [ ] Body wrapped at 72 chars?
- [ ] No filenames in message?
- [ ] Explicit user confirmation received?

# Documentation Rules
1. **Template**: All module documentation MUST follow `templete/module_doc_template.md`.
2. **Structure**:
   - `# [Module Name] (`path/to/file.py`)` (H1)
   - Description (Text)
   - `# Core Logic` (H1)
   - `# Key Functions` (H1)
     - `## function_name` (H2)
   - `# Configuration` (H1)
   - `# Usage Example` (H1)
3. **Language**: Use **Korean** for documentation explanations.
4. **Deviation**: If the template cannot be followed, **ASK the user for guidance**.
