"""
주말 및 공휴일 체크 유틸리티
"""
import json
import os
from datetime import datetime, date
from typing import Set, Optional
import holidays


class HolidayChecker:
    """주말 및 공휴일 체크 클래스"""
    
    def __init__(self, holidays_file: str = "utils/manual_holidays.json"):
        """
        초기화
        
        Args:
            holidays_file: 수동 추가 공휴일 저장 파일 경로
        """
        # 상대 경로를 절대 경로로 변환 (프로젝트 루트 기준)
        if not os.path.isabs(holidays_file):
            # 현재 파일의 디렉토리 기준으로 경로 계산
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)  # utils의 상위 디렉토리
            self.holidays_file = os.path.join(project_root, holidays_file)
        else:
            self.holidays_file = holidays_file
        
        self.manual_holidays: Set[date] = set()
        
        # 한국 공휴일 자동 감지 (SouthKorea 또는 KR 사용)
        try:
            # holidays 0.34+ 버전에서는 SouthKorea() 사용
            self.kr_holidays = holidays.SouthKorea()
        except (AttributeError, TypeError):
            # 일부 버전에서는 KR() 사용
            try:
                self.kr_holidays = holidays.KR()
            except (AttributeError, TypeError):
                # 최신 버전에서는 years 파라미터 필요할 수 있음
                self.kr_holidays = holidays.SouthKorea(years=range(2020, 2030))
        
        # 수동 추가 공휴일 로드
        self._load_manual_holidays()
    
    def _load_manual_holidays(self):
        """수동 추가 공휴일 파일에서 로드"""
        if os.path.exists(self.holidays_file):
            try:
                with open(self.holidays_file, 'r', encoding='utf-8') as f:
                    date_strings = json.load(f)
                    self.manual_holidays = {date.fromisoformat(d) for d in date_strings}
                print(f"✅ 수동 공휴일 {len(self.manual_holidays)}개 로드 완료")
            except Exception as e:
                print(f"⚠️ 수동 공휴일 로드 실패: {e}")
                self.manual_holidays = set()
        else:
            # 파일이 없으면 빈 세트로 시작
            self.manual_holidays = set()
            self._save_manual_holidays()  # 빈 파일 생성
    
    def _save_manual_holidays(self):
        """수동 추가 공휴일을 파일에 저장"""
        try:
            # 디렉토리가 없으면 생성
            dir_path = os.path.dirname(self.holidays_file)
            if dir_path:  # 빈 문자열이 아닌 경우에만 디렉토리 생성
                os.makedirs(dir_path, exist_ok=True)
            
            date_strings = [d.isoformat() for d in sorted(self.manual_holidays)]
            with open(self.holidays_file, 'w', encoding='utf-8') as f:
                json.dump(date_strings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ 수동 공휴일 저장 실패: {e}")
    
    def is_weekend(self, check_date: Optional[date] = None) -> bool:
        """
        주말인지 확인
        
        Args:
            check_date: 확인할 날짜 (None이면 오늘)
            
        Returns:
            주말이면 True
        """
        if check_date is None:
            check_date = date.today()
        
        # 토요일(5) 또는 일요일(6)
        return check_date.weekday() >= 5
    
    def is_holiday(self, check_date: Optional[date] = None) -> bool:
        """
        공휴일인지 확인 (자동 감지 + 수동 추가)
        
        Args:
            check_date: 확인할 날짜 (None이면 오늘)
            
        Returns:
            공휴일이면 True
        """
        if check_date is None:
            check_date = date.today()
        
        # 한국 공휴일 자동 감지
        if check_date in self.kr_holidays:
            return True
        
        # 수동 추가 공휴일 체크
        if check_date in self.manual_holidays:
            return True
        
        return False
    
    def is_weekend_or_holiday(self, check_date: Optional[date] = None) -> bool:
        """
        주말 또는 공휴일인지 확인
        
        Args:
            check_date: 확인할 날짜 (None이면 오늘)
            
        Returns:
            주말 또는 공휴일이면 True
        """
        if check_date is None:
            check_date = date.today()
        
        return self.is_weekend(check_date) or self.is_holiday(check_date)
    
    def add_manual_holiday(self, holiday_date: date) -> bool:
        """
        수동 공휴일 추가
        
        Args:
            holiday_date: 추가할 날짜
            
        Returns:
            추가 성공 여부 (이미 있으면 False)
        """
        if holiday_date in self.manual_holidays:
            return False
        
        self.manual_holidays.add(holiday_date)
        self._save_manual_holidays()
        return True
    
    def remove_manual_holiday(self, holiday_date: date) -> bool:
        """
        수동 공휴일 제거
        
        Args:
            holiday_date: 제거할 날짜
            
        Returns:
            제거 성공 여부 (없으면 False)
        """
        if holiday_date not in self.manual_holidays:
            return False
        
        self.manual_holidays.remove(holiday_date)
        self._save_manual_holidays()
        return True
    
    def get_manual_holidays(self) -> Set[date]:
        """
        수동 추가 공휴일 목록 반환
        
        Returns:
            수동 공휴일 세트
        """
        return self.manual_holidays.copy()
    
    def get_all_holidays(self, year: Optional[int] = None) -> Set[date]:
        """
        모든 공휴일 목록 반환 (자동 + 수동)
        
        Args:
            year: 연도 (None이면 올해)
            
        Returns:
            공휴일 세트
        """
        if year is None:
            year = date.today().year
        
        all_holidays = set()
        
        # 한국 공휴일 (해당 연도)
        for holiday_date in self.kr_holidays:
            if holiday_date.year == year:
                all_holidays.add(holiday_date)
        
        # 수동 추가 공휴일 (해당 연도)
        for holiday_date in self.manual_holidays:
            if holiday_date.year == year:
                all_holidays.add(holiday_date)
        
        return all_holidays

