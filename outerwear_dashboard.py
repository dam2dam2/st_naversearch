import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# --- 페이지 설정 ---
st.set_page_config(
    page_title="아우터 트렌드 분석 대시보드",
    page_icon="🧥",
    layout="wide"
)

# --- CSS 스타일링 ---
st.markdown("""
    <style>
    /* 메인 배경색 강제 지정 제거 (테마 따름) */
    /* .main { background-color: #f8f9fa; } */
    
    /* Metric 카드 스타일: 배경이 흰색이므로 글자색을 검정으로 강제 */
    .stMetric { 
        background-color: #ffffff; 
        padding: 20px; 
        border-radius: 12px; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); 
        border-top: 4px solid #00c853; 
        color: #000000 !important;
    }
    
    /* Metric 내부 라벨 색상도 강제 (Streamlit 버전마다 클래스가 다를 수 있어 포괄적으로 지정) */
    .stMetric label { color: #666666 !important; }
    .stMetric div[data-testid="stMetricValue"] { color: #000000 !important; }

    /* 헤더 색상: 다크모드 대응을 위해 제거하거나 조정. 여기서는 테마 기본값 사용 권장으로 주석 처리 */
    /* h1, h2, h3 { color: #1a237e; font-weight: 800; } */
    
    /* 사이드바 배경: 테마 따름 */
    /* div[data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #dee2e6; } */
    </style>
""", unsafe_allow_html=True)

# --- 인증 및 경로 설정 ---
def get_api_keys():
    try:
        if 'NAVER_CLIENT_ID' in st.secrets:
            return st.secrets['NAVER_CLIENT_ID'], st.secrets['NAVER_CLIENT_SECRET']
    except Exception:
        pass
    
    # 상위 디렉터리의 .env 파일 로드 시도
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
    return os.getenv('NAVER_CLIENT_ID'), os.getenv('NAVER_CLIENT_SECRET')

CLIENT_ID, CLIENT_SECRET = get_api_keys()
HEADERS = {"X-Naver-Client-Id": CLIENT_ID, "X-Naver-Client-Secret": CLIENT_SECRET, "Content-Type": "application/json"}

# --- 아우터 키워드 정의 ---
OUTER_KEYWORDS = ["패딩", "항공점퍼", "바람막이", "블루종", "플리스점퍼", "야상점퍼", "후드점퍼"]

# --- API 호출 함수 ---
@st.cache_data(ttl=600)
def fetch_datalab_trend(keywords, start_date, end_date="2025-12-31", time_unit="date"):
    """네이버 데이터랩(검색어 트렌드) API 호출"""
    if not CLIENT_ID: return None, "API Key 미설정"
    url = "https://openapi.naver.com/v1/datalab/search"
    
    # 5개씩 묶어서 요청해야 함 (네이버 API 제한: 주제어 그룹 최대 5개)
    # 여기서는 7개이므로 2번 요청해서 합치거나, 주요 키워드 Top 5를 선택하게 해야 함.
    # 또는 각각 1개씩 요청해서 합치는 방식 사용 (절대값이 아닌 상대값이므로 100 기준이 달라질 수 있어 주의 필요)
    # 정확한 비교를 위해서는 한 번에 요청해야 하는데 5개가 최대임.
    # 사용자 편의를 위해 UI에서 5개까지 선택하도록 유도하거나, 
    # 대표 키워드('패딩')를 포함하여 그룹을 나누어 스케일링하는 방법이 있음.
    # 여기서는 간단히 '선택된 키워드(최대 5개)'만 호출하도록 구현.
    
    if len(keywords) > 5:
        keywords = keywords[:5] # 상위 5개로 제한

    body = {
        "startDate": start_date,
        "endDate": datetime.now().strftime("%Y-%m-%d"), # 미래 날짜 불가, 오늘까지
        "timeUnit": time_unit,
        "keywordGroups": [{"groupName": k, "keywords": [k]} for k in keywords],
        "device": "",
        "ages": [],
        "gender": ""
    }
    
    try:
        res = requests.post(url, headers=HEADERS, data=json.dumps(body))
        if res.status_code == 200:
            results = res.json().get('results', [])
            dfs = []
            for r in results:
                df = pd.DataFrame(r['data'])
                df['keyword'] = r['title']
                dfs.append(df)
            
            if dfs:
                return pd.concat(dfs), None
            else:
                return pd.DataFrame(), "데이터가 없습니다."
        else:
            return None, f"API Error: {res.status_code} - {res.text}"
    except Exception as e:
        return None, str(e)

@st.cache_data(ttl=600)
def fetch_shop_search(keyword):
    """네이버 쇼핑 검색 API"""
    if not CLIENT_ID: return None, "API Key 미설정"
    url = f"https://openapi.naver.com/v1/search/shop.json?query={keyword}&display=100&sort=sim"
    res = requests.get(url, headers=HEADERS)
    if res.status_code == 200:
        return pd.DataFrame(res.json()['items']), None
    return None, f"Shop API Error: {res.status_code}"

# --- 메인 UI ---
st.title("🧥 아우터(Outer) 트렌드 분석")
st.markdown("주요 아우터 종류에 대한 **검색 트렌드**와 **실시간 쇼핑 정보**를 분석합니다.")

# 사이드바 설정
st.sidebar.header("설정")
selected_keywords = st.sidebar.multiselect(
    "분석할 아우터 선택 (최대 5개)",
    options=OUTER_KEYWORDS,
    default=["패딩", "플리스점퍼", "바람막이"]
)

if len(selected_keywords) > 5:
    st.sidebar.error("최대 5개까지만 선택 가능합니다.")
    selected_keywords = selected_keywords[:5]

start_date = st.sidebar.date_input("조회 시작일", datetime(2025, 1, 1))

run_btn = st.sidebar.button("분석 실행", type="primary")

if not run_btn and "outer_trend" not in st.session_state:
    st.info("좌측 사이드바에서 아우터를 선택하고 '분석 실행'을 눌러주세요.")
    st.stop()

if run_btn:
    with st.spinner("네이버 데이터랩 API 요청 중..."):
        df_trend, err = fetch_datalab_trend(selected_keywords, start_date.strftime("%Y-%m-%d"))
        st.session_state['outer_trend'] = df_trend
        st.session_state['outer_err'] = err
        st.session_state['outer_selected'] = selected_keywords

# 결과 표시
if 'outer_trend' in st.session_state:
    df = st.session_state['outer_trend']
    err = st.session_state.get('outer_err')
    keywords = st.session_state.get('outer_selected', [])

    if err:
        st.error(err)
    elif df is not None and not df.empty:
        df['period'] = pd.to_datetime(df['period'])
        
        # Tab 구성
        tab1, tab2, tab3 = st.tabs(["📈 검색 트렌드 비교", "🛍️ 아우터별 인기 상품", "📊 고급 데이터 분석"])
        
        # Tab 1: 트렌드
        with tab1:
            st.subheader(f"선택된 아우터 검색량 추이 ({start_date} ~ 현재)")
            fig = px.line(df, x='period', y='ratio', color='keyword', 
                          title="일별 검색량 추이 (상대지표 0~100)", markers=True)
            st.plotly_chart(fig, use_container_width=True)
            
            # 통계
            st.subheader("기간 내 검색량 요약")
            stats = df.groupby('keyword')['ratio'].agg(['mean', 'max', 'min']).reset_index().round(1)
            stats.columns = ['아우터', '평균 지수', '최대 지수', '최소 지수']
            st.dataframe(stats, use_container_width=True)
            
            # 상관관계 (2개 이상 선택 시)
            if len(keywords) >= 2:
                st.divider()
                st.subheader("검색 패턴 상관관계")
                pivot_df = df.pivot(index='period', columns='keyword', values='ratio')
                conn_mat = pivot_df.corr()
                fig_corr = px.imshow(conn_mat, text_auto=True, title="상관계수 히트맵")
                st.plotly_chart(fig_corr, use_container_width=True)

        # Tab 2: 쇼핑 정보
        with tab2:
            st.subheader("현재 네이버 쇼핑 인기 상품")
            
            # 선택된 키워드 중 하나를 선택해서 상세 보기
            target_kw = st.selectbox("상품을 확인할 아우터 선택", keywords)
            
            if target_kw:
                with st.spinner(f"'{target_kw}' 쇼핑 데이터 수집 중..."):
                    shop_df, s_err = fetch_shop_search(target_kw)
                    
                if s_err:
                    st.error(s_err)
                elif shop_df is not None and not shop_df.empty:
                    # 전처리
                    shop_df['lprice'] = pd.to_numeric(shop_df['lprice'], errors='coerce')
                    shop_df['title'] = shop_df['title'].str.replace('<b>', '').str.replace('</b>', '')
                    
                    # 지표
                    c1, c2, c3 = st.columns(3)
                    c1.metric("최저가 평균", f"{int(shop_df['lprice'].mean()):,}원")
                    c2.metric("최고가 상품", f"{int(shop_df['lprice'].max()):,}원")
                    c3.metric("최저가 상품", f"{int(shop_df['lprice'].min()):,}원")
                    
                    # 가격 분포
                    fig_hist = px.histogram(shop_df, x='lprice', nbins=20, 
                                            title=f"'{target_kw}' 가격대 분포",
                                            labels={'lprice': '가격(원)'})
                    st.plotly_chart(fig_hist, use_container_width=True)
                    
                    # 상품 리스트
                    st.markdown(f"**Top 20 인기 상품**")
                    st.dataframe(
                        shop_df[['title', 'lprice', 'mallName', 'brand', 'category1']].head(20),
                        use_container_width=True
                    )
        
        # Tab 3: 고급 데이터 분석
        with tab3:
            st.header("📊 데이터 분석 결과물")
            st.markdown("수집된 **쇼핑 트렌드** 및 **쇼핑 검색** 데이터를 기반으로 심층 분석을 수행합니다.")

            # 1. 컬럼별 결측값 개수 및 비율 시각화
            st.subheader("1. 데이터 품질 점검 (결측치)")
            
            # (1) 트렌드 데이터
            trend_nulls = df.isnull().sum().reset_index()
            trend_nulls.columns = ['Column', 'Missing Count']
            trend_nulls['Missing Ratio (%)'] = (trend_nulls['Missing Count'] / len(df)) * 100
            
            # (2) 쇼핑 데이터 (만약 tab2에서 로드되었다면 사용, 아니면 재로드 필요)
            # 여기서는 편의상 현재 세션에 있는 keywords 전체에 대해 쇼핑 데이터를 가져와서 합쳐본다.
            full_shop_df = pd.DataFrame()
            if 'full_shop_df' not in st.session_state:
                with st.spinner("분석용 쇼핑 전체 데이터 로드 중..."):
                    temp_dfs = []
                    for k in keywords:
                        t_df, _ = fetch_shop_search(k)
                        if t_df is not None:
                            t_df['keyword'] = k
                            temp_dfs.append(t_df)
                    if temp_dfs:
                        full_shop_df = pd.concat(temp_dfs)
                        # 전처리
                        full_shop_df['lprice'] = pd.to_numeric(full_shop_df['lprice'], errors='coerce')
                    st.session_state['full_shop_df'] = full_shop_df
            else:
                full_shop_df = st.session_state['full_shop_df']

            shop_nulls = full_shop_df.isnull().sum().reset_index()
            shop_nulls.columns = ['Column', 'Missing Count']
            shop_nulls['Missing Ratio (%)'] = (shop_nulls['Missing Count'] / len(full_shop_df)) * 100

            c_null1, c_null2 = st.columns(2)
            with c_null1:
                st.markdown("**트렌드 데이터 결측 현황**")
                if trend_nulls['Missing Count'].sum() == 0:
                    st.success("✅ 트렌드 데이터에 결측치가 없습니다.")
                fig_null1 = px.bar(trend_nulls, x='Column', y='Missing Count', text='Missing Count', 
                                   title="트렌드 데이터 결측치 (막대 #1)", color_discrete_sequence=['#ef5350'])
                fig_null1.update_yaxes(range=[0, max(1, trend_nulls['Missing Count'].max() * 1.1)]) # Y축 강제 설정
                st.plotly_chart(fig_null1, use_container_width=True)
                with st.expander("트렌드 데이터 결측 상세 보기"):
                    st.dataframe(trend_nulls, use_container_width=True)

            with c_null2:
                st.markdown("**쇼핑 데이터 결측 현황**")
                if shop_nulls['Missing Count'].sum() == 0:
                    st.success("✅ 쇼핑 데이터에 결측치가 없습니다.")
                fig_null2 = px.bar(shop_nulls, x='Column', y='Missing Count', text='Missing Count', 
                                   title="쇼핑 데이터 결측치 (막대 #2)", color_discrete_sequence=['#ffa726'])
                fig_null2.update_yaxes(range=[0, max(1, shop_nulls['Missing Count'].max() * 1.1)])
                st.plotly_chart(fig_null2, use_container_width=True)
                with st.expander("쇼핑 데이터 결측 상세 보기"):
                    st.dataframe(shop_nulls, use_container_width=True)

            # 2. 이상치·결측치 현황 (박스플롯)
            st.subheader("2. 이상치 및 데이터 분포 (Box Plot)")
            c_box1, c_box2 = st.columns(2)
            with c_box1:
                st.markdown("**트렌드 검색량(Ratio) 분포**")
                fig_box1 = px.box(df, x='keyword', y='ratio', color='keyword', 
                                  title="검색어별 검색량 이상치 분석")
                st.plotly_chart(fig_box1, use_container_width=True)
            with c_box2:
                st.markdown("**쇼핑 가격(Price) 분포**")
                if not full_shop_df.empty:
                    fig_box2 = px.box(full_shop_df, x='keyword', y='lprice', color='keyword', 
                                      title="아우터별 가격대 이상치 분석")
                    st.plotly_chart(fig_box2, use_container_width=True)

            # 3. 주요 분석 결과 (유형별 시각화)
            st.divider()
            st.header("3. 주요 분석 결과 (Visual Analysis)")
            st.markdown("분석의 명확성을 위해 **피봇 테이블, 막대 그래프, 히트맵**을 유형별로 구분하여 시각화했습니다.")

            # 데이터 준비 (Data Preparation)
            # (1) 요일별 데이터
            df['day_name'] = df['period'].dt.day_name()
            days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            df['day_name'] = pd.Categorical(df['day_name'], categories=days, ordered=True)
            day_pivot = df.pivot_table(index='day_name', columns='keyword', values='ratio', aggfunc='mean')
            
            # (2) 브랜드/몰 데이터
            top_brands_df = pd.DataFrame()
            brand_pivot = pd.DataFrame()
            mall_top10 = pd.DataFrame()
            
            if not full_shop_df.empty and 'brand' in full_shop_df.columns:
                brand_df = full_shop_df[full_shop_df['brand'] != ""].copy()
                top_brands = brand_df['brand'].value_counts().head(15).index
                filtered_brand = brand_df[brand_df['brand'].isin(top_brands)]
                
                # 브랜드 피봇
                brand_pivot = filtered_brand.pivot_table(index='brand', values='lprice', aggfunc=['count', 'mean']).reset_index()
                brand_pivot.columns = ['Brand', 'Count', 'AvgPrice']
                brand_pivot = brand_pivot.sort_values('Count', ascending=False)
                
                # 몰 데이터
                mall_pivot = full_shop_df.pivot_table(index='mallName', values='lprice', aggfunc=['count', 'mean']).reset_index()
                mall_pivot.columns = ['Mall', 'Count', 'AvgPrice']
                mall_top10 = mall_pivot.sort_values('Count', ascending=False).head(10)
                
                # 브랜드-키워드 피봇 (히트맵용)
                brand_kw_pivot = filtered_brand.pivot_table(index='brand', columns='keyword', values='lprice', aggfunc='mean')

            # --- Row 1: Pivot Tables (2개 이상) ---
            st.subheader("📋 피봇 테이블 (Pivot Tables)")
            p_col1, p_col2 = st.columns(2)
            
            with p_col1:
                st.markdown("**1) 요일별 평균 검색량 (Search Volume by Day)**")
                st.dataframe(day_pivot.style.background_gradient(cmap='Blues'), use_container_width=True)
            
            with p_col2:
                st.markdown("**2) 브랜드별 시장 지표 (Brand Market Stats)**")
                if not brand_pivot.empty:
                    st.dataframe(brand_pivot.style.format({'AvgPrice': '{:,.0f}'}).background_gradient(subset=['Count'], cmap='Purples'), use_container_width=True)
                else:
                    st.info("브랜드 데이터가 부족합니다.")

            # --- Row 2: Bar Charts (2개 이상) ---
            st.subheader("📊 막대 그래프 (Bar Charts)")
            b_col1, b_col2 = st.columns(2)
            
            with b_col1:
                st.markdown("**1) 쇼핑몰별 상품 등록 수 (Mall Volume)**")
                if not mall_top10.empty:
                    fig_bar_mall = px.bar(mall_top10, x='Mall', y='Count', color='AvgPrice',
                                          title="상위 10개 몰 상품 수",
                                          color_continuous_scale='Tealgrn')
                    st.plotly_chart(fig_bar_mall, use_container_width=True)
                else:
                    st.info("쇼핑몰 데이터가 없습니다.")
            
            with b_col2:
                st.markdown("**2) Top 15 브랜드 상품 점유율 (Brand Volume)**")
                if not brand_pivot.empty:
                    fig_bar_brand = px.bar(brand_pivot, x='Brand', y='Count', color='AvgPrice',
                                           title="Top 15 브랜드 상품 수",
                                           color_continuous_scale='Bluered')
                    st.plotly_chart(fig_bar_brand, use_container_width=True)
                else:
                    st.info("브랜드 데이터가 없습니다.")

            # --- Row 3: Heatmaps (2개 이상) ---
            st.subheader("🌡️ 히트맵 (Heatmaps)")
            h_col1, h_col2 = st.columns(2)
            
            with h_col1:
                st.markdown("**1) 검색어 트렌드 상관관계 (Trend Correlation)**")
                trend_pivot = df.pivot_table(index='period', columns='keyword', values='ratio')
                if not trend_pivot.empty:
                    corr_mat = trend_pivot.corr()
                    fig_heat_corr = px.imshow(corr_mat, text_auto=True, color_continuous_scale='RdBu_r', 
                                              title="키워드 간 상관계수")
                    st.plotly_chart(fig_heat_corr, use_container_width=True)
            
            with h_col2:
                st.markdown("**2) 브랜드별 가격 포지셔닝 (Price Positioning)**")
                if not brand_pivot.empty and not brand_kw_pivot.empty:
                    fig_heat_brand = px.imshow(brand_kw_pivot, text_auto='.0f', color_continuous_scale='Magma',
                                               title="브랜드 x 키워드 평균 가격")
                    st.plotly_chart(fig_heat_brand, use_container_width=True)
                else:
                    st.info("브랜드 가격 데이터가 부족합니다.")

            # 4. 분석 인사이트 (결론)
            st.divider()
            st.subheader("💡 종합 분석 인사이트")
            st.success(f"""
            - **[피봇 분석] 요일 패턴**: {days[day_pivot.mean(axis=1).argmax()]}에 검색량이 가장 높게 나타나는 경향이 있음. 소비 패턴에 맞춘 마케팅 필요.
            - **[막대 분석] 유통 채널**: 상위 쇼핑몰 및 브랜드의 파이를 확인하여 입점 전략 또는 경쟁사 분석에 활용 가능.
            - **[히트맵 분석] 연관성**: **{' / '.join(keywords[:2])}** 간의 강한 상관관계가 확인될 경우, 번들 판매나 연관 상품 추천 전략이 유효함.
            """)
    else:
        st.warning("데이터가 없습니다.")
