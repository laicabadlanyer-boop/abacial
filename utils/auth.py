import bcrypt
from flask import session, request
from functools import wraps
from utils.database import get_db


def _update_last_timestamp(db, table, pk_column, pk_value, column):
    """Safely update last_login/last_logout columns if they exist."""
    if not db or pk_value is None:
        return
    cursor = None
    try:
        cursor = db.cursor()
        cursor.execute(f"SHOW COLUMNS FROM {table} LIKE %s", (column,))
        if not cursor.fetchone():
            return
        cursor.execute(
            f"UPDATE {table} SET {column} = NOW() WHERE {pk_column} = %s",
            (pk_value,),
        )
        db.commit()
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        print(f"⚠️ Unable to update {table}.{column}: {exc}")
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(hashed_password, user_password):
    try:
        return bcrypt.checkpw(user_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def login_user(account_id, role, email, full_name="", auth_user_id=None):
    session['user_id'] = account_id
    session['auth_user_id'] = auth_user_id or account_id
    session['user_role'] = role
    session['user_email'] = email
    session['user_name'] = full_name
    session['logged_in'] = True
    session.pop('auth_session_id', None)
    
    db = None
    cursor = None
    try:
        db = get_db()
        if db:
            cursor = db.cursor()
            try:
                # Check which columns exist in auth_sessions table
                cursor.execute('SHOW COLUMNS FROM auth_sessions')
                columns_raw = cursor.fetchall()
                columns = [col.get('Field') if isinstance(col, dict) else col[0] for col in columns_raw]
                
                # Map role for auth_sessions table: 'admin' -> 'super_admin' (per database schema)
                # auth_sessions.role is ENUM('hr','applicant','super_admin')
                db_role = 'super_admin' if role == 'admin' else role
                
                # Build dynamic INSERT statement based on available columns
                has_last_activity = 'last_activity' in columns
                has_logout_time = 'logout_time' in columns
                has_ip_address = 'ip_address' in columns
                has_user_agent = 'user_agent' in columns
                has_is_active = 'is_active' in columns

                fields = ['user_id', 'role', 'login_time']
                values = ['%s', '%s', 'NOW()']
                params = [session.get('auth_user_id'), db_role]
                last_activity_value = 'NOW()'

                if has_last_activity:
                    fields.append('last_activity')
                    values.append(last_activity_value)
                if has_logout_time:
                    fields.append('logout_time')
                    values.append('NOW()')

                if has_ip_address:
                    try:
                        ip_address = request.remote_addr if request else None
                    except Exception:
                        ip_address = None
                    fields.append('ip_address')
                    values.append('%s')
                    params.append(ip_address)

                if has_user_agent:
                    try:
                        user_agent = request.headers.get('User-Agent', '') if request else ''
                    except Exception:
                        user_agent = ''
                    fields.append('user_agent')
                    values.append('%s')
                    params.append(user_agent)

                if has_is_active:
                    fields.append('is_active')
                    values.append('1')

                sql = f"INSERT INTO auth_sessions ({', '.join(fields)}) VALUES ({', '.join(values)})"
                cursor.execute(sql, tuple(params))
                db.commit()
                session['auth_session_id'] = cursor.lastrowid
                _update_last_timestamp(db, 'users', 'user_id', session.get('auth_user_id'), 'last_login')
                if role in {'admin', 'hr'}:
                    _update_last_timestamp(db, 'admins', 'admin_id', account_id, 'last_login')
                elif role == 'applicant':
                    _update_last_timestamp(db, 'applicants', 'applicant_id', account_id, 'last_login')
            except Exception as e:
                print(f"Error logging session: {e}")
                import traceback
                traceback.print_exc()
                if db:
                    try:
                        db.rollback()
                    except Exception:
                        pass
            finally:
                if cursor:
                    try:
                        cursor.close()
                    except Exception:
                        pass
    except Exception as outer_e:
        print(f"Error in login_user database connection: {outer_e}")
        import traceback
        traceback.print_exc()

def logout_user():
    auth_user_id = session.get('auth_user_id')
    account_id = session.get('user_id')
    role = session.get('user_role')

    db = get_db()
    if db and auth_user_id:
        cursor = db.cursor()
        try:
            auth_session_id = session.get('auth_session_id')
            if auth_session_id:
                cursor.execute("SHOW COLUMNS FROM auth_sessions")
                columns = {row[0] if isinstance(row, tuple) else row.get('Field') for row in (cursor.fetchall() or [])}
                fields = []
                params = []
                if 'is_active' in columns:
                    fields.append('is_active = 0')
                if 'last_activity' in columns:
                    fields.append('last_activity = NOW()')
                if 'logout_time' in columns:
                    fields.append('logout_time = NOW()')
                set_clause = ', '.join(fields) if fields else 'logout_time = NOW()'
                cursor.execute(
                    f"UPDATE auth_sessions SET {set_clause} WHERE session_id = %s",
                    (auth_session_id,)
                )
            else:
                cursor.execute("SHOW COLUMNS FROM auth_sessions")
                columns = {row[0] if isinstance(row, tuple) else row.get('Field') for row in (cursor.fetchall() or [])}
                fields = []
                params = []
                if 'is_active' in columns:
                    fields.append('is_active = 0')
                if 'last_activity' in columns:
                    fields.append('last_activity = NOW()')
                if 'logout_time' in columns:
                    fields.append('logout_time = NOW()')
                set_clause = ', '.join(fields) if fields else 'logout_time = NOW()'
                cursor.execute(
                    f"UPDATE auth_sessions SET {set_clause} WHERE user_id = %s AND ({'is_active = 1' if 'is_active' in columns else '1=1'})",
                    (session['auth_user_id'],)
                )
            db.commit()
            _update_last_timestamp(db, 'users', 'user_id', auth_user_id, 'last_logout')
            if role in {'admin', 'hr'}:
                _update_last_timestamp(db, 'admins', 'admin_id', account_id, 'last_logout')
            elif role == 'applicant':
                _update_last_timestamp(db, 'applicants', 'applicant_id', account_id, 'last_logout')
        except Exception as e:
            print(f"Error updating logout time: {e}")
            db.rollback()
        finally:
            cursor.close()
    
    session.pop('auth_session_id', None)
    session.clear()

def get_current_user():
    if not session.get('logged_in'):
        return None

    auth_user_id = session.get('auth_user_id')
    if not auth_user_id:
        return None

    db = get_db()
    if not db:
        return {
            'id': session.get('user_id'),
            'role': session.get('user_role'),
            'email': session.get('user_email'),
            'name': session.get('user_name', 'User'),
            'branch_id': session.get('branch_id'),
            'branch_name': session.get('branch_name'),
        }

    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT user_id, email, user_type, is_active
            FROM users
            WHERE user_id = %s
            LIMIT 1
            """,
            (auth_user_id,),
        )
        user_record = cursor.fetchone()

        if not user_record or not user_record.get('is_active'):
            logout_user()
            return None

        user_type = user_record['user_type']
        role = session.get('user_role')
        account_id = session.get('user_id')
        display_name = session.get('user_name', 'User')
        branch_id = None
        branch_name = None

        if user_type in {'super_admin', 'hr'}:
            cursor.execute(
                """
                SELECT a.admin_id,
                       a.full_name
                FROM admins a
                WHERE a.user_id = %s
                LIMIT 1
                """,
                (auth_user_id,),
            )
            admin_record = cursor.fetchone()
            if admin_record:
                account_id = admin_record['admin_id']
                display_name = admin_record.get('full_name') or display_name
                # branch_id column has been removed from admins table
                # HR accounts manage all branches
                branch_id = None
                branch_name = None
                role = 'admin' if user_type == 'super_admin' else 'hr'
            else:
                role = 'admin' if user_type == 'super_admin' else 'hr'
                branch_id = None
                branch_name = None
        elif user_type == 'applicant':
            cursor.execute(
                """
                SELECT applicant_id, full_name
                FROM applicants
                WHERE user_id = %s
                LIMIT 1
                """,
                (auth_user_id,),
            )
            applicant_record = cursor.fetchone()
            if applicant_record:
                account_id = applicant_record['applicant_id']
                display_name = applicant_record.get('full_name') or display_name
                role = 'applicant'
            else:
                role = 'applicant'
        else:
            role = 'applicant'

        # Sync session with canonical values
        session['user_role'] = role
        session['user_id'] = account_id
        session['user_name'] = display_name
        session['user_email'] = user_record['email']

        if branch_id:
            session['branch_id'] = branch_id
            session['branch_name'] = branch_name
        else:
            session.pop('branch_id', None)
            session.pop('branch_name', None)

        return {
            'id': account_id,
            'role': role,
            'email': user_record['email'],
            'name': display_name,
            'branch_id': branch_id,
            'branch_name': branch_name,
            'user_type': user_type,
        }
    except Exception as exc:
        print(f'⚠️ current_user lookup failed: {exc}')
        return {
            'id': session.get('user_id'),
            'role': session.get('user_role'),
            'email': session.get('user_email'),
            'name': session.get('user_name', 'User'),
            'branch_id': session.get('branch_id'),
            'branch_name': session.get('branch_name'),
        }
    finally:
        cursor.close()

def is_logged_in():
    return 'logged_in' in session and session['logged_in']
