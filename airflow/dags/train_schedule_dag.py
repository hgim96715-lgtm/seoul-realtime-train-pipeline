import pendulum
from airflow.decorators import dag,task
import sys



default_args={
        'owner':'airflow',
        'retries':1,
        'retry_delay':pendulum.duration(minutes=5),
        'depend_on_past':False,
        'email':['hgim96715@gmail.com'],
        'email_on_failure':True,
        'email_on_retry':False
}

@dag(
    dag_id='train_schedule_dag',
    default_args=default_args,
    description='매일 00:05에 => 당일 서울역에서 출발하는 열차 운행계획 수집',
    schedule='5 0 * * *',
    start_date=pendulum.datetime(2026,3,15, tz='Asia/Seoul'),
    catchup=False,
    tags=['train','schedule']
)

def train_schedule_pipeline():
    
    @task
    def collect_schedule(**context):
        sys.path.insert(0,'/opt/airflow/producer')
        from producer import TrainProducer
        
        run_ymd=pendulum.now('Asia/Seoul').strftime('%Y%m%d')
        print(f"[운행계획 DAG] 수집 시작  🚆 - {run_ymd}")
        
        tp=TrainProducer()
        tp.run_schedule(run_ymd)
        tp.producer.flush()
        tp.producer.close()
        print(f"[운행계획 DAG] 수집 완료  ✅ - {run_ymd}")
        
    collect_schedule()

# train_schedule_dag=train_schedule_pipeline()
train_schedule_pipeline()