-- SIP-0108 §10i item 1: every enabled agent in a squad profile declares the step roles it
-- serves, so the role → agent map is read from a declaration and never inferred from a role
-- name. Profiles seeded before 1.8.1 carry no `serves_roles` key.
--
-- An absent declaration is DATA TO MIGRATE, not a runtime interpretation rule. Every such
-- agent served exactly its own role — that is what `resolve_agent_config` did with it — so the
-- backfill writes that fact down once, here, and the reader may then require the key.
--
-- Idempotent: the WHERE guard skips a row whose agents all declare already, so a re-run is a
-- no-op. Order-preserving: WITH ORDINALITY keeps the agent list in its authored order, which
-- the profile snapshot hash is taken over.
UPDATE squad_profiles
SET agents = (
        SELECT jsonb_agg(
                   CASE
                       WHEN agent ? 'serves_roles'
                            AND jsonb_typeof(agent -> 'serves_roles') = 'array'
                            AND jsonb_array_length(agent -> 'serves_roles') > 0
                       THEN agent
                       ELSE agent || jsonb_build_object(
                                'serves_roles', jsonb_build_array(agent ->> 'role')
                            )
                   END
                   ORDER BY ord
               )
        FROM jsonb_array_elements(squad_profiles.agents) WITH ORDINALITY AS elements(agent, ord)
    ),
    updated_at = NOW()
WHERE EXISTS (
    SELECT 1
    FROM jsonb_array_elements(squad_profiles.agents) AS elements(agent)
    WHERE NOT (agent ? 'serves_roles')
       OR jsonb_typeof(agent -> 'serves_roles') <> 'array'
       OR jsonb_array_length(agent -> 'serves_roles') = 0
);
