"""
中学自动调课系统 - 调课逻辑模块
实现正课和晚自习分离的顶课算法，支持科目顺序排课和冲突记忆
"""
from database import get_db
from collections import defaultdict

DAY_NAMES = {1: '周一', 2: '周二', 3: '周三', 4: '周四', 5: '周五'}
PERIOD_NAMES = {
    1: '第1节', 2: '第2节', 3: '第3节', 4: '第4节', 5: '第5节',
    6: '第6节', 7: '第7节', 8: '第8节', 9: '第9节',
    10: '晚1节', 11: '晚2节'
}

# 科目顺序列表 - 17个位置，语数英重复
COURSE_ORDER = [
    '语文', '数学', '英语', '物理', '化学', '道法', '历史', '生物', 
    '地理', '语文', '数学', '英语', '音乐', '体育', '美术', '信息技术', '劳动'
]


class SubstitutionEngine:
    """调课引擎"""
    
    def __init__(self):
        self.db = get_db()
        self.assigned_teachers = []  # 已分配的教师（避免重复顶替）
        self.skipped_teachers = {}  # 被跳过的教师 {teacher_id: skip_count}
        self.current_round = 0  # 当前轮次
        self.all_skipped_exhausted = False  # 所有跳过教师是否已轮完
    
    def generate_substitution_plan(self, absent_teacher_id, class_id, day_of_week, period, course_name=None):
        """
        为单个课程生成顶课方案
        
        Args:
            absent_teacher_id: 请假教师ID
            class_id: 班级ID
            day_of_week: 星期几 (1-5)
            period: 第几节课 (1-11)
            course_name: 课程名称（可选）
        
        Returns:
            dict: 包含success, substitute_id, teacher_name, message, assignment_type等
        """
        # 判断是正课还是晚自习
        if period in [10, 11]:
            return self._assign_evening_duty(absent_teacher_id, class_id, day_of_week, period)
        else:
            return self._assign_regular_class(absent_teacher_id, class_id, day_of_week, period, course_name)
    
    def _assign_regular_class(self, absent_teacher_id, class_id, day_of_week, period, course_name=None):
        """分配正课顶替教师（从请假教师所教班级的任课老师中选取，按科目顺序）"""
        
        # 排除列表：请假教师 + 已分配的教师
        exclude = [absent_teacher_id] + self.assigned_teachers
        
        # 获取请假教师所教班级的所有可顶课教师（使用新的核心逻辑）
        available = self.db.get_available_substitute_teachers(absent_teacher_id, day_of_week, period, exclude)
        
        if available.empty:
            return {
                'success': False,
                'substitute_id': None,
                'teacher_name': None,
                'message': '该时段无空闲教师（请假教师所教班级范围内）',
                'assignment_type': 'auto',
                'all_available': [],
                'conflict_teachers': []
            }
        
        # 记录有冲突的教师（原本能顶课但因已分配被排除的）
        conflict_teachers = []
        
        # 获取所有可能顶课的教师（不排除assigned的）
        all_potential = self.db.get_available_substitute_teachers(absent_teacher_id, day_of_week, period, [absent_teacher_id])
        if not all_potential.empty:
            for _, row in all_potential.iterrows():
                if row['id'] in self.assigned_teachers:
                    conflict_teachers.append({
                        'id': row['id'],
                        'name': row['name'],
                        'course': row.get('course_types', '')
                    })
        
        # 获取被跳过过的教师（按跳过次数优先）
        # 注意：跳过记录仍然按班级记录，但查询时改为在请假教师所教班级范围内
        skipped_list = self._get_skipped_teachers_in_scope(absent_teacher_id, class_id, day_of_week, period)
        
        # 优先选择被跳过过的教师
        priority_teachers = [t for t in skipped_list if t['id'] not in exclude]
        
        chosen = None
        assignment_type = 'auto'
        
        if priority_teachers:
            # 选择跳过次数最多的教师
            chosen = priority_teachers[0]
            assignment_type = 'auto_priority'  # 自动分配但优先处理历史冲突
        else:
            # 按科目顺序选择第一个可用的
            if not available.empty:
                chosen = available.iloc[0].to_dict()
                assignment_type = 'auto_order'
        
        if chosen:
            chosen_id = chosen['id'] if isinstance(chosen, dict) else chosen['id']
            self.assigned_teachers.append(chosen_id)
            
            teacher_name = chosen['name'] if isinstance(chosen, dict) else chosen['name']
            
            return {
                'success': True,
                'substitute_id': chosen_id,
                'teacher_name': teacher_name,
                'message': f'已安排{teacher_name}顶替',
                'assignment_type': assignment_type,
                'all_available': available.to_dict('records') if not available.empty else [],
                'conflict_teachers': conflict_teachers,
                'was_skipped_before': any(t['id'] == chosen_id for t in skipped_list)
            }
        
        return {
            'success': False,
            'substitute_id': None,
            'teacher_name': None,
            'message': '无法分配合适的教师',
            'assignment_type': 'auto',
            'all_available': available.to_dict('records') if not available.empty else [],
            'conflict_teachers': conflict_teachers
        }
    
    def _get_skipped_teachers_in_scope(self, absent_teacher_id, class_id, day_of_week, period):
        """获取请假教师所教班级范围内被跳过过的教师"""
        # 获取请假教师所教的所有班级
        classes_of_absent = self.db.get_teachers_of_teacher(absent_teacher_id)
        if classes_of_absent.empty:
            return []
        
        # 获取这些班级的任课老师中有跳过记录的
        # 简化为返回该范围内的跳过记录
        cursor = self.db.conn.cursor()
        semester = '2024-2025-1'
        
        # 获取请假教师所教班级
        cursor.execute("""
            SELECT DISTINCT class_id FROM schedule_items WHERE teacher_id = ?
        """, (absent_teacher_id,))
        class_ids = [row[0] for row in cursor.fetchall()]
        
        if not class_ids:
            return []
        
        placeholders = ','.join(['?'] * len(class_ids))
        cursor.execute(f"""
            SELECT t.id, t.name, s.skip_count, s.last_skip_at
            FROM teacher_skip_records s
            JOIN teachers t ON s.teacher_id = t.id
            WHERE s.class_id IN ({placeholders}) AND s.day_of_week = ? AND s.period = ? 
            AND s.semester = ?
            ORDER BY s.skip_count DESC, s.last_skip_at ASC
        """, class_ids + [day_of_week, period, semester])
        
        return [dict(row) for row in cursor.fetchall()]
    
    def _clear_skip_if_exists(self, teacher_id, class_id, day_of_week, period):
        """清除指定教师的跳过记录"""
        # 实际保留记录用于统计，只是在新一轮分配时不再"优先"
        pass
    
    def _assign_evening_duty(self, absent_teacher_id, class_id, day_of_week, period):
        """分配晚自习顶替教师（按轮值表顺序）"""
        # 获取下一个晚自习值班教师
        next_teacher = self.db.assign_evening_duty()
        
        if not next_teacher:
            return {
                'success': False,
                'substitute_id': None,
                'teacher_name': None,
                'message': '晚自习轮值表未设置',
                'assignment_type': 'auto',
                'all_available': [],
                'conflict_teachers': []
            }
        
        conflict_teachers = []
        
        # 检查该教师是否已被分配
        if next_teacher['teacher_id'] in self.assigned_teachers:
            # 尝试找下一个
            for _ in range(100):  # 最多尝试100次
                next_teacher = self.db.assign_evening_duty()
                if not next_teacher or next_teacher['teacher_id'] not in self.assigned_teachers:
                    break
            else:
                # 记录冲突
                conflict_teachers.append({
                    'id': next_teacher['teacher_id'],
                    'name': next_teacher['teacher_name'],
                    'course': '晚自习'
                })
        
        if not next_teacher:
            return {
                'success': False,
                'substitute_id': None,
                'teacher_name': None,
                'message': '所有值班教师均已分配',
                'assignment_type': 'auto',
                'all_available': [],
                'conflict_teachers': conflict_teachers
            }
        
        self.assigned_teachers.append(next_teacher['teacher_id'])
        
        return {
            'success': True,
            'substitute_id': next_teacher['teacher_id'],
            'teacher_name': next_teacher['teacher_name'],
            'message': f'已按轮值安排{next_teacher["teacher_name"]}值班晚自习',
            'assignment_type': 'auto_rotation',
            'all_available': [],
            'conflict_teachers': conflict_teachers
        }
    
    def get_conflict_teachers(self, class_id, day_of_week, period, absent_teacher_id):
        """获取指定时段有冲突的教师列表"""
        exclude = [absent_teacher_id] + self.assigned_teachers
        
        # 获取所有可能顶课的教师（使用新的核心逻辑）
        all_potential = self.db.get_available_substitute_teachers(absent_teacher_id, day_of_week, period, [absent_teacher_id])
        
        conflict = []
        if not all_potential.empty:
            for _, row in all_potential.iterrows():
                if row['id'] in exclude:
                    conflict.append({
                        'id': row['id'],
                        'name': row['name'],
                        'course': row.get('course_types', '')
                    })
        
        return conflict
    
    def batch_generate(self, absent_teacher_id, class_id, day_of_week, periods):
        """
        批量生成顶课方案
        
        Args:
            absent_teacher_id: 请假教师ID
            class_id: 班级ID
            day_of_week: 星期几
            periods: 要顶替的节次列表
        
        Returns:
            list: 顶课结果列表
        """
        self.assigned_teachers = []  # 重置
        self.skipped_teachers = {}
        results = []
        
        # 获取课程信息
        class_schedule = self.db.get_class_schedule(class_id)
        
        for period in periods:
            # 获取该节次的课程信息
            course_info = None
            for item in class_schedule:
                if item['day_of_week'] == day_of_week and item['period'] == period:
                    course_info = item
                    break
            
            course_name = course_info['course_name'] if course_info else ''
            
            result = self.generate_substitution_plan(
                absent_teacher_id, class_id, day_of_week, period, course_name
            )
            results.append({
                'day': DAY_NAMES.get(day_of_week, f'周{day_of_week}'),
                'period': PERIOD_NAMES.get(period, f'第{period}节'),
                'period_value': period,
                'course_type': '晚自习' if period in [10, 11] else '正课',
                'course_name': course_name,
                **result
            })
        
        return results
    
    def get_course_order_display(self):
        """获取科目顺序显示"""
        return COURSE_ORDER


def create_substitution_records(teacher_courses, created_by=None, operated_by=None, leave_reason=''):
    """
    创建批量顶课记录
    
    Args:
        teacher_courses: [(class_id, day, period), ...] 请假老师的课程列表
        created_by: 创建人用户ID
        operated_by: 操作人用户ID
        leave_reason: 请假事宜
    
    Returns:
        list: 顶课结果
    """
    engine = SubstitutionEngine()
    db = get_db()
    
    # 获取请假教师信息
    if not teacher_courses:
        return []
    
    # 获取第一个课程的教师信息
    first_class_id = teacher_courses[0][0]
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT t.* FROM teachers t
        JOIN schedule_items s ON t.id = s.teacher_id
        WHERE s.class_id = ? LIMIT 1
    """, (first_class_id,))
    row = cursor.fetchone()
    absent_teacher = dict(row) if row else None
    
    if not absent_teacher:
        return []
    
    # 获取该教师ID
    cursor.execute("""
        SELECT DISTINCT teacher_id FROM schedule_items 
        WHERE class_id = ? AND teacher_id IN (
            SELECT teacher_id FROM schedule_items 
            WHERE class_id = ? 
            LIMIT 100
        )
    """, (teacher_courses[0][0], teacher_courses[0][0]))
    teacher_rows = cursor.fetchall()
    
    # 由于无法准确知道请假教师，我们从第一个课程关联的教师中查找
    # 实际使用时，absent_teacher_id应该从外部传入
    absent_teacher_id = absent_teacher['id']
    
    results = []
    now = datetime.now().isoformat()
    
    # 按班级分组处理
    by_class = defaultdict(list)
    for class_id, day, period in teacher_courses:
        by_class[class_id].append((day, period))
    
    for class_id, lessons in by_class.items():
        engine.assigned_teachers = []  # 每个班级重置
        
        for day, period in lessons:
            # 获取课程信息
            class_schedule = db.get_class_schedule(class_id)
            course_info = None
            for item in class_schedule:
                if item['day_of_week'] == day and item['period'] == period:
                    course_info = item
                    break
            
            course_name = course_info['course_name'] if course_info else ''
            course_type = '晚自习' if period in [10, 11] else '正课'
            
            # 生成顶课方案
            plan = engine.generate_substitution_plan(
                absent_teacher_id, class_id, day, period, course_name
            )
            
            # 记录被跳过的教师
            for conflict in plan.get('conflict_teachers', []):
                db.record_teacher_skip(
                    conflict['id'], class_id, day, period, 
                    reason=f'已被安排顶替其他课程'
                )
            
            # 创建记录
            sub_id = db.create_substitution({
                'absent_teacher_id': absent_teacher_id,
                'substitute_teacher_id': plan['substitute_id'],
                'class_id': class_id,
                'day_of_week': day,
                'period': period,
                'course_type': course_type,
                'original_course': course_name,
                'leave_reason': leave_reason,  # 保存请假事宜
                'assignment_type': plan.get('assignment_type', 'auto'),
                'status': 'confirmed' if plan['success'] else 'pending',
                'created_by': created_by,
                'operated_by': operated_by,
                'operated_at': now if plan['success'] else None
            })
            
            # 发送通知
            if plan['success']:
                # 获取顶替教师用户
                cursor.execute("SELECT * FROM users WHERE teacher_id = ?", (plan['substitute_id'],))
                user_row = cursor.fetchone()
                if user_row:
                    user_id = dict(user_row)['id']
                    db.add_notification(
                        user_id,
                        '新的顶课任务',
                        f'{DAY_NAMES.get(day)} {PERIOD_NAMES.get(period)} {course_type}，{course_name}课需您代上。'
                    )
            
            # 记录结果
            class_info = db.get_class(class_id)
            results.append({
                'id': sub_id,
                'class': class_info['name'] if class_info else '',
                'class_id': class_id,
                'day': DAY_NAMES.get(day, f'周{day}'),
                'day_value': day,
                'period': PERIOD_NAMES.get(period, f'第{period}节'),
                'period_value': period,
                'course': course_name,
                'course_type': course_type,
                'absent_teacher': absent_teacher['name'],
                'absent_teacher_id': absent_teacher_id,
                'leave_reason': leave_reason,  # 包含请假事宜
                'substitute_teacher': plan['teacher_name'] or '待分配',
                'substitute_teacher_id': plan['substitute_id'],
                'assignment_type': plan.get('assignment_type', 'auto'),
                'status': '已安排' if plan['success'] else '待手动处理',
                'message': plan['message'],
                'all_available': plan.get('all_available', []),
                'conflict_teachers': plan.get('conflict_teachers', [])
            })
    
    return results


def format_day_period(day, period):
    """格式化星期和节次"""
    return f"{DAY_NAMES.get(day, f'周{day}')} {PERIOD_NAMES.get(period, f'第{period}节')}"


from datetime import datetime
