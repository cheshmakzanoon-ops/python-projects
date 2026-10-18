def query(cursor):
    key = input()
    cursor.execute("SELECT restricted_measurement FROM readings WHERE key = '" + key + "'")
