from django.db import migrations

SQL = r"""
DO $$ BEGIN
 IF EXISTS(SELECT j.id FROM meridian_journal j LEFT JOIN meridian_posting p ON p.journal_id=j.id GROUP BY j.id HAVING count(p.id)<2 OR count(p.id)>256 OR sum(p.amount::numeric)<>0) OR EXISTS(SELECT 1 FROM meridian_posting p JOIN meridian_journal j ON j.id=p.journal_id JOIN meridian_account a ON a.id=p.account_id WHERE a.tenant_id<>j.tenant_id OR a.currency<>j.currency) THEN
 RAISE EXCEPTION 'existing fixture ledger violates accounting invariants' USING ERRCODE='23514';
 END IF;
END $$;
CREATE FUNCTION meridian_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'immutable posted or audit data' USING ERRCODE='23514'; END $$;
CREATE TRIGGER immutable_journal BEFORE UPDATE OR DELETE ON meridian_journal FOR EACH ROW EXECUTE FUNCTION meridian_immutable();
CREATE TRIGGER immutable_posting BEFORE UPDATE OR DELETE ON meridian_posting FOR EACH ROW EXECUTE FUNCTION meridian_immutable();
CREATE TRIGGER immutable_idempotency BEFORE UPDATE OR DELETE ON meridian_idempotency FOR EACH ROW EXECUTE FUNCTION meridian_immutable();
CREATE TRIGGER immutable_statement BEFORE UPDATE OR DELETE ON meridian_statementrow FOR EACH ROW EXECUTE FUNCTION meridian_immutable();
CREATE TRIGGER immutable_decision BEFORE UPDATE OR DELETE ON meridian_decisionaudit FOR EACH ROW EXECUTE FUNCTION meridian_immutable();
CREATE TRIGGER immutable_match BEFORE UPDATE OR DELETE ON meridian_approvedmatch FOR EACH ROW EXECUTE FUNCTION meridian_immutable();
CREATE FUNCTION meridian_sequence() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 UPDATE meridian_tenant SET last_sequence=last_sequence+1 WHERE id=NEW.tenant_id RETURNING last_sequence INTO NEW.sequence;
 RETURN NEW;
END $$;
CREATE TRIGGER sequence_journal BEFORE INSERT ON meridian_journal FOR EACH ROW EXECUTE FUNCTION meridian_sequence();
CREATE FUNCTION meridian_account_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (NEW.tenant_id,NEW.currency) IS DISTINCT FROM (OLD.tenant_id,OLD.currency) AND EXISTS(SELECT 1 FROM meridian_posting WHERE account_id=OLD.id) THEN
  RAISE EXCEPTION 'used account tenant/currency is immutable' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER account_guard BEFORE UPDATE ON meridian_account FOR EACH ROW EXECUTE FUNCTION meridian_account_guard();
CREATE FUNCTION meridian_posting_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE j meridian_journal; a meridian_account; journal_xid bigint;
BEGIN
 SELECT *, xmin::text::bigint INTO j FROM meridian_journal WHERE id=NEW.journal_id;
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
CREATE TRIGGER posting_guard BEFORE INSERT ON meridian_posting FOR EACH ROW EXECUTE FUNCTION meridian_posting_guard();
CREATE FUNCTION meridian_journal_check() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE target uuid; j meridian_journal; total numeric; count_rows bigint;
BEGIN
 IF TG_TABLE_NAME='meridian_journal' THEN target=NEW.id; ELSE target=NEW.journal_id; END IF;
 SELECT * INTO j FROM meridian_journal WHERE id=target;
 SELECT count(*),COALESCE(sum(amount::numeric),0) INTO count_rows,total FROM meridian_posting WHERE journal_id=target;
 IF count_rows<2 OR count_rows>256 OR total<>0 THEN
  RAISE EXCEPTION 'journal must have 2..256 balanced postings' USING ERRCODE='23514';
 END IF;
 IF j.reversal_of_id IS NOT NULL THEN
  IF NOT EXISTS(SELECT 1 FROM meridian_journal original WHERE original.id=j.reversal_of_id AND original.tenant_id=j.tenant_id AND original.currency=j.currency AND original.reversal_of_id IS NULL) OR EXISTS(
   SELECT account_id FROM meridian_posting WHERE journal_id IN(target,j.reversal_of_id) GROUP BY account_id HAVING sum(amount::numeric)<>0 OR count(*)<>2
  ) THEN RAISE EXCEPTION 'invalid full reversal' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER journal_balance AFTER INSERT ON meridian_journal DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION meridian_journal_check();
CREATE CONSTRAINT TRIGGER posting_balance AFTER INSERT ON meridian_posting DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION meridian_journal_check();
CREATE FUNCTION meridian_statement_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM meridian_account WHERE id=NEW.account_id AND currency=NEW.currency) THEN RAISE EXCEPTION 'statement currency mismatch' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER statement_guard BEFORE INSERT ON meridian_statementrow FOR EACH ROW EXECUTE FUNCTION meridian_statement_guard();
CREATE FUNCTION meridian_match_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p meridian_proposal; run_account uuid;
BEGIN
 IF TG_TABLE_NAME='meridian_approvedmatch' THEN
  SELECT * INTO p FROM meridian_proposal WHERE id=NEW.proposal_id;
  IF p.row_id<>NEW.row_id OR p.posting_id<>NEW.posting_id THEN RAISE EXCEPTION 'match proposal mismatch' USING ERRCODE='23514'; END IF;
 ELSE p=NEW;
 END IF;
 SELECT account_id INTO run_account FROM meridian_reconciliationrun WHERE id=p.run_id;
 IF NOT EXISTS(SELECT 1 FROM meridian_statementrow s JOIN meridian_posting e ON e.id=p.posting_id WHERE s.id=p.row_id AND s.account_id=run_account AND e.account_id=run_account AND e.amount=s.amount) THEN
  RAISE EXCEPTION 'reconciliation account or amount mismatch' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER proposal_guard BEFORE INSERT ON meridian_proposal FOR EACH ROW EXECUTE FUNCTION meridian_match_guard();
CREATE TRIGGER match_guard BEFORE INSERT ON meridian_approvedmatch FOR EACH ROW EXECUTE FUNCTION meridian_match_guard();
"""

REVERSE = r"""
DROP FUNCTION meridian_match_guard() CASCADE;
DROP FUNCTION meridian_statement_guard() CASCADE;
DROP FUNCTION meridian_journal_check() CASCADE;
DROP FUNCTION meridian_posting_guard() CASCADE;
DROP FUNCTION meridian_account_guard() CASCADE;
DROP FUNCTION meridian_sequence() CASCADE;
DROP FUNCTION meridian_immutable() CASCADE;
"""


class Migration(migrations.Migration):
    dependencies = [("meridian", "0001_initial")]
    operations = [
        migrations.RunSQL(
            SQL.replace("SELECT *, xmin::text::bigint INTO j", "SELECT * INTO j"), REVERSE
        )
    ]
