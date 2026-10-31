---
template_id: request.proposal_approved_manifest
version: "1"
required_variables:
  - stack
  - commit
  - manifest
---
### The interface manifest this product was initialized from

The product's first commit, `{{commit}}`, was rendered from this approved manifest on the `{{stack}}`
blueprint. It describes the product as it was then. The tree above is what the product is now, and
your change is to that tree: write no `manifest_delta` against this.

```yaml
{{manifest}}
```
