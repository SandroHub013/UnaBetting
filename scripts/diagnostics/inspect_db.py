import sqlite3
import pandas as pd

db_path = r"G:\tennis betting\data\betanalytix.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

print("Tables in Database:")
for table in tables:
    table_name = table[0]
    print(f"\n--- Table: {table_name} ---")
    
    # Get column info
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = cursor.fetchall()
    print("Columns:", [col[1] for col in columns])
    
    # Get row count
    cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
    count = cursor.fetchone()[0]
    print(f"Row count: {count}")
    
    # Sample data
    if count > 0:
        df = pd.read_sql_query(f"SELECT * FROM {table_name} LIMIT 3;", conn)
        print("Sample data:")
        print(df.to_string(index=False))

conn.close()
