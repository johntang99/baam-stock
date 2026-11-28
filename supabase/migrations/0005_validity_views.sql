-- DP 1.23 · display_state + snapshot validity (DC §3.7 display_state is derived, never stored; D-41; AC-49; OQ-53).
-- Each has an "_at(t)" form so a replay can ask what the page showed at any past moment, and a view at now().
-- Views are security_invoker so the RLS of the underlying tables applies to whoever queries them (functions are
-- SECURITY INVOKER by default).

create function prediction_display_state_at(p_at timestamptz)
returns table (prediction_id text, display_state text, superseded_by text, valid_until timestamptz)
language sql stable as $$
  select p.prediction_id,
         case
           when p.status in ('settled', 'unsettleable') then 'settled'
           when n.prediction_id is not null then 'superseded'
           when p_at > p.valid_until then 'expired'
           else 'current'
         end,
         n.prediction_id,
         p.valid_until
    from predictions p
    left join lateral (
      select x.prediction_id from predictions x
       where x.supersedes_prediction_id = p.prediction_id and x.published_at <= p_at
       order by x.published_at desc limit 1
    ) n on true
   where p.published_at is not null and p.published_at <= p_at
$$;

create view prediction_display_state with (security_invoker = true) as
  select * from prediction_display_state_at(now());

-- the latest snapshot per security known at t, with whether its explanation has expired (D-41)
create function security_snapshot_current_at(p_at timestamptz)
returns table (security_id text, snapshot_id text, analysis_as_of timestamptz, data_quality data_quality,
               run_state run_state, last_valid_at timestamptz, valid_until timestamptz, expired boolean)
language sql stable as $$
  select distinct on (s.security_id) s.security_id, s.snapshot_id, s.analysis_as_of, s.data_quality, s.run_state,
         s.last_valid_at, s.valid_until, p_at > s.valid_until
    from security_state_snapshots s
   where s.published_at <= p_at
   order by s.security_id, s.analysis_as_of desc
$$;

create view security_snapshot_current with (security_invoker = true) as
  select * from security_snapshot_current_at(now());
