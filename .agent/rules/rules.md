---
trigger: always_on
---

# Rules

---

## 1. Conversation Rules
1. Use **Korean** for all interactions unless asked otherwise.
2. Use **bold style** for important points or key terms.

## 2. Tool Usage (MCP)
1. Strongly recommend using MCP tools whenever applicable.

## 3. Command Execution Rules
1. **Git Commands**:
   - Only ask for confirmation when running `git commit`, `git push`, or destructive commands (e.g., `git reset --hard`).
   - For `git status`, `git diff`, etc., run them without asking.
2. **File Operations**:
   - Do NOT ask for permission to read project files. Just read them.

## 4. Coding Rules
1. **Language**: Use **English only** for variable names, comments, and documentation. Never use Korean in code.
2. **Security**:
   - NEVER hardcode API keys or passwords.
   - ALWAYS use `load_credentials()` or environment variables.
   - NEVER read `.enc` files containing sensitive data.

## 5. Commit Message Rules (STRICT)
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
   - **NEVER** include file names (e.g., `main.py`, `utils.py`) in the message. Focus on *what* and *why*.
4. **Workflow**:
   - When asked for a commit message, **ONLY show the message**.
   - **DO NOT** prepare or suggest the `git commit` command immediately. Wait for user approval.

### Checklist for Commit Messages:
- [ ] Subject < 50 chars?
- [ ] Body wrapped at 72 chars?
- [ ] No filenames in message?
- [ ] Did I stop before running the command?
