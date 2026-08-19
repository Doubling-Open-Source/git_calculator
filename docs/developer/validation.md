# Validation

After changing product code, run:

```
pytest tests/
```

After changing MDCP shards, run:

```
npm run docs:compile
npm run docs:check
```

`mdcp check` validates the four-tier guides. Legacy markdown under `docs/adr/` and other unsharded files is out of that gate until migrated.
