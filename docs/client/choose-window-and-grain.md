# Choose window and grain

**Window** is which commits count. **Grain** is how those commits become rows. Pass both when you want a bounded series instead of full-history monthly charts.

Use a **window** when you care about a slice of time (for example the last eight weeks). `--from` and `--to` are UTC instants. The slice is half-open: commits at `--to` are out. Pass both flags together, or omit both.

Use **`--grain weekly`** when each row should be one ISO week (`YYYY-Www`). Use **`--grain monthly`** when each row should be one calendar month (`YYYY-MM`). Weekly grain always needs a window.

The GitHub Action still chooses a trailing window of UTC Mondays and forwards `--grain weekly`. You can run the same contract locally:

```sh
git-calculator single /path/to/repo \
  --from 2026-06-22T00:00:00Z \
  --to 2026-08-17T00:00:00Z \
  --grain weekly \
  --backend sql \
  --work-style squash
```

Quiet weeks or months in the window still appear as rows; they do not invent a 0% change-failure rate.

Contract: [window and grain](../features/window-and-grain.md).
