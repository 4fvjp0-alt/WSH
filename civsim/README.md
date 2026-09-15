# CivSim — 서울 문명 시뮬레이터

계획서: [`../docs/seoul-civilization-simulator-plan.md`](../docs/seoul-civilization-simulator-plan.md)

## 구성

```
civsim/
├─ src/CivSim.Core/        엔진 독립 시뮬레이션 코어 (netstandard2.1, Unity에 그대로 링크)
│  ├─ Time/                JulianDay, KoreaCivilTime, TimeScale, SimClock
│  ├─ Astronomy/           DeltaT, SolarPosition, SunEvents
│  └─ Geo/                 LocalFrame (시청 원점 미터 좌표계)
├─ tests/CivSim.Core.Tests xUnit (서울 일출·일몰 검증값 포함)
├─ tools/                  astro_reference.py (검증된 파이썬 참조 구현), bake_dem.py (DEM → 하이트맵)
└─ unity/Assets/CivSim/    Unity 6 스크립트 (시계, 태양광, 시간 UI, 카메라, 지형 로더)
```

## 코어 빌드·테스트 (Windows, .NET 8 SDK)

```powershell
cd civsim
dotnet test
```

파이썬 참조 구현 검증(numpy·pillow 필요):

```powershell
python tools\test_astro_reference.py
```

## 지형 베이크

```powershell
pip install numpy pillow
# 실제 DEM (Copernicus GLO-30, 서울을 덮는 2개 타일 자동 다운로드)
python tools\bake_dem.py --download data\raw
python tools\bake_dem.py --tiles data\raw --out data\baked\seoul --res 30
# 데이터 없이 엔진 작업을 시작하려면 합성 지형
python tools\bake_dem.py --synthetic --out data\baked\seoul --res 30
```

생성된 `seoul.r16` / `seoul.json`을 Unity 프로젝트의 `Assets/StreamingAssets/terrain/`에 복사한다.

## Unity 프로젝트 설정 (M1)

1. Unity 6 (6000.x) 에서 **URP 3D** 템플릿으로 `civsim/unity` 위치에 프로젝트 생성. 스타일라이즈드 룩에는 URP가 가볍고 충분하다.
2. 코어 소스를 Assets에 링크 (관리자 PowerShell):
   ```powershell
   cmd /c mklink /J civsim\unity\Assets\CivSim\Core civsim\src\CivSim.Core
   ```
   `CivSim.Core.asmdef`가 함께 링크되므로 Unity가 별도 어셈블리로 컴파일한다. `dotnet build` 산출물은 `civsim/build/`로 나가도록 되어 있어 Assets를 오염시키지 않는다.
3. 씬 구성:
   - 빈 오브젝트 `SimClock` + `SimClockBehaviour`
   - Directional Light + `SunLightController`
   - Main Camera + `GodViewCamera`
   - 빈 오브젝트 `Terrain` + `TerrainLoader` (fileStem = `seoul`)
   - 빈 오브젝트 `UI` + `TimeControlPanel` (sun 필드에 Directional Light 연결)
4. 재생: 스페이스 일시정지/재개, `[` `]` 배속 변경, WASD 이동, 휠 줌, 우클릭 드래그 회전.

## 현재 상태

- [x] M0: 시계·달력·한국 시간대 이력·ΔT·태양 위치·일출일몰·로컬 좌표계, 테스트, DEM 베이크 툴
- [x] M1 스크립트 초안: 태양광 연동, 배속 UI, 신 시점 카메라, 지형 로더 (Unity에서 컴파일 확인 필요)
- [ ] M1 완료 기준: Unity에서 실제 태양이 뜨고 지는 10년/초 타임랩스 영상

주의: 이 코어의 C# 코드는 검증된 파이썬 참조(`tools/astro_reference.py`)를 그대로 옮긴 것이며,
작성 환경에 .NET SDK가 없어 `dotnet test`는 아직 실행되지 않았다. 첫 실행에서 컴파일 오류가 나면 사소한 문법 문제일 가능성이 높다.
