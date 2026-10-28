---
template_id: request.strategy_propose_product_increment
version: "2"
required_variables:
  - objective_statement
  - objective_measurement
  - allowed_scope_lines
  - prior_criteria_lines
  - head_commit
  - product_profile_section
  - previous_verification_section
  - requirements_section
optional_variables:
  - product_tree_section
  - approved_manifest_section
  - frozen_conventions_section
  - supervisor_note_section
  - unapproved_proposals_section
  - prd_section
  - accepted_prd_section
  - outcome_goals_section
  - quality_moves_section
  - abandoned_increment_section
  - qa_proposed_behaviours_section
  - task_instructions_section
  - project_instructions_section
  - cross_cycle_lessons_section
---
## Propose the next increment of this product

The product below is an existing repository, accepted as it stands at commit `{{head_commit}}`. Your
job is to propose **one** change that moves it toward the campaign's objective, small enough to build
and verify in one cycle. You do not build it. A supervisor rules on your proposal; only an approved
proposal is built.

**The objective:** {{objective_statement}}

**How the campaign will know it is met:** {{objective_measurement}}

**The files a proposal may reach** (a proposal whose footprint reaches outside these is refused
whole, not trimmed). The product's own test files are product files: editing one needs it inside
these. Each criterion's own new test file is the framework's, and is not read against them:
{{allowed_scope_lines}}

**Criteria earlier increments froze**: each is something the product already does. Every one keeps
passing unless you retire it, with a reason, and the supervisor rules on the retirement:
{{prior_criteria_lines}}

**Each criterion you add names something the product does not do yet.** Its test is run against the
product at `{{head_commit}}` before your change, and must fail there, then pass after it. A
criterion the product already meets cannot be proven, and the proposal is returned. A test that
fails only because it imports something your change adds does not count as failing: assert the
behaviour where a caller reaches it.

{{requirements_section}}

{{product_profile_section}}

{{previous_verification_section}}
{{supervisor_note_section}}
{{unapproved_proposals_section}}
{{abandoned_increment_section}}
{{qa_proposed_behaviours_section}}
{{task_instructions_section}}{{project_instructions_section}}{{cross_cycle_lessons_section}}
{{product_tree_section}}
{{approved_manifest_section}}

### What you emit

Exactly one fenced block whose header carries the filename `change_request.yaml`, in this shape. The
example proposes a change to a different product; yours changes the product above.

```yaml:change_request.yaml
kind: feature            # feature | fix | refactor (a refactor adds no new criteria)
prd_delta:
  - id: export-csv
    op: add              # add | modify | retire, against the requirements above
    text: "The export command writes the ledger as CSV when given --format csv."
footprint:               # the product files the change touches, as path globs
  - "src/ledgerkit/export.py"
  - "src/ledgerkit/cli.py"
  - "web/src/views/ExportView.jsx"
criteria:
  - id: T1
    statement: The export command writes CSV when asked to
    surface_kind: command          # endpoint | client_route | command | package
    surface: "ledgerkit export"    # one of the product's public surfaces above
    observable: "with --format csv, stdout's first line is the header 'date,amount,memo'"
    paths:                         # optional: the product paths it exercises (default: footprint)
      - "src/ledgerkit/export.py"
  - id: T2
    statement: The export page offers CSV
    surface_kind: client_route
    surface: "/export"             # a page this change adds
    observable: "the page lists 'CSV' among the formats it offers"
    anchor: "export-view"          # only on a page this change adds: its view's root data-testid
    paths:
      - "web/src/views/ExportView.jsx"
must_not_break: []                 # earlier criteria ids, from the list above
```

**A criterion on a page this change adds names its view's `anchor`.** At acceptance each page is
opened in a browser on the built product. A page this change adds holds only when an element on it
carries `data-testid` equal to the anchor, so the build gives the view's root element that
attribute, as `<section data-testid="export-view">` in the example. A page with no element carrying
it rejects the increment. Write the anchor as a letter followed by letters, digits, `-` or `_`. A
page acceptance already reads is judged by its own view's anchor, so a criterion there names none,
and a criterion on anything but a page never names one. A page this change adds is opened at its
path exactly as written, so give it a fixed path, such as `/reports/latest`: a page this change adds
whose path has a parameter (`/reports/:report_id`, `/reports/{report_id}`, `/reports/[report_id]`)
or a `*` is refused, because nothing fills it in.

There is no interface manifest here, so write no `manifest_delta`: a proposal that has one is
refused. The framework places each criterion's own test file under the product's runner that tests
its paths, adds those files to the footprint, and computes the proposal's identity and hash. Leave
`content_hash`, `proposal_id` and `version` out: a proposal that sets them is refused.
