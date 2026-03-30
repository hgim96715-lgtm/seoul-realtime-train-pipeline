CREATE DATABASE airflow;
CREATE USER airflow WITH PASSWORD 'airflow';
GRANT ALL PRIVILEGES ON DATABASE airflow TO airflow;
ALTER DATABASE airflow OWNER TO airflow;

-- 1. 여객열차 운행계획 (하루 1회 적재)
CREATE TABLE IF NOT EXISTS train_schedule (
    id SERIAL PRIMARY KEY,
    run_ymd VARCHAR(8),
    trn_no VARCHAR(20),
    dptre_stn_cd VARCHAR(10),
    dptre_stn_nm VARCHAR(50),
    arvl_stn_cd VARCHAR(10),
    arvl_stn_nm VARCHAR(50),
    trn_plan_dptre_dt VARCHAR(50),
    trn_plan_arvl_dt VARCHAR(50),
    data_type VARCHAR(20), 
    created_at TIMESTAMP DEFAULT NOW()
);

-- 2. 여객열차 운행 현황 (당일 시뮬레이션 전광판용)
CREATE TABLE IF NOT EXISTS train_realtime (
    id SERIAL PRIMARY KEY,
    trn_no VARCHAR(20),
    -- mrnt_nm VARCHAR(50), -- 노선명 ,추정이 너무 안맞아서 제거 -> train_delay 테이블에만 남김
    dptre_stn_nm VARCHAR(50), 
    arvl_stn_nm VARCHAR(50), 
    plan_dep VARCHAR(10), 
    plan_arr VARCHAR(10), 
    status VARCHAR(100), 
    progress_pct INTEGER, 
    data_type VARCHAR(20), 
    created_at TIMESTAMP DEFAULT NOW()
);

-- 3. 지연 분석 (전날 계획 vs 실제 비교) — Superset 대시보드용
-- ENUM을 삭제하고 VARCHAR로 변경하여 "정시 (0분)" 같은 텍스트가 잘 들어가게 수정!
CREATE TABLE IF NOT EXISTS train_delay (
    id SERIAL PRIMARY KEY,
    run_ymd VARCHAR(8), 
    trn_no VARCHAR(20), 
    mrnt_nm VARCHAR(50), 
    dptre_stn_nm VARCHAR(50),
    arvl_stn_nm VARCHAR(50), 
    plan_dep VARCHAR(10), 
    plan_arr VARCHAR(10), 
    real_dep VARCHAR(10), 
    real_arr VARCHAR(10), 
    dep_delay INTEGER, 
    arr_delay INTEGER, 
    dep_status VARCHAR(50),
    arr_status VARCHAR(50),
    data_type VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);