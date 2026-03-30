

# 🚆 Seoul Station Train Dashboard

> **공공데이터 API → Kafka → Spark → PostgreSQL → Superset** 서울역 열차 운행 데이터를 수집하고 실시간 운행 현황 및 지연 분석을 시각화하는 End-to-End 데이터 파이프라인

---

## 💡 기획 배경

기차역 전광판에 실시간으로 열차 정보(지연 시간, 도착 예정 시간, 탑승 플랫폼 등)가 뜨는 것을 보며 단순한 호기심이 생겼습니다.

> **"저 데이터는 어디서 오고, 어떻게 실시간으로 업데이트될까?"**

공부하다 보니 이것이 결국 **데이터 파이프라인**의 영역이라는 것을 알게 되었고, 코레일톡과 전광판을 직접 확인해 가며 나만의 **실시간 기차 전광판 및 지연 분석 대시보드**를 직접 구축해 보았습니다.

공공데이터 API로 서울역 열차 운행 데이터를 수집하여 **실시간 운행 현황을 추적하고 전날의 노선별 지연 분석을 시각화하는 전체 데이터 파이프라인**입니다.

---

## 🏗 아키텍처

```
공공데이터 API
    ↓
  Producer (Python)
    ↓ (60초 주기)
  Kafka
    ├── train-schedule   매일 00:05  당일 운행계획 (Airflow 배치)
    ├── train-realtime   60초마다    실시간 운행 상태 추정
    └── train-delay      매일 02:00  전날 지연 분석 (Airflow 배치)
    ↓
  Spark Streaming Consumer
    ↓
  PostgreSQL
    ↓
  Superset 대시보드
```

---

## 🛠 기술 스택

|역할|기술|
|---|---|
|메시지 큐|Apache Kafka 3.7.0|
|스트리밍 처리|Apache Spark 3.5.0 + PySpark|
|배치 파이프라인|Apache Airflow 2.9.1|
|데이터베이스|PostgreSQL 16|
|시각화|Apache Superset 3.1.0|
|컨테이너|Docker Compose|

---

## 🔌 포트 구성

|서비스|포트|설명|
|---|---|---|
|PostgreSQL|`5433`|DB 접속 (DataGrip 등)|
|Kafka|`9092`|외부 접속용|
|Spark Web UI|`8080`|작업 모니터링|
|Airflow UI|`8082`|DAG 관리|
|Superset|`8088`|대시보드|
|Spark Jobs UI|`4040`|Job 모니터링|

---
## 📈 대시보드 시각화 결과 

![[train-final.jpg]]


### 주요 인사이트

- **오늘 열차 운행 횟수:** 897회 / **전날 기준 지연 횟수:** 87회
- **가장 많이 도착하는 곳:** 부산행 열차가 압도적 다수 (Pie 차트에서 가장 큰 비중)
- **지연 최다 노선:** 경전선 도착 평균 지연 최대 (~6분)

**시간대별 운행 패턴:**

- 출퇴근 시간대 피크: **6시 65회 / 18시 56회** 운행 횟수 최고
- **15시 57회** 급증: 타지역 출장자 오후 복귀 및 숙박객 체크아웃·이동 시점 집중 수요로 추정
- **오전 11시 27회** 최저: 이동 수요 공백기 및 열차 일상 정비·승무원 교대 시간대, 점심시간으로 추정

> 💡 **11시 운행 감소 원인 추가 조사:** 철도 운영 기준상 **주간 안전 점검**을 하는 황금 시간대가 바로 오전 10시~12시 사이라고 한다. 단순히 수요가 적은 것이 아니라 안전 점검을 위해 운행 편수 자체를 줄이는 구조적 이유가 있었다.

---

## 🚀 빠른 시작

> **시스템 권장 사양:** RAM 8GB 이상

### 1. 환경 변수 설정

```bash
cp .env.example .env
```

```env
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_DB=
TRAIN_API_KEY=
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
SUPERSET_SECRET_KEY=
AIRFLOW_SECRET_KEY=
AIRFLOW_SMTP_USER=
AIRFLOW_SMTP_PASSWORD=
```

### 2. 컨테이너 실행

```bash
docker compose up -d
docker compose ps
```

### 3. Spark JAR 파일 복사

```bash
docker cp spark_drivers/. train-spark-master:/opt/spark/jars/
```

### 4. Kafka 토픽 생성

```bash
for topic in train-schedule train-realtime train-delay; do
  docker exec -it train-kafka /opt/kafka/bin/kafka-topics.sh \
    --bootstrap-server localhost:9092 --create \
    --topic $topic --partitions 1 --replication-factor 1
done
```

### 5. Producer 실행

```bash
cd producer && python3 producer.py
```

### 6. Spark Consumer 실행

```bash
docker exec -it train-spark-master \
  /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --jars /opt/spark/jars/spark-sql-kafka-0-10_2.12-3.5.0.jar,\
/opt/spark/jars/spark-token-provider-kafka-0-10_2.12-3.5.0.jar,\
/opt/spark/jars/kafka-clients-3.4.1.jar,\
/opt/spark/jars/commons-pool2-2.11.1.jar,\
/opt/spark/jars/postgresql-42.7.1.jar \
  /opt/spark/apps/consumer.py
```

### 7. Airflow DAG 활성화 및 대시보드 확인

- **Airflow:** `http://localhost:8082` (admin / admin)
    - `train_schedule_dag` 토글 ON
    - `train_delay_dag` 토글 ON
- **Superset:** `http://localhost:8088` (admin / admin)

---

## ⚠️ 재시작 체크리스트

```
□ docker compose up -d
□ docker cp spark_drivers/. train-spark-master:/opt/spark/jars/   ← 매번 필수!!!!!
□ Kafka 토픽 확인 (없으면 위 명령어로 재생성)
□ python3 producer/producer.py 재실행
□ spark-submit 재실행
□ Airflow UI → DAG 토글 ON 확인
□ producer_state.json 삭제 여부 확인
  (처음부터 다시 수집하려면 삭제)
```

---

## 📂 폴더 구조

```
train-project/
├── airflow/
│   └── dags/
│       ├── __pycache__/
│       │   ├── train_delay_dag.cpython-312.pyc (2.0 KB)
│       │   └── train_schedule_dag.cpython-312.pyc (1.9 KB)
│       ├── train_delay_dag.py (1.9 KB)  # 매일 06:00 지연 분석
│       └── train_schedule_dag.py (1.2 KB)  # 매일 00:05 운행계획 수집
├── docs/
│   ├── final_dashboard.jpg (337.5 KB)
│   └── README.md (8.5 KB)
├── postgres/
│   └── init.sql (1.8 KB)   # 초기 DB·테이블 생성
├── producer/
│   ├── __pycache__/
│   │   ├── main.cpython-312.pyc (8.7 KB)
│   │   └── producer.cpython-312.pyc (17.1 KB)
│   ├── main.py (7.4 KB)
│   ├── producer_state.json (0.1 KB) # 중복 발행 방지 상태 파일
│   ├── producer.py (13.0 KB)  # 60초 realtime 폴링
│   └── requirements.txt (0.1 KB)
├── spark/
│   ├── consumer.py (7.0 KB) # Kafka → PostgreSQL
│   └── requirements.txt (0.0 KB)
├── spark_drivers/  # JDBC·Kafka 연동 JAR 파일
│   ├── commons-pool2-2.11.1.jar (142.1 KB)
│   ├── kafka-clients-3.4.1.jar (4932.1 KB)
│   ├── postgresql-42.7.1.jar (1058.8 KB)
│   ├── spark-sql-kafka-0-10_2.12-3.5.0.jar (422.2 KB)
│   └── spark-token-provider-kafka-0-10_2.12-3.5.0.jar (55.5 KB)
└── docker-compose.yml (5.5 KB)
```

---

## 📊 핵심 설계 전략

### [Strategy 1] API 제약 파악 → 우회 로직 직접 설계

```
문제: 코레일 정책상 당일 실시간 위치 API 제공 안 됨
해결: 운행계획(예정 시각) + 현재 시각을 SQL 에서 실시간 비교하여
     운행 상태 / 진행률 / 카운트다운을 동적으로 추정
```

### [Strategy 2] Kafka 멀티 토픽 설계 — 역할 분리

```
train-schedule   당일 운행계획 (Airflow 배치)
train-realtime   실시간 운행 상태 추정 (Producer 60초)
train-delay      전날 실제 vs 계획 지연 분석 (Airflow 배치)
```

### [Strategy 3] Airflow DAG 분리 — Backfill 가능한 구조

```
기존: Producer while 루프 안에서 시간 체크로 배치 처리
개선: DAG 분리 → 날짜 파라미터 주입 → 과거 날짜 재실행 가능
     멱등성 보장
```

---

## 🔥 트러블슈팅 & 문제 해결

단순히 정상 경로(Happy Path)로 파이프라인을 구축하는 것에 그치지 않고, 실제 데이터를 다루며 발생한 문제들을 주도적으로 해결했습니다.

### [Issue 1] 당일 실시간 API 제약 — 상태 추정 로직 설계

- **Situation:** 코레일 정책상 당일 실시간 열차 위치 API가 제공되지 않아 실시간 운행 현황 구현이 불가능했습니다.
- **Task:** API 없이도 현재 열차 상태를 동적으로 표현할 방법이 필요했습니다.
- **Action:** 운행계획(예정 시각)과 `NOW() AT TIME ZONE 'Asia/Seoul'` 을 SQL에서 직접 비교하는 로직을 설계했습니다. 출발/도착 시각 비교로 운행 상태를, 경과 시간 비율로 진행률을, 남은 시간으로 카운트다운을 동적으로 계산했습니다.
- **Result:** API 없이도 실시간 전광판 UI를 구현했으며, 실제 코레일톡 앱과 직접 대조하여 데이터 정합성을 검증했습니다.

### [Issue 2] 자정 통과 열차 시간 계산 오류

- **Situation:** 자정을 넘겨 운행하는 열차의 진행률이 비정상적으로 계산됐습니다.
- **Task:** TIME 타입 간 연산은 날짜 개념이 없어 자정 통과 시 음수가 발생하는 문제 해결이 필요했습니다.
- **Action:** **Action:** 계산 결과가 -43200초(-12시간) 미만이면 +86400초(+24시간 = 하루)를 보정하는  로직을 추가했습니다. 하루는 60초 × 60분 × 24시간 = 86400초이므로, 자정을 넘긴 음수 시간에 86400을 더해 올바른 경과 시간으로 되돌립니다.
- **Result:** 야간 운행 열차의 진행률과 카운트다운이 정상적으로 표시됐습니다.

### [Issue 3] UTC / KST 시차 문제

- **Situation:** Docker 컨테이너 기본 시각이 UTC로 설정되어 한국 시간 기준 운행 현황이 9시간 어긋났습니다.
- **Task:** 모든 시간 연산을 KST 기준으로 통일해야 했습니다.
- **Action:** SQL 전체에 `NOW() AT TIME ZONE 'Asia/Seoul'` 을 명시하고, Spark consumer의 `created_at` 도 `from_utc_timestamp(current_timestamp(), "Asia/Seoul")` 로 변경했습니다.
- **Result:** 전광판의 시각과 실제 한국 시간이 일치했습니다.

### [Issue 4] 지연 분석 DAG 스케줄 시각 조정 — 반복 검증

- **Situation:** `train_delay_dag` 를 매일 새벽 2시(`0 2 * * *`)로 설정했지만, 다음 날 확인해 보니 전날 지연 데이터가 수집되지 않아 있었습니다. API 응답이 아직 준비되지 않은 상태에서 DAG 가 실행된 것으로 추정했습니다.
- **Task:** 전날 운행 종료 후 API 에 실제 지연 데이터가 모두 반영되는 시점을 파악해야 했습니다.
- **Action:** 새벽 2시 → 4시로 변경 후 하루를 기다렸지만 여전히 데이터가 불완전한 경우가 발생했습니다. 한 번의 시도로 결론 내리지 않고, 여러 날에 걸쳐 직접 수집 결과를 확인하며 반복 검증했습니다. 최종적으로 새벽 6시(`0 6 * * *`)로 설정했을 때 안정적으로 전날 데이터가 완전히 수집되는 것을 확인했습니다.
- **Result:** 2시 → 4시 → 6시, 총 3번의 조정과 며칠에 걸친 반복 검증 끝에 안정적인 스케줄을 확정했습니다. 단순히 설정하고 넘어가는 것이 아니라 실제 데이터로 끝까지 확인하는 습관이 중요하다는 것을 배웠습니다.



---

## 🚧 한계점

```
KTX-산천 / KTX-청룡 데이터 누락
  → API 에서 일부 열차 제외 → 지연 통계에 영향 가능

경유지 데이터 부재
  → 중간 경유역 데이터 없음 → 최종 도착역만 표기 가능

로컬 환경 한계
  → 맥북 로컬 실행 → 컴퓨터 종료 시 파이프라인 중단
```

---

## 💬 프로젝트 회고

아키텍처를 구상하고 시작했음에도 _"이 구성이 맞나?"_ 하는 고민이 많았습니다. 특히 Superset 대시보드에서 원하는 전광판 UI를 위해 SQL 쿼리를 계속 수정하는 데 예상보다 훨씬 많은 시간이 들었습니다.

하지만 SQL 로직을 이리저리 수정해 보며 원하는 결과물(실시간 카운트다운, 진행률 바)이 화면에 짠! 하고 나타나고, 이를 실제 코레일톡 앱과 띄워 놓고 대조해 보며 데이터가 실시간으로 정확하게 맞아떨어지는 것을 직접 확인했을 때의 희열은 말로 다 할 수 없었습니다.

이전 프로젝트에서 많이 헤맸던 부분들을 떠올려 이번에는 원인을 더 빠르게 파악하고 트러블슈팅할 수 있었습니다. **"데이터가 흐르는 길을 직접 뚫어본"** 정말 재미있고 의미 있는 경험이었습니다.

---

## 🔑 API 키 발급

- **공공데이터 API:** [data.go.kr](https://www.data.go.kr/) → 한국철도공사_열차운행정보 조회서비스
