# 프론트엔드 Mock fixture 사용 안내

모든 JSON은 `docs/openapi.yaml`의 응답 스키마를 따르는 합성 데이터입니다. 실제 TMAP·Kakao·서울시 운행정보가 아니며 화면이나 발표에서 실제 정보처럼 표시하면 안 됩니다.

## 화면별 fixture

| 화면/상태 | API | Fixture |
|---|---|---|
| 회원가입 성공 | `POST /auth/signup` | `auth/signup.success.json` |
| 로그인 성공 | `POST /auth/login` | `auth/login.success.json` |
| 내 프로필 | `GET /users/me/profile` | `profile/me.success.json` |
| 서울역 검색 | `GET /places/search?q=서울역` | `places/search.success.json` |
| 접근 가능한 대중교통 | `POST /routes/search`, `TRANSIT` | `routes/transit.accessible.json` |
| 저상버스 상태 미확인 | `POST /routes/search`, `TRANSIT` | `routes/transit.caution.json` |
| 택시 예상 경로 | `POST /routes/search`, `TAXI` | `routes/taxi.success.json` |
| 개인화 도보 경로 | `POST /routes/search`, `WALK` | `routes/walk.success.json` |
| 접근 가능한 경로 없음 | `POST /routes/search`, `TRANSIT` | `routes/no-accessible-route.json` |
| 안내 시작 | `POST /navigation/sessions` | `navigation/start.success.json` |
| 자동 재탐색 제안 | `POST /navigation/sessions/{sessionId}/position` | `navigation/position.reroute-suggested.json` |
| 놓침 후 재탐색 | `POST /navigation/sessions/{sessionId}/reroute` | `navigation/reroute.missed-transit.success.json` |
| 안내 완료·속도 갱신 | `POST /navigation/sessions/{sessionId}/complete` | `navigation/complete.success.json` |
| 외부 API 장애 | 공통 503 | `errors/upstream-unavailable.json` |
| 호출 한도 초과 | 공통 429 | `errors/rate-limited.json` |
| 중복 이메일 | 회원가입 409 | `errors/email-already-exists.json` |
| 잘못된 로그인 | 로그인 401 | `errors/invalid-credentials.json` |
| 프로필 미완성 | 경로 검색 422 | `errors/profile-required.json` |
| 경로 만료 | 상세조회·안내 시작 410 | `errors/route-expired.json` |

## 개발 방식

가장 단순한 방식은 JSON을 React의 `public/mocks`에 복사하고 `fetch`하는 것입니다.

```ts
const response = await fetch('/mocks/routes/transit.accessible.json');
const data = await response.json();
```

실제 API 연결 시 응답을 사용하는 컴포넌트는 바꾸지 않고 데이터 로더만 다음처럼 교체합니다.

```ts
const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/routes/search`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${accessToken}`,
  },
  body: JSON.stringify(request),
});
```

## 요청 조건

- `transit.accessible`: 서울역 → 잠실역, 수동 휠체어·엘리베이터 필수
- `transit.caution`: 강남역 → 서울성모병원, 저상버스 필수이나 차량 상태 미확인
- `taxi.success`, `walk.success`: 서울역 → 서울시청
- `no-accessible-route`: 저상버스 필수 조건을 만족하는 경로가 없음
- `reroute.missed-transit.success`: 시청역에서 지하철을 놓친 뒤 시청역을 새 출발점으로 재탐색

## 주의

- fixture의 `generatedAt`과 `expiresAt`은 시연용 고정값입니다.
- 실제 서버 응답은 생성 후 10분 동안만 유효합니다.
- `UNKNOWN` 상태를 `AVAILABLE` 또는 `false`로 임의 변환하지 않습니다.
- `NO_ACCESSIBLE_ROUTE`는 HTTP 오류가 아니라 정상적인 검색 결과입니다.
