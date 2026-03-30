import requests
import os
import urllib.parse
from dotenv import load_dotenv
from datetime import datetime,timedelta
from requests.exceptions import RequestException,JSONDecodeError

load_dotenv()

class TrainInfo:
    def __init__(self):
        train_api_key=os.getenv("TRAIN_API_KEY")
        if not train_api_key:
            raise ValueError("환경변수 TRAIN_API_KEY 가 설정되지 않았습니다 확인해주세요")
        
        self.api_key=urllib.parse.unquote(train_api_key)
        self.base_url="https://apis.data.go.kr/B551457/run/v2"
        
        self.session=requests.Session()
        
    def _request_api(self,endpoint:str,query_string:str)->dict:
        url = f"{self.base_url}/{endpoint}?serviceKey={self.api_key}&returnType=JSON&{query_string}"
        if endpoint == "travelerTrainRunInfo2":
            # API 키가 터미널에 다 보이면 좀 그러니까, 가려서 출력합니다.
            safe_url = url.replace(self.api_key, "내_API_키_비밀") 
            # print(f"\n[🔍디버깅] 요청 URL: {safe_url}")
        
        try:
            res=self.session.get(url,timeout=10)
            res.raise_for_status()
            
            # if endpoint == "travelerTrainRunInfo2":
            #     print(f"[🔍디버깅] 원본 응답: {res.text[:300]}")
            return res.json()
        
        except JSONDecodeError:
            print(f"[오류] JSON 형식이 아닙니다. API 키 오류이거나 트래픽 초과일 수 있습니다.\n응답 내용: {res.text[:100]}")
            return {}
        
        except RequestException as e:
            print(f"[네트워크 오류] API 요청 중 문제가 발생했습니다: {e}")
            return {}
    
    # item만 리스트로 받는이유는 사이트 example에  response->body->items->item순이고 item이 리스트로 되어있기 때문 
    def _extract_items(self,data:dict)->list:
        try:
            # 데이터를 꺼낼 때는 서버가 정해둔 이름("response")으로 찾아야 합니다.
            items=data.get("response",{}).get("body",{}).get("items",{}).get("item",[])
            return items if isinstance(items,list) else [items]
        
        except AttributeError:
            return []
    
    def get_train_schedule(self,run_ymd:str)->list:
        all_items=[]
        page_no=1
        while True:
            print(f" 운행계획 {page_no}페이지 데이터를 가져오는 중입니다...")
            query_str = f"pageNo={page_no}&numOfRows=100&cond[run_ymd::EQ]={run_ymd}"
            data = self._request_api("travelerTrainRunPlan2",query_str)
            
            items=self._extract_items(data)
            if not items:
                break
            all_items.extend(items)
            
            body=data.get("response",{}).get("body",{})
            total_count=body.get("totalCount",0)
            print(f"🔄 {page_no}페이지 수집 중... (모은 데이터: {len(all_items)}개 / 서버가 말하는 전체 데이터: {total_count}개)")
            
            if len(all_items)>=total_count:
                break
            if page_no >= 10:
                print("🚨 [경고] 데이터가 비정상적으로 많습니다. 무한 루프를 강제 종료합니다.")
                break
            
            page_no+=1
        return all_items
    
    def get_train_realtime(self,run_ymd:str,trn_no:str)->list:
        all_items=[]
        page_no=1
        while True:
            print(f"⚡️ 정보 {page_no}페이지 데이터를 가져오는 중입니다...")
            query_str = f"pageNo={page_no}&numOfRows=100&cond[run_ymd::EQ]={run_ymd}&cond[trn_no::EQ]={trn_no}"
            data = self._request_api("travelerTrainRunInfo2",query_str)
            items=self._extract_items(data)
            if not items:
                msg = data.get("response", {}).get("header", {}).get("resultMsg", "알수없음")
                print(f"   [서버 응답 메시지] {msg}")
                break
            
            all_items.extend(items)
            body=data.get("response",{}).get("body",{})
            total_count=int(body.get("totalCount",0))
            
            if len(all_items)>=total_count or page_no>=10:
                break
            
            page_no+=1
            
        return all_items
    
    # 문자열을 HH:MM 형식으로 변환
    @staticmethod
    def _format_dt(date_str:str,default_text:str)->str:
        if not date_str or not isinstance(date_str,str) or len(date_str)<16:
            return default_text
        try:
            dt_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S.%f")
            return dt_obj.strftime("%H:%M")
        except ValueError:
            return date_str[11:16]
        
if __name__=="__main__":
    today=datetime.now().strftime("%Y%m%d")
    print(f"[조회날짜] {today}")
    
    try:
        train_info=TrainInfo()
        
        schedule_items=train_info.get_train_schedule(today)
        
        print("\n===실시간 기차 전광판===")
        
        if schedule_items:
            current_time_str = datetime.now().strftime("%H:%M")
            target_train=None
            
            for item in schedule_items:
                raw_arr=item.get("trn_plan_arvl_dt","")
                # 클래스 내부 함수 호출 시 train_info._format_dt 혹은 TrainInfo._format_dt 사용
                arr_time_str = TrainInfo._format_dt(raw_arr, "00:00")
                dep_stn = item.get("dptre_stn_nm", "")
                if current_time_str <= arr_time_str and dep_stn=="서울":
                    target_train=item
                    break
                
                
            if target_train:
                target_trn_no=target_train.get('trn_no','00000')
                route = f"{target_train.get('dptre_stn_nm', '모름')}➡️{target_train.get('arvl_stn_nm', '모름')}"
                # dptre_name = target_train.get('dptre_stn_nm', '모름')
                # dptre_code = target_train.get('dptre_stn_cd', '코드모름')
                # arvl_name = target_train.get('arvl_stn_nm', '모름')
                # arvl_code=target_train.get('arvl_stn_cd','코드모름')
                
                
                print(f" 현재 시각({current_time_str}) 기준, 운행 중인 [{route}] {target_trn_no}호 열차를 추적합니다.\n")
                # print(f"{dptre_name}역의 진짜 코드는 '{dptre_code}' 입니다!\n")
                yesterday=(datetime.now()-timedelta(days=1)).strftime("%Y%m%d")
                realtime_items=train_info.get_train_realtime(yesterday, target_trn_no)
                
                if realtime_items:
                    for item in realtime_items[:5]: 
                        real_dep=TrainInfo._format_dt(item.get("trn_dptre_dt"),"출발 전")
                        real_arr=TrainInfo._format_dt(item.get("trn_arvl_dt"),"운행중")
                        
                        print(f"[{item.get('trn_no', '000')}호 열차] "
                              f"현재: {item.get('stn_nm', '미확인역')} ({item.get('stop_se_nm', '운행중')}) | "
                              f"출발: {real_dep} | 도착: {real_arr}")
                
                else:
                    print("해당 열차의 실시간 위치 정보가 업데이트 되지 않았습니다.")
            else:
                print(f"현재시각({current_time_str}), 금일 여객열차 운행이 모두 종료되었습니다. 모두 안녕히 주무세요😴")
    
    except ValueError as e:
        print(e)
    