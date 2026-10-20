"""Seal committed journals and protect sequencing and terminal review decisions."""

from importlib import import_module

from django.db import migrations, models

SQL = r"""
-- Publication state belongs to the database, not the public ORM model.
-- Old journals are already committed. Inserts become sealed only after their
-- deferred accounting checks, without relying on physical tuple/XID identity.
ALTER TABLE meridian_journal ADD COLUMN sealed boolean NOT NULL DEFAULT true;
DROP TRIGGER immutable_journal ON meridian_journal;
CREATE FUNCTION meridian_journal_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='UPDATE' THEN
  IF NOT OLD.sealed AND NEW.sealed AND
     (to_jsonb(NEW)-'sealed') IS NOT DISTINCT FROM (to_jsonb(OLD)-'sealed') THEN
   RETURN NEW;
  END IF;
 END IF;
 RAISE EXCEPTION 'immutable posted journal' USING ERRCODE='23514';
END $$;
CREATE TRIGGER immutable_journal BEFORE UPDATE OR DELETE ON meridian_journal
 FOR EACH ROW EXECUTE FUNCTION meridian_journal_guard();
CREATE OR REPLACE FUNCTION meridian_sequence() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 NEW.sealed := false;
 UPDATE meridian_tenant SET last_sequence=last_sequence+1
  WHERE id=NEW.tenant_id RETURNING last_sequence INTO NEW.sequence;
 RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION meridian_posting_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE j meridian_journal; a meridian_account;
BEGIN
 SELECT * INTO j FROM meridian_journal WHERE id=NEW.journal_id;
 SELECT * INTO a FROM meridian_account WHERE id=NEW.account_id FOR SHARE;
 IF j.id IS NULL OR a.id IS NULL OR j.tenant_id<>a.tenant_id OR j.currency<>a.currency THEN
  RAISE EXCEPTION 'posting tenant/currency mismatch' USING ERRCODE='23514';
 END IF;
 IF j.sealed THEN
  RAISE EXCEPTION 'cannot append to committed journal' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION meridian_journal_check() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE target uuid; j meridian_journal; total numeric; count_rows bigint;
BEGIN
 IF TG_TABLE_NAME='meridian_journal' THEN target=NEW.id; ELSE target=NEW.journal_id; END IF;
 SELECT * INTO j FROM meridian_journal WHERE id=target;
 SELECT count(*),COALESCE(sum(amount::numeric),0) INTO count_rows,total
  FROM meridian_posting WHERE journal_id=target;
 IF count_rows<2 OR count_rows>256 OR total<>0 THEN
  RAISE EXCEPTION 'journal must have 2..256 balanced postings' USING ERRCODE='23514';
 END IF;
 IF j.reversal_of_id IS NOT NULL THEN
  IF NOT EXISTS(
   SELECT 1 FROM meridian_journal original WHERE original.id=j.reversal_of_id
    AND original.tenant_id=j.tenant_id AND original.currency=j.currency
    AND original.reversal_of_id IS NULL
  ) OR EXISTS(
   SELECT account_id FROM meridian_posting WHERE journal_id IN(target,j.reversal_of_id)
    GROUP BY account_id HAVING sum(amount::numeric)<>0 OR count(*)<>2
  ) THEN
   RAISE EXCEPTION 'invalid full reversal' USING ERRCODE='23514';
  END IF;
 END IF;
 UPDATE meridian_journal SET sealed=true WHERE id=target AND NOT sealed;
 RETURN NULL;
END $$;

DO $$ BEGIN
 IF EXISTS(
  SELECT t.id FROM meridian_tenant t LEFT JOIN meridian_journal j ON j.tenant_id=t.id
  GROUP BY t.id HAVING t.last_sequence<>COALESCE(max(j.sequence),0)
   OR t.last_sequence<>count(j.id) OR COALESCE(min(j.sequence),1)<>1
 ) THEN
  RAISE EXCEPTION 'tenant counter disagrees with immutable history' USING ERRCODE='23514';
 END IF;
END $$;
CREATE FUNCTION meridian_counter_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='INSERT' THEN
  IF NEW.last_sequence<>0 THEN
   RAISE EXCEPTION 'new tenant counter must be zero' USING ERRCODE='23514';
  END IF;
 ELSIF NEW.last_sequence IS DISTINCT FROM OLD.last_sequence AND NOT (
  pg_trigger_depth()=2 AND NEW.last_sequence=OLD.last_sequence+1
 ) THEN
  RAISE EXCEPTION 'tenant counter is managed by journal allocation' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER tenant_counter_guard BEFORE INSERT OR UPDATE ON meridian_tenant
 FOR EACH ROW EXECUTE FUNCTION meridian_counter_guard();

-- A BEFORE INSERT trigger runs even if ON CONFLICT later skips the journal.
-- Check every allocation, not only the final maximum: a skipped allocation
-- followed by a successful insert would otherwise hide an interior gap.
CREATE FUNCTION meridian_counter_check() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE current_counter bigint; history_max bigint;
BEGIN
 SELECT last_sequence INTO current_counter FROM meridian_tenant WHERE id=NEW.id;
 IF NOT FOUND THEN RETURN NULL; END IF;
 IF TG_OP='UPDATE' THEN
  IF NEW.last_sequence IS DISTINCT FROM OLD.last_sequence AND NOT EXISTS(
   SELECT 1 FROM meridian_journal WHERE tenant_id=NEW.id AND sequence=NEW.last_sequence
  ) THEN
   RAISE EXCEPTION 'tenant counter allocation has no immutable journal' USING ERRCODE='23514';
  END IF;
 END IF;
 SELECT COALESCE(max(sequence),0) INTO history_max FROM meridian_journal WHERE tenant_id=NEW.id;
 IF current_counter<>history_max THEN
  RAISE EXCEPTION 'tenant counter disagrees with immutable history' USING ERRCODE='23514';
 END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER tenant_counter_check AFTER INSERT OR UPDATE ON meridian_tenant
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION meridian_counter_check();

CREATE OR REPLACE FUNCTION meridian_match_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p meridian_proposal; run_account uuid;
BEGIN
 IF TG_TABLE_NAME='meridian_approvedmatch' THEN
  SELECT * INTO p FROM meridian_proposal WHERE id=NEW.proposal_id;
  IF p.row_id<>NEW.row_id OR p.posting_id<>NEW.posting_id THEN
   RAISE EXCEPTION 'match proposal mismatch' USING ERRCODE='23514';
  END IF;
 ELSE p=NEW;
 END IF;
 SELECT account_id INTO run_account FROM meridian_reconciliationrun WHERE id=p.run_id;
 PERFORM 1 FROM meridian_account WHERE id=run_account FOR SHARE;
 IF NOT EXISTS(
  SELECT 1 FROM meridian_statementrow s JOIN meridian_posting e ON e.id=p.posting_id
  WHERE s.id=p.row_id AND s.account_id=run_account AND e.account_id=run_account AND e.amount=s.amount
 ) THEN
  RAISE EXCEPTION 'reconciliation account or amount mismatch' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION meridian_proposal_identity_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (NEW.id,NEW.run_id,NEW.row_id,NEW.posting_id,NEW.ambiguous) IS DISTINCT FROM
    (OLD.id,OLD.run_id,OLD.row_id,OLD.posting_id,OLD.ambiguous) THEN
  RAISE EXCEPTION 'proposal identity is immutable' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;

CREATE FUNCTION meridian_proposal_state_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.status IS DISTINCT FROM OLD.status AND OLD.status<>'pending' THEN
  RAISE EXCEPTION 'proposal decision is terminal' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER proposal_state_guard BEFORE UPDATE ON meridian_proposal
 FOR EACH ROW EXECUTE FUNCTION meridian_proposal_state_guard();
CREATE TRIGGER immutable_proposal BEFORE DELETE ON meridian_proposal
 FOR EACH ROW EXECUTE FUNCTION meridian_immutable();

CREATE FUNCTION meridian_validate_decision(target uuid) RETURNS void LANGUAGE plpgsql AS $$
DECLARE p meridian_proposal; match_count bigint; audit_count bigint; action text;
BEGIN
 SELECT * INTO p FROM meridian_proposal WHERE id=target FOR SHARE;
 SELECT count(*) INTO match_count FROM meridian_approvedmatch WHERE proposal_id=target;
 SELECT count(*),min(decision) INTO audit_count,action
  FROM meridian_decisionaudit WHERE proposal_id=target;
 IF (p.status='pending' AND (match_count<>0 OR audit_count<>0)) OR
    (p.status='approved' AND (match_count<>1 OR audit_count<>1 OR action<>'approve')) OR
    (p.status='rejected' AND (match_count<>0 OR audit_count<>1 OR action<>'reject')) THEN
  RAISE EXCEPTION 'proposal status, approved match and audit must agree' USING ERRCODE='23514';
 END IF;
END $$;
-- Validate the previous state rather than silently accepting legacy corruption.
DO $$ BEGIN
 PERFORM meridian_validate_decision(id) FROM meridian_proposal;
END $$;
CREATE FUNCTION meridian_decision_check() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_TABLE_NAME='meridian_proposal' THEN
  PERFORM meridian_validate_decision(NEW.id);
 ELSE
  PERFORM meridian_validate_decision(NEW.proposal_id);
 END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER proposal_decision_check AFTER INSERT OR UPDATE ON meridian_proposal
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION meridian_decision_check();
CREATE CONSTRAINT TRIGGER match_decision_check AFTER INSERT ON meridian_approvedmatch
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION meridian_decision_check();
CREATE CONSTRAINT TRIGGER audit_decision_check AFTER INSERT ON meridian_decisionaudit
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION meridian_decision_check();
"""

REVERSE = r"""
CREATE OR REPLACE FUNCTION meridian_match_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p meridian_proposal; run_account uuid;
BEGIN
 IF TG_TABLE_NAME='meridian_approvedmatch' THEN
  SELECT * INTO p FROM meridian_proposal WHERE id=NEW.proposal_id;
  IF p.row_id<>NEW.row_id OR p.posting_id<>NEW.posting_id THEN
   RAISE EXCEPTION 'match proposal mismatch' USING ERRCODE='23514';
  END IF;
 ELSE p=NEW;
 END IF;
 SELECT account_id INTO run_account FROM meridian_reconciliationrun WHERE id=p.run_id;
 IF NOT EXISTS(
  SELECT 1 FROM meridian_statementrow s JOIN meridian_posting e ON e.id=p.posting_id
  WHERE s.id=p.row_id AND s.account_id=run_account AND e.account_id=run_account AND e.amount=s.amount
 ) THEN
  RAISE EXCEPTION 'reconciliation account or amount mismatch' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION meridian_proposal_identity_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (NEW.run_id,NEW.row_id,NEW.posting_id,NEW.ambiguous) IS DISTINCT FROM
    (OLD.run_id,OLD.row_id,OLD.posting_id,OLD.ambiguous) THEN
  RAISE EXCEPTION 'proposal identity is immutable' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;

DROP TRIGGER proposal_decision_check ON meridian_proposal;
DROP TRIGGER match_decision_check ON meridian_approvedmatch;
DROP TRIGGER audit_decision_check ON meridian_decisionaudit;
DROP FUNCTION meridian_decision_check();
DROP FUNCTION meridian_validate_decision(uuid);
DROP TRIGGER immutable_proposal ON meridian_proposal;
DROP FUNCTION meridian_proposal_state_guard() CASCADE;
DROP FUNCTION meridian_counter_check() CASCADE;
DROP FUNCTION meridian_counter_guard() CASCADE;
CREATE OR REPLACE FUNCTION meridian_sequence() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 UPDATE meridian_tenant SET last_sequence=last_sequence+1
  WHERE id=NEW.tenant_id RETURNING last_sequence INTO NEW.sequence;
 RETURN NEW;
END $$;
CREATE OR REPLACE FUNCTION meridian_posting_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE j meridian_journal; a meridian_account; journal_xid bigint;
BEGIN
 SELECT * INTO j FROM meridian_journal WHERE id=NEW.journal_id;
 SELECT xmin::text::bigint INTO journal_xid FROM meridian_journal WHERE id=NEW.journal_id;
 SELECT * INTO a FROM meridian_account WHERE id=NEW.account_id FOR SHARE;
 IF j.id IS NULL OR a.id IS NULL OR j.tenant_id<>a.tenant_id OR j.currency<>a.currency THEN
  RAISE EXCEPTION 'posting tenant/currency mismatch' USING ERRCODE='23514';
 END IF;
 IF journal_xid <> (txid_current() % 4294967296) THEN
  RAISE EXCEPTION 'cannot append to committed journal' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
DROP FUNCTION meridian_journal_guard() CASCADE;
CREATE TRIGGER immutable_journal BEFORE UPDATE OR DELETE ON meridian_journal
 FOR EACH ROW EXECUTE FUNCTION meridian_immutable();
ALTER TABLE meridian_journal DROP COLUMN sealed;
"""


class Migration(migrations.Migration):
    dependencies = [("meridian", "0005_tenant_identity_history")]
    operations = [
        migrations.AddConstraint(
            model_name="proposal",
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=["pending", "approved", "rejected"]),
                name="proposal_status",
            ),
        ),
        migrations.AddConstraint(
            model_name="decisionaudit",
            constraint=models.UniqueConstraint(fields=["proposal"], name="one_proposal_decision"),
        ),
        migrations.AddConstraint(
            model_name="decisionaudit",
            constraint=models.CheckConstraint(
                condition=models.Q(decision__in=["approve", "reject"]), name="decision_action"
            ),
        ),
        migrations.RunSQL(
            SQL,
            import_module("pp_meridian.persistence.migrations.0003_reversal_guard_alias")
            .Migration.operations[0]
            .sql
            + REVERSE,
        ),
    ]
