# picqa 사용 가이드 (한국어)

## 무엇을 하는 도구인가

picqa는 실리콘 포토닉스 웨이퍼 테스트 결과를 자동으로 분석하는 파이썬
라이브러리이자 명령줄 도구입니다. HY202103 데이터셋(LION1 마스크셋,
1310 nm O-band 디바이스)을 기준으로 만들어졌습니다.

XML 측정 파일을 입력으로 받아서 다음을 자동으로 만들어 줍니다.

- 디바이스별 특성 파라미터 표 (CSV)
- 웨이퍼 맵 / 스펙트럼 / IV 그래프 (PNG)
- spec 기반 양·불 판정과 yield 통계
- 위 모든 것을 묶은 Markdown 리포트

GUI는 사용하지 않으며, 모든 동작은 터미널 명령으로 실행합니다.

## 빠른 시작

```bash
# 1) 설치 (의존성 패키지가 이미 있는 환경에서)
git clone <repo-url>
cd picqa
pip install --no-build-isolation -e .

# 2) 데이터 인벤토리 확인
picqa inventory ./HY202103

# 3) MZ 변조기 특성 추출
picqa extract mzm ./HY202103 -o ./out/features.csv

# 4) 웨이퍼 맵 그리기
picqa plot wafermap ./out/features.csv \
    --metric I_at_-1V_pA -o ./out/wafermap.png

# 5) 6패널 종합 그래프
picqa plot summary ./out/features.csv -o ./out/summary.png

# 6) Spec 기반 yield 계산
picqa yield ./out/features.csv \
    --spec configs/mzm_spec.yaml --family mzm \
    -o ./out/yield.csv

# 7) 한 번에 모든 결과 + Markdown 리포트
picqa report ./HY202103 -o ./out/report \
    --spec configs/mzm_spec.yaml --family mzm
```

## 라이브러리 사용

```python
from picqa.io.xml_parser import parse_directory
from picqa.extract.mzm import extract_mzm_features
from picqa.analysis.outlier import flag_failed_contacts
from picqa.analysis.yield_calc import load_spec, evaluate_yield, yield_summary

# 1) XML 파싱
measurements = parse_directory("./HY202103", test_site="DCM_LMZO")

# 2) 특성 추출
features = extract_mzm_features(measurements)
features = flag_failed_contacts(features)

# 3) Spec 적용
spec = load_spec("configs/mzm_spec.yaml", "mzm")
evaluated = evaluate_yield(features, spec)

# 4) 웨이퍼별 yield 요약
print(yield_summary(evaluated, group_by=["Wafer"]))
```

## 추출되는 MZM 특성 6가지

| 컬럼 | 의미 | 단위 |
|---|---|---|
| `FSR_nm` | 자유 스펙트럼 영역 (notch 간격의 중앙값) | nm |
| `Notch_at_0V_nm` | 1310 nm에 가장 가까운 0V 시점 notch 파장 | nm |
| `dLambda_dV_pm_per_V` | bias에 따른 notch 이동 (변조 효율) | pm/V |
| `PeakIL_near_1310_dB` | 1310 nm ±4 nm 범위 IL 95퍼센타일 (그레이팅 손실) | dB |
| `I_at_-1V_pA`, `I_at_-2V_pA` | 역방향 누설전류 | pA |
| `FailedContact` | 컨택 실패 자동 검출 결과 | bool |

## Spec 파일 작성법

YAML로 디바이스 종류별 합격 기준을 적습니다.

```yaml
mzm:
  I_at_-1V_pA:
    max_abs: 1.0e6        # |I| ≤ 1 µA
  dLambda_dV_pm_per_V:
    min_abs: 100          # |기울기| ≥ 100 pm/V
  PeakIL_near_1310_dB:
    min: -12              # IL ≥ -12 dB
  FSR_nm:
    min: 9.3
    max: 10.3
```

지원 키: `min`, `max`, `min_abs`, `max_abs`. 한 메트릭에 여러 키를 동시
사용할 수 있습니다.

## 새 디바이스 추가하기

`extract/` 폴더에 파일 하나를 만들면 끝납니다. 다음 패턴을 따르세요.

```python
# src/picqa/extract/ring.py
import pandas as pd
from picqa.io.schemas import Measurement

def extract_ring_features(measurements: list[Measurement]) -> pd.DataFrame:
    rows = []
    for m in measurements:
        if m.test_site != "DCM_RING":   # 본인 디바이스의 테스트 태그
            continue
        # m.iv, m.sweeps 에서 원하는 값 추출
        rows.append({...})
    return pd.DataFrame(rows)
```

그리고 `cli.py`의 `cmd_extract` 함수의 `test_site_map`과 `device` 선택지에
`ring`을 추가하면 CLI에서도 사용할 수 있습니다.

## 폴더 구조

```
src/picqa/
    io/         XML 파싱과 데이터 클래스
    extract/    디바이스별 특성 추출
    analysis/   통계, yield, 이상치 검출
    viz/        그래프 (matplotlib, 파일 저장 전용)
    report/     Markdown 리포트 생성기
    cli.py      `picqa` 명령 진입점
tests/          pytest 단위·통합 테스트
examples/       사용 예제 스크립트
configs/        YAML spec 파일
docs/           아키텍처와 데이터 형식 문서
```

자세한 설계 결정은 `docs/architecture.md`를, 측정 데이터 형식은
`docs/data_format.md`를, 특성 추출 알고리즘은 `docs/extraction_methods.md`를
참고하세요.

## 자주 마주치는 상황

**Q: GPDO에서 dark current를 추출했는데 빈 표가 나옵니다.**
A: HY202103 데이터셋의 GPDO 파일에는 IV 측정이 없고 광 손실만 들어
   있습니다. 다른 측정 세트(IV가 포함된 GPDO)가 들어오면 코드 수정 없이
   바로 동작합니다.

**Q: 같은 die가 여러 세션에 있는데 어떻게 처리되나요?**
A: 각 세션은 독립된 행으로 들어갑니다. `Wafer + Session + Die`가 사실상
   유니크 키입니다. 통계나 yield 계산도 세션 단위 / 웨이퍼 단위 둘 다
   지원합니다 (`per_group_stats`, `yield_summary`의 `group_by` 인자).

**Q: 컨택 실패 검출의 임계값을 바꾸고 싶어요.**
A: `flag_failed_contacts()`에 `slope_threshold_pm_per_v`,
   `leakage_threshold_pa` 키워드 인자를 넣으면 됩니다. 기본값은 각각
   30 pm/V와 1000 pA입니다.

**Q: 새 spec 메트릭을 추가했는데 yield 계산이 모두 fail이 됩니다.**
A: spec 키 이름이 features DataFrame의 컬럼명과 정확히 일치해야 합니다
   (대소문자 포함). 컬럼이 없으면 자동으로 fail로 처리됩니다.

## 개발

```bash
# 테스트 (시스템에 pytest가 있을 때)
pytest --cov=picqa

# pytest 없는 환경에서 직접 검증
python run_tests_no_pytest.py

# 린트
ruff check src/ tests/
```
