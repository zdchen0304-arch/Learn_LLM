# Learn_LLM

This repository contains a Docker-first integration of
[AutoResearchLab](./AutoResearchLab), a multi-agent research workflow from
idea refinement through paper drafting.

Start the application from its project directory:

```powershell
Set-Location AutoResearchLab
Copy-Item .env.example .env
docker compose up --build
```

The service is available at <http://localhost:3001>. See the
[AutoResearchLab README](./AutoResearchLab/README.md) for operational modes,
security boundaries, and the optional Task Agent Docker runtime.
