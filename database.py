"""
中学自动调课系统 - 数据库模块
使用SQLite进行数据持久化
"""
import sqlite3
from datetime import datetime
from pathlib import Path
import pandas as pd

# 数据库路径
DB_PATH = Path(__file__).parent / "data" / "schedule.db"

class Database:
    """数据库操作类"""
    
    def __init__(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()
    
    def _init_tables(self):
        """初始化数据库表"""
        cursor = self.conn.cursor()
        
        # 用户表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', '教务')),
                name TEXT,
                teacher_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 教师表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS teachers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                course_types TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 班级表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                grade TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 课表明细表 (每条记录：班级+星期+节次 -> 教师+课程)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schedule_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER NOT NULL,
                day_of_week INTEGER NOT NULL,
                period INTEGER NOT NULL,
                teacher_id INTEGER NOT NULL,
                course_name TEXT,
                is_evening INTEGER DEFAULT 0,
                FOREIGN KEY (class_id) REFERENCES classes(id),
                FOREIGN KEY (teacher_id) REFERENCES teachers(id),
                UNIQUE(class_id, day_of_week, period)
            )
        """)
        
        # 晚自习轮值表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evening_rotation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER NOT NULL,
                order_index INTEGER NOT NULL,
                semester TEXT DEFAULT '2024-2025-1',
                FOREIGN KEY (teacher_id) REFERENCES teachers(id)
            )
        """)
        
        # 当前晚自习指针
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evening_pointer (
                id INTEGER PRIMARY KEY,
                current_index INTEGER DEFAULT -1,
                semester TEXT DEFAULT '2024-2025-1',
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 科目顺序列表（固定顺序，用于顶课分配）
        COURSE_ORDER = [
            '语文', '数学', '英语', '物理', '化学', '道法', '历史', '生物', 
            '地理', '音乐', '体育', '美术', '信息技术', '劳动'
        ]
        
        # 教师排课冲突记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS teacher_skip_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER NOT NULL,
                class_id INTEGER NOT NULL,
                day_of_week INTEGER NOT NULL,
                period INTEGER NOT NULL,
                reason TEXT DEFAULT 'conflict',
                semester TEXT DEFAULT '2024-2025-1',
                skip_count INTEGER DEFAULT 1,
                last_skip_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (teacher_id) REFERENCES teachers(id),
                FOREIGN KEY (class_id) REFERENCES classes(id),
                UNIQUE(teacher_id, class_id, day_of_week, period, semester)
            )
        """)
        
        # 顶课记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS substitutions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                absent_teacher_id INTEGER NOT NULL,
                substitute_teacher_id INTEGER,
                class_id INTEGER NOT NULL,
                day_of_week INTEGER NOT NULL,
                period INTEGER NOT NULL,
                course_type TEXT NOT NULL,
                original_course TEXT,
                leave_reason TEXT DEFAULT '',
                assignment_type TEXT DEFAULT 'auto',
                created_by INTEGER,
                operated_by INTEGER,
                operated_at TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (absent_teacher_id) REFERENCES teachers(id),
                FOREIGN KEY (substitute_teacher_id) REFERENCES teachers(id),
                FOREIGN KEY (class_id) REFERENCES classes(id),
                FOREIGN KEY (created_by) REFERENCES users(id),
                FOREIGN KEY (operated_by) REFERENCES users(id)
            )
        """)
        
        # 通知表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT NOT NULL,
                content TEXT,
                is_read INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 创建默认用户
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO users (username, password, role, name) VALUES (?, ?, ?, ?)",
                ('admin', 'admin123', 'admin', '系统管理员')
            )
            cursor.execute(
                "INSERT INTO users (username, password, role, name) VALUES (?, ?, ?, ?)",
                ('jiaowu', 'jiaowu123', '教务', '教务员')
            )
        
        # 初始化晚自习指针
        cursor.execute("SELECT COUNT(*) FROM evening_pointer")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO evening_pointer (id, current_index) VALUES (1, -1)")
        
        # 数据库迁移：添加 leave_reason 字段（如果不存在）
        try:
            cursor.execute("ALTER TABLE substitutions ADD COLUMN leave_reason TEXT DEFAULT ''")
        except:
            pass
        
        # 迁移：确保 evening_assigned 表存在（用于跟踪已分配的晚自习教师）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evening_assigned (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER NOT NULL,
                rotation_id INTEGER,
                assigned_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.conn.commit()
    
    # ==================== 用户相关 ====================
    
    def check_login(self, username, password):
        """验证登录"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, username, role, name, teacher_id FROM users WHERE username = ? AND password = ?",
            (username, password)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_user(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_teachers_for_user(self):
        """获取可以作为用户的教师列表"""
        df = pd.read_sql("""
            SELECT t.*, u.id as user_id, u.username 
            FROM teachers t 
            LEFT JOIN users u ON t.id = u.teacher_id AND u.role = '教师'
            WHERE t.is_active = 1 
            ORDER BY t.name
        """, self.conn)
        return df
    
    # ==================== 教师相关 ====================
    
    def import_teachers(self, teachers_list):
        cursor = self.conn.cursor()
        for name in teachers_list:
            cursor.execute("INSERT OR IGNORE INTO teachers (name) VALUES (?)", (name,))
        self.conn.commit()
    
    def get_all_teachers(self):
        df = pd.read_sql("SELECT * FROM teachers WHERE is_active = 1 ORDER BY name", self.conn)
        return df
    
    def get_teacher(self, teacher_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM teachers WHERE id = ?", (teacher_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_teacher_by_name(self, name):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM teachers WHERE name = ?", (name,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_teacher_courses(self, teacher_id):
        """获取某教师的所有课程"""
        df = pd.read_sql("""
            SELECT s.*, c.name as class_name, c.grade
            FROM schedule_items s
            JOIN classes c ON s.class_id = c.id
            WHERE s.teacher_id = ?
            ORDER BY s.day_of_week, s.period
        """, self.conn, params=(teacher_id,))
        return df
    
    def update_teacher_name(self, teacher_id, new_name):
        """修改教师姓名"""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE teachers SET name = ? WHERE id = ?", (new_name, teacher_id))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def add_teacher(self, name):
        """添加教师"""
        cursor = self.conn.cursor()
        try:
            cursor.execute("INSERT INTO teachers (name) VALUES (?)", (name,))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None  # 教师已存在
    
    def delete_teacher(self, teacher_id):
        """删除教师（软删除，设为非活跃）"""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE teachers SET is_active = 0 WHERE id = ?", (teacher_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def reactivate_teacher(self, teacher_id):
        """重新激活教师"""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE teachers SET is_active = 1 WHERE id = ?", (teacher_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def get_all_teachers_including_inactive(self):
        """获取所有教师（包括已删除的）"""
        df = pd.read_sql("SELECT * FROM teachers ORDER BY is_active DESC, name", self.conn)
        return df
    
    def get_teacher_schedule_by_day(self, teacher_id, day_of_week):
        """获取教师某一天的课表"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT s.*, c.name as class_name, c.grade,
                   CASE WHEN sub.id IS NOT NULL THEN 1 ELSE 0 END as is_substituted,
                   sub.substitute_teacher_id, sub.status as sub_status
            FROM schedule_items s
            JOIN classes c ON s.class_id = c.id
            LEFT JOIN substitutions sub ON s.teacher_id = sub.absent_teacher_id 
                AND s.class_id = sub.class_id 
                AND s.day_of_week = sub.day_of_week 
                AND s.period = sub.period
                AND sub.status = 'confirmed'
            WHERE s.teacher_id = ? AND s.day_of_week = ?
        """, (teacher_id, day_of_week))
        return [dict(row) for row in cursor.fetchall()]
    
    # ==================== 班级相关 ====================
    
    def import_classes(self, classes_list):
        cursor = self.conn.cursor()
        for name, grade in classes_list:
            cursor.execute(
                "INSERT OR IGNORE INTO classes (name, grade) VALUES (?, ?)",
                (name, grade)
            )
        self.conn.commit()
    
    def get_all_classes(self):
        df = pd.read_sql("SELECT * FROM classes ORDER BY grade, name", self.conn)
        return df
    
    def get_class(self, class_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM classes WHERE id = ?", (class_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_class_by_name(self, name):
        """根据名称获取班级"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM classes WHERE name = ?", (name,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_class_schedule(self, class_id):
        """获取班级课表"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT s.*, t.name as teacher_name, c.grade
            FROM schedule_items s
            JOIN teachers t ON s.teacher_id = t.id
            JOIN classes c ON s.class_id = c.id
            WHERE s.class_id = ?
            ORDER BY s.day_of_week, s.period
        """, (class_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_class_teachers(self, class_id):
        """获取某班级所有任课老师"""
        df = pd.read_sql("""
            SELECT DISTINCT t.id, t.name, t.course_types
            FROM schedule_items s
            JOIN teachers t ON s.teacher_id = t.id
            WHERE s.class_id = ? AND t.is_active = 1
            ORDER BY t.name
        """, self.conn, params=(class_id,))
        return df
    
    # ==================== 课表相关 ====================
    
    def import_schedule(self, schedule_list):
        """批量导入课表"""
        cursor = self.conn.cursor()
        for item in schedule_list:
            cursor.execute("""
                INSERT OR REPLACE INTO schedule_items 
                (class_id, day_of_week, period, teacher_id, course_name, is_evening)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (item['class_id'], item['day_of_week'], item['period'], 
                  item['teacher_id'], item['course_name'], item.get('is_evening', 0)))
        self.conn.commit()
    
    def clear_schedule(self):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM schedule_items")
        cursor.execute("DELETE FROM teachers")
        cursor.execute("DELETE FROM classes")
        self.conn.commit()
    
    def update_schedule_teacher(self, schedule_item_id, new_teacher_id):
        """修改课表的任课教师"""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE schedule_items SET teacher_id = ? WHERE id = ?",
            (new_teacher_id, schedule_item_id)
        )
        self.conn.commit()
        return cursor.rowcount > 0
    
    def get_schedule_item(self, schedule_item_id):
        """获取单条课表记录"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT s.*, t.name as teacher_name, c.name as class_name, c.grade
            FROM schedule_items s
            JOIN teachers t ON s.teacher_id = t.id
            JOIN classes c ON s.class_id = c.id
            WHERE s.id = ?
        """, (schedule_item_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def delete_schedule_item(self, schedule_item_id):
        """删除课表记录"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM schedule_items WHERE id = ?", (schedule_item_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def add_schedule_item(self, class_id, day_of_week, period, teacher_id, course_name, is_evening=0):
        """添加课表记录"""
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO schedule_items 
                (class_id, day_of_week, period, teacher_id, course_name, is_evening)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (class_id, day_of_week, period, teacher_id, course_name, is_evening))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # 如果已存在，更新
            cursor.execute("""
                UPDATE schedule_items 
                SET teacher_id = ?, course_name = ?, is_evening = ?
                WHERE class_id = ? AND day_of_week = ? AND period = ?
            """, (teacher_id, course_name, is_evening, class_id, day_of_week, period))
            self.conn.commit()
            return cursor.lastrowid
    
    def get_available_teachers_for_class(self, class_id, day_of_week, period, exclude_teachers=None):
        """获取某班级某时段可顶课的教师（正课）"""
        cursor = self.conn.cursor()
        exclude = exclude_teachers or []
        
        # 获取该班级所有任课老师中该时段空闲的
        query = """
            SELECT DISTINCT t.id, t.name, t.course_types
            FROM teachers t
            JOIN schedule_items s ON t.id = s.teacher_id
            WHERE s.class_id = ? 
            AND t.id NOT IN (
                SELECT teacher_id FROM schedule_items 
                WHERE class_id = ? AND day_of_week = ? AND period = ?
            )
            AND t.is_active = 1
        """
        
        params = [class_id, class_id, day_of_week, period]
        
        # 如果有排除的教师
        if exclude:
            placeholders = ','.join(['?'] * len(exclude))
            query += f" AND t.id NOT IN ({placeholders})"
            params.extend(exclude)
        
        query += " ORDER BY t.name"
        
        df = pd.read_sql(query, self.conn, params=params)
        return df
    
    # ==================== 晚自习轮值相关 ====================
    
    def set_evening_rotation(self, teacher_ids):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM evening_rotation")
        cursor.execute("UPDATE evening_pointer SET current_index = -1")
        for idx, tid in enumerate(teacher_ids):
            cursor.execute(
                "INSERT INTO evening_rotation (teacher_id, order_index) VALUES (?, ?)",
                (tid, idx)
            )
        self.conn.commit()
    
    def get_evening_rotation(self):
        df = pd.read_sql("""
            SELECT r.*, t.name as teacher_name
            FROM evening_rotation r
            JOIN teachers t ON r.teacher_id = t.id
            ORDER BY r.order_index
        """, self.conn)
        return df
    
    def get_evening_assigned_teachers(self):
        """获取已安排的晚自习教师列表（按姓名排序）"""
        df = pd.read_sql("""
            SELECT DISTINCT t.id, t.name, t.course_types
            FROM teachers t
            JOIN schedule_items s ON t.id = s.teacher_id
            WHERE s.is_evening = 1 AND t.is_active = 1
            UNION
            SELECT DISTINCT t.id, t.name, t.course_types
            FROM teachers t
            JOIN evening_rotation r ON t.id = r.teacher_id
            WHERE t.is_active = 1
            ORDER BY name
        """, self.conn)
        return df
    
    def get_evening_unassigned_teachers(self):
        """获取未安排晚自习的教师列表"""
        # 获取已安排晚自习的教师
        assigned = self.get_evening_assigned_teachers()
        assigned_ids = assigned['id'].tolist() if not assigned.empty else []
        
        # 获取所有活跃教师
        all_teachers = self.get_all_teachers()
        
        if assigned_ids:
            unassigned = all_teachers[~all_teachers['id'].isin(assigned_ids)]
        else:
            unassigned = all_teachers
        
        return unassigned.sort_values('name')
    
    def add_teacher_to_evening_rotation(self, teacher_id):
        """添加教师到晚自习轮值表"""
        cursor = self.conn.cursor()
        # 获取当前最大order_index
        cursor.execute("SELECT MAX(order_index) FROM evening_rotation")
        max_idx = cursor.fetchone()[0] or -1
        cursor.execute(
            "INSERT INTO evening_rotation (teacher_id, order_index) VALUES (?, ?)",
            (teacher_id, max_idx + 1)
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def remove_teacher_from_evening_rotation(self, teacher_id):
        """从晚自习轮值表移除教师"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM evening_rotation WHERE teacher_id = ?", (teacher_id,))
        # 重新排序
        cursor.execute("""
            UPDATE evening_rotation 
            SET order_index = (
                SELECT COUNT(*) FROM evening_rotation r2 
                WHERE r2.order_index < evening_rotation.order_index
            )
        """)
        self.conn.commit()
        return cursor.rowcount > 0
    
    def reorder_evening_rotation(self, ordered_teacher_ids):
        """重新排序晚自习轮值表"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM evening_rotation")
        for idx, tid in enumerate(ordered_teacher_ids):
            cursor.execute(
                "INSERT INTO evening_rotation (teacher_id, order_index) VALUES (?, ?)",
                (tid, idx)
            )
        self.conn.commit()
    
    def assign_evening_duty(self):
        """分配下一个晚自习值班教师"""
        cursor = self.conn.cursor()
        
        # 获取当前指针
        cursor.execute("SELECT current_index FROM evening_pointer WHERE id = 1")
        row = cursor.fetchone()
        current = row['current_index'] if row else -1
        
        # 获取轮值表长度
        cursor.execute("SELECT COUNT(*) FROM evening_rotation")
        total = cursor.fetchone()[0]
        
        if total == 0:
            return None
        
        # 下一个
        next_idx = (current + 1) % total
        cursor.execute("""
            SELECT r.*, t.name as teacher_name
            FROM evening_rotation r
            JOIN teachers t ON r.teacher_id = t.id
            WHERE r.order_index = ?
        """, (next_idx,))
        
        row = cursor.fetchone()
        if row:
            cursor.execute(
                "UPDATE evening_pointer SET current_index = ?, updated_at = ? WHERE id = 1",
                (next_idx, datetime.now().isoformat())
            )
            self.conn.commit()
            return dict(row)
        return None
    
    def get_current_evening_teacher(self):
        """获取当前晚自习值班教师"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT current_index FROM evening_pointer WHERE id = 1")
        row = cursor.fetchone()
        current = row['current_index'] if row else -1
        
        if current < 0:
            return None
        
        cursor.execute("""
            SELECT r.*, t.name as teacher_name
            FROM evening_rotation r
            JOIN teachers t ON r.teacher_id = t.id
            WHERE r.order_index = ?
        """, (current,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    # ==================== 顶课记录相关 ====================
    
    def create_substitution(self, data):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO substitutions 
            (absent_teacher_id, substitute_teacher_id, class_id, day_of_week, period,
             course_type, original_course, leave_reason, status, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['absent_teacher_id'],
            data.get('substitute_teacher_id'),
            data['class_id'],
            data['day_of_week'],
            data['period'],
            data['course_type'],
            data.get('original_course', ''),
            data.get('leave_reason', ''),  # 请假事宜
            data.get('status', 'pending'),
            data.get('created_by')
        ))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_substitutions(self, filters=None):
        query = """
            SELECT sub.*,
                   at.name as absent_teacher_name,
                   st.name as substitute_teacher_name,
                   c.name as class_name, c.grade
            FROM substitutions sub
            JOIN teachers at ON sub.absent_teacher_id = at.id
            LEFT JOIN teachers st ON sub.substitute_teacher_id = st.id
            JOIN classes c ON sub.class_id = c.id
        """
        params = []
        conditions = []
        
        if filters:
            if filters.get('absent_teacher_id'):
                conditions.append("sub.absent_teacher_id = ?")
                params.append(filters['absent_teacher_id'])
            if filters.get('substitute_teacher_id'):
                conditions.append("sub.substitute_teacher_id = ?")
                params.append(filters['substitute_teacher_id'])
            if filters.get('course_type'):
                conditions.append("sub.course_type = ?")
                params.append(filters['course_type'])
            if filters.get('status'):
                conditions.append("sub.status = ?")
                params.append(filters['status'])
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY sub.day_of_week, sub.period"
        
        df = pd.read_sql(query, self.conn, params=params)
        return df
    
    def get_my_substitutions(self, teacher_id):
        df = pd.read_sql("""
            SELECT sub.*,
                   at.name as absent_teacher_name,
                   c.name as class_name, c.grade
            FROM substitutions sub
            JOIN teachers at ON sub.absent_teacher_id = at.id
            JOIN classes c ON sub.class_id = c.id
            WHERE sub.substitute_teacher_id = ? AND sub.status = 'confirmed'
            ORDER BY sub.day_of_week, sub.period
        """, self.conn, params=(teacher_id,))
        return df
    
    def get_my_leave_records(self, teacher_id):
        """获取我请假被顶的记录（请假记录）"""
        df = pd.read_sql("""
            SELECT sub.*,
                   st.name as substitute_teacher_name,
                   c.name as class_name, c.grade
            FROM substitutions sub
            LEFT JOIN teachers st ON sub.substitute_teacher_id = st.id
            JOIN classes c ON sub.class_id = c.id
            WHERE sub.absent_teacher_id = ? AND sub.status = 'confirmed'
            ORDER BY sub.day_of_week, sub.period
        """, self.conn, params=(teacher_id,))
        return df
    
    def get_teacher_substitutions_filtered(self, teacher_id, start_date=None, end_date=None):
        """获取教师顶课记录（帮别人顶的），支持时间筛选"""
        query = """
            SELECT sub.*,
                   at.name as absent_teacher_name,
                   c.name as class_name, c.grade
            FROM substitutions sub
            JOIN teachers at ON sub.absent_teacher_id = at.id
            JOIN classes c ON sub.class_id = c.id
            WHERE sub.substitute_teacher_id = ? AND sub.status = 'confirmed'
        """
        params = [teacher_id]
        
        if start_date:
            query += " AND sub.created_at >= ?"
            params.append(start_date)
        if end_date:
            query += " AND sub.created_at <= ?"
            params.append(end_date)
        
        query += " ORDER BY sub.day_of_week, sub.period"
        
        df = pd.read_sql(query, self.conn, params=params)
        return df
    
    def get_teacher_leave_records_filtered(self, teacher_id, start_date=None, end_date=None):
        """获取教师请假记录，支持时间筛选"""
        query = """
            SELECT sub.*,
                   st.name as substitute_teacher_name,
                   c.name as class_name, c.grade
            FROM substitutions sub
            LEFT JOIN teachers st ON sub.substitute_teacher_id = st.id
            JOIN classes c ON sub.class_id = c.id
            WHERE sub.absent_teacher_id = ? AND sub.status = 'confirmed'
        """
        params = [teacher_id]
        
        if start_date:
            query += " AND sub.created_at >= ?"
            params.append(start_date)
        if end_date:
            query += " AND sub.created_at <= ?"
            params.append(end_date)
        
        query += " ORDER BY sub.day_of_week, sub.period"
        
        df = pd.read_sql(query, self.conn, params=params)
        return df
    
    def update_substitution(self, sub_id, substitute_id, status='confirmed'):
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE substitutions 
            SET substitute_teacher_id = ?, status = ?, created_at = ?
            WHERE id = ?
        """, (substitute_id, status, datetime.now().isoformat(), sub_id))
        self.conn.commit()
    
    # ==================== 通知相关 ====================
    
    def add_notification(self, user_id, title, content):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO notifications (user_id, title, content) VALUES (?, ?, ?)",
            (user_id, title, content)
        )
        self.conn.commit()
    
    def get_notifications(self, user_id=None, unread_only=False):
        query = "SELECT * FROM notifications"
        params = []
        conditions = []
        
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if unread_only:
            conditions.append("is_read = 0")
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY created_at DESC LIMIT 50"
        
        df = pd.read_sql(query, self.conn, params=params)
        return df
    
    def mark_read(self, notification_id):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
        self.conn.commit()
    
    def get_unread_count(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
            (user_id,)
        )
        return cursor.fetchone()[0]
    
    # ==================== 冲突记录相关 ====================
    
    def record_teacher_skip(self, teacher_id, class_id, day_of_week, period, reason='conflict'):
        """记录教师被跳过（冲突）"""
        cursor = self.conn.cursor()
        semester = '2024-2025-1'
        now = datetime.now().isoformat()
        
        # 使用 INSERT OR UPDATE 语法
        cursor.execute("""
            INSERT INTO teacher_skip_records 
            (teacher_id, class_id, day_of_week, period, reason, semester, last_skip_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(teacher_id, class_id, day_of_week, period, semester) 
            DO UPDATE SET 
                skip_count = skip_count + 1,
                last_skip_at = excluded.last_skip_at,
                reason = excluded.reason
        """, (teacher_id, class_id, day_of_week, period, reason, semester, now))
        self.conn.commit()
    
    def get_skipped_teachers(self, class_id, day_of_week, period):
        """获取被跳过过的教师列表（按跳过次数降序）"""
        cursor = self.conn.cursor()
        semester = '2024-2025-1'
        
        cursor.execute("""
            SELECT t.id, t.name, s.skip_count, s.last_skip_at
            FROM teacher_skip_records s
            JOIN teachers t ON s.teacher_id = t.id
            WHERE s.class_id = ? AND s.day_of_week = ? AND s.period = ? 
            AND s.semester = ?
            ORDER BY s.skip_count DESC, s.last_skip_at ASC
        """, (class_id, day_of_week, period, semester))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def clear_skipped_teachers(self, class_id=None, day_of_week=None, period=None):
        """清除跳过记录（可选按班级/星期/节次筛选）"""
        cursor = self.conn.cursor()
        semester = '2024-2025-1'
        
        if class_id and day_of_week and period:
            cursor.execute("""
                DELETE FROM teacher_skip_records 
                WHERE class_id = ? AND day_of_week = ? AND period = ? AND semester = ?
            """, (class_id, day_of_week, period, semester))
        else:
            cursor.execute("DELETE FROM teacher_skip_records WHERE semester = ?", (semester,))
        
        self.conn.commit()
    
    def get_class_teachers_with_course_order(self, class_id):
        """获取班级教师，按科目顺序排列"""
        df = pd.read_sql("""
            SELECT DISTINCT t.id, t.name, t.course_types,
                   s.course_name,
                   CASE 
                       WHEN t.course_types = '语文' THEN 0
                       WHEN t.course_types = '数学' THEN 1
                       WHEN t.course_types = '英语' THEN 2
                       WHEN t.course_types = '物理' THEN 3
                       WHEN t.course_types = '化学' THEN 4
                       WHEN t.course_types = '道法' THEN 5
                       WHEN t.course_types = '历史' THEN 6
                       WHEN t.course_types = '生物' THEN 7
                       WHEN t.course_types = '地理' THEN 8
                       WHEN t.course_types = '音乐' THEN 9
                       WHEN t.course_types = '体育' THEN 10
                       WHEN t.course_types = '美术' THEN 11
                       WHEN t.course_types = '信息技术' THEN 12
                       WHEN t.course_types = '劳动' THEN 13
                       ELSE 99
                   END as course_order
            FROM schedule_items s
            JOIN teachers t ON s.teacher_id = t.id
            WHERE s.class_id = ? AND t.is_active = 1
            ORDER BY course_order, t.name
        """, self.conn, params=(class_id,))
        return df
    
    def get_teachers_by_course_order(self, class_id, day_of_week, period, exclude_teachers=None):
        """获取某时段可顶课的教师，按科目顺序优先推荐"""
        cursor = self.conn.cursor()
        exclude = exclude_teachers or []
        
        query = """
            SELECT DISTINCT t.id, t.name, t.course_types,
                   CASE 
                       WHEN t.course_types = '语文' THEN 0
                       WHEN t.course_types = '数学' THEN 1
                       WHEN t.course_types = '英语' THEN 2
                       WHEN t.course_types = '物理' THEN 3
                       WHEN t.course_types = '化学' THEN 4
                       WHEN t.course_types = '道法' THEN 5
                       WHEN t.course_types = '历史' THEN 6
                       WHEN t.course_types = '生物' THEN 7
                       WHEN t.course_types = '地理' THEN 8
                       WHEN t.course_types = '音乐' THEN 9
                       WHEN t.course_types = '体育' THEN 10
                       WHEN t.course_types = '美术' THEN 11
                       WHEN t.course_types = '信息技术' THEN 12
                       WHEN t.course_types = '劳动' THEN 13
                       ELSE 99
                   END as course_order
            FROM teachers t
            WHERE t.is_active = 1
            AND t.id NOT IN (
                SELECT teacher_id FROM schedule_items 
                WHERE class_id = ? AND day_of_week = ? AND period = ?
            )
        """
        
        params = [class_id, day_of_week, period]
        
        if exclude:
            placeholders = ','.join(['?'] * len(exclude))
            query += f" AND t.id NOT IN ({placeholders})"
            params.extend(exclude)
        
        query += " ORDER BY course_order, t.name"
        
        df = pd.read_sql(query, self.conn, params=params)
        return df
    
    def update_substitution_manual(self, sub_id, substitute_id, operated_by):
        """手动更新顶课记录"""
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute("""
            UPDATE substitutions 
            SET substitute_teacher_id = ?, 
                assignment_type = 'manual',
                operated_by = ?,
                operated_at = ?,
                status = 'confirmed'
            WHERE id = ?
        """, (substitute_id, operated_by, now, sub_id))
        self.conn.commit()
    
    def close(self):
        self.conn.close()


# 单例
_db = None

def get_db():
    global _db
    if _db is None:
        _db = Database()
    return _db
