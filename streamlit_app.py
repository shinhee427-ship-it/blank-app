import streamlit as st
import pandas as pd
import random

st.set_page_config(page_title="🏸 배드민턴 스마트 자동 배정판", layout="wide")
st.title("🏸 배드민턴 ")

LEVEL_WEIGHTS = {"A":5,"B":4,"C":3,"D":2,"E":1}

# ---------------------------
# 세션 초기화
# ---------------------------
for key in ['members','current_players','court_games','game_queue','waiting_pool','manual_mode','refresh_trigger']:
    if key not in st.session_state:
        st.session_state[key] = {} if key in ['court_games','manual_mode'] else []

# ---------------------------
# 1. CSV 업로드
# ---------------------------
with st.sidebar:
    uploaded_file = st.file_uploader("CSV 업로드 (이름,성별,급수,혼합가능 True/False)", type=["csv"])
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        required_cols = ["이름","성별","급수","혼합가능"]
        if all(col in df.columns for col in required_cols):
            df['혼합가능'] = df['혼합가능'].astype(bool)
            st.session_state.members = df.to_dict(orient="records")
            st.success(f"{len(st.session_state.members)}명 회원 불러옴")
        else:
            st.error(f"CSV 컬럼 필요: {required_cols}")

# ---------------------------
# 2. 참석자 선택
# ---------------------------
selected = st.multiselect(
    "참석 체크",
    options=[f"{m['이름']}({m['성별']}/{m['급수']})" for m in st.session_state.members]
)
st.session_state.current_players = [
    m for m in st.session_state.members
    if f"{m['이름']}({m['성별']}/{m['급수']})" in selected
]

# 대기 pool 업데이트 (중복 제거)
for p in st.session_state.current_players:
    if p not in st.session_state.waiting_pool:
        st.session_state.waiting_pool.append(p)

st.info(f"참여: {len(st.session_state.current_players)}, 대기 pool: {len(st.session_state.waiting_pool)}")

# ---------------------------
# 3. 게임 생성 함수 (중복 없음)
# ---------------------------
def generate_game_queue(waiting_pool):
    """대기 풀에서 중복 없이 게임 큐 생성"""
    queue = []
    pool = waiting_pool.copy()
    used_players = set()
    
    random.shuffle(pool)
    
    while len(pool) >= 4:
        available = [p for p in pool if p['이름'] not in used_players]
        if len(available) < 4:
            break
        
        available = sorted(available, key=lambda x: LEVEL_WEIGHTS.get(x.get('급수','E'),1), reverse=True)
        t1, t2 = available[:2], available[2:4]
        
        for p in t1+t2:
            pool.remove(p)
            used_players.add(p['이름'])
            
        queue.append((t1,t2))
    
    return queue

num_courts = st.select_slider(
    "🏟️ 코트 수",
    options=[1,2,3,4],
    value=min(len(st.session_state.current_players)//4,4) if len(st.session_state.current_players)>=4 else 1
)

if st.button("게임 생성"):
    st.session_state.game_queue = generate_game_queue(st.session_state.waiting_pool.copy())
    st.session_state.court_games = {i+1: None for i in range(num_courts)}

# ---------------------------
# 4. 코트별 진행/대기 + 완료 자동 이동
# ---------------------------
for c in range(1,num_courts+1):
    st.markdown(f"### 📍 {c}번 코트")
    if c not in st.session_state.court_games:
        st.session_state.court_games[c] = None
    
    # 현재 진행 게임 없으면 대기 1 게임 가져오기
    if st.session_state.court_games.get(c) is None and st.session_state.game_queue:
        st.session_state.court_games[c] = st.session_state.game_queue.pop(0)
    
    game = st.session_state.court_games.get(c)
    
    if game:
        t1, t2 = game
        t1_names = [f"{p['이름']}({p['성별']}/{p['급수']})" for p in t1]
        t2_names = [f"{p['이름']}({p['성별']}/{p['급수']})" for p in t2]
        col1,col2,col3 = st.columns([3,1,3])
        
        with col1: st.text("TEAM A: " + ", ".join(t1_names))
        with col3: st.text("TEAM B: " + ", ".join(t2_names))
        
        with col2:
            if st.button("✅ 완료", key=f"done_{c}"):
                # 완료 인원 → 대기 pool에 추가, 중복 제거
                for p in t1+t2:
                    if p not in st.session_state.waiting_pool:
                        st.session_state.waiting_pool.append(p)
                # 현재 게임 제거 후 다음 대기 게임 배정
                if st.session_state.game_queue:
                    st.session_state.court_games[c] = st.session_state.game_queue.pop(0)
                else:
                    st.session_state.court_games[c] = None
                # 대기 게임 다시 생성
                st.session_state.game_queue = generate_game_queue(st.session_state.waiting_pool.copy())
                # 화면 즉시 갱신용
                st.session_state['refresh_trigger'] = random.random()

            if st.button("✏️ 수정", key=f"manual_{c}"):
                st.session_state.manual_mode[c] = True

        # 수정 모드
        if st.session_state.manual_mode.get(c,False):
            names_pool = [f"{p['이름']}({p['성별']}/{p['급수']})" for p in st.session_state.current_players]
            t1_new = st.multiselect("TEAM A 수정", names_pool, default=t1_names, key=f"t1_manual_{c}")
            t2_new = st.multiselect("TEAM B 수정", names_pool, default=t2_names, key=f"t2_manual_{c}")
            if st.button("적용", key=f"apply_{c}"):
                t1 = [next(p for p in st.session_state.current_players if f"{p['이름']}({p['성별']}/{p['급수']})"==name) for name in t1_new]
                t2 = [next(p for p in st.session_state.current_players if f"{p['이름']}({p['성별']}/{p['급수']})"==name) for name in t2_new]
                st.session_state.court_games[c] = (t1,t2)
                st.session_state.manual_mode[c] = False

    # 대기 1 / 대기 2 게임 표시
    for idx, label in enumerate(["대기 1 게임","대기 2 게임"]):
        if len(st.session_state.game_queue) > idx:
            t1d, t2d = st.session_state.game_queue[idx]
            st.markdown(f"**{label}**")
            st.text(
                "TEAM A: " + ", ".join([f"{p['이름']}({p['성별']}/{p['급수']})" for p in t1d]) +
                " VS TEAM B: " + ", ".join([f"{p['이름']}({p['성별']}/{p['급수']})" for p in t2d])
            )

# ---------------------------
# 5. 현재 대기자 리스트 표시 (게임 배정 제외)
# ---------------------------
assigned_players = set()
for game in st.session_state.court_games.values():
    if game:
        assigned_players.update([p['이름'] for p in game[0]+game[1]])
for idx in range(min(2,len(st.session_state.game_queue))):
    t1d, t2d = st.session_state.game_queue[idx]
    assigned_players.update([p['이름'] for p in t1d+t2d])

real_waiting = [p for p in st.session_state.waiting_pool if p['이름'] not in assigned_players]

if real_waiting:
    st.markdown("### 🕒 현재 대기자 리스트")
    waiting_names = [f"{p['이름']}({p['성별']}/{p['급수']})" for p in real_waiting]
    st.text(", ".join(waiting_names))
else:
    st.markdown("### 🕒 현재 대기자 없음")
