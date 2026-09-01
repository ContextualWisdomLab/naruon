# Prompt response semantic identifiers

## Decision

Naruon's Prompt Catalog bounded context owns the internal meaning of a stored prompt-template database record. The response model therefore uses `prompt_record_id` rather than the generic organization-owned field name `id`.

The established `/api/prompts` JSON contract remains unchanged. `PromptResponse.prompt_record_id` uses Pydantic's `id` alias, so ORM extraction continues to read the persisted `PromptTemplate.id` compatibility attribute and FastAPI alias serialization continues to emit the existing public `id` key. No database column, endpoint path, persisted value, tenant filter, or frontend wire key changes.

| Previous owned name | Specific owned name | Compatibility surface |
| --- | --- | --- |
| `PromptResponse.id` | `PromptResponse.prompt_record_id` | JSON/ORM alias `id` |

## DDD and compatibility boundary

- **Bounded context:** Prompt Catalog.
- **Entity:** persisted prompt-template record.
- **Value/identity:** `prompt_record_id` is the database-record identity; `prompt_uid` remains the distinct stable prompt UID already exposed by the domain model.
- **Invariant:** organization-owned Python vocabulary states which aggregate/entity owns an identifier.
- **Anti-corruption boundary:** the historical JSON/ORM key `id` is confined to the Pydantic alias instead of remaining authoritative internal vocabulary.
- **Persistence:** unchanged. No migration, backfill, new lock, UPSERT change, partition change, or read/write split is introduced by this repair.

## Verification contract

`backend/tests/test_prompt_response_naming_contract.py` requires the internal field set to contain `prompt_record_id` and not bare `id`, while also proving `model_dump(by_alias=True)` still emits `id`. The test constructs through the legacy alias so existing compatibility callers remain covered. Exact-head repository CI, security workflows, review threads, and branch protection remain authoritative merge evidence.

## Research traceability

Empirical software-engineering research supports treating identifier names as program-comprehension artifacts rather than cosmetic style. Feitelson et al. found that explicitly choosing the concepts represented in a name improved judged name quality and tended to produce names containing more concepts; later replication work corroborated that model and found that simply asking for longer names was not equivalent to selecting meaningful concepts. This repair therefore adds the owning concept (`prompt_record`) rather than mechanically lengthening or recasing the identifier.

### References

Alpern, R., Lazer, I., Tzachor, I., Hakim, H., Weissbuch, S., & Feitelson, D. G. (2024). *Reproducing, extending, and analyzing naming experiments*. arXiv. https://doi.org/10.48550/arXiv.2402.10022

Feitelson, D. G., Mizrahi, A., Noy, N., Ben Shabat, A., Eliyahu, O., & Sheffer, R. (2022). How developers choose names. *IEEE Transactions on Software Engineering, 48*(1), 37–52. https://doi.org/10.1109/TSE.2020.2976920
