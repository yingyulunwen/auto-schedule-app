"""
中学自动调课系统 - 调课逻辑模块
实现正课和晚自习分离的顶课算法
"""
from database import get_db
from collections import defaultdict

DAY_NAMES = {1: '周一', 2: '周二', 3: '周三', 4: '周四', 5: '周五'}
PERIOD_NAMES = {
    1: '第1节', 2: '第2节', 3: '第3节', 4: '第4节', 5: '第5节',
    6: '第6节', 7: '第7节', 8: '第8节', 9: '第9节',
    10: '晚1节', 11: '晚2节'
}

class SubstitutionEngine:
    """调课引擎"""
    
    def __init__(self):
        self.db = get_db()
        self.assigned_teachers = []  # 已分配的教师（避免重复顶替）
    
    def generate_substitution_plan(self, absent_teacher_id, class_id, day_of_week, period):
        """
        为单个课程生成顶课方案
        
        Args:
            absent_teacher_id: 请假教师ID
            class_id: 班级ID
            day_of_week: 星期几 (1-5)
            period: 第几节课 (1-11)
        
        Returns:
            dict: {success: bool, substitute_id: int, teacher_name: str, message: str}
        """
        # 判断是正课还是晚自习
        if period in [10, 11]:
            return self._assign_evening_duty(absent_teacher_id, class_id, day_of_week, period)
        else:
            return self._assign_regular_class(absent_teacher_id, class_id, day_of_week, period)
    
    def _assign_regular_class(self, absent_teacher_id, class_id, day_of_week, period):
        """分配正课顶替教师（本班任课老师轮流，跳过有课教师）"""
        # 获取该班级所有任课老师
        class_teachers = self.db.get_class_teachers(class_id)
        
        if class_teachers.empty:
            return {
                'success': False,
                'substitute_id': None,
                'teacher_name': None,
                'message': '该班级没有任课老师信息'
            }
        
        # 排除请假教师和已分配的教师
        exclude = [absent_teacher_id] + self.assigned_teachers
        
        # 获取该时段空闲的教师
        available = self.db.get_available_teachers_for_class(
            class_id, day_of_week, period, exclude
        )
        
        if available.empty:
            return {
                'success': False,
                'substitute_id': None,
                'teacher_name': None,
                'message': '该时段无空闲的任课老师'
            }
        
        # 选择第一个可用的教师
        chosen = available.iloc[0]
        self.assigned_teachers.append(chosen['id'])
        
        return {
            'success': True,
            'substitute_id': chosen['id'],
            'teacher_name': chosen['name'],
            'message': f'已安排{chosen["name"]}顶替'
        }
    
    def _assign_evening_duty(self, absent_teacher_id, class_id, day_of_week, period):
        """分配晚自习顶替教师（按轮值表顺序）"""
        # 获取下一个晚自习值班教师
        next_teacher = self.db.assign_evening_duty()
        
        if not next_teacher:
            return {
                'success': False,
                'substitute_id': None,
                'teacher_name': None,
                'message': '晚自习轮值表未设置'
            }
        
        # 检查该教师是否已被分配
        if next_teacher['teacher_id'] in self.assigned_teachers:
            # 尝试找下一个
            for _ in range(100):  # 最多尝试100次
                next_teacher = self.db.assign_evening_duty()
                if not next_teacher or next_teacher['teacher_id'] not in self.assigned_teachers:
                    break
        
        if not next_teacher:
            return {
                'success': False,
                'substitute_id': None,
                'teacher_name': None,
                'message': '所有值班教师均已分配'
            }
        
        self.assigned_teachers.append(next_teacher['teacher_id'])
        
        return {
            'success': True,
            'substitute_id': next_teacher['teacher_id'],
            'teacher_name': next_teacher['teacher_name'],
            'message': f'已按轮值安排{next_teacher["teacher_name"]}值班晚自习'
        }
    
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
        results = []
        
        for period in periods:
            result = self.generate_substitution_plan(absent_teacher_id, class_id, day_of_week, period)
            results.append({
                'day': DAY_NAMES.get(day_of_week, f'周{day_of_week}'),
                'period': PERIOD_NAMES.get(period, f'第{period}节'),
                'period_type': '晚自习' if period in [10, 11] else '正课',
                **result
            })
        
        return results


def create_substitution_records(teacher_courses, created_by=None):
    """
    创建批量顶课记录
    
    Args:
        teacher_courses: [(class_id, day, period), ...] 请假老师的课程列表
        created_by: 创建人用户ID
    
    Returns:
        list: 顶课结果
    """
    engine = SubstitutionEngine()
    db = get_db()
    
    # 获取请假教师信息
    absent_teacher = db.get_teacher(teacher_courses[0][0] if teacher_courses else None)
    if not absent_teacher:
        return []
    
    results = []
    
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
                absent_teacher['id'], class_id, day, period
            )
            
            # 创建记录
            sub_id = db.create_substitution({
                'absent_teacher_id': absent_teacher['id'],
                'substitute_teacher_id': plan['substitute_id'],
                'class_id': class_id,
                'day_of_week': day,
                'period': period,
                'course_type': course_type,
                'original_course': course_name,
                'status': 'confirmed' if plan['success'] else 'failed',
                'created_by': created_by
            })
            
            # 发送通知
            if plan['success']:
                # 通知顶替教师
                db.add_notification(
                    plan['substitute_id'],
                    f'新的顶课任务',
                    f'{DAY_NAMES.get(day)} {PERIOD_NAMES.get(period)} {course_type}，{course_name}课需您代上。'
                )
            
            # 记录结果
            class_info = db.get_class(class_id)
            results.append({
                'id': sub_id,
                'class': class_info['name'] if class_info else '',
                'day': DAY_NAMES.get(day, f'周{day}'),
                'period': PERIOD_NAMES.get(period, f'第{period}节'),
                'course': course_name,
                'course_type': course_type,
                'absent_teacher': absent_teacher['name'],
                'substitute_teacher': plan['teacher_name'] or '无',
                'status': '已安排' if plan['success'] else '待手动处理',
                'message': plan['message']
            })
    
    return results


def format_day_period(day, period):
    """格式化星期和节次"""
    return f"{DAY_NAMES.get(day, f'周{day}')} {PERIOD_NAMES.get(period, f'第{period}节')}"
