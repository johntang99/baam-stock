-- 0003_collection_links · DP 1.27/1.28. collection_items stay append-only, except that the analysis step may
-- later record which event/evidence used an item (DC §3.2 linked_event_id / linked_evidence_ids):
-- linked_event_id may be set once (null -> value); linked_evidence_ids may only grow.
drop trigger collection_items_append_only on collection_items;

create function collection_items_guard() returns trigger
language plpgsql as $$
begin
  if tg_op = 'DELETE' then
    raise exception 'IMMUTABLE: collection items are append-only' using errcode = 'P0001';
  end if;
  if (to_jsonb(new) - 'linked_event_id' - 'linked_evidence_ids') is distinct from
     (to_jsonb(old) - 'linked_event_id' - 'linked_evidence_ids') then
    raise exception 'IMMUTABLE: collection item % is append-only (only links may be added)', old.item_id
      using errcode = 'P0001';
  end if;
  if old.linked_event_id is not null and new.linked_event_id is distinct from old.linked_event_id then
    raise exception 'IMMUTABLE: collection item % already linked to %', old.item_id, old.linked_event_id
      using errcode = 'P0001';
  end if;
  if not (new.linked_evidence_ids @> old.linked_evidence_ids) then
    raise exception 'IMMUTABLE: linked_evidence_ids of % may only grow', old.item_id using errcode = 'P0001';
  end if;
  return new;
end $$;

create trigger collection_items_guard before update or delete on collection_items
  for each row execute function collection_items_guard();

create index collection_items_run_idx on collection_items (collection_run_id);
create index collection_items_doc_version_idx on collection_items (doc_version_id);
