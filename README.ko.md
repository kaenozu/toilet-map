# 🚽 화장실 청결도 지도

Google Maps 리뷰에서 화장실 청결도를 자동 평가하여 지도에 표시합니다.

🌐 [日本語](README.ja.md) | [English](README.md) | [한국어](README.ko.md) | [中文](README.zh.md)

## 빠른 시작

```bash
git clone https://github.com/kaenozu/toilet-map.git
cd toilet-map
pip install -r requirements.txt
streamlit run app.py
```

## 테스트

```bash
pip install -r requirements-dev.txt
python -m playwright install chromium
pytest tests/e2e tests/visual -q
```

## 라이선스

MIT
