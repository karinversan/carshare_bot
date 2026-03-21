# Known limitations

- Real local inference requires installed ML dependencies and valid checkpoints; otherwise the API now returns `503` when `REQUIRE_REAL_INFERENCE=true`
- Public research datasets have a domain gap vs real carsharing images
- Small damages may not be visible in mandatory wide views
- Human confirmation is required to suppress false positives
- Comparison uses same-view normalized geometry and review state, not raw pixel differencing
