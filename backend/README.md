# FastAPI 백엔드

현재 구현은 해커톤 수직 슬라이스입니다. `Bearer demo-token`과 고정 이동 프로필을 사용하며 회원가입·JWT·SQLite는 후속 범위입니다.

## 로컬 실행

```bash
cd backend
cp .env.example .env
uv sync
uv run uvicorn app.main:app --reload
```

- Health: `GET http://localhost:8000/health`
- Swagger UI: `http://localhost:8000/docs`
- API Base: `http://localhost:8000/api/v1`
- 인증 헤더: `Authorization: Bearer demo-token`

## 공급자 모드

- `ROUTE_PROVIDER=mock`: 외부 키 없이 세 경로 모드와 안내 흐름을 합성 데이터로 실행합니다.
- `ROUTE_PROVIDER=tmap`: TMAP 대중교통·자동차·보행 API와 서울시 데이터를 호출합니다. `TMAP_APP_KEY`, 서울 일반 데이터용 `SEOUL_API_KEY`, 실시간 지하철용 `SEOUL_SUBWAY_API_KEY`가 필요하며 장애 시 Mock으로 자동 전환하지 않습니다.
- 접근성 어댑터의 저상버스·경사·단차는 현재 `SYNTHETIC_FIXTURE`, 지하철 엘리베이터는 TMAP 모드에서 `SEOUL_OPEN_DATA`로 표시됩니다.

## 테스트

```bash
uv run pytest
uv run ruff check .
```

팀원의 개인화 로직은 `PersonalizationEngine` 프로토콜을 구현해 `BaselinePersonalizationEngine` 대신 주입하면 됩니다. API 응답 모델은 바뀌지 않습니다.

## Docker

저장소 루트에서 실행합니다.

```bash
docker build -t tech4good-backend .
docker run --rm -p 8000:8000 -e ROUTE_PROVIDER=mock tech4good-backend
```

Render·Railway에서는 이 Dockerfile을 사용하고 배포 환경변수에 CORS와 공급자 키를 등록합니다. 프로세스 메모리 저장소이므로 재시작 시 경로·안내 세션이 초기화됩니다.
