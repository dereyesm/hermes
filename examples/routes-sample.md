# Sample Routing Table

## Namespace → Files

| Namespace | Config | Memory | Agents |
|-----------|--------|--------|--------|
| `controller` | `~/.amaru/controller/config.md` | `~/.amaru/controller/memory/` | `~/.amaru/controller/agents/` |
| `engineering` | `~/.amaru/engineering/config.md` | `~/.amaru/engineering/memory/` | `~/.amaru/engineering/agents/` |
| `operations` | `~/.amaru/operations/config.md` | `~/.amaru/operations/memory/` | `~/.amaru/operations/agents/` |
| `finance` | `~/.amaru/finance/config.md` | `~/.amaru/finance/memory/` | `~/.amaru/finance/agents/` |

## Namespace → Head Agent → Tools

| Namespace | Head Agent | Allowed Tools | Account |
|-----------|-----------|---------------|---------|
| `controller` | router | NONE (read-only) | — |
| `engineering` | lead-dev | github, jira, ci-pipeline | eng@company.com |
| `operations` | pm | calendar, jira, docs | ops@company.com |
| `finance` | accountant | sheets, banking, invoicing | fin@company.com |

## Permitted Data Crosses

| Source | Destination | Type | Example |
|--------|-------------|------|---------|
| engineering | finance | `data_cross` | Infrastructure costs as "Engineering" category |
| operations | finance | `data_cross` | Vendor invoices as "Operations" category |
| finance | `*` | `state` | Monthly financial summaries (broadcast) |
| engineering | `*` | `alert` | System incidents (broadcast) |

## Adjacency

```
          controller
         /    |    \
  engineering  operations  finance
        \          |        /
         `-- data_cross ---'
```

Controller sees all. Namespaces communicate only via bus.
Data crosses are one-directional and explicitly permitted above.
