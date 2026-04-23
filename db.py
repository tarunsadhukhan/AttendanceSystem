import mysql.connector

# ── Main database (attendance, employees, masters) ────────────
DB_CONFIG = {
    "host":        "13.126.47.172",
    "user":        "myroot",
    "password":    "deb#9876",
    "database":    "sjm",
    "ssl_disabled": True
}

# ── Auth database (login / signup) ───────────────────────────
AUTH_DB_CONFIG = {
    "host":        "13.126.47.172",
    "user":        "myroot",
    "password":    "deb#9876",
    "database":    "sjm",
    "ssl_disabled": True
}

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

def get_auth_db():
    return mysql.connector.connect(**AUTH_DB_CONFIG)

def init_db():
    """Create tables if they don't exist."""
    # ── vownjm: users table (login/signup) ───────────────────
    auth_db     = get_auth_db()
    auth_cursor = auth_db.cursor()
    auth_cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_mst (
            user_id               INT AUTO_INCREMENT PRIMARY KEY,
            email_id              VARCHAR(255) NOT NULL UNIQUE,
            name                  VARCHAR(255),
            password              VARCHAR(255),
            refresh_token         VARCHAR(255),
            active                TINYINT(1)  NOT NULL DEFAULT 1,
            updated_by_con_user   INT         NOT NULL DEFAULT 0,
            updated_date_time     DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    auth_db.commit()
    auth_cursor.close()
    auth_db.close()

    # ── attendance_db: occupations + attendance migrations ────
    db     = get_db()
    cursor = db.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS occupations (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            name        VARCHAR(100) NOT NULL UNIQUE,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()

    # Add att_type column (R=Regular, O=OT, C=Cash)
    try:
        cursor.execute("ALTER TABLE attendance ADD COLUMN att_type CHAR(1) DEFAULT 'R'")
        db.commit()
        print("   [OK] Added 'att_type' column to attendance table")
    except Exception:
        pass

    # Add photo_att column
    try:
        cursor.execute("ALTER TABLE attendance ADD COLUMN photo_att LONGTEXT DEFAULT NULL")
        db.commit()
        print("   [OK] Added 'photo_att' column to attendance table")
    except Exception:
        pass

    # Add shift_hours column
    try:
        cursor.execute("ALTER TABLE attendance ADD COLUMN shift_hours DECIMAL(5,2) DEFAULT 0")
        db.commit()
        print("   [OK] Added 'shift_hours' column to attendance table")
    except Exception:
        pass

    # Add working_hours column
    try:
        cursor.execute("ALTER TABLE attendance ADD COLUMN working_hours DECIMAL(5,2) DEFAULT 0")
        db.commit()
        print("   [OK] Added 'working_hours' column to attendance table")
    except Exception:
        pass

    # Add idle_hours column
    try:
        cursor.execute("ALTER TABLE attendance ADD COLUMN idle_hours DECIMAL(5,2) DEFAULT 0")
        db.commit()
        print("   [OK] Added 'idle_hours' column to attendance table")
    except Exception:
        pass

    cursor.close()
    db.close()
