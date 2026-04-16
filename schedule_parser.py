"""
中学自动调课系统 - 课表解析模块
从Excel文件解析课表并导入数据库
"""
import pandas as pd
import openpyxl
import re
from pathlib import Path
from database import get_db

# Excel文件路径
EXCEL_FILE = Path(__file__).parent / "用户上传" / "2025-2026第一学期七八九年级班级课表（2025.12.23修改)(1)_1776239900375_0_udqx.xlsx"

def parse_cell(cell_value):
    """解析单元格，提取课程名和教师名"""
    if pd.isna(cell_value) or cell_value is None:
        return None, None
    
    cell_str = str(cell_value).strip()
    if not cell_str:
        return None, None
    
    if '\n' in cell_str and '(' in cell_str:
        parts = cell_str.split('\n')
        course = parts[0].strip()
        teacher_match = re.search(r'[（(]([^)）]+)[)）]', cell_str)
        teacher = teacher_match.group(1).strip() if teacher_match else None
        return course, teacher
    
    return None, None

def get_grade_from_sheet(sheet_name):
    """从sheet名获取年级"""
    if sheet_name.startswith('七'):
        return '七年级'
    elif sheet_name.startswith('八'):
        return '八年级'
    elif sheet_name.startswith('九'):
        return '九年级'
    return ''

def import_schedule_to_db(excel_file=None):
    """从Excel导入课表到数据库
    
    Args:
        excel_file: Excel文件路径，如果为None则使用默认路径
    
    Returns:
        dict: 导入统计信息
    """
    db = get_db()
    
    # 确定要使用的文件路径
    file_path = excel_file if excel_file else EXCEL_FILE
    
    if not Path(file_path).exists():
        raise FileNotFoundError(f"课表文件未找到: {file_path}")
    
    # 清空旧数据
    db.clear_schedule()
    
    teachers_set = set()
    classes_list = []
    schedule_records = []
    
    wb = openpyxl.load_workbook(file_path, read_only=True)
    
    for sheet_name in wb.sheetnames:
        df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
        class_name = sheet_name
        grade = get_grade_from_sheet(sheet_name)
        classes_list.append((class_name, grade))
        
        # 遍历行
        for row_idx in range(4, df.shape[0]):
            row = df.iloc[row_idx]
            period = row[1]
            
            if pd.isna(period):
                continue
            
            try:
                period = int(period)
            except:
                continue
            
            if period < 1 or period > 11:
                continue
            
            # 周一到周五 (列3-7 对应 周一~周五)
            # 原来的列2是时间，不是课程
            for day_offset, col_idx in enumerate(range(3, 8)):
                day = day_offset + 1
                cell_value = row[col_idx]
                course, teacher = parse_cell(cell_value)
                
                if teacher and course:
                    teachers_set.add(teacher)
                    is_evening = 1 if period in [10, 11] else 0
                    schedule_records.append({
                        'class_name': class_name,
                        'day': day,
                        'period': period,
                        'teacher_name': teacher,
                        'course': course,
                        'is_evening': is_evening
                    })
    
    wb.close()
    
    print(f"解析到 {len(schedule_records)} 条原始记录")
    
    # 导入教师
    db.import_teachers(sorted(teachers_set))
    print(f"已导入 {len(teachers_set)} 位教师")
    
    # 导入班级
    db.import_classes(classes_list)
    print(f"已导入 {len(classes_list)} 个班级")
    
    # 构建映射
    teacher_name_to_id = {}
    for name in teachers_set:
        t = db.get_teacher_by_name(name)
        if t:
            teacher_name_to_id[name] = t['id']
    
    class_name_to_id = {}
    for name, grade in classes_list:
        c = db.get_class_by_name(name)
        if c:
            class_name_to_id[name] = c['id']
    
    # 批量插入
    cursor = db.conn.cursor()
    inserted = 0
    for rec in schedule_records:
        class_id = class_name_to_id.get(rec['class_name'])
        teacher_id = teacher_name_to_id.get(rec['teacher_name'])
        
        if class_id and teacher_id:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO schedule_items 
                    (class_id, day_of_week, period, teacher_id, course_name, is_evening)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (class_id, rec['day'], rec['period'], teacher_id, rec['course'], rec['is_evening']))
                inserted += 1
            except Exception as e:
                pass
    
    db.conn.commit()
    print(f"已导入 {inserted} 条课表记录")
    
    # 设置晚自习轮值
    all_teachers = db.get_all_teachers()
    evening_teacher_ids = all_teachers['id'].tolist()
    db.set_evening_rotation(evening_teacher_ids)
    print(f"已设置 {len(evening_teacher_ids)} 位教师参与晚自习轮值")
    
    return {
        'teachers': len(teachers_set),
        'classes': len(classes_list),
        'schedule_items': inserted
    }


def get_statistics():
    """获取数据统计"""
    db = get_db()
    
    try:
        teachers = db.get_all_teachers()
        classes = db.get_all_classes()
        rotation = db.get_evening_rotation()
        
        return {
            'teachers_count': len(teachers),
            'classes_count': len(classes),
            'rotation_count': len(rotation)
        }
    except:
        return {
            'teachers_count': 0,
            'classes_count': 0,
            'rotation_count': 0
        }


if __name__ == '__main__':
    result = import_schedule_to_db()
    print("\n导入完成！")
    print(f"教师: {result['teachers']}")
    print(f"班级: {result['classes']}")
    print(f"课表记录: {result['schedule_items']}")
