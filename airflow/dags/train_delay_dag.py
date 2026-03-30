import pendulum
from airflow.decorators import dag,task
import sys
import logging

default_args={
        'owner':'airflow',
        'retries':2,
        'retry_delay':pendulum.duration(minutes=10),
        'depend_on_past':False,
        'email':['hgim96715@gmail.com'],
        'email_on_failure':True,
        'email_on_retry':False
}

@dag(
    dag_id='train_delay_dag',
    default_args=default_args,
    description='매일 새벽 6:00 -> 전날 서울역에서 출발하는 열차 지연 정보 수집',
    schedule='0 6 * * *',
    start_date=pendulum.datetime(2026,3,14, tz='Asia/Seoul'),
    catchup=False,
    tags=['train','delay']
)

def train_delay_pipeline():
    
    @task
    # **context 는 Airflow 가 태스크 실행 시 자동으로 주입하는 딕셔너리
    # logical_date 는 Airflow 가 태스크 실행 시 자동으로 주입하는 실행 날짜 정보로, pendulum 객체 형태로 제공
    def run_delay_analysis_task(logical_date=None,**context):
        sys.path.insert(0,'/opt/airflow/producer')
        from producer import TrainProducer
        
        
        kst_date=logical_date.in_timezone('Asia/Seoul')
        # Airflow에서 Actions 실행시 오늘 날짜로 실행되는 것을 전날로 바꾸기 위한 로직 (필요할 때만 사용)
        now_kst=pendulum.now('Asia/Seoul')
        if kst_date==now_kst.date():
            kst_date=kst_date.subtract(days=1)
        target_date=kst_date.strftime('%Y%m%d')
        print(f"[지연 정보 DAG] 수집 시작  🚆- {target_date} 기준 열차 지연 정보")
        
        tp=TrainProducer()
        # 0건일때 성공으로 Airflow 상태 되어서 0건일때 로그 남기기
        if tp.delay_count==0:
            logging.warning(f"[지연분석]{target_date} 발행건수 0건이니 확인해주세요!")
        
        tp.run_delay_analysis(target_date)
        tp.producer.flush()
        tp.producer.close()
        print(f"[지연 정보 DAG] 수집 완료 ✅ - {target_date} 기준 열차 지연 정보")
        
    run_delay_analysis_task()

train_delay_pipeline()
        
        
        
        
        