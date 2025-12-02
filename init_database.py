import mysql.connector
from mysql.connector import Error
import config
import bcrypt
import sys
import os

# Add the parent directory to the path to import utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.auth import hash_password

def initialize_database():
    connection = None
    try:
        # Connect to MySQL server
        connection = mysql.connector.connect(
            host=config.Config.MYSQL_HOST,
            user=config.Config.MYSQL_USER,
            password=config.Config.MYSQL_PASSWORD
        )
        
        if connection.is_connected():
            cursor = connection.cursor()
            
            # Create database
            cursor.execute("CREATE DATABASE IF NOT EXISTS recruitment_system")
            cursor.execute("USE recruitment_system")
            
            print("✅ Database created successfully")
            
            # First, disable foreign key checks to allow dropping tables
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            
            # Drop all tables in correct order (child tables first)
            tables_to_drop = [
                'activity_logs', 'evaluations', 'evaluation', 'interviews', 
                'notifications', 'job_views', 'applications', 'jobs',
                'profile_changes', 'password_resets', 'auth_sessions', 
                'resumes', 'resume', 'admin', 'admins', 'applicants', 'branch', 'branches',
                'hr_branch_assignments', 'system_settings', 'users', 'saved_jobs', 'positions', 'results'
            ]
            
            for table in tables_to_drop:
                try:
                    cursor.execute(f"DROP TABLE IF EXISTS {table}")
                    print(f"✅ Dropped table: {table}")
                except Error as e:
                    print(f"⚠️ Could not drop table {table}: {e}")
            
            # Re-enable foreign key checks
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            
            print("✅ All existing tables dropped successfully")
            
            # Create tables in correct order (parent tables first)
            # Matching COMPLETE_DATABASE_SCHEMA.sql exactly
            tables_sql = [
                # TABLE 1: users
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    user_type ENUM('super_admin', 'hr', 'applicant') NOT NULL,
                    is_active TINYINT(1) NOT NULL DEFAULT 1,
                    password_change_at DATETIME DEFAULT NULL,
                    last_login DATETIME DEFAULT NULL,
                    last_logout DATETIME DEFAULT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    email_verified TINYINT(1) DEFAULT 0
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """,
                # TABLE 2: branches
                """
                CREATE TABLE IF NOT EXISTS branches (
                    branch_id INT(20) NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    branch_name VARCHAR(200) NOT NULL,
                    address VARCHAR(200) NOT NULL,
                    operating_hours VARCHAR(200) NOT NULL,
                    is_active TINYINT(1) NOT NULL DEFAULT 1,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """,
                # TABLE 3: admins
                """
                CREATE TABLE IF NOT EXISTS admins (
                    admin_id INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    user_id INT(11) DEFAULT NULL,
                    full_name VARCHAR(200) NOT NULL,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    role ENUM('admin', 'hr') NOT NULL DEFAULT 'hr',
                    is_active TINYINT(1) NOT NULL DEFAULT 1,
                    last_login DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_logout DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """,
                # TABLE 4: applicants
                """
                CREATE TABLE IF NOT EXISTS applicants (
                    applicant_id INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    user_id INT(11) DEFAULT NULL,
                    full_name VARCHAR(200) NOT NULL,
                    email VARCHAR(200) NOT NULL UNIQUE,
                    phone_number VARCHAR(255) NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """,
                # TABLE 5: jobs
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id INT(20) NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    description TEXT NOT NULL,
                    requirements TEXT NOT NULL,
                    status ENUM('open', 'closed') NOT NULL DEFAULT 'open',
                    branch_id INT(20) DEFAULT NULL,
                    posted_by INT(20) DEFAULT NULL,
                    posted_at DATETIME NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (branch_id) REFERENCES branches(branch_id) ON DELETE SET NULL,
                    FOREIGN KEY (posted_by) REFERENCES admins(admin_id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """,
                # TABLE 6: resumes
                """
                CREATE TABLE IF NOT EXISTS resumes (
                    resume_id INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    applicant_id INT(11) NOT NULL,
                    file_name VARCHAR(255) NOT NULL,
                    file_path VARCHAR(255) NOT NULL,
                    file_size_bytes INT(11) NOT NULL,
                    uploaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (applicant_id) REFERENCES applicants(applicant_id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """,
                # TABLE 7: applications
                """
                CREATE TABLE IF NOT EXISTS applications (
                    application_id INT(20) NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    applicant_id INT(11) NOT NULL,
                    job_id INT(20) NOT NULL,
                    resume_id INT(11) DEFAULT NULL,
                    status ENUM('pending', 'scheduled', 'interviewed', 'hired', 'rejected') NOT NULL DEFAULT 'pending',
                    submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
                    view_at DATETIME DEFAULT NULL,
                    FOREIGN KEY (applicant_id) REFERENCES applicants(applicant_id) ON DELETE CASCADE,
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
                    FOREIGN KEY (resume_id) REFERENCES resumes(resume_id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """,
                # TABLE 8: interviews
                """
                CREATE TABLE IF NOT EXISTS interviews (
                    interview_id INT(20) NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    application_id INT(20) NOT NULL,
                    scheduled_date DATETIME NOT NULL,
                    interview_mode VARCHAR(50) NOT NULL,
                    location VARCHAR(255) NOT NULL,
                    notes TEXT NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (application_id) REFERENCES applications(application_id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """,
                # TABLE 9: notifications
                """
                CREATE TABLE IF NOT EXISTS notifications (
                    notification_id INT(20) NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    application_id INT(20) DEFAULT NULL,
                    message TEXT NOT NULL,
                    sent_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    is_read TINYINT(1) NOT NULL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (application_id) REFERENCES applications(application_id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """,
                # TABLE 10: auth_sessions
                """
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    session_id INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    user_id INT(11) NOT NULL,
                    role ENUM('hr', 'applicant', 'super_admin') NOT NULL,
                    login_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    logout_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    is_active TINYINT(1) NOT NULL DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """,
                # TABLE 11: password_resets
                """
                CREATE TABLE IF NOT EXISTS password_resets (
                    id INT(20) NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    user_email VARCHAR(100) NOT NULL,
                    token VARCHAR(255) NOT NULL,
                    role ENUM('admin', 'applicant', 'hr') NOT NULL,
                    expired_at DATETIME NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """,
                # TABLE 12: profile_changes
                """
                CREATE TABLE IF NOT EXISTS profile_changes (
                    change_id INT(20) NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    user_id INT(20) NOT NULL,
                    role ENUM('admin', 'hr', 'applicant') DEFAULT NULL,
                    field_changed VARCHAR(255) NOT NULL,
                    old_value TEXT NOT NULL,
                    new_value TEXT NOT NULL,
                    changed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """,
                # TABLE 13: saved_jobs
                """
                CREATE TABLE IF NOT EXISTS saved_jobs (
                    save_job_id INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    applicant_id INT(11) NOT NULL,
                    job_id INT(11) NOT NULL,
                    saved_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_saved_job (applicant_id, job_id),
                    FOREIGN KEY (applicant_id) REFERENCES applicants(applicant_id) ON DELETE CASCADE,
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
                """,
                # TABLE 14: activity_logs
                """
                CREATE TABLE IF NOT EXISTS activity_logs (
                    log_id INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    admin_id INT(11) DEFAULT NULL,
                    action VARCHAR(255) NOT NULL,
                    target_table VARCHAR(255) NOT NULL,
                    details TEXT DEFAULT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (admin_id) REFERENCES admins(admin_id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """,


            ]
            
            for sql in tables_sql:
                try:
                    cursor.execute(sql)
                    table_name = sql.split('(')[0].split()[-1]
                    print(f"✅ Created table: {table_name}")
                except Error as e:
                    print(f"❌ Error creating table: {e}")
            
            connection.commit()
            print("✅ All tables created successfully")
            
            # Create default admin account
            try:
                # Hash password for default admin using the same function as the app
                default_password = "whitehat88@2025"
                password_hash = hash_password(default_password)
                
                # Insert into users table (update password_hash if user already exists)
                cursor.execute("""
                    INSERT INTO users (email, password_hash, user_type, is_active, email_verified)
                    VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                        password_hash=VALUES(password_hash),
                        user_type=VALUES(user_type),
                        is_active=VALUES(is_active),
                        email_verified=VALUES(email_verified)
                """, ('admin@whitehat88.com', password_hash, 'super_admin', 1, 1))
                
                # Get the user_id
                cursor.execute("SELECT user_id FROM users WHERE email = %s", ('admin@whitehat88.com',))
                user_result = cursor.fetchone()
                
                if user_result:
                    user_id = user_result[0]
                    
                    # Insert into admins table (update password_hash and other fields if admin already exists)
                    cursor.execute("""
                        INSERT INTO admins (user_id, full_name, email, password_hash, role, is_active)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE 
                            password_hash=VALUES(password_hash),
                            full_name=VALUES(full_name),
                            role=VALUES(role),
                            is_active=VALUES(is_active)
                    """, (user_id, 'System Administrator', 'admin@whitehat88.com', password_hash, 'admin', 1))
                    
                    print("✅ Default admin account created")
                    print("   Email: admin@whitehat88.com")
                    print("   Password: whitehat88@2025")
                
                connection.commit()
            except Error as e:
                print(f"⚠️ Could not create default admin account: {e}")
            
            print("")
            print("🎉 Database setup completed successfully!")
            print("")
            print("📝 Database is ready for use!")
            
    except Error as e:
        print(f"❌ Error: {e}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print("✅ Database initialization completed")

if __name__ == "__main__":
    initialize_database()