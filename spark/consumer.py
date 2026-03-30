import os
from pyspark.sql import SparkSession,DataFrame
from pyspark.sql.functions import col, from_json, current_timestamp
from pyspark.sql.types import (
    StructType, StructField,
    StringType, IntegerType
)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

KAFKA_BOOTSTRAP=os.getenv("KAFKA_BOOTSTRAP_SERVERS","kafka:9092")
PG_USER=os.getenv("POSTGRES_USER","train_user")
PG_PASSWORD=os.getenv("POSTGRES_PASSWORD","train_password")
PG_DB=os.getenv("POSTGRES_DB","train_db")
PG_HOST="postgres"
PG_PORT="5432"

JDBC_URL=f"jdbc:postgresql://{PG_HOST}:{PG_PORT}/{PG_DB}"
JDBC_PROPS={
    "user":PG_USER,
    "password":PG_PASSWORD,
    "driver":"org.postgresql.Driver"
}


SCHEMA_SCHEDULE = StructType([
    StructField("run_ymd",           StringType()),
    StructField("trn_no",            StringType()),
    StructField("dptre_stn_cd",      StringType()),
    StructField("dptre_stn_nm",      StringType()),
    StructField("arvl_stn_cd",       StringType()),
    StructField("arvl_stn_nm",       StringType()),
    StructField("trn_plan_dptre_dt", StringType()),
    StructField("trn_plan_arvl_dt",  StringType()),
    StructField("data_type",         StringType()),
    StructField("created_at",        StringType()),
])

SCHEMA_REALTIME = StructType([
    StructField("trn_no",        StringType()),
    # StructField("mrnt_nm",       StringType()),
    StructField("dptre_stn_nm",  StringType()),
    StructField("arvl_stn_nm",   StringType()),
    StructField("plan_dep",      StringType()),
    StructField("plan_arr",      StringType()),
    StructField("status",        StringType()),
    StructField("progress_pct",  IntegerType()),
    StructField("data_type",     StringType()),
    StructField("created_at",    StringType()),
])

SCHEMA_DELAY = StructType([
    StructField("run_ymd",       StringType()),
    StructField("trn_no",        StringType()),
    StructField("mrnt_nm",       StringType()),
    StructField("dptre_stn_nm",  StringType()),
    StructField("arvl_stn_nm",   StringType()),
    StructField("plan_dep",      StringType()),
    StructField("plan_arr",      StringType()),
    StructField("real_dep",      StringType()),
    StructField("real_arr",      StringType()),
    StructField("dep_delay",     IntegerType()),
    StructField("arr_delay",     IntegerType()),
    StructField("dep_status",    StringType()),
    StructField("arr_status",    StringType()),
    StructField("data_type",     StringType()),
    StructField("created_at",    StringType()),
])

# ----

class TrainConsumer:
    #[[Spark_Core_Objects]]
    def __init__(self):
        self.spark=(
            SparkSession.builder
            .appName("TrainConsumer")
            .config("spark.sql.shuffle.partitions","2")
            .getOrCreate()
        )
        self.spark.sparkContext.setLogLevel("WARN")
        
    def _read_stream(self,topic:str)->"DataFrame":
        return(
            self.spark.readStream
            .format("kafka")
            .option("kafka.bootstrap.servers",KAFKA_BOOTSTRAP)
            .option("subscribe",topic)
            .option("startingOffsets","latest")
            .option("failOnDataLoss","false")
            .load()   
        )
    # [[Spark_Streaming_Kafka_Integration]]
    def _write_jdbc(self,table:str):
        def write_batch(batch_df,batch_id):
            if batch_df.isEmpty():
                return
            (
                batch_df
                .write
                .jdbc(
                    url=JDBC_URL,
                    table=table,
                    mode="append",
                    properties=JDBC_PROPS,
                )
            )
            print(f"[{table}] batch_id={batch_id}| {batch_df.count()}건 DB저장 완료!")
            
        return write_batch
            
    def run_schedule(self):
        raw=self._read_stream("train-schedule")
        
        parsed=(
            raw
            .select(from_json(col("value").cast("string"),SCHEMA_SCHEDULE).alias("data"))
            .select("data.*")
            .withColumn("created_at",current_timestamp()) # 시각이 달라지니깐 덮어씌우고 수정 
        )
        
        final=parsed.select(
            "run_ymd", "trn_no",
            "dptre_stn_cd","dptre_stn_nm",
            "arvl_stn_cd","arvl_stn_nm",
            "trn_plan_dptre_dt","trn_plan_arvl_dt",
            "data_type","created_at"
        )
        
        return(
            final.writeStream
            .foreachBatch(self._write_jdbc("train_schedule"))  # 클로저로 테이블 지정
            .option("checkpointLocation","/tmp/checkpoint/schedule")
            .trigger(processingTime="10 seconds")
            .start()
        )
        
    def run_realtime(self):
        raw=self._read_stream("train-realtime")
        
        parsed=(
            raw
            .select(from_json(col("value").cast("string"),SCHEMA_REALTIME).alias("data"))
            .select("data.*")
            .withColumn("created_at",current_timestamp())
        )
        
        final=parsed.select(
            "trn_no",
            "dptre_stn_nm", "arvl_stn_nm",
            "plan_dep", "plan_arr",
            "status", "progress_pct",
            "data_type", "created_at",
        )
        
        return(
            final.writeStream
            .foreachBatch(self._write_jdbc("train_realtime"))
            .option("checkpointLocation","/tmp/checkpoint/realtime")
            .trigger(processingTime="10 seconds")
            .start()
        )
    
    def run_delay(self):
        raw=self._read_stream("train-delay")
        
        parsed=(
            raw
            .select(from_json(col("value").cast("string"),SCHEMA_DELAY).alias("data"))
            .select("data.*")
            .withColumn("created_at",current_timestamp())
        )
        
        final=parsed.select(
            "run_ymd", "trn_no", "mrnt_nm",
            "dptre_stn_nm", "arvl_stn_nm",
            "plan_dep", "plan_arr",
            "real_dep", "real_arr",
            "dep_delay", "arr_delay",
            "dep_status", "arr_status",
            "data_type", "created_at",
        )
        
        return(
            final.writeStream
            .foreachBatch(self._write_jdbc("train_delay"))
            .option("checkpointLocation","/tmp/checkpoint/delay")
            .trigger(processingTime="30 seconds") # 배치-> 여유있게 30초
            .start()
        )
        
    def run(self):
        print("Spark Consumer 파이프라인 준비 완료!!!!")
        
        q_schedule=self.run_schedule()
        q_realtime=self.run_realtime()
        q_delay=self.run_delay()
        
        print("[train-schedule] 모니터링 시작")
        print("[train-realtime] 모니터링 시작")
        print("[train-delay] 모니터링 시작")
        print("\n Spark Web UI 모니터링 → http://localhost:4040\n")
        
        self.spark.streams.awaitAnyTermination()
        
if __name__=="__main__":
    tc=TrainConsumer()
    try:
        tc.run()
    except KeyboardInterrupt:
        print("\n 사용자의 요청으로 Consumer 종료")
    finally:
        tc.spark.stop()