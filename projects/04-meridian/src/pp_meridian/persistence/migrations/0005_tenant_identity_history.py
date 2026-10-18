"""Bind cached results to their tenant and freeze every used account identity."""

from django.db import migrations, models

SQL = r"""
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM meridian_statementrow s JOIN meridian_account a ON a.id=s.account_id WHERE s.currency<>a.currency) OR
 EXISTS(SELECT 1 FROM meridian_proposal p JOIN meridian_reconciliationrun r ON r.id=p.run_id JOIN meridian_statementrow s ON s.id=p.row_id JOIN meridian_posting e ON e.id=p.posting_id WHERE r.account_id<>s.account_id OR r.account_id<>e.account_id OR s.amount<>e.amount) THEN
  RAISE EXCEPTION 'existing statement or proposal history violates account identity' USING ERRCODE='23514';
 END IF;
END $$;
ALTER TABLE meridian_idempotency ADD CONSTRAINT idempotency_journal_tenant_fk
 FOREIGN KEY (journal_id, tenant_id) REFERENCES meridian_journal(id, tenant_id)
 DEFERRABLE INITIALLY IMMEDIATE;
CREATE OR REPLACE FUNCTION meridian_account_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (NEW.tenant_id,NEW.currency) IS DISTINCT FROM (OLD.tenant_id,OLD.currency) AND (
  EXISTS(SELECT 1 FROM meridian_posting WHERE account_id=OLD.id) OR
  EXISTS(SELECT 1 FROM meridian_statementrow WHERE account_id=OLD.id) OR
  EXISTS(SELECT 1 FROM meridian_reconciliationrun WHERE account_id=OLD.id)
 ) THEN
  RAISE EXCEPTION 'used account tenant/currency is immutable' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE OR REPLACE FUNCTION meridian_statement_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE a meridian_account;
BEGIN
 SELECT * INTO a FROM meridian_account WHERE id=NEW.account_id FOR SHARE;
 IF a.id IS NULL OR a.currency<>NEW.currency THEN
  RAISE EXCEPTION 'statement currency mismatch' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE FUNCTION meridian_run_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 PERFORM 1 FROM meridian_account WHERE id=NEW.account_id FOR SHARE;
 RETURN NEW;
END $$;
CREATE TRIGGER run_account_guard BEFORE INSERT ON meridian_reconciliationrun FOR EACH ROW EXECUTE FUNCTION meridian_run_guard();
CREATE TRIGGER immutable_run BEFORE UPDATE OR DELETE ON meridian_reconciliationrun FOR EACH ROW EXECUTE FUNCTION meridian_immutable();
CREATE FUNCTION meridian_proposal_identity_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (NEW.run_id,NEW.row_id,NEW.posting_id,NEW.ambiguous) IS DISTINCT FROM (OLD.run_id,OLD.row_id,OLD.posting_id,OLD.ambiguous) THEN
  RAISE EXCEPTION 'proposal identity is immutable' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER proposal_identity_guard BEFORE UPDATE ON meridian_proposal FOR EACH ROW EXECUTE FUNCTION meridian_proposal_identity_guard();
"""
REVERSE = r"""
DROP FUNCTION meridian_proposal_identity_guard() CASCADE;
DROP TRIGGER immutable_run ON meridian_reconciliationrun;
DROP FUNCTION meridian_run_guard() CASCADE;
ALTER TABLE meridian_idempotency DROP CONSTRAINT idempotency_journal_tenant_fk;
CREATE OR REPLACE FUNCTION meridian_account_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (NEW.tenant_id,NEW.currency) IS DISTINCT FROM (OLD.tenant_id,OLD.currency) AND EXISTS(SELECT 1 FROM meridian_posting WHERE account_id=OLD.id) THEN
  RAISE EXCEPTION 'used account tenant/currency is immutable' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
"""


class Migration(migrations.Migration):
    dependencies = [("meridian", "0004_account_insert_lock")]
    operations = [
        migrations.AddConstraint(
            model_name="journal",
            constraint=models.UniqueConstraint(
                fields=("id", "tenant"), name="journal_identity_tenant"
            ),
        ),
        migrations.RunSQL(SQL, REVERSE),
    ]
