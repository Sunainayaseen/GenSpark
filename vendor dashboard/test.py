import mysql.connector

try:
    conn = mysql.connector.connect(
        host="localhost",        # usually localhost
        user="root",             # your MySQL username
        password="",             # your MySQL password
        database="genspark_erp" # your database name
    )
    
    if conn.is_connected():
        print("✅ Database connected successfully!")
        
        # Test query
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES;")
        tables = cursor.fetchall()
        print("Tables in database:", tables)
    else:
        print("❌ Connection failed.")

except mysql.connector.Error as err:
    print("Error:", err)

finally:
    if 'conn' in locals() and conn.is_connected():
        conn.close()
        print("Connection closed.")