# Amaru Metaverse — Roadmap Vault

This folder is an **Obsidian vault**. Open it directly in Obsidian:

1. Obsidian → Open folder as vault → select `docs/roadmap/`
2. Switch to **Graph view** (`Ctrl+G` / `Cmd+G`) to see the dependency graph
3. Use the **left sidebar** to navigate by topic

## Entry points

- [[00-VISION]] — Central hub. Start here.
- [[PROGRESS]] — Live tracking of % completion per component.
- [[principles/fractal]] — Each member is a piece of Amaru and Amaru itself.

## How to update

Every component file uses YAML frontmatter:

```yaml
status: planned | in-progress | live
percent: 0-100
tier: foundation | identity | network | experience | governance | reputation | marketplace
depends_on: ["[[other-node]]"]
```

Update `percent` as work advances. The graph rebuilds automatically.

## Philosophy

The roadmap is **not a project plan** — it is a **map of a living system**. Each node has its own life, its own owners, its own pace. The metaverse is not built top-down; it grows fractally from each clan that adopts the protocol and contributes back.

See [[principles/fractal]] for the deeper "why".
