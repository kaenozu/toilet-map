# 🚽 厕所清洁度地图

自动从 Google Maps 评论中评估厕所清洁度，并在地图上可视化显示。

🌐 [日本語](README.ja.md) | [English](README.md) | [한국어](README.ko.md) | [中文](README.zh.md)

## 快速开始

```bash
git clone https://github.com/kaenozu/toilet-map.git
cd toilet-map
pip install -r requirements.txt
streamlit run app.py
```

## 测试

```bash
pip install -r requirements-dev.txt
python -m playwright install chromium
pytest tests/e2e tests/visual -q
```

## 许可证

MIT
