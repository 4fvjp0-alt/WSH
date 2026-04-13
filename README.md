# WSH — Windows 디스크 용량 분석 스크립트

C 드라이브(또는 다른 드라이브)의 용량을 빠르게 분석하고, 정리 가능한 항목을 식별해주는 PowerShell 스크립트입니다.

## 기능

| 분석 항목 | 내용 |
|-----------|------|
| 전체 현황 | 드라이브 사용률 (바 그래프 포함) |
| 최상위 폴더 | 용량 상위 폴더 목록 |
| 의심 구역 | Temp, Windows.old, SoftwareDistribution 등 |
| 시스템 특수 파일 | hiberfil.sys, pagefile.sys |
| Docker / WSL | `.vhdx` 가상 디스크 탐색 |
| 개발 캐시 | npm, pip, conda, Gradle, Maven 등 |
| 브라우저 캐시 | Chrome, Edge, Firefox, Brave |
| 단일 대용량 파일 | 500MB 이상 파일 Top 20 |
| 정리 권고 | 안전하게 정리 가능한 명령어 안내 |

## 요구 사항

- Windows 10 / 11
- PowerShell 5.1 이상 (기본 내장)
- 관리자 권한 권장 (일부 경로 접근을 위해)

## 사용법

### 기본 실행

```powershell
# PowerShell을 관리자 권한으로 열고:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\Analyze-DiskSpace.ps1
```

### 옵션

```powershell
# 다른 드라이브 분석
.\Analyze-DiskSpace.ps1 -Drive D

# 상위 30개 폴더 표시
.\Analyze-DiskSpace.ps1 -TopN 30

# 결과를 CSV로 저장
.\Analyze-DiskSpace.ps1 -ExportPath "$env:USERPROFILE\Desktop\DiskReport.csv"

# 모든 옵션 조합
.\Analyze-DiskSpace.ps1 -Drive C -TopN 30 -ExportPath "C:\report.csv"
```

## 출력 예시

```
======================================================================
  C 드라이브 디스크 용량 분석
======================================================================
  실행 시각: 2025-01-15 14:30:00
  분석 대상: C:\

── 전체 현황 ──────────────────────────────────────────────────────
  전체 용량  : 476.84 GB
  사용 중    : 380.12 GB  (79.7%)
  남은 공간  : 96.72 GB

  [##################################----------------] 79.7%

── 의심 구역 점검 ─────────────────────────────────────────────────
  임시 파일 (사용자)                                    3.42 GB  ← C:\Users\...\Temp
  Windows.old (구버전 윈도우)                          18.50 GB  ← C:\Windows.old
  WU 다운로드 캐시                                      2.10 GB  ← C:\Windows\SoftwareDistribution\Download
```

## 정리 방법

### 빠른 정리 (GUI)
1. **설정 → 시스템 → 저장소 → 임시 파일** 에서 체크 후 삭제

### 명령줄 정리 (관리자 권한 필요)

```powershell
# 디스크 정리 (Windows.old, 업데이트 캐시 포함)
cleanmgr /sageset:1   # 항목 선택
cleanmgr /sagerun:1   # 실행

# 임시 폴더
Remove-Item "$env:LOCALAPPDATA\Temp\*" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$env:SystemRoot\Temp\*"   -Recurse -Force -ErrorAction SilentlyContinue

# npm 캐시
npm cache clean --force

# pip 캐시
pip cache purge

# conda 캐시
conda clean --all

# 최대절전모드 비활성화 (hiberfil.sys 제거)
powercfg /h off

# Docker 최적화
wsl --shutdown
# 이후 Docker Desktop에서 Troubleshoot → Clean / Purge data
```

### 주의 사항

| 경로 | 주의 이유 |
|------|-----------|
| `C:\Windows\WinSxS` | 직접 삭제 금지. `dism /online /cleanup-image /startcomponentcleanup` 사용 |
| `C:\pagefile.sys` | 가상 메모리 — 삭제/이동 시 성능 저하 또는 시스템 불안정 |
| `AppData\Roaming` | 앱 설정 포함 — 폴더별로 확인 후 삭제 |

## 라이선스

MIT
