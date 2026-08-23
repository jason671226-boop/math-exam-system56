# Runtime Router v1

Resolve route before skill lookup.

- G1-G9: PREHIGH, no track.
- G10 ordinary: GENERAL, common.
- G11 ordinary: GENERAL + A/B.
- G12 ordinary: GENERAL + 甲/乙.
- G10 technical: TECHNICAL + A/B/C.

The router intentionally refuses ambiguous G11/G12/technical requests.
After routing, functional modules load only the target pack plus referenced prerequisite nodes.
