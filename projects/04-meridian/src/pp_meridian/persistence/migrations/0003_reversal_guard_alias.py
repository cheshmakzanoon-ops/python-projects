from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("meridian", "0002_database_invariants")]
    operations = [
        migrations.RunSQL(
            "CREATE OR REPLACE FUNCTION meridian_journal_check() RETURNS trigger LANGUAGE plpgsql AS $$\nDECLARE target uuid; j meridian_journal; total numeric; count_rows bigint;\nBEGIN\n IF TG_TABLE_NAME='meridian_journal' THEN target=NEW.id; ELSE target=NEW.journal_id; END IF;\n SELECT * INTO j FROM meridian_journal WHERE id=target;\n SELECT count(*),COALESCE(sum(amount::numeric),0) INTO count_rows,total FROM meridian_posting WHERE journal_id=target;\n IF count_rows<2 OR count_rows>256 OR total<>0 THEN\n  RAISE EXCEPTION 'journal must have 2..256 balanced postings' USING ERRCODE='23514';\n END IF;\n IF j.reversal_of_id IS NOT NULL THEN\n  IF NOT EXISTS(SELECT 1 FROM meridian_journal original WHERE original.id=j.reversal_of_id AND original.tenant_id=j.tenant_id AND original.currency=j.currency AND original.reversal_of_id IS NULL) OR EXISTS(\n   SELECT account_id FROM meridian_posting WHERE journal_id IN(target,j.reversal_of_id) GROUP BY account_id HAVING sum(amount::numeric)<>0 OR count(*)<>2\n  ) THEN RAISE EXCEPTION 'invalid full reversal' USING ERRCODE='23514'; END IF;\n END IF;\n RETURN NULL;\nEND $$;\n",
            migrations.RunSQL.noop,
        )
    ]
