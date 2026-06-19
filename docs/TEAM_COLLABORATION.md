# Team Collaboration Guide

## Adding Team Members

### GitHub Repository Access
1. Go to https://github.com/nyeinpyaesone-ui/ERP/settings/access
2. Click **Invite a collaborator**
3. Enter username or email
4. Select role:
   - **Read** — Can view and clone
   - **Triage** — Can manage issues/PRs
   - **Write** — Can push code
   - **Maintain** — Can manage settings
   - **Admin** — Full control

### Recommended Team Structure
| Role | GitHub Role | Responsibility |
|------|-------------|--------------|
| Project Lead | Admin | Repository management, releases |
| Senior Dev | Maintain | Code review, branch protection |
| Developer | Write | Feature development |
| QA Engineer | Triage | Testing, bug reports |
| Designer | Read | UI/UX feedback |

### Branch Protection Rules
1. Go to Settings → Branches
2. Add rule for `main`:
   - ✅ Require pull request reviews (1 approval)
   - ✅ Require status checks (CI must pass)
   - ✅ Require up-to-date branches
   - ✅ Restrict pushes (only maintainers)

### Code Review Process
1. Create feature branch: `git checkout -b feature/name`
2. Push and open PR
3. Request review from 1+ team member
4. Address feedback
5. Merge only after approval + CI pass

### Communication
- **GitHub Issues** — Bug reports, feature requests
- **GitHub Discussions** — General questions, ideas
- **Email** — nyeinpyaesone273@gmail.com
- **LinkedIn** — linkedin.com/in/nyein-pyae-sone-3250501ba
- **Phone** — +959699795380

### Development Schedule
| Day | Activity |
|-----|----------|
| Monday | Sprint planning, standup |
| Tuesday-Thursday | Feature development |
| Friday | Code review, testing |
| Weekend | Deployment, monitoring |

### Meeting Links
- Daily Standup: [Your meeting link]
- Sprint Review: [Your meeting link]
- Retrospective: [Your meeting link]
