# Code Review Guide

## 1. Code Review Principles

### Purpose
- Improve code quality
- Share knowledge
- Catch bugs early
- Maintain consistency
- Mentor team members

### Core Values
- **Respectful**: Focus on code, not the person
- **Constructive**: Suggest improvements, don't just criticize
- **Timely**: Review within 24 hours
- **Thorough**: Actually read and understand the changes

## 2. Review Checklist

### Functionality
- [ ] Does the code work as intended?
- [ ] Are edge cases handled?
- [ ] Are error messages clear and helpful?
- [ ] Is logging appropriate?

### Code Quality
- [ ] Is the code readable and maintainable?
- [ ] Are functions/methods small and focused?
- [ ] Is there unnecessary duplication (DRY)?
- [ ] Are variable/function names descriptive?

### Testing
- [ ] Are tests included for new functionality?
- [ ] Do tests cover edge cases?
- [ ] Are tests readable and maintainable?
- [ ] Do all tests pass?

### Security
- [ ] Is user input validated/sanitized?
- [ ] Are SQL queries parameterized (no injection)?
- [ ] Is sensitive data properly handled?
- [ ] Are authentication/authorization checks in place?

### Performance
- [ ] Are there obvious performance issues?
- [ ] Is database querying efficient (N+1 problems)?
- [ ] Are large datasets handled appropriately?
- [ ] Is caching used where beneficial?

### Documentation
- [ ] Is public API documented?
- [ ] Are complex algorithms explained?
- [ ] Is README updated (if needed)?
- [ ] Are changelogs updated?

## 3. Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed

## Screenshots (if applicable)
{Add screenshots}

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] No debug statements left
- [ ] Documentation updated
- [ ] No new warnings introduced

## Related Issues
Closes #{issue_number}
```

## 4. Review Process

### For Authors
1. **Self-Review**: Review your own code first
2. **Small PRs**: Keep PRs under 400 lines when possible
3. **Clear Description**: Explain what and why
4. **Address Feedback**: Respond to all comments
5. **Update Promptly**: Make requested changes quickly

### For Reviewers
1. **Understand Context**: Read the description and linked issues
2. **Run Locally**: Test the changes if significant
3. **Check Tests**: Ensure adequate test coverage
4. **Provide Feedback**: Leave specific, actionable comments
5. **Approve/Merge**: When satisfied, approve or request changes

## 5. Comment Types

### Nitpick (Optional)
```
nit: Consider using a more descriptive variable name
```

### Question (Clarification Needed)
```
question: Why was this approach chosen over X?
```

### Suggestion (Recommended)
```
suggestion: Extract this logic into a separate function for reusability
```

### Blocker (Must Fix)
```
blocker: This security vulnerability must be fixed before merge
```

## 6. Common Review Comments

### Positive Feedback
```
✓ Great use of list comprehension here!
✓ Excellent test coverage for edge cases
✓ Clean separation of concerns
```

### Improvement Suggestions
```
⚠ Consider adding type hints for better IDE support
⚠ This function is getting long; consider breaking it up
⚠ Add error handling for network failures
⚠ Missing test for null input case
```

### Security Concerns
```
🔒 This user input needs sanitization
🔒 Use parameterized queries to prevent SQL injection
🔒 Add authorization check before accessing this resource
```

## 7. Review Tools

### GitHub Features
- Inline comments
- Suggested changes (code blocks)
- Review summaries
- Approval requirements

### Automated Checks
- CI/CD pipeline status
- Code coverage reports
- Linting results
- Security scans

## 8. Metrics & Goals

### Team Goals
- Average review time: < 24 hours
- PR size: < 400 lines (ideal), < 800 lines (max)
- Review depth: At least one thorough review
- Merge rate: > 90% of PRs merged within 48 hours

### Individual Goals
- Review at least 2 PRs per week
- Provide constructive feedback
- Learn from others' code
- Share knowledge through reviews

## 9. Handling Disagreements

### Best Practices
1. **Discuss, Don't Argue**: Focus on technical merits
2. **Seek Understanding**: Ask questions before pushing back
3. **Escalate When Needed**: Involve tech lead if stuck
4. **Document Decisions**: Record rationale for future reference

### Example Response
```
I understand your concern about performance. However, 
this approach improves readability significantly. 
Given that this code path is rarely executed, I believe 
the trade-off is acceptable. What do you think?
```

## 10. Post-Merge

### After Approval
1. Squash commits if appropriate
2. Write clear commit message
3. Delete feature branch
4. Monitor for issues in production

### Retrospective
- Note common issues for team learning
- Update coding standards if needed
- Share interesting solutions with team
