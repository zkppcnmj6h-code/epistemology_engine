CREATE SCHEMA IF NOT EXISTS ops;
CREATE OR REPLACE FUNCTION ops.rollback_run(p_run_id uuid)
RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
  RAISE NOTICE 'rollback_run placeholder for %', p_run_id;
END $$;
