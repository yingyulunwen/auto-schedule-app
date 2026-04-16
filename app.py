"""
中学自动调课系统 - Streamlit Web应用
5个页面：首页、发起顶课、课表页、晚自习轮值、个人中心
支持科目顺序排课、手动选择教师和冲突记录
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_db, COURSE_ORDER
from schedule_parser import import_schedule_to_db, get_statistics
from substitution_engine import create_substitution_records, DAY_NAMES, PERIOD_NAMES

# 页面配置
st.set_page_config(
    page_title="中学自动调课系统",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 初始化session_state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'substitution_results' not in st.session_state:
    st.session_state.substitution_results = None

# ==================== 登录函数 ====================

def login(username, password):
    db = get_db()
    user = db.check_login(username, password)
    if user:
        st.session_state.logged_in = True
        st.session_state.user = user
        return True
    return False

def logout():
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.substitution_results = None

# ==================== 侧边栏 ====================

def render_sidebar():
    with st.sidebar:
        st.markdown("---")
        if st.session_state.user:
            role_emoji = "👨‍💼" if st.session_state.user['role'] == 'admin' else "👩‍💼"
            st.success(f"{role_emoji} {st.session_state.user['name']}")
            st.caption(f"角色: {st.session_state.user['role']}")
        
        st.markdown("---")
        
        if st.session_state.logged_in:
            page = st.radio(
                "导航菜单",
                ["🏠 首页", "📝 发起顶课", "📅 课表查询", "🌙 晚自习轮值", "👤 个人中心", "⚙️ 数据管理"],
                captions=[
                    "主页和快捷入口",
                    "选择请假教师，发起顶课",
                    "查看班级和教师课表",
                    "查看和调整晚自习顺序",
                    "我的课表和顶课记录",
                    "管理教师和课表数据"
                ]
            )
            
            st.markdown("---")
            if st.button("🚪 退出登录", use_container_width=True):
                logout()
                st.rerun()
        else:
            page = None
        
        return page

# ==================== 登录页面 ====================

def render_login_page():
    st.title("📚 中学自动调课系统")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### 🔐 用户登录")
        
        with st.form("login_form"):
            username = st.text_input("用户名", placeholder="请输入用户名")
            password = st.text_input("密码", type="password", placeholder="请输入密码")
            
            col_a, col_b = st.columns(2)
            with col_a:
                submitted = st.form_submit_button("登录", type="primary", use_container_width=True)
            
            if submitted:
                if login(username, password):
                    st.success("登录成功！")
                    st.rerun()
                else:
                    st.error("用户名或密码错误")
        
        st.markdown("---")
        st.markdown("#### 👤 测试账号")
        st.info("""
        - **管理员**: admin / admin123
        - **教务**: jiaowu / jiaowu123
        """)
        
        # 初始化数据按钮（仅管理员可见）
        st.markdown("---")
        st.markdown("#### ⚙️ 数据初始化")
        if st.button("📥 从Excel导入课表数据", use_container_width=True):
            try:
                with st.spinner("正在导入数据..."):
                    result = import_schedule_to_db()
                st.success(f"""
                ✅ 导入完成！
                - 教师: {result['teachers']} 位
                - 班级: {result['classes']} 个
                - 课表记录: {result['schedule_items']} 条
                """)
            except Exception as e:
                st.error(f"导入失败: {str(e)}")

# ==================== 首页 ====================

def render_home_page():
    st.title("🏠 首页")
    st.markdown("---")
    
    db = get_db()
    user = st.session_state.user
    
    # 欢迎信息
    st.markdown(f"### 欢迎，{user['name']}！")
    
    # 统计卡片
    stats = get_statistics()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("👨‍🏫 教师数", stats['teachers_count'])
    with col2:
        st.metric("🏫 班级数", stats['classes_count'])
    with col3:
        st.metric("🌙 晚自习轮值", stats['rotation_count'])
    
    # 待处理提醒
    st.markdown("---")
    st.markdown("### 📌 待处理提醒")
    
    if user['role'] in ['admin', '教务']:
        # 显示最近的顶课记录
        recent = db.get_substitutions({'status': 'pending'}).head(5)
        if not recent.empty:
            st.warning(f"有 {len(recent)} 条待处理顶课记录")
        else:
            st.success("暂无待处理事项")
    
    # 快捷入口
    st.markdown("---")
    st.markdown("### 🚀 快捷入口")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.page_link("?page=📝 发起顶课", label="📝 发起顶课", icon="📝")
        st.caption("选择请假教师，发起顶课申请")
    
    with col2:
        st.page_link("?page=📅 课表查询", label="📅 课表查询", icon="📅")
        st.caption("查看班级或教师课表")
    
    with col3:
        st.page_link("?page=👤 个人中心", label="👤 个人中心", icon="👤")
        st.caption("查看我的课表和顶课记录")
    
    # 数据状态
    st.markdown("---")
    if stats['teachers_count'] == 0:
        st.warning("⚠️ 尚未导入课表数据，请先点击侧边栏的「数据初始化」按钮。")
    
    # 科目顺序说明
    st.markdown("---")
    st.markdown("### 📋 顶课科目顺序")
    st.caption("顶课时按以下科目顺序安排教师：")
    order_str = " → ".join(COURSE_ORDER)
    st.info(order_str)

# ==================== 发起顶课页面 ====================

def render_substitution_page():
    st.title("📝 发起顶课")
    st.markdown("---")
    
    db = get_db()
    
    # 检查数据
    teachers = db.get_all_teachers()
    if teachers.empty:
        st.warning("⚠️ 尚未导入课表数据，请先在首页初始化数据。")
        return
    
    # 显示科目顺序说明
    with st.expander("📋 顶课科目顺序说明", expanded=False):
        st.markdown("顶课时系统按以下固定科目顺序安排教师：")
        order_str = " → ".join(COURSE_ORDER)
        st.info(order_str)
        st.caption("""
        - 当某科目教师有冲突时，自动跳过并尝试下一科目
        - 被跳过的教师会在后续排课中优先考虑
        - 如需手动调整，可点击「手动选择」按钮
        """)
    
    # 步骤1：选择请假教师
    st.markdown("#### 步骤1：选择请假教师")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        selected_teacher = st.selectbox(
            "👨‍🏫 请假教师",
            options=teachers['id'].tolist(),
            format_func=lambda x: teachers[teachers['id']==x]['name'].values[0]
        )
    
    with col2:
        leave_reason = st.text_input("📝 请假事宜", placeholder="如：出差、培训、病假...")
    
    if selected_teacher:
        # 保存请假事宜到session_state
        if 'leave_reason' not in st.session_state:
            st.session_state.leave_reason = ''
        st.session_state.leave_reason = leave_reason
    
    if selected_teacher:
        # 显示该教师的课程
        teacher_courses = db.get_teacher_courses(selected_teacher)
        
        if teacher_courses.empty:
            st.info("该教师暂无课程安排。")
            return
        
        st.markdown(f"该教师共有 **{len(teacher_courses)}节课**，课程分布如下：")
        
        # 按星期分组显示
        teacher_courses['day_name'] = teacher_courses['day_of_week'].map(DAY_NAMES)
        teacher_courses['period_name'] = teacher_courses['period'].map(PERIOD_NAMES)
        teacher_courses['type'] = teacher_courses['period'].apply(lambda x: '🌙晚自习' if x in [10, 11] else '📚正课')
        
        # 显示课程列表
        display_df = teacher_courses[['day_name', 'period_name', 'class_name', 'course_name', 'type', 'grade']].copy()
        display_df.columns = ['星期', '节次', '班级', '课程', '类型', '年级']
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # 步骤2：选择要顶课的节次
        st.markdown("---")
        st.markdown("#### 步骤2：选择需顶课的节次")
        
        # 按正课和晚自习分类
        regular_courses = teacher_courses[~teacher_courses['period'].isin([10, 11])]
        evening_courses = teacher_courses[teacher_courses['period'].isin([10, 11])]
        
        tabs = st.tabs(["📚 正课 (第1-9节)", "🌙 晚自习 (第10-11节)"])
        
        selected_periods = []
        
        with tabs[0]:
            st.markdown("**勾选需要顶课的正课节次：**")
            if not regular_courses.empty:
                for _, row in regular_courses.iterrows():
                    key = f"reg_{row['id']}"
                    if st.checkbox(
                        f"{row['day_name']} {row['period_name']} - {row['class_name']} - {row['course_name']}",
                        value=False,
                        key=key
                    ):
                        selected_periods.append((row['class_id'], row['day_of_week'], row['period']))
            else:
                st.info("该教师没有正课")
        
        with tabs[1]:
            st.markdown("**勾选需要顶课的晚自习节次：**")
            if not evening_courses.empty:
                for _, row in evening_courses.iterrows():
                    key = f"eve_{row['id']}"
                    if st.checkbox(
                        f"{row['day_name']} {row['period_name']} - {row['class_name']} - {row['course_name']}",
                        value=False,
                        key=key
                    ):
                        selected_periods.append((row['class_id'], row['day_of_week'], row['period']))
            else:
                st.info("该教师没有晚自习")
        
        # 步骤3：生成调课方案
        st.markdown("---")
        st.markdown("#### 步骤3：生成调课方案")
        
        if st.button("🚀 一键生成调课方案", type="primary", use_container_width=True, disabled=len(selected_periods)==0):
            if not selected_periods:
                st.warning("请先选择要顶课的节次")
            else:
                with st.spinner("正在生成调课方案..."):
                    results = create_substitution_records(
                        selected_periods,
                        created_by=st.session_state.user['id'],
                        operated_by=st.session_state.user['id'],
                        leave_reason=st.session_state.get('leave_reason', '')
                    )
                
                if results:
                    st.session_state.substitution_results = results
                    st.success(f"✅ 已成功生成 **{len(results)}条** 调课记录")
                    st.rerun()
                else:
                    st.error("生成调课方案失败")
    
    # 显示调课结果和处理界面
    if st.session_state.substitution_results:
        st.markdown("---")
        st.markdown("#### 步骤4：确认/调整调课方案")
        
        # 显示请假事宜
        leave_reason_display = st.session_state.get('leave_reason', '')
        if leave_reason_display:
            st.info(f"📋 请假事宜：{leave_reason_display}")
        
        results = st.session_state.substitution_results
        db = get_db()
        
        # 初始化session_state中的选择索引
        if 'selected_teacher_indices' not in st.session_state:
            st.session_state.selected_teacher_indices = {}
        
        # 显示每条记录的详细信息
        for i, result in enumerate(results):
            with st.container():
                st.markdown(f"##### 📌 {result['day']} {result['period']} - {result['class']} - {result['course']}")
                
                col1, col2 = st.columns([2, 2])
                
                with col1:
                    st.markdown(f"**请假教师:** {result['absent_teacher']}")
                    if result.get('leave_reason'):
                        st.caption(f"📝 请假事宜: {result['leave_reason']}")
                
                with col2:
                    if result['status'] == '已安排':
                        st.markdown(f"**顶替教师:** {result['substitute_teacher']}")
                        assignment_badge = "🔄 自动" if result.get('assignment_type', '').startswith('auto') else "✋ 手动"
                        st.caption(f"{assignment_badge} | {result['message']}")
                    else:
                        st.markdown("**顶替教师:** 待分配")
                        st.caption("⚠️ " + result['message'])
                
                # 手动选择功能
                if result['course_type'] != '晚自习':  # 只对正课提供手动选择
                    available_teachers = result.get('all_available', [])
                    conflict_teachers = result.get('conflict_teachers', [])
                    
                    if available_teachers or conflict_teachers:
                        st.markdown("---")
                        st.markdown("**🔧 手动调整顶替教师**")
                        
                        col1, col2, col3 = st.columns([2, 1, 1])
                        
                        # 构建教师选项
                        teacher_options = []
                        teacher_map = {}
                        
                        # 优先显示可用教师
                        if available_teachers:
                            for idx, t in enumerate(available_teachers):
                                label = f"{t['name']} ({t.get('course_types', '未知')})"
                                teacher_options.append(label)
                                teacher_map[label] = {'id': t['id'], 'name': t['name'], 'available': True, 'index': idx}
                        
                        # 显示冲突教师
                        if conflict_teachers:
                            for t in conflict_teachers:
                                label = f"{t['name']} ({t.get('course', '未知')}) ⚠️"
                                teacher_options.append(label)
                                teacher_map[label] = {'id': t['id'], 'name': t['name'], 'available': False, 'index': len(teacher_options)-1}
                        
                        # 当前选择的教师
                        current_teacher_name = result.get('substitute_teacher', '')
                        current_option = None
                        for opt, info in teacher_map.items():
                            if info['name'] == current_teacher_name:
                                current_option = opt
                                break
                        
                        with col1:
                            # 手动选择下拉框
                            selected_option = st.selectbox(
                                "选择顶替教师",
                                options=["(保持当前)"] + teacher_options if current_option else teacher_options,
                                key=f"manual_select_{i}",
                                label_visibility="collapsed"
                            )
                        
                        # 检查是否有冲突（当前选择的教师在conflict_teachers中）
                        has_conflict = any(c['name'] == current_teacher_name for c in conflict_teachers)
                        
                        if has_conflict:
                            st.warning(f"⚠️ 当前选择的 {current_teacher_name} 有冲突（已被分配到其他课程）")
                            
                            # 获取下一个可用的教师
                            next_available = None
                            for opt, info in teacher_map.items():
                                if info['available'] and info['name'] != current_teacher_name:
                                    next_available = (opt, info)
                                    break
                            
                            if next_available:
                                with col2:
                                    if st.button(f"➡️ 下一个", key=f"next_{i}", use_container_width=True):
                                        # 切换到下一个可用教师
                                        st.session_state.selected_teacher_indices[i] = next_available[1]['index']
                                        st.rerun()
                                
                                with col3:
                                    if st.button(f"✅ 确认选择", key=f"confirm_{i}", use_container_width=True):
                                        # 更新记录
                                        db.update_substitution_manual(
                                            result['id'],
                                            next_available[1]['id'],
                                            st.session_state.user['id']
                                        )
                                        # 同时更新本地结果
                                        result['substitute_teacher'] = next_available[1]['name']
                                        result['substitute_teacher_id'] = next_available[1]['id']
                                        result['status'] = '已安排'
                                        result['assignment_type'] = 'manual'
                                        st.success(f"已指定 {next_available[1]['name']} 顶课")
                                        st.session_state.substitution_results = results
                                        st.rerun()
                            else:
                                with col2:
                                    st.warning("无更多可选教师")
                        else:
                            with col2:
                                if st.button(f"➡️ 下一个", key=f"next_{i}", use_container_width=True):
                                    # 切换到下一个可用教师
                                    current_idx = 0
                                    for opt, info in teacher_map.items():
                                        if info['name'] == current_teacher_name:
                                            current_idx = list(teacher_map.keys()).index(opt) if opt in teacher_map else 0
                                            break
                                    
                                    all_options = list(teacher_map.keys())
                                    next_idx = (all_options.index(current_option) + 1) % len(all_options) if current_option in all_options else 0
                                    next_option = all_options[next_idx]
                                    next_info = teacher_map[next_option]
                                    
                                    if next_info['available']:
                                        db.update_substitution_manual(
                                            result['id'],
                                            next_info['id'],
                                            st.session_state.user['id']
                                        )
                                        result['substitute_teacher'] = next_info['name']
                                        result['substitute_teacher_id'] = next_info['id']
                                        st.session_state.substitution_results = results
                                        st.success(f"已切换到 {next_info['name']}")
                                        st.rerun()
                            
                            with col3:
                                if st.button(f"✅ 确认选择", key=f"confirm_{i}", use_container_width=True):
                                    if selected_option != "(保持当前)" and selected_option in teacher_map:
                                        manual_teacher_id = teacher_map[selected_option]['id']
                                        db.update_substitution_manual(
                                            result['id'],
                                            manual_teacher_id,
                                            st.session_state.user['id']
                                        )
                                        result['substitute_teacher'] = teacher_map[selected_option]['name']
                                        result['substitute_teacher_id'] = manual_teacher_id
                                        result['assignment_type'] = 'manual'
                                        st.session_state.substitution_results = results
                                        st.success(f"已手动指定 {selected_option.split(' (')[0]} 顶课")
                                        st.rerun()
                
                # 显示冲突教师信息
                conflict = result.get('conflict_teachers', [])
                if conflict:
                    st.caption(f"⚠️ 以下教师有冲突: {', '.join([c['name'] for c in conflict])}")
                
                st.markdown("---")
        
        # 统计和操作
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("✅ 已安排", len([r for r in results if r['status'] == '已安排']))
        with col2:
            failed = len([r for r in results if r['status'] != '已安排'])
            st.metric("⚠️ 待手动处理", failed, delta="需要人工处理" if failed > 0 else None)
        with col3:
            st.metric("📊 总计", len(results))
        
        # 导出功能
        if st.button("📥 下载调课方案 (CSV)", use_container_width=True):
            display_results = []
            for r in results:
                display_results.append({
                    '星期': r['day'],
                    '节次': r['period'],
                    '班级': r['class'],
                    '课程': r['course'],
                    '类型': r['course_type'],
                    '请假教师': r['absent_teacher'],
                    '请假事宜': r.get('leave_reason', ''),
                    '顶替教师': r['substitute_teacher'],
                    '分配方式': '手动' if r.get('assignment_type') == 'manual' else '自动',
                    '状态': r['status']
                })
            
            df = pd.DataFrame(display_results)
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                "📥 确认下载",
                csv,
                f"调课方案_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                "text/csv",
                use_container_width=True
            )
        
        # 完成按钮
        if st.button("✅ 完成调课", type="primary", use_container_width=True):
            st.session_state.substitution_results = None
            st.success("调课已完成！")
            st.rerun()

# ==================== 课表查询页面 ====================

def render_schedule_page():
    st.title("📅 课表查询")
    st.markdown("---")
    
    db = get_db()
    
    query_type = st.radio("查询方式", ["按班级查询", "按教师查询"], horizontal=True)
    
    if query_type == "按班级查询":
        st.markdown("#### 🏫 班级课表")
        classes = db.get_all_classes()
        
        if classes.empty:
            st.warning("暂无班级数据")
            return
        
        selected_class = st.selectbox(
            "选择班级",
            options=classes['id'].tolist(),
            format_func=lambda x: f"{classes[classes['id']==x]['name'].values[0]} ({classes[classes['id']==x]['grade'].values[0]})"
        )
        
        if selected_class:
            schedule = db.get_class_schedule(selected_class)
            
            if not schedule:
                st.info("该班级暂无课表")
            else:
                # 构建课表矩阵
                days = ['周一', '周二', '周三', '周四', '周五']
                periods = list(range(1, 12))
                
                # 创建空矩阵
                matrix = {}
                for d in days:
                    matrix[d] = {f"第{p}节": "" for p in periods}
                    matrix[d]["晚1节"] = ""
                    matrix[d]["晚2节"] = ""
                
                # 填充数据
                for item in schedule:
                    day_name = DAY_NAMES.get(item['day_of_week'], '')
                    period_name = PERIOD_NAMES.get(item['period'], f"第{item['period']}节")
                    matrix[day_name][period_name] = f"{item['course_name']}\n({item['teacher_name']})"
                
                # 转换为DataFrame
                rows = []
                for period in periods + ['晚1节', '晚2节']:
                    row = [period]
                    for day in days:
                        row.append(matrix[day].get(period, ''))
                    rows.append(row)
                
                df = pd.DataFrame(rows, columns=['节次'] + days)
                st.dataframe(df, use_container_width=True, hide_index=True)
    
    else:
        st.markdown("#### 👨‍🏫 教师课表")
        teachers = db.get_all_teachers()
        
        if teachers.empty:
            st.warning("暂无教师数据")
            return
        
        selected_teacher = st.selectbox(
            "选择教师",
            options=teachers['id'].tolist(),
            format_func=lambda x: teachers[teachers['id']==x]['name'].values[0]
        )
        
        if selected_teacher:
            teacher_courses = db.get_teacher_courses(selected_teacher)
            
            if teacher_courses.empty:
                st.info("该教师暂无课表")
            else:
                # 按星期分组
                teacher_courses['day_name'] = teacher_courses['day_of_week'].map(DAY_NAMES)
                teacher_courses['period_name'] = teacher_courses['period'].map(PERIOD_NAMES)
                teacher_courses['type'] = teacher_courses['period'].apply(lambda x: '🌙晚' if x in [10, 11] else '📚')
                
                display_df = teacher_courses[['day_name', 'period_name', 'class_name', 'course_name', 'type']].copy()
                display_df.columns = ['星期', '节次', '班级', '课程', '']
                
                st.dataframe(display_df, use_container_width=True, hide_index=True)
                
                # 统计
                total = len(teacher_courses)
                regular = len([c for _, c in teacher_courses.iterrows() if c['period'] not in [10, 11]])
                evening = total - regular
                
                st.caption(f"总计: {total}节课 (正课{regular}节, 晚自习{evening}节)")

# ==================== 晚自习轮值页面 ====================

def render_evening_rotation_page():
    st.title("🌙 晚自习轮值管理")
    st.markdown("---")
    
    db = get_db()
    
    # 显示当前轮值状态
    st.markdown("#### 📊 轮值状态")
    
    current = db.get_current_evening_teacher()
    if current:
        st.info(f"🌙 当前值班教师: **{current['teacher_name']}** (第{current['order_index']+1}位)")
    else:
        st.warning("晚自习轮值表尚未设置")
    
    # 双列布局：已安排 vs 未安排
    st.markdown("---")
    st.markdown("#### 👥 教师分组")
    
    col_assigned, col_unassigned = st.columns(2)
    
    with col_assigned:
        st.markdown("##### ✅ 已安排轮值")
        rotation = db.get_evening_rotation()
        
        if rotation.empty:
            st.info("暂无已安排的教师")
        else:
            rotation_sorted = rotation.sort_values('teacher_name')
            
            # 显示已安排的教师
            for idx, row in rotation_sorted.iterrows():
                with st.container():
                    col_t, col_b = st.columns([4, 1])
                    with col_t:
                        st.markdown(f"📌 {row['teacher_name']}")
                    with col_b:
                        if st.session_state.user['role'] == 'admin':
                            if st.button("❌", key=f"remove_{row['id']}", help=f"移除{row['teacher_name']}"):
                                db.remove_teacher_from_evening_rotation(row['teacher_id'])
                                st.success(f"已移除 {row['teacher_name']}")
                                st.rerun()
            
            st.markdown("---")
            st.caption(f"共 {len(rotation)} 位教师")
    
    with col_unassigned:
        st.markdown("##### ⏳ 未安排轮值")
        
        # 获取所有活跃教师
        all_teachers = db.get_all_teachers()
        assigned_ids = rotation['teacher_id'].tolist() if not rotation.empty else []
        unassigned = all_teachers[~all_teachers['id'].isin(assigned_ids)] if assigned_ids else all_teachers
        
        if unassigned.empty:
            st.info("所有教师已安排")
        else:
            unassigned_sorted = unassigned.sort_values('name')
            
            for idx, row in unassigned_sorted.iterrows():
                with st.container():
                    col_t, col_b = st.columns([4, 1])
                    with col_t:
                        st.markdown(f"👤 {row['name']}")
                    with col_b:
                        if st.button("➕", key=f"add_{row['id']}", help=f"添加{row['name']}到轮值"):
                            db.add_teacher_to_evening_rotation(row['id'])
                            st.success(f"已添加 {row['name']}")
                            st.rerun()
    
    # 管理员功能：调整轮值顺序
    if st.session_state.user['role'] == 'admin':
        st.markdown("---")
        st.markdown("#### ⚙️ 调整轮值顺序 (管理员)")
        
        rotation = db.get_evening_rotation()
        
        if not rotation.empty:
            st.info("拖拽调整顺序后点击保存")
            
            # 获取当前顺序
            ordered_ids = rotation['teacher_id'].tolist()
            ordered_names = []
            for tid in ordered_ids:
                name = rotation[rotation['teacher_id']==tid]['teacher_name'].values
                if len(name) > 0:
                    ordered_names.append(name[0])
            
            # 编辑模式
            edited_names = st.data_editor(
                pd.DataFrame({'教师姓名': ordered_names}),
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                key="evening_rotation_editor"
            )
            
            if st.button("💾 保存新的轮值顺序", type="primary"):
                # 获取新顺序
                new_names = edited_names['教师姓名'].tolist()
                new_ids = []
                for name in new_names:
                    t = db.get_teacher_by_name(name)
                    if t:
                        new_ids.append(t['id'])
                
                if new_ids:
                    db.reorder_evening_rotation(new_ids)
                    st.success("✅ 轮值顺序已更新")
                    st.rerun()
        
        # 冲突记录管理
        st.markdown("---")
        st.markdown("#### 🗑️ 冲突记录管理 (管理员)")
        
        if st.button("🗑️ 清除所有冲突记录"):
            db.clear_skipped_teachers()
            st.success("✅ 已清除所有冲突记录")
            st.rerun()
        
        st.caption("清除冲突记录后，系统将重新按科目顺序分配顶课")

# ==================== 个人中心页面 ====================

def render_profile_page():
    st.title("👤 个人中心")
    st.markdown("---")
    
    db = get_db()
    user = st.session_state.user
    
    # 用户信息
    st.markdown("#### 👤 个人信息")
    
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("姓名", value=user['name'], disabled=True)
    with col2:
        st.text_input("角色", value="管理员" if user['role']=='admin' else "教务", disabled=True)
    
    # 用户名不可修改
    col3, col4 = st.columns(2)
    with col3:
        st.text_input("用户名", value=user['username'], disabled=True)
    
    # 如果用户关联了教师，显示该教师的课表
    if user.get('teacher_id'):
        st.markdown("#### 📚 我的课表")
        
        schedule = db.get_teacher_courses(user['teacher_id'])
        
        if not schedule.empty:
            # 按星期分组
            schedule['day_name'] = schedule['day_of_week'].map(DAY_NAMES)
            schedule['period_name'] = schedule['period'].map(PERIOD_NAMES)
            
            display_df = schedule[['day_name', 'period_name', 'class_name', 'course_name']].copy()
            display_df.columns = ['星期', '节次', '班级', '课程']
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # 统计
            st.caption(f"本周共 {len(schedule)} 节课")
        else:
            st.info("暂无课表安排")
        
        # Tabs: 顶课记录 vs 请假记录
        st.markdown("---")
        st.markdown("#### 📋 我的调课记录")
        
        tab1, tab2 = st.tabs(["📌 顶课记录（帮别人顶的）", "🏖️ 请假记录（自己请假被顶的）"])
        
        with tab1:
            # 顶课记录
            st.markdown("##### 顶课记录")
            st.caption("这是我帮其他教师顶的课程")
            
            # 时间筛选
            col_start, col_end = st.columns(2)
            with col_start:
                start_date = st.date_input("开始日期", value=None, key="sub_start")
            with col_end:
                end_date = st.date_input("结束日期", value=None, key="sub_end")
            
            # 获取数据
            start_str = start_date.isoformat() if start_date else None
            end_str = end_date.isoformat() + " 23:59:59" if end_date else None
            
            my_subs = db.get_teacher_substitutions_filtered(
                user['teacher_id'], 
                start_date=start_str, 
                end_date=end_str
            )
            
            if not my_subs.empty:
                display_df = my_subs[['day_of_week', 'period', 'class_name', 'absent_teacher_name', 'original_course', 'leave_reason', 'assignment_type']].copy()
                display_df['day_of_week'] = display_df['day_of_week'].map(DAY_NAMES)
                display_df['period'] = display_df['period'].map(PERIOD_NAMES)
                display_df['分配方式'] = display_df['assignment_type'].apply(lambda x: '手动' if x == 'manual' else '自动')
                display_df = display_df[['day_of_week', 'period', 'class_name', 'absent_teacher_name', 'original_course', 'leave_reason', '分配方式']]
                display_df.columns = ['星期', '节次', '班级', '请假教师', '课程', '请假事宜', '分配方式']
                
                st.dataframe(display_df, use_container_width=True, hide_index=True)
                st.caption(f"共有 {len(my_subs)} 条顶课记录")
                
                # 导出
                csv = display_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    "📥 导出顶课记录",
                    csv,
                    f"顶课记录_{datetime.now().strftime('%Y%m%d')}.csv",
                    "text/csv",
                    use_container_width=True
                )
            else:
                st.info("暂无顶课记录")
        
        with tab2:
            # 请假记录
            st.markdown("##### 请假记录")
            st.caption("这是我请假后被其他教师顶替的课程")
            
            # 时间筛选
            col_start2, col_end2 = st.columns(2)
            with col_start2:
                start_date2 = st.date_input("开始日期", value=None, key="leave_start")
            with col_end2:
                end_date2 = st.date_input("结束日期", value=None, key="leave_end")
            
            start_str2 = start_date2.isoformat() if start_date2 else None
            end_str2 = end_date2.isoformat() + " 23:59:59" if end_date2 else None
            
            my_leaves = db.get_teacher_leave_records_filtered(
                user['teacher_id'],
                start_date=start_str2,
                end_date=end_str2
            )
            
            if not my_leaves.empty:
                display_df = my_leaves[['day_of_week', 'period', 'class_name', 'substitute_teacher_name', 'original_course', 'leave_reason', 'assignment_type']].copy()
                display_df['day_of_week'] = display_df['day_of_week'].map(DAY_NAMES)
                display_df['period'] = display_df['period'].map(PERIOD_NAMES)
                display_df['顶课教师'] = display_df['substitute_teacher_name'].fillna('待安排')
                display_df['分配方式'] = display_df['assignment_type'].apply(lambda x: '手动' if x == 'manual' else '自动')
                display_df = display_df[['day_of_week', 'period', 'class_name', '顶课教师', 'original_course', 'leave_reason', '分配方式']]
                display_df.columns = ['星期', '节次', '班级', '顶课教师', '课程', '请假事宜', '分配方式']
                
                st.dataframe(display_df, use_container_width=True, hide_index=True)
                st.caption(f"共有 {len(my_leaves)} 条请假记录")
                
                # 导出
                csv = display_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    "📥 导出请假记录",
                    csv,
                    f"请假记录_{datetime.now().strftime('%Y%m%d')}.csv",
                    "text/csv",
                    use_container_width=True
                )
            else:
                st.info("暂无请假记录")
    
    # 所有顶课记录（管理员/教务）
    if user['role'] in ['admin', '教务']:
        st.markdown("---")
        st.markdown("#### 📜 所有调课记录")
        
        all_subs = db.get_substitutions()
        
        if not all_subs.empty:
            # 筛选
            col1, col2 = st.columns(2)
            with col1:
                type_filter = st.selectbox(
                    "按类型筛选",
                    options=['全部', '正课', '晚自习'],
                    index=0
                )
            with col2:
                status_filter = st.selectbox(
                    "按状态筛选",
                    options=['全部', 'pending', 'confirmed', 'failed'],
                    index=1
                )
            
            filtered = all_subs.copy()
            if type_filter == '正课':
                filtered = filtered[filtered['course_type'] == '正课']
            elif type_filter == '晚自习':
                filtered = filtered[filtered['course_type'] == '晚自习']
            
            if status_filter != '全部':
                filtered = filtered[filtered['status'] == status_filter]
            
            # 显示
            display_df = filtered[['created_at', 'day_of_week', 'period', 'class_name', 
                                   'absent_teacher_name', 'substitute_teacher_name', 
                                   'original_course', 'leave_reason', 'course_type', 
                                   'assignment_type', 'status']].copy()
            display_df['day_of_week'] = display_df['day_of_week'].map(DAY_NAMES)
            display_df['period'] = display_df['period'].map(PERIOD_NAMES)
            display_df['分配方式'] = display_df['assignment_type'].apply(lambda x: '手动' if x == 'manual' else '自动')
            display_df = display_df[['created_at', 'day_of_week', 'period', 'class_name', 
                                      'absent_teacher_name', 'substitute_teacher_name', 
                                      'original_course', 'leave_reason', 'course_type', 
                                      '分配方式', 'status']]
            display_df.columns = ['创建时间', '星期', '节次', '班级', '请假教师', 
                                   '顶替教师', '课程', '请假事宜', '类型', '分配方式', '状态']
            display_df['创建时间'] = pd.to_datetime(display_df['创建时间']).dt.strftime('%m-%d %H:%M')
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # 导出
            csv = display_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                "📥 导出调课记录 (CSV)",
                csv,
                f"调课记录_{datetime.now().strftime('%Y%m%d')}.csv",
                "text/csv",
                use_container_width=True
            )
        else:
            st.info("暂无调课记录")

# ==================== 数据管理页面 ====================

def render_data_management_page():
    st.title("⚙️ 数据管理")
    st.markdown("---")
    
    db = get_db()
    
    # 仅管理员可访问
    if st.session_state.user['role'] != 'admin':
        st.warning("仅管理员可访问此页面")
        return
    
    # Tab 页面
    tab1, tab2, tab3 = st.tabs(["👨‍🏫 教师管理", "📅 课表管理", "🏫 班级管理"])
    
    with tab1:
        st.markdown("#### 👨‍🏫 教师管理")
        
        # 添加教师
        with st.expander("➕ 添加新教师", expanded=False):
            col1, col2 = st.columns([3, 1])
            with col1:
                new_teacher_name = st.text_input("教师姓名", placeholder="输入教师姓名")
            with col2:
                st.markdown("")  # 空白占位
                if st.button("添加", type="primary", use_container_width=True):
                    if new_teacher_name.strip():
                        result = db.add_teacher(new_teacher_name.strip())
                        if result:
                            st.success(f"✅ 已添加教师：{new_teacher_name}")
                            st.rerun()
                        else:
                            st.error("❌ 教师已存在")
                    else:
                        st.warning("请输入教师姓名")
        
        # 显示所有教师
        st.markdown("##### 教师列表")
        
        teachers = db.get_all_teachers_including_inactive()
        
        if teachers.empty:
            st.info("暂无教师数据")
        else:
            # 按活跃状态分组显示
            active_teachers = teachers[teachers['is_active'] == 1]
            inactive_teachers = teachers[teachers['is_active'] == 0]
            
            st.markdown(f"**活跃教师 ({len(active_teachers)})**")
            
            if not active_teachers.empty:
                for idx, row in active_teachers.iterrows():
                    col1, col2, col3 = st.columns([3, 2, 1])
                    with col1:
                        st.markdown(f"👨‍🏫 {row['name']}")
                    with col2:
                        new_name = st.text_input(
                            "新姓名",
                            value=row['name'],
                            key=f"teacher_name_{row['id']}",
                            label_visibility="collapsed"
                        )
                        if new_name != row['name']:
                            if st.button("💾", key=f"save_{row['id']}", help="保存修改"):
                                if new_name.strip():
                                    db.update_teacher_name(row['id'], new_name.strip())
                                    st.success(f"已更新教师姓名")
                                    st.rerun()
                    with col3:
                        if st.button("🗑️", key=f"delete_{row['id']}", help="删除教师"):
                            db.delete_teacher(row['id'])
                            st.warning(f"已删除教师：{row['name']}")
                            st.rerun()
            
            if not inactive_teachers.empty:
                st.markdown("---")
                st.markdown(f"**已删除教师 ({len(inactive_teachers)})**")
                
                for idx, row in inactive_teachers.iterrows():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"~~👤 {row['name']}~~")
                    with col2:
                        if st.button("恢复", key=f"restore_{row['id']}", use_container_width=True):
                            db.reactivate_teacher(row['id'])
                            st.success(f"已恢复教师：{row['name']}")
                            st.rerun()
    
    with tab2:
        st.markdown("#### 📅 课表管理")
        
        # 选择班级
        classes = db.get_all_classes()
        
        if classes.empty:
            st.info("暂无班级数据，请先导入课表")
        else:
            selected_class = st.selectbox(
                "选择班级",
                options=classes['id'].tolist(),
                format_func=lambda x: f"{classes[classes['id']==x]['name'].values[0]}"
            )
            
            if selected_class:
                # 获取该班级的课表
                schedule = db.get_class_schedule(selected_class)
                
                if not schedule:
                    st.info("该班级暂无课表")
                else:
                    # 按星期分组显示
                    schedule['day_name'] = schedule['day_of_week'].map(DAY_NAMES)
                    schedule['period_name'] = schedule['period'].map(PERIOD_NAMES)
                    
                    # 显示课表
                    st.markdown("##### 当前课表")
                    
                    for day in range(1, 6):
                        day_schedule = [s for s in schedule if s['day_of_week'] == day]
                        if day_schedule:
                            st.markdown(f"**{DAY_NAMES.get(day, f'周{day}')}**")
                            
                            for item in sorted(day_schedule, key=lambda x: x['period']):
                                col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 2, 1])
                                
                                with col1:
                                    st.markdown(f"第{item['period']}节")
                                with col2:
                                    st.markdown(f"{item['course_name']}")
                                with col3:
                                    current_teacher = item['teacher_name']
                                    teachers = db.get_all_teachers()
                                    new_teacher_id = st.selectbox(
                                        "教师",
                                        options=teachers['id'].tolist(),
                                        format_func=lambda x: teachers[teachers['id']==x]['name'].values[0],
                                        index=list(teachers['id']).index(item['teacher_id']) if item['teacher_id'] in teachers['id'].values else 0,
                                        key=f"schedule_{item['id']}",
                                        label_visibility="collapsed"
                                    )
                                with col4:
                                    st.caption(f"班级: {item['class_name']}")
                                with col5:
                                    if new_teacher_id != item['teacher_id']:
                                        if st.button("💾", key=f"save_schedule_{item['id']}", help="保存修改"):
                                            db.update_schedule_teacher(item['id'], new_teacher_id)
                                            st.success("已更新教师")
                                            st.rerun()
    
    with tab3:
        st.markdown("#### 🏫 班级管理")
        
        classes = db.get_all_classes()
        
        if classes.empty:
            st.info("暂无班级数据")
        else:
            st.markdown(f"**班级列表 (共 {len(classes)} 个)**")
            
            for idx, row in classes.iterrows():
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.markdown(f"🏫 {row['name']} ({row['grade']})")
                with col2:
                    # 显示该班级的课程数量
                    class_schedule = db.get_class_schedule(row['id'])
                    st.caption(f"共 {len(class_schedule)} 节课" if not class_schedule.empty else "暂无课表")
    
    # 数据初始化（保留在底部）
    st.markdown("---")
    st.markdown("#### ⚙️ 数据初始化")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📥 从Excel导入课表数据", use_container_width=True):
            try:
                with st.spinner("正在导入数据..."):
                    result = import_schedule_to_db()
                st.success(f"""
                ✅ 导入完成！
                - 教师: {result['teachers']} 位
                - 班级: {result['classes']} 个
                - 课表记录: {result['schedule_items']} 条
                """)
                st.rerun()
            except Exception as e:
                st.error(f"导入失败: {str(e)}")
    
    with col2:
        if st.button("⚠️ 清空所有数据", use_container_width=True):
            st.warning("此操作不可逆！请确认是否清空所有数据。")
            if st.button("确认清空", type="primary", use_container_width=True):
                db.clear_schedule()
                st.success("✅ 所有数据已清空")
                st.rerun()

# ==================== 主程序 ====================

def main():
    # 检查登录状态
    if not st.session_state.logged_in:
        render_login_page()
        return
    
    # 渲染侧边栏并获取当前页面
    page = render_sidebar()
    
    # 根据页面导航渲染对应内容
    if page == "🏠 首页":
        render_home_page()
    elif page == "📝 发起顶课":
        render_substitution_page()
    elif page == "📅 课表查询":
        render_schedule_page()
    elif page == "🌙 晚自习轮值":
        render_evening_rotation_page()
    elif page == "👤 个人中心":
        render_profile_page()
    elif page == "⚙️ 数据管理":
        render_data_management_page()
    else:
        render_home_page()

if __name__ == "__main__":
    main()
