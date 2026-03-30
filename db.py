import mysql.connector

DB_CONFIG = {
    "host":     "3.7.255.145",
    "user":     "Tarun",
    "password": "db_tarunji!123",   # ← your MySQL password
    "database": "attendance_db",
    "ssl_disabled": True
}

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

def init_db():
    """Create the users table if it doesn't exist."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            username    VARCHAR(50)  NOT NULL UNIQUE,
            password    VARCHAR(255) NOT NULL,
            full_name   VARCHAR(100) NOT NULL,
            email       VARCHAR(100) UNIQUE,
            role        ENUM('admin','user') DEFAULT 'user',
            is_active   TINYINT(1) DEFAULT 1,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS occupations (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            name        VARCHAR(100) NOT NULL UNIQUE,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()

    # ── Attendance table migrations ──────────────────────────
    # Add att_type column (R=Regular, O=OT, C=Cash)
    try:
        cursor.execute("""
            ALTER TABLE attendance ADD COLUMN att_type CHAR(1) DEFAULT 'R'
        """)
        db.commit()
        print("   [OK] Added 'att_type' column to attendance table")
    except Exception:
        pass  # column already exists

    # Add photo_att column (stores captured attendance photo as HTML img)
    try:
        cursor.execute("""
            ALTER TABLE attendance ADD COLUMN photo_att LONGTEXT DEFAULT NULL
        """)
        db.commit()
        print("   [OK] Added 'photo_att' column to attendance table")
    except Exception:
        pass  # column already exists

    # Add shift_hours column
    try:
        cursor.execute("""
            ALTER TABLE attendance ADD COLUMN shift_hours DECIMAL(5,2) DEFAULT 0
        """)
        db.commit()
        print("   [OK] Added 'shift_hours' column to attendance table")
    except Exception:
        pass  # column already exists

    # Add working_hours column
    try:
        cursor.execute("""
            ALTER TABLE attendance ADD COLUMN working_hours DECIMAL(5,2) DEFAULT 0
        """)
        db.commit()
        print("   [OK] Added 'working_hours' column to attendance table")
    except Exception:
        pass  # column already exists

    # Add idle_hours column
    try:
        cursor.execute("""
            ALTER TABLE attendance ADD COLUMN idle_hours DECIMAL(5,2) DEFAULT 0
        """)
        db.commit()
        print("   [OK] Added 'idle_hours' column to attendance table")
    except Exception:
        pass  # column already exists

    cursor.close()
    db.close()
