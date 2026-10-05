# Evaluation lifecycle

## Registration / regression / platform quality

Same immutable Golden assets; run kind records the trigger. Runner records current agent fingerprint, frozen custom judge definitions, platform evaluator versions and actual model SHA256. Existing golden can run against a newly registered agent version, but modified repository source must be re-registered first. Optional explicit dependency IDs select related test cases; if no dependency matches, run the full golden. Automatic Git diff impact inference and batch multi-agent platform rollout are deferred.

## Production closed loop

Agent request → Phoenix `prd` root with retrieval/tool child spans → Phoenix REST query → candidate preserving original input/output, span/trace and observed reason → local owner edits the intended contract → approval → Golden snapshot → `evaluate` execution. Original failure output is not ground truth. A regression may correctly HOLD until the agent is fixed. Candidate reason is evidence of an incident, not the desired assertion.

Known definition/knowledge cases and production cases can share scenario IDs, but source lineage is retained separately to avoid silently merging conflicting contracts. Query variations retain original text; semantic scenario clustering/minimum-set optimization is explicitly deferred.

Owner edits an approved case reset it to pending unless the edit explicitly includes fresh approval. Excluded cases and deletion tombstones survive regeneration. Excluding an observed failure does not remove it from the known failure coverage denominator. Golden versions cannot be mutated or deleted through the API. Local audit events record mutations; local owner identity is a PoC placeholder, not authentication.
