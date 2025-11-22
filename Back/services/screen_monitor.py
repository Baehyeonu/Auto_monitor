"""
화면 모니터링 서비스
Zep 화면을 캡처하여 학생 이름과 얼굴을 감지합니다.
"""
import cv2
import numpy as np
import mss
import pytesseract
import asyncio
from datetime import datetime
from typing import List, Optional, Set
from difflib import get_close_matches

try:
    from Levenshtein import distance as levenshtein_distance
    LEVENSHTEIN_AVAILABLE = True
except ImportError:
    LEVENSHTEIN_AVAILABLE = False
    print("⚠️ python-Levenshtein이 설치되지 않았습니다. 이름 매칭 정확도가 낮아질 수 있습니다.")

from config import config
from database import DBService


class ScreenMonitor:
    """화면 모니터링 클래스"""
    
    def __init__(self, discord_bot):
        """
        화면 모니터링 초기화
        
        Args:
            discord_bot: DiscordBot 인스턴스
        """
        self.discord_bot = discord_bot
        self.db_service = DBService()
        self.is_running = False
        
        # 얼굴 감지 모델 초기화
        try:
            self.face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            if self.face_cascade.empty():
                raise Exception("얼굴 감지 모델을 로드할 수 없습니다.")
        except Exception as e:
            print(f"❌ 얼굴 감지 모델 초기화 실패: {e}")
            self.face_cascade = None
        
        # 설정
        self.check_interval = config.SCREEN_CHECK_INTERVAL
        self.threshold = config.FACE_DETECTION_THRESHOLD
        self.start_time = None  # 서비스 시작 시간
        self.warmup_minutes = 1  # 워밍업 시간 (분)
        
        print("✅ 화면 모니터링 서비스 초기화 완료")
    
    async def start(self):
        """모니터링 시작"""
        if not config.SCREEN_MONITOR_ENABLED:
            print("ℹ️ 화면 모니터링이 비활성화되어 있습니다. (.env에서 SCREEN_MONITOR_ENABLED=true로 설정)")
            return
        
        if not self.face_cascade:
            print("❌ 얼굴 감지 모델이 초기화되지 않아 화면 모니터링을 시작할 수 없습니다.")
            return
        
        self.is_running = True
        self.start_time = datetime.now()  # 시작 시간 기록
        
        print(f"👁️ 화면 모니터링 시작 (체크 간격: {self.check_interval}초 / {self.check_interval//60}분)")
        print(f"   • 감지 차이 임계값: {self.threshold}명")
        print(f"   • 워밍업 시간: {self.warmup_minutes}분 (시작 후 알림 안 보냄)")
        
        while self.is_running:
            try:
                await self._check_screen()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                print(f"❌ 화면 모니터링 중 오류: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def stop(self):
        """모니터링 중지"""
        self.is_running = False
        print("🛑 화면 모니터링 중지")
    
    async def _check_screen(self):
        """화면 체크 실행"""
        # 워밍업 시간 체크 (프로그램 시작 직후 알림 방지)
        if self.start_time:
            elapsed = (datetime.now() - self.start_time).total_seconds() / 60
            if elapsed < self.warmup_minutes:
                # 조용히 스킵
                return
        
        current_time = datetime.now().strftime("%H:%M")
        print(f"\n🔍 [{current_time}] 화면 체크 시작...")
        
        # 1. DB에서 카메라 ON 학생 조회
        camera_on_students = await self.db_service.get_camera_on_students()
        
        if not camera_on_students:
            print("   ℹ️ 카메라 ON 상태인 학생이 없습니다.")
            return
        
        expected_count = len(camera_on_students)
        student_names = [s.zep_name for s in camera_on_students]
        print(f"   📊 카메라 ON 학생: {expected_count}명")
        print(f"   👥 {', '.join(student_names)}")
        
        # 2. 화면 캡처 및 분석
        try:
            frame = self.capture_screen()
            if frame is None:
                print("   ❌ 화면 캡처 실패")
                return
            
            # 3. 화면에서 이름 + 얼굴 감지
            detected_names = self.detect_students_on_screen(frame, student_names)
            detected_count = len(detected_names)
            
            print(f"   🎯 화면에서 감지: {detected_count}명")
            if detected_names:
                print(f"   ✅ 감지된 학생: {', '.join(detected_names)}")
            
            # 4. 차이 확인
            missing_count = expected_count - detected_count
            
            if missing_count >= self.threshold:
                # 누가 없는지 파악
                missing_students = [name for name in student_names if name not in detected_names]
                
                print(f"   ⚠️ {missing_count}명 부재 감지!")
                print(f"   ❌ 미감지 학생: {', '.join(missing_students)}")
                
                # 강사에게 알림
                await self._notify_instructor_about_missing(
                    camera_on_students,
                    detected_names,
                    missing_students
                )
            else:
                print(f"   ✅ 정상 (차이: {missing_count}명, 임계값: {self.threshold}명)")
        
        except Exception as e:
            print(f"   ❌ 화면 분석 실패: {e}")
            import traceback
            traceback.print_exc()
    
    def capture_screen(self) -> Optional[np.ndarray]:
        """
        화면 캡처
        
        Returns:
            캡처된 화면 이미지 (numpy array) 또는 None
        """
        try:
            with mss.mss() as sct:
                # 메인 모니터 캡처
                monitor = sct.monitors[1]
                screenshot = sct.grab(monitor)
                
                # numpy array로 변환
                img = np.array(screenshot)
                
                # BGRA → BGR 변환 (OpenCV 형식)
                frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                
                return frame
        except Exception as e:
            print(f"❌ 화면 캡처 오류: {e}")
            return None
    
    def detect_students_on_screen(self, frame: np.ndarray, student_names: List[str]) -> Set[str]:
        """
        화면에서 학생 이름 + 얼굴 감지
        
        Args:
            frame: 캡처된 화면
            student_names: 감지할 학생 이름 목록
            
        Returns:
            감지된 학생 이름 집합
        """
        detected = set()
        
        # 방법 1: OCR로 이름 찾기 (시도)
        detected_by_ocr = self._detect_by_ocr(frame, student_names)
        detected.update(detected_by_ocr)
        
        # 방법 2: 얼굴 개수로 추정 (OCR 실패 시)
        if len(detected) == 0:
            face_count = self._count_faces(frame)
            print(f"   ℹ️ OCR 실패, 얼굴 개수만 카운트: {face_count}개")
            # 얼굴 개수만큼 학생이 있다고 가정 (누군지는 모름)
            # 이 경우 차이만 계산 가능
            return set(student_names[:face_count])  # 임시로 앞에서부터 채움
        
        return detected
    
    def _detect_by_ocr(self, frame: np.ndarray, student_names: List[str]) -> Set[str]:
        """
        OCR로 화면에서 학생 이름 찾기
        
        Args:
            frame: 캡처된 화면
            student_names: 학생 이름 목록
            
        Returns:
            감지된 학생 이름 집합
        """
        detected = set()
        
        try:
            # 이미지 전처리 (여러 방법)
            processed_images = self._preprocess_for_ocr(frame)
            
            all_texts = []
            
            # 여러 전처리 방법으로 OCR 시도
            for i, processed in enumerate(processed_images):
                try:
                    # Tesseract OCR 실행
                    custom_config = r'--oem 3 --psm 11'
                    text = pytesseract.image_to_string(
                        processed,
                        lang='kor+eng',
                        config=custom_config
                    )
                    all_texts.append(text)
                except Exception as e:
                    print(f"   ⚠️ OCR 시도 {i+1} 실패: {e}")
            
            # OCR 결과에서 학생 이름 찾기
            for text in all_texts:
                for student_name in student_names:
                    # 학생 이름이 OCR 결과에 있는지 확인
                    if self._match_name_in_text(student_name, text, student_names):
                        detected.add(student_name)
        
        except Exception as e:
            print(f"   ⚠️ OCR 감지 오류: {e}")
        
        return detected
    
    def _preprocess_for_ocr(self, image: np.ndarray) -> List[np.ndarray]:
        """
        OCR을 위한 이미지 전처리 (여러 방법)
        
        Args:
            image: 원본 이미지
            
        Returns:
            전처리된 이미지 리스트
        """
        results = []
        
        # 그레이스케일 변환
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # 방법 1: 해상도 2배 업스케일 + Otsu 이진화
        resized = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        denoised = cv2.fastNlMeansDenoising(resized, None, 10, 7, 21)
        _, binary1 = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        results.append(binary1)
        
        # 방법 2: CLAHE + 이진화
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        _, binary2 = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        results.append(binary2)
        
        # 방법 3: 어댑티브 이진화
        adaptive = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        results.append(adaptive)
        
        return results
    
    def _match_name_in_text(self, student_name: str, ocr_text: str, all_student_names: List[str]) -> bool:
        """
        OCR 텍스트에서 학생 이름 매칭
        
        Args:
            student_name: 찾을 학생 이름
            ocr_text: OCR 결과 텍스트
            all_student_names: 전체 학생 명단
            
        Returns:
            매칭 여부
        """
        # 공백/특수문자 제거
        clean_text = ''.join(c for c in ocr_text if c.isalnum() or ord('가') <= ord(c) <= ord('힣'))
        
        # 완전 일치
        if student_name in clean_text:
            return True
        
        # 유사도 매칭 (get_close_matches)
        words = ocr_text.split()
        matches = get_close_matches(student_name, words, n=1, cutoff=0.8)
        if matches:
            return True
        
        # Levenshtein 거리 (1~2글자 차이 허용)
        if LEVENSHTEIN_AVAILABLE:
            for word in words:
                clean_word = ''.join(c for c in word if c.isalnum() or ord('가') <= ord(c) <= ord('힣'))
                if clean_word and levenshtein_distance(student_name, clean_word) <= 1:
                    return True
        
        return False
    
    def _count_faces(self, frame: np.ndarray) -> int:
        """
        화면에서 얼굴 개수 세기
        
        Args:
            frame: 캡처된 화면
            
        Returns:
            감지된 얼굴 개수
        """
        if not self.face_cascade:
            return 0
        
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # 얼굴 감지
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30)
            )
            
            return len(faces)
        except Exception as e:
            print(f"   ⚠️ 얼굴 감지 오류: {e}")
            return 0
    
    async def _notify_instructor_about_missing(
        self,
        camera_on_students: List,
        detected_names: Set[str],
        missing_students: List[str]
    ):
        """
        강사에게 부재 학생 알림
        
        Args:
            camera_on_students: 카메라 ON 학생 리스트
            detected_names: 화면에서 감지된 이름
            missing_students: 미감지 학생 이름
        """
        if not config.INSTRUCTOR_CHANNEL_ID:
            print("   ⚠️ 강사 채널 ID가 설정되지 않았습니다.")
            return
        
        try:
            import discord
            
            channel = self.discord_bot.get_channel(int(config.INSTRUCTOR_CHANNEL_ID))
            
            if not channel:
                print(f"   ❌ 강사 채널을 찾을 수 없습니다: {config.INSTRUCTOR_CHANNEL_ID}")
                return
            
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
            
            embed = discord.Embed(
                title="🚨 화면 모니터링 알림",
                description="학생들이 화면에서 감지되지 않습니다.",
                color=discord.Color.red()
            )
            
            embed.add_field(
                name="📊 카메라 ON",
                value=f"{len(camera_on_students)}명",
                inline=True
            )
            
            embed.add_field(
                name="🎯 화면 감지",
                value=f"{len(detected_names)}명",
                inline=True
            )
            
            embed.add_field(
                name="❌ 미감지",
                value=f"{len(missing_students)}명",
                inline=True
            )
            
            # 미감지 학생 목록
            if missing_students:
                missing_list = "\n".join([f"• {name}" for name in missing_students])
                embed.add_field(
                    name="🔴 미감지 학생 명단",
                    value=missing_list,
                    inline=False
                )
            
            embed.set_footer(text=f"체크 시간: {current_time}")
            
            await channel.send(embed=embed)
            
            print(f"   📢 강사 채널에 알림 전송 완료")
            
        except Exception as e:
            print(f"   ❌ 강사 채널 알림 실패: {e}")
            import traceback
            traceback.print_exc()

