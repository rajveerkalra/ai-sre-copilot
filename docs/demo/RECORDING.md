# Recording a demo GIF / video

You do not need paid tools. Pick one path:

## Option A — Terminal recording (asciinema)

```bash
# brew install asciinema
asciinema rec docs/demo/demo.cast -c './scripts/demo.sh'
# Convert to GIF (optional):
# agg docs/demo/demo.cast docs/demo/demo.gif
```

Commit `demo.cast` or host on https://asciinema.org.

## Option B — Screen capture (UI)

1. Start stack + `./scripts/demo.sh` prep.
2. Record browser: Dashboard login → incident → RCA → approve/execute.
3. Tools: macOS Screenshot toolbar (⌘⇧5), OBS, or Kap for GIF.
4. Drop files into `docs/demo/media/` (gitignored for large binaries) and link from README.

Suggested clips (15–45s each):

| Clip | Content |
|------|---------|
| `01-overview.mp4` | Dashboard KPIs |
| `02-rca.mp4` | Incident RCA + evidence |
| `03-approval.mp4` | Remediation 409 → approve → execute |

## Option C — Static screenshots

Follow [SCREENSHOTS.md](../SCREENSHOTS.md).
