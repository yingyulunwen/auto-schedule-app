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
                ["🏠 首页", "📝 发起顶课", "📅 课表查询", "🌙 晚自习轮值", "👤 个人中心"],
                captions=[
                    "主页和快捷入口",
                    "选择请假教师，发起顶课",
                    "查看班级和教师课表",
                    "查看和调整晚自习顺序",
                    "我的课表和顶课记录"
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
    
    selected_teacher = st.selectbox(
        "👨‍🏫 请假教师",
        options=teachers['id'].tolist(),
        format_func=lambda x: teachers[teachers['id']==x]['name'].values[0]
    )
    
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
                        operated_by=st.session_state.user['id']
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
        
        results = st.session_state.substitution_results
        db = get_db()
        
        # 显示每条记录的详细信息
        for i, result in enumerate(results):
            with st.container():
                st.markdown(f"##### 📌 {result['day']} {result['period']} - {result['class']} - {result['course']}")
                
                col1, col2, col3 = st.columns([2, 2, 3])
                
                with col1:
                    st.markdown(f"**请假教师:** {result['absent_teacher']}")
                
                with col2:
                    if result['status'] == '已安排':
                        st.markdown(f"**顶替教师:** {result['substitute_teacher']}")
                        assignment_badge = "🔄 自动" if result.get('assignment_type', '').startswith('auto') else "✋ 手动"
                        st.caption(f"{assignment_badge} | {result['message']}")
                    else:
                        st.markdown("**顶替教师:** 待分配")
                        st.caption("⚠️ " + result['message'])
                
                # 手动选择功能
                with col3:
                    if result['course_type'] != '晚自习':  # 只对正课提供手动选择
                        available_teachers = result.get('all_available', [])
                        conflict_teachers = result.get('conflict_teachers', [])
                        
                        if available_teachers or conflict_teachers:
                            # 构建教师选项
                            teacher_options = []
                            teacher_map = {}
                            
                            # 优先显示可用教师
                            if available_teachers:
                                teacher_options.append("--- 可用教师 ---")
                                for t in available_teachers:
                                    label = f"{t['name']} ({t.get('course_types', '未知')})"
                                    teacher_options.append(label)
                                    teacher_map[label] = t['id']
                            
                            # 显示冲突教师
                            if conflict_teachers:
                                teacher_options.append("--- 冲突教师(已被分配) ---")
                                for t in conflict_teachers:
                                    label = f"{t['name']} ({t.get('course', '未知')}) ⚠️"
                                    teacher_options.append(label)
                                    teacher_map[label] = t['id']
                            
                            # 手动选择下拉框
                            selected_option = st.selectbox(
                                "手动选择顶替教师",
                                options=["(保持自动分配)"] + teacher_options,
                                key=f"manual_select_{i}",
                                label_visibility="collapsed"
                            )
                            
                            if selected_option != "(保持自动分配)" and selected_option in teacher_map:
                                manual_teacher_id = teacher_map[selected_option]
                                if st.button(f"✅ 确认选择", key=f"confirm_{i}"):
                                    # 更新记录
                                    db.update_substitution_manual(
                                        result['id'],
                                        manual_teacher_id,
                                        st.session_state.user['id']
                                    )
                                    st.success(f"已手动指定 {selected_option.split(' (')[0]} 顶课")
                                    st.session_state.substitution_results = None
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
    
    # 显示完整轮值表
    st.markdown("---")
    st.markdown("#### 📋 晚自习轮值顺序表")
    
    rotation = db.get_evening_rotation()
    
    if rotation.empty:
        st.warning("暂无轮值数据，请先在首页初始化数据")
    else:
        # 显示轮值表
        display_df = rotation[['order_index', 'teacher_name']].copy()
        display_df.columns = ['序号', '教师姓名']
        display_df['序号'] = display_df['序号'] + 1
        display_df.index = range(1, len(display_df) + 1)
        
        st.dataframe(display_df, use_container_width=True)
        
        st.caption(f"共 {len(rotation)} 位教师参与轮值")
    
    # 管理员可以调整轮值顺序
    if st.session_state.user['role'] == 'admin':
        st.markdown("---")
        st.markdown("#### ⚙️ 调整轮值顺序 (管理员)")
        
        teachers = db.get_all_teachers()
        
        if not teachers.empty:
            st.info("拖拽调整顺序后点击保存")
            
            # 获取当前顺序
            ordered_ids = rotation['teacher_id'].tolist() if not rotation.empty else teachers['id'].tolist()
            ordered_names = []
            for tid in ordered_ids:
                name = teachers[teachers['id']==tid]['name'].values
                if len(name) > 0:
                    ordered_names.append(name[0])
            
            # 编辑模式
            edited_names = st.data_editor(
                pd.DataFrame({'教师姓名': ordered_names}),
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True
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
                    db.set_evening_rotation(new_ids)
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
    
    st.markdown("---")
    
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
    
    # 我的顶课记录
    st.markdown("---")
    st.markdown("#### 📋 我的顶课记录")
    
    # 获取我被安排的顶课
    my_subs = db.get_substitutions({'status': 'confirmed'})
    
    if user.get('teacher_id'):
        my_duties = my_subs[my_subs['substitute_teacher_id'] == user['teacher_id']]
    else:
        my_duties = my_subs
    
    if not my_duties.empty:
        display_df = my_duties[['day_of_week', 'period', 'class_name', 'absent_teacher_name', 'original_course', 'assignment_type']].copy()
        display_df['day_of_week'] = display_df['day_of_week'].map(DAY_NAMES)
        display_df['period'] = display_df['period'].map(PERIOD_NAMES)
        display_df['分配方式'] = display_df['assignment_type'].apply(lambda x: '手动' if x == 'manual' else '自动')
        display_df = display_df[['day_of_week', 'period', 'class_name', 'absent_teacher_name', 'original_course', '分配方式']]
        display_df.columns = ['星期', '节次', '班级', '原任课教师', '课程', '分配方式']
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        st.caption(f"共有 {len(my_duties)} 条顶课记录")
    else:
        st.info("暂无顶课记录")
    
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
                                   'original_course', 'course_type', 'assignment_type', 'status']].copy()
            display_df['day_of_week'] = display_df['day_of_week'].map(DAY_NAMES)
            display_df['period'] = display_df['period'].map(PERIOD_NAMES)
            display_df['分配方式'] = display_df['assignment_type'].apply(lambda x: '手动' if x == 'manual' else '自动')
            display_df = display_df[['created_at', 'day_of_week', 'period', 'class_name', 
                                     'absent_teacher_name', 'substitute_teacher_name', 
                                     'original_course', 'course_type', '分配方式', 'status']]
            display_df.columns = ['创建时间', '星期', '节次', '班级', '请假教师', 
                                   '顶替教师', '课程', '类型', '分配方式', '状态']
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
    else:
        render_home_page()

if __name__ == "__main__":
    main()
