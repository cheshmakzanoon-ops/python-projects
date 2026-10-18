from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("meridian", "0003_reversal_guard_alias")]
    operations = [
        migrations.RunSQL(
            "CREATE OR REPLACE FUNCTION meridian_posting_guard() RETURNS trigger LANGUAGE plpgsql AS $$\nDECLARE j meridian_journal; a meridian_account; journal_xid bigint;\nBEGIN\n SELECT * INTO j FROM meridian_journal WHERE id=NEW.journal_id;\n SELECT xmin::text::bigint INTO journal_xid FROM meridian_journal WHERE id=NEW.journal_id;\n SELECT * INTO a FROM meridian_account WHERE id=NEW.account_id FOR SHARE;\n IF j.id IS NULL OR a.id IS NULL OR j.tenant_id<>a.tenant_id OR j.currency<>a.currency THEN\n  RAISE EXCEPTION 'posting tenant/currency mismatch' USING ERRCODE='23514';\n END IF;\n IF journal_xid <> (txid_current() % 4294967296) THEN\n  RAISE EXCEPTION 'cannot append to committed journal' USING ERRCODE='23514';\n END IF;\n RETURN NEW;\nEND $$;\n",
            migrations.RunSQL.noop,
        )
    ]
