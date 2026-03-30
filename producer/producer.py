import os
import json
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from kafka import KafkaProducer
from kafka.errors import KafkaError, KafkaTimeoutError
from typing import Optional
from main import TrainInfo

load_dotenv()

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
POLL_INTERVAL   = 60
MY_STATION      = "서울"
MAX_TARGETS     = 5


# utils


def estimate_status(plan_dep: str, plan_arr: str) -> dict:
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    
    try:
        dep_dt = datetime.strptime(f"{today} {plan_dep}", "%Y-%m-%d %H:%M")
        arr_dt = datetime.strptime(f"{today} {plan_arr}", "%Y-%m-%d %H:%M")
        

        if arr_dt < dep_dt:
            arr_dt += timedelta(days=1)
            
    except ValueError as e:
        print(f"  🚨 [디버깅] 시간 변환 실패: {e}")
        return {"status": "시각 정보 없음", "progress_pct": 0}
    
    diff_dep = (dep_dt - now).total_seconds() / 60
    diff_arr = (arr_dt - now).total_seconds() / 60
    
    total_mins = (arr_dt - dep_dt).total_seconds() / 60
    elapsed_mins = (now - dep_dt).total_seconds() / 60
    progress = max(0, min(100, round((elapsed_mins / total_mins) * 100))) if total_mins > 0 else 0
    
    def format_time_diff(mins:int)->str:
        if mins >=60:        
            hours = mins // 60
            minutes = mins % 60
            return f"{hours}시간" if minutes == 0 else f"{hours}시간 {minutes}분"
        else:
            return f"{mins}분"
    
    # 상태 텍스트 분기
    if diff_dep > 15:
        mins = int(diff_dep)
        time_str = format_time_diff(mins)
        status = f"출발 {time_str}전 (대기중)"
        
    elif 0< diff_dep<=1:
        status="곧 출발 (탑승 마감)"
    
    elif 1 < diff_dep <= 15:
        status = f"곧 출발 ({int(diff_dep)}분 후)- 탑승 중"
 
    elif diff_dep <= 0 and diff_arr > 0:
        
        rem_str = format_time_diff(int(diff_arr))
        
        
        status = f"운행 중 ({progress}%진행 , 약 {rem_str} 후 도착예정)"
        
    else:
        status = f"도착 완료 ({int(abs(diff_arr))}분 전)"
        
    return {"status": status, "progress_pct": progress}

# def calc_delay_min(plan_hm:str,actual_hm:str)->int|None:
def calc_delay_min(plan_hm: str, actual_hm: str) -> Optional[int]:
    if "--:--" in (plan_hm,actual_hm) or "" in (plan_hm,actual_hm):
        return None
    
    try:
        p_h,p_m=map(int,plan_hm.split(':'))
        a_h,a_m=map(int,actual_hm.split(':'))
        
        diff=(a_h*60+a_m)-(p_h*60+p_m)
        
        if diff< -720:diff +=1440
        elif diff>730: diff -=1440
        return diff
    except ValueError:
        return None
    
# def delay_label(mins:int|None)->str:
def delay_label(mins: Optional[int]) -> str:
    if mins is None: return "확인불가"
    if mins<=0 : return f"정시({mins}분)"
    if mins<=5: return f"소폭지연(+{mins}분)"
    if mins<=30: return f"지연(+{mins}분)"
    return f"대폭지연 (+{mins}분)"

# 새로 추가한 노선 판별함수 (실시간API가 없으므로 노선미상이 될수 밖에 없는것을 추정해서 추가)>너무 안 맞아서 2024-06-17 삭제

# STATION_ROUTE = {
#     "부산": "경부선",
#     "동대구": "경부선",
#     "대구": "경부선",
#     "대전": "경부선",
#     "울산": "경부선",
#     "신경주": "경부선",
#     "구포": "경부선",
#     "밀양": "경부선",

#     "광주송정": "호남선",
#     "목포": "호남선",
#     "익산": "호남선",
#     "정읍": "호남선",
#     "나주": "호남선",
# }

# def get_route_name(arvl_stn_nm: str) -> str:
#     return STATION_ROUTE.get(arvl_stn_nm, "일반노선")


    


class TrainProducer:
    def __init__(self):
        self.producer=KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v,ensure_ascii=False).encode('utf-8'),
            acks="all",
            retries=3,
        )
        
        self.train_info=TrainInfo()
        self.daily_schedule=[]
        self.current_date=""
        self.delay_done_today=False
        self.delay_count=0
        
        # 다시 producer 실행할때 데이터가 뻥튀기 되는 문제 방지를 위해
        # 상대경로 -> 절대경로로 변경
        self.state_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 
            "producer_state.json"
        )
        self.state=self._load_state()
        
    def _load_state(self)->dict:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file,"r",encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print("상태 파일 로드 실패, 초기 상태로 시작")
                return {}
        else:
            return {}
    
    def _save_state(self):
        with open(self.state_file,"w",encoding="utf-8") as f:
            json.dump(self.state,f,ensure_ascii=False,indent=2)
        
        
    def _send(self,topic:str,message:dict):
        try:
            future=self.producer.send(topic,value=message)
            future.get(timeout=10)
        except KafkaTimeoutError:
            print(f"[{topic}]전송 Timeout!!")
        except KafkaError as e:
            print(f"[{topic}]발행 실패 :{e}")
            
    
    def run_schedule(self,run_ymd:str):
        print(f"\n[운행계획] {run_ymd}발행시작(하루1회)")
        
        items=self.train_info.get_train_schedule(run_ymd)
        
        if not items:
            print("[운행계획] 데이터가 없습니다")
            return
        
        self.daily_schedule=items
        
        if self.state.get("last_schedule_date")==run_ymd:
            print(f"[운행계획] 이미 {run_ymd} 데이터 발행한 기록이 있습니다. 중복발행 방지 위해 스킵합니다.")
            return
        
        for item in items:
            item["created_at"]=datetime.now().isoformat()
            item["data_type"]="schedule"
            self._send("train-schedule",item)
            
        self.producer.flush()
        self.daily_schedule=items
        print(f"[운행계획]-> {len(self.daily_schedule)}건 발행완료!")
        
        self.state["last_schedule_date"]=run_ymd
        self._save_state()
        
    # 실시간이 없어서 추정  
    def run_estimated(self,target:dict):
        now=datetime.now()
        trn_no=target.get("trn_no","?")
        dep_name=target.get("dptre_stn_nm","?")
        arr_name=target.get("arvl_stn_nm","?")
        arvl_stn_nm = target.get("arvl_stn_nm", "")
        # mrnt_nm = target.get("mrnt_nm") or get_route_name(arvl_stn_nm)
        plan_dep=TrainInfo._format_dt(target.get("trn_plan_dptre_dt",""),"--:--")
        plan_arr=TrainInfo._format_dt(target.get("trn_plan_arvl_dt",""),"--:--")
        
        estimated=estimate_status(plan_dep,plan_arr)
        
        self._send("train-realtime",{
            "trn_no":trn_no,
            # "mrnt_nm":mrnt_nm,
            "dptre_stn_nm":dep_name,
            "arvl_stn_nm":arr_name,
            "plan_dep":plan_dep,
            "plan_arr":plan_arr,
            "status":estimated["status"],
            "progress_pct":estimated["progress_pct"],
            "data_type":"estimated",
            "created_at":now.isoformat()
        })
        
        print(
            f"[KTX {trn_no}호 열차] {plan_dep}출발 |"
            f"{dep_name:<4} ➡️ {arr_name:<4} | {estimated['status']}"
        )
        
    def run_delay_analysis(self,target_date:Optional[str]=None):
        
        if target_date is None:
            target_date=(datetime.now()-timedelta(days=1)).strftime("%Y%m%d")
        print(f"\n[지연분석] {target_date}분석 시작!")
        
        # 이미 지연분석 완료한 날짜인지 체크
        if self.state.get("last_delay_analysis_date")==target_date:
            print(f"[지연분석] 이미 {target_date} 분석한 기록이 있습니다. 중복분석 방지 위해 스킵합니다.")
            self.delay_done_today=True
            return
        
        plan_items=self.train_info.get_train_schedule(target_date)
        
            
        
        if not plan_items:
            print(f"[지연분석] 운행계획 데이터 없음")
            return
        print(f"👉 [디버그] 전체 운행계획 수: {len(plan_items)}개")
        plan_map={
            item.get("trn_no"):item for item in plan_items if item.get("dptre_stn_nm")==MY_STATION
        }
        print(f"👉 [디버그] '{MY_STATION}' 출발 대상 기차 수: {len(plan_map)}개")
        count=0
        
        for trn_no,plan in plan_map.items():
            time.sleep(0.3)
            
            actual_items=self.train_info.get_train_realtime(target_date,trn_no)
            if not actual_items:
                continue
            
            actual_dep_item=next((i for i in actual_items if i.get("trn_dptre_dt")),None)
            # 종착역은 맨뒤에 데이터가 있기때문 reversed
            actual_arr_item=next((i for i in reversed(actual_items) if i.get("trn_arvl_dt")),None)
            
            plan_dep=TrainInfo._format_dt(plan.get("trn_plan_dptre_dt",""),"--:--")
            plan_arr=TrainInfo._format_dt(plan.get("trn_plan_arvl_dt",""),"--:--")
            

            actual_dep = TrainInfo._format_dt(actual_dep_item.get("trn_dptre_dt", "") if actual_dep_item else "", "--:--")
            actual_arr = TrainInfo._format_dt(actual_arr_item.get("trn_arvl_dt", "") if actual_arr_item else "", "--:--")
            
            dep_delay=calc_delay_min(plan_dep,actual_dep)
            arr_delay=calc_delay_min(plan_arr,actual_arr)
            
            self._send("train-delay",{
                "run_ymd":target_date,
                "trn_no":trn_no,
                "mrnt_nm":actual_items[0].get("mrnt_nm", ""),
                "dptre_stn_nm":plan.get("dptre_stn_nm",""),
                "arvl_stn_nm":plan.get("arvl_stn_nm",""),
                "plan_dep":plan_dep,
                "plan_arr":plan_arr,
                "real_dep":actual_dep,
                "real_arr":actual_arr,
                "dep_delay":dep_delay,
                "arr_delay":arr_delay,
                "dep_status":delay_label(dep_delay),
                "arr_status":delay_label(arr_delay),
                "data_type":"delay_analysis",
                "created_at":datetime.now().isoformat()
            })
            
            print(
                f"{trn_no}호 |"
                f"[출발] : 계획 {plan_dep} -> 실제 {actual_dep} [{delay_label(dep_delay)}] |"
                f"[도착] : 계획 {plan_arr} -> 실제 {actual_arr} [{delay_label(arr_delay)}]"
            )
            count+=1
            self.delay_count+=1
            
        self.producer.flush()
        print(f"[지연분석]{count}건 발행완료")
        self.delay_done_today=True
        
        self.state["last_delay_analysis_date"]=target_date
        self._save_state()
        
    
    def run(self):
        print(f"Train Producer 시작 (폴링간격 :{POLL_INTERVAL}초)\n")
        
        self.current_date=datetime.now().strftime("%Y%m%d")
        self.run_schedule(self.current_date)
        
            
        while True:
            now=datetime.now()
            today_str=now.strftime("%Y%m%d")
            current_hm=now.strftime("%H:%M")
            
            if today_str !=self.current_date:
                print(f"\n 하루가 지났군요! 날짜 변경하겠습니다. [{self.current_date} -> {today_str}]")
                self.current_date=today_str
                self.delay_done_today=False
                self.run_schedule(self.current_date)
                

                
            print(f"\n{'='*58}")
            print(f"{now.strftime('%Y-%m-%d %H:%M:%S')} 서울역 기준 출발 열차 현황")
            print(f"\n{'='*58}")
            
            past_15_mins=(now-timedelta(minutes=15)).strftime("%H:%M")
            targets=[]
            
            for item in self.daily_schedule:
                dep_time=TrainInfo._format_dt(item.get("trn_plan_dptre_dt",""),"99:99")
                
                if item.get("dptre_stn_nm")==MY_STATION and dep_time>=past_15_mins:
                    targets.append(item)
                    
                if len(targets)>=MAX_TARGETS:
                    break
                
            if targets:
                for target in targets:
                    self.run_estimated(target)
                    time.sleep(0.5)
                    
            else:
                print(f"{current_hm} 현재 - 금일 서울역 출발 열차 운행 종료되었습니다. 편안한 밤 보내세요 🌝")
                
            print(f"\n {POLL_INTERVAL}초 후 갱신..\n")
            time.sleep(POLL_INTERVAL)
            
            
if __name__=="__main__":
    tp=None
    try:
        tp=TrainProducer()
        tp.run()
    except ValueError as e:
        print(f"설정오류:{e}")
    except KeyboardInterrupt:
        print("\n 사용자 요청으로 Producer 종료")
    finally:
        if tp:
            tp.producer.flush()
            tp.producer.close()