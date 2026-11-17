# 🛒 쇼핑 리스트

Streamlit으로 만드는 간단한 쇼핑 리스트 웹 앱입니다. 요구사항은 [PRD.md](PRD.md)를 참고하세요.

## 로컬 실행

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

브라우저에서 http://localhost:8501 로 접속합니다.

## 데이터

목록은 `data.json`에 저장되며 처음 저장할 때 자동 생성됩니다.
