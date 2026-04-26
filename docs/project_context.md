# 프로젝트 컨텍스트

## 1. 프로젝트 개요

이 저장소는 **교육 서비스 구현 전문 AI Agent 팀**을 구현하고 검증하기 위한 저장소다.

장기적으로는 다양한 교육 서비스 명세서를 입력받아,
구현 가능한 MVP 산출물과 실행 결과를 자동으로 만들어내는 것이 목표다.

현재 검증 사례는 **질문력 향상 퀴즈 서비스 MVP**다.
다만 이 팀의 정체성은 특정 퀴즈 서비스 전용이 아니라,
다른 교육 서비스 구현 명세서도 처리할 수 있는 범용 구현팀으로 유지한다.

---

## 2. 현재 단계

### 현재 단계
**2단계: AI 구현팀 실행 골격 구현**

### 현재 단계의 목표
교육 서비스 구현 명세서를 입력으로 받아,
AI Agent 팀이 순차적으로 산출물을 만들고,
최종적으로는 코드와 실행 결과를 남기는 최소 실행 골격을 구현한다.

### 현재 단계의 성공 기준

- 구현팀의 역할과 순서가 명확하다
- 입력 명세서가 구조적으로 해석된다
- 각 Agent의 입력값과 출력값이 정의되어 있다
- 실제 LLM 호출 구조가 존재한다
- 생성된 산출물이 `outputs/`에 저장된다
- Streamlit MVP가 생성되거나 갱신된다
- 실행·테스트·수정 결과와 QA 요약이 남는다

---

## 3. AI 구현팀 정체성

이 팀은 기획을 다시 하는 팀이 아니라,
**이미 정의된 구현 명세서를 받아 실행 가능한 교육 서비스 산출물로 변환하는 팀**이다.

### 구현팀의 기본 원칙

- 입력은 구현 명세서다
- 사람은 퀴즈 콘텐츠를 직접 작성하지 않는다
- 교육 콘텐츠와 상호작용은 AI Agent가 생성한다
- 생성된 서비스 코드는 실행 가능한 형태여야 한다
- 실행 결과, 오류, 수정 내역, QA 결과가 문서와 파일로 남아야 한다

---

## 4. 현재 검증 사례

현재 저장소의 첫 검증 사례는 다음과 같다.

**질문력 향상 퀴즈 서비스 MVP**

### 대상 사용자
- 주 대상은 중학생
- 질문이 모호하거나 정보가 부족한 학생
- 자신의 질문을 더 구체적으로 바꾸는 연습이 필요한 학생

### 학습 목표
- 질문의 구체성을 높인다
- 질문의 맥락성을 드러낸다
- 질문의 목적성을 분명하게 만든다

### 이번 MVP에서 보여줘야 하는 경험
- 질문력 향상 퀴즈 4개 유형
- 각 유형당 2문제씩, 총 8문제
- 문제, 선택지, 정답, 해설, 학습 포인트 자동 생성
- Streamlit에서 문제 풀이 및 결과 확인

---

## 5. 현재 팀 구조

현재 기준 AI 구현팀은 아래 6개 Agent로 구성한다.

1. **Spec Intake Agent / 구현 명세서 분석 Agent**
2. **Requirement Mapping Agent / 구현 요구사항 정리 Agent**
3. **Content & Interaction Agent / 교육 콘텐츠·상호작용 생성 Agent**
4. **Prototype Builder Agent / MVP 서비스 코드 생성 Agent**
5. **Run Test And Fix Agent / 실행·테스트·수정 Agent**
6. **QA & Alignment Agent / 최종 검수·정합성 확인 Agent**

이 6개 Agent 구조를 현재 저장소의 active 팀 구조로 삼는다.

기존 질문력 기획용 5-Agent skeleton은 legacy reference로 남긴다.

---

## 6. Agent별 역할 정의

### 6-1. Spec Intake Agent / 구현 명세서 분석 Agent
**역할**
구현 명세서를 읽고 구조화된 입력으로 정규화하는 역할

**주요 업무**
- Markdown 명세서 해석
- 서비스 목적 정리
- 대상 사용자와 학습 목표 추출
- 기대 산출물 및 검수 기준 정리

**예상 산출물**
- 명세서 요약
- 정규화된 요구사항
- 전달 기대 산출물

### 6-2. Requirement Mapping Agent / 구현 요구사항 정리 Agent
**역할**
명세서를 실제 구현 가능한 작업 계약으로 바꾸는 역할

**주요 업무**
- 기능 요구사항 정리
- 산출물 형식 정의
- 파일 계획 및 구현 순서 정리
- 콘텐츠 생성 제약 정리

**예상 산출물**
- 구현 요구사항 목록
- 파일 계획
- 콘텐츠 생성 제약
- 앱 제약 및 테스트 기준

### 6-3. Content & Interaction Agent / 교육 콘텐츠·상호작용 생성 Agent
**역할**
교육 서비스에 필요한 콘텐츠와 상호작용 구조를 생성하는 역할

**주요 업무**
- 퀴즈 유형 설계
- 문제/선택지/정답/해설 생성
- 학습 포인트 생성
- 서비스 내 상호작용 흐름 정리

**예상 산출물**
- 퀴즈 유형 목록
- 문제 데이터 JSON
- 정답표
- 해설 및 학습 포인트

### 6-4. Prototype Builder Agent / MVP 서비스 코드 생성 Agent
**역할**
생성된 콘텐츠를 사용해 실제 MVP 코드를 만드는 역할

**주요 업무**
- Streamlit 앱 코드 생성
- 콘텐츠 로딩 구조 정리
- 실행 메모 작성

**예상 산출물**
- `app.py` 코드
- 생성 파일 목록
- 실행 메모

### 6-5. Run Test And Fix Agent / 실행·테스트·수정 Agent
**역할**
생성된 코드를 실행하고 오류를 확인하고, 수정 결과를 남기는 역할

**주요 업무**
- 컴파일 확인
- Streamlit smoke test
- 오류 로그 수집
- 필요한 수정 반영 또는 수정 산출물 생성

**예상 산출물**
- 실행 체크 목록
- 실패 내역
- 적용된 수정
- 남은 리스크

### 6-6. QA & Alignment Agent / 최종 검수·정합성 확인 Agent
**역할**
전체 산출물이 원본 명세서와 맞는지 확인하고 최종 요약을 남기는 역할

**주요 업무**
- 명세 반영 여부 검토
- QA 리포트 작성
- 변경사항 기록
- 최종 요약 작성

**예상 산출물**
- QA 리포트
- 변경 로그
- 최종 요약 포인트

---

## 7. 협업 흐름

기본 협업 흐름은 아래와 같다.

1. **Spec Intake Agent / 구현 명세서 분석 Agent**
2. **Requirement Mapping Agent / 구현 요구사항 정리 Agent**
3. **Content & Interaction Agent / 교육 콘텐츠·상호작용 생성 Agent**
4. **Prototype Builder Agent / MVP 서비스 코드 생성 Agent**
5. **Run Test And Fix Agent / 실행·테스트·수정 Agent**
6. **QA & Alignment Agent / 최종 검수·정합성 확인 Agent**

### 요약 흐름
**명세서 해석 → 구현 요구사항 정리 → 콘텐츠 생성 → MVP 코드 생성 → 실행·수정 → 최종 QA**

---

## 8. 입력값/출력값 설계 원칙

이 프로젝트는 구조화된 순차 파이프라인 방식으로 구현한다.

### 기본 원칙
- 각 Agent는 구조화된 입력을 받는다
- 각 Agent는 자신의 역할에 맞는 구조화된 출력을 만든다
- 출력은 다음 Agent가 그대로 사용할 수 있어야 한다
- 출력은 JSON 직렬화 가능해야 한다
- 최종 산출물은 사람이 읽을 수 있는 문서와 코드에서 다룰 수 있는 데이터 둘 다 제공해야 한다

### 공식 입력 원본
- `inputs/quiz_service_spec.md`

### 현재 필수 outputs
- `spec_intake_output.json`
- `requirement_mapping_output.json`
- `quiz_contents.json`
- `prototype_builder_output.json`
- `run_test_and_fix_output.json`
- `qa_alignment_output.json`
- `execution_log.txt`
- `qa_report.md`
- `change_log.md`
- `final_summary.md`

---

## 9. 구현 원칙

- 실제 실행 경로에서는 환경변수 기반 LLM client를 사용한다
- 자동 테스트에서는 deterministic fake/mock LLM client를 사용한다
- 기존 skeleton은 삭제하지 않고 legacy reference로 남긴다
- 새 active path는 6-Agent 구현팀 구조를 따른다
- Streamlit 앱은 `outputs/quiz_contents.json`을 읽는 MVP 데모여야 한다
- 구현 중 기존 설계와 달라지는 판단은 `docs/implementation_decisions.md` 또는 `outputs/change_log.md`에 기록한다

---

## 10. 현재 제외 범위

현재 단계에서 아래는 필수 범위가 아니다.

- 로그인
- DB
- 장기 학습 기록
- 완성형 UI
- 고도화 개인화
- 다회 자동 복구 오케스트레이션

이번 단계에서는 **명세서를 받아 교육 서비스 MVP를 생성하는 최소 실행 골격**이 핵심이다.
