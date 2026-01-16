# Running Claude Code in the Cloud

This guide explains how to run Claude Code automatically on GitHub's servers - no local machine needed.

## How It Works

```
You create a task (via GitHub UI or Issue)
        ↓
GitHub Actions spins up a cloud server
        ↓
Claude Code runs and makes changes
        ↓
A Pull Request is created with the changes
        ↓
You review and merge (when convenient)
```

## Setup (One-Time, ~5 minutes)

### Step 1: Get an Anthropic API Key

1. Go to [console.anthropic.com](https://console.anthropic.com/)
2. Sign in or create an account
3. Navigate to **API Keys**
4. Click **Create Key**
5. Copy the key (starts with `sk-ant-...`)

### Step 2: Add the API Key to GitHub

1. Go to your GitHub repository
2. Click **Settings** (tab at the top)
3. In the left sidebar, click **Secrets and variables** → **Actions**
4. Click **New repository secret**
5. Fill in:
   - **Name:** `ANTHROPIC_API_KEY`
   - **Secret:** Paste your API key
6. Click **Add secret**

That's it! The workflow file is already in `.github/workflows/claude-code.yml`.

## Usage

### Option 1: Manual Trigger (Quick Tasks)

Best for: One-off tasks you want to run right now.

1. Go to your repo on GitHub
2. Click **Actions** (tab at the top)
3. In the left sidebar, click **Claude Code Agent**
4. Click **Run workflow** (dropdown on the right)
5. Enter your task description
6. Click **Run workflow**

Example tasks:
- "Add input validation to the web form"
- "Refactor the ChromeController class to use async/await"
- "Add unit tests for the build_prompt function"

### Option 2: Issue-Based (Queued Tasks)

Best for: Tasks you want to queue up and run later, or when you're out of tokens.

1. Go to your repo on GitHub
2. Click **Issues** → **New issue**
3. Write your task in the issue body (be detailed!)
4. Add the label **`claude`** to the issue
5. The workflow triggers automatically

The workflow will:
- Read the task from your issue
- Make the changes
- Create a PR
- Comment on the issue with a link to the PR

### Option 3: Scheduled (Coming Soon)

You can modify the workflow to run on a schedule by adding:

```yaml
on:
  schedule:
    # Runs at 2 AM UTC every day
    - cron: '0 2 * * *'
```

## Writing Good Task Descriptions

Claude works best with clear, specific instructions:

### Good Examples

```
Add a --verbose flag to debate.py that prints the full prompt
being sent to each AI before sending it.
```

```
In web_app.py, add rate limiting to the /api/start endpoint.
Limit to 10 requests per minute per IP. Use Flask-Limiter.
```

```
Create unit tests for the build_prompt function in web_app.py.
Test these cases:
- With opponent_response
- Without opponent_response
- With custom instructions
- With round info
```

### Bad Examples

```
Make the code better
```

```
Fix bugs
```

```
Add some features
```

## Viewing Results

1. After the workflow runs, go to **Pull Requests**
2. Find the PR created by Claude
3. Review the changes in the **Files changed** tab
4. If good, click **Merge pull request**
5. If changes needed, comment on the PR or close it and try again

## Troubleshooting

### "ANTHROPIC_API_KEY not found"

Make sure you added the secret correctly:
- Settings → Secrets and variables → Actions → Repository secrets
- The name must be exactly `ANTHROPIC_API_KEY`

### Workflow didn't trigger on issue

- Make sure the issue has the **`claude`** label
- Check that the label name is exactly "claude" (lowercase)
- Create the label first if it doesn't exist (Issues → Labels → New label)

### Claude made wrong changes

- Be more specific in your task description
- Break large tasks into smaller, focused issues
- Include file names and function names when relevant

### Workflow failed

1. Go to **Actions**
2. Click the failed run
3. Click the failed job
4. Expand the failed step to see the error

Common issues:
- API key expired or invalid
- Rate limit hit (wait and retry)
- Task too large or complex (break it down)

## Costs

- **GitHub Actions:** Free for public repos (2,000 mins/month for private)
- **Anthropic API:** Pay-per-use based on tokens ([pricing](https://anthropic.com/pricing))

A typical task uses roughly $0.05-0.50 in API costs depending on complexity.

## Security Notes

- Your API key is stored encrypted in GitHub Secrets
- The key is never exposed in logs
- Only repository collaborators can trigger workflows
- Review all PRs before merging (Claude can make mistakes!)

## Customizing the Workflow

The workflow file is at `.github/workflows/claude-code.yml`. You can modify it to:

- Change the trigger conditions
- Add a schedule
- Use a different branch naming convention
- Add tests before creating the PR
- Require approval before running

## Quick Reference

| Action | How |
|--------|-----|
| Run task now | Actions → Claude Code Agent → Run workflow |
| Queue task | Create issue with `claude` label |
| View progress | Actions → Click running workflow |
| See results | Pull Requests → Find Claude's PR |
| Check logs | Actions → Click workflow → Click job |
