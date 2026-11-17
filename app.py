"""쇼핑 리스트 앱 - 3단계: UI 디자인 (기능은 2단계와 동일)."""

import json
import os
import re
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st

MAX_NAME_LEN = 100
MAX_QUANTITY = 999
FILTERS = ["전체", "미완료", "완료"]

# ---------------------------------------------------------------------------
# 데이터: 파일 I/O는 load_items / save_items 두 함수에서만 한다 (DB 교체 대비)
# ---------------------------------------------------------------------------
DATA_FILE = Path(__file__).parent / "data.json"


def _normalize(raw: dict) -> dict | None:
    """파일에서 읽은 dict를 데이터 모델에 맞게 보정한다. 이름이 없으면 버린다."""
    name = str(raw.get("name", "")).strip()[:MAX_NAME_LEN]
    if not name:
        return None
    try:
        quantity = min(max(int(raw.get("quantity", 1)), 1), MAX_QUANTITY)
    except (TypeError, ValueError):
        quantity = 1
    return {
        "id": str(raw.get("id") or uuid.uuid4()),
        "name": name,
        "quantity": quantity,
        "checked": bool(raw.get("checked", False)),
        "created_at": str(raw.get("created_at", "")),
    }


def load_items() -> list[dict]:
    """data.json에서 목록을 읽는다. 파일이 없거나 깨졌으면 빈 리스트."""
    try:
        # utf-8-sig: 메모장 등에서 BOM이 붙어 저장된 파일도 읽을 수 있게 한다.
        data = json.loads(DATA_FILE.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    items = (_normalize(d) for d in data if isinstance(d, dict))
    return [item for item in items if item is not None]


def save_items(items: list[dict]) -> None:
    """목록을 data.json에 저장한다. 임시 파일에 쓴 뒤 교체해서 파일이 깨지지 않게 한다."""
    fd, tmp_path = tempfile.mkstemp(dir=DATA_FILE.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, DATA_FILE)
    except OSError:
        Path(tmp_path).unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------------------
# 기능 로직: UI와 무관한 순수 함수 (입력 목록을 바꾸지 않고 새 목록을 반환)
# ---------------------------------------------------------------------------
def clean_name(name: str) -> str:
    """이름을 검증하고 공백을 제거해서 반환한다. 잘못되면 ValueError."""
    name = (name or "").strip()
    if not name:
        raise ValueError("아이템 이름을 입력해 주세요.")
    if len(name) > MAX_NAME_LEN:
        raise ValueError(f"이름은 {MAX_NAME_LEN}자 이하여야 해요.")
    return name


def add_item(items: list[dict], name: str, quantity: int) -> list[dict]:
    new = {
        "id": str(uuid.uuid4()),
        "name": clean_name(name),
        "quantity": quantity,
        "checked": False,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    return [*items, new]


def update_item(items: list[dict], item_id: str, name: str, quantity: int) -> list[dict]:
    name = clean_name(name)
    return [
        {**i, "name": name, "quantity": quantity} if i["id"] == item_id else i
        for i in items
    ]


def delete_item(items: list[dict], item_id: str) -> list[dict]:
    return [i for i in items if i["id"] != item_id]


def toggle_item(items: list[dict], item_id: str, checked: bool) -> list[dict]:
    return [{**i, "checked": checked} if i["id"] == item_id else i for i in items]


def clear_checked(items: list[dict]) -> list[dict]:
    return [i for i in items if not i["checked"]]


def clear_all(items: list[dict]) -> list[dict]:
    return []


def filter_items(items: list[dict], mode: str) -> list[dict]:
    if mode == "미완료":
        return [i for i in items if not i["checked"]]
    if mode == "완료":
        return [i for i in items if i["checked"]]
    return items


# ---------------------------------------------------------------------------
# 상태 / 콜백
# ---------------------------------------------------------------------------
def init_state() -> None:
    """매 실행마다 파일에서 목록을 읽어 화면과 파일이 항상 일치하게 한다.

    새로고침은 물론, 다른 탭에서 바뀐 내용도 다음 실행에 반영된다.
    """
    # 주의: "items"는 dict.items() 메서드와 이름이 겹치므로 키로 쓰면 안 된다.
    st.session_state.item_list = load_items()
    st.session_state.setdefault("editing_id", None)
    # 새로고침해도 보기 필터가 유지되도록 URL 쿼리 파라미터와 동기화한다.
    if "filter" not in st.session_state:
        saved = st.query_params.get("view", "전체")
        st.session_state.filter = saved if saved in FILTERS else "전체"


def flash(kind: str, message: str) -> None:
    """콜백 안에서 다음 화면에 보여줄 메시지를 예약한다."""
    st.session_state.flash = (kind, message)


def commit(new_items: list[dict]) -> None:
    """상태를 갱신하고 파일에 저장한다."""
    st.session_state.item_list = new_items
    try:
        save_items(new_items)
    except OSError:
        flash("error", "저장에 실패했어요. 변경 내용이 파일에 기록되지 않았을 수 있어요.")


# 콜백은 화면에 남은 오래된 목록이 아니라 항상 파일의 최신 목록을 기준으로 바꾼다.
def on_add() -> None:
    try:
        new_items = add_item(
            load_items(),
            st.session_state.get("new_name", ""),
            int(st.session_state.get("new_qty", 1)),
        )
    except ValueError as e:
        flash("warning", str(e))
        return
    commit(new_items)


def on_toggle(item_id: str) -> None:
    checked = bool(st.session_state[f"chk_{item_id}"])
    commit(toggle_item(load_items(), item_id, checked))


def on_delete(item_id: str) -> None:
    if st.session_state.editing_id == item_id:
        st.session_state.editing_id = None
    commit(delete_item(load_items(), item_id))


def on_edit_start(item_id: str) -> None:
    # 이전 편집 입력값이 남아 있지 않도록 비우고, 한 번에 한 항목만 편집한다.
    for key in list(st.session_state.keys()):
        if key.startswith(("edit_name_", "edit_qty_")):
            del st.session_state[key]
    st.session_state.editing_id = item_id


def on_edit_cancel() -> None:
    st.session_state.editing_id = None


def on_edit_save(item_id: str) -> None:
    try:
        new_items = update_item(
            load_items(),
            item_id,
            st.session_state.get(f"edit_name_{item_id}", ""),
            int(st.session_state.get(f"edit_qty_{item_id}", 1)),
        )
    except ValueError as e:
        flash("warning", str(e))  # 편집 모드는 유지한다
        return
    st.session_state.editing_id = None
    commit(new_items)


def on_clear_checked() -> None:
    commit(clear_checked(load_items()))


def on_clear_all() -> None:
    st.session_state.editing_id = None
    st.session_state.confirm_clear = False
    commit(clear_all(load_items()))


def on_filter_change() -> None:
    mode = st.session_state.get("filter") or "전체"  # 선택 해제되면 전체로 되돌린다
    st.session_state.filter = mode
    st.query_params["view"] = mode


# ---------------------------------------------------------------------------
# 스타일: CSS는 이 한 곳에서만 주입한다.
# 선택자는 data-testid와 위젯 key에서 생기는 st-key-* 클래스만 쓴다 (해시 클래스 금지).
# 중립색은 rgba(128,128,128,x)로 지정해서 라이트/다크 테마 모두에서 읽히게 한다.
# ---------------------------------------------------------------------------
ACCENT = "#2E9E5B"
DANGER = "#D64545"

CSS = f"""
<style>
.stMainBlockContainer {{ padding-top: 2.5rem; max-width: 640px; }}

/* 헤더 */
.app-sub {{ margin: -0.6rem 0 1.2rem; opacity: .65; font-size: .95rem; }}

/* 카드: 입력 폼, 진행 상태 */
[data-testid="stForm"], .st-key-progress_card {{
  border: 1px solid rgba(128,128,128,.25);
  border-radius: 14px;
  background: rgba(128,128,128,.05);
  padding: 1rem 1.1rem;
}}
.st-key-progress_card [data-testid="stProgress"] > div > div > div > div {{
  background-color: {ACCENT};
}}
.progress-text {{ font-size: 1.05rem; margin: 0 0 .2rem; }}
.progress-text b {{ color: {ACCENT}; }}

/* 항목 행 */
[class*="st-key-row_"], [class*="st-key-editrow_"] {{
  border: 1px solid rgba(128,128,128,.22);
  border-radius: 12px;
  padding: .35rem .75rem;
  margin-bottom: .1rem;
}}
[class*="st-key-row_done_"] {{ opacity: .55; background: rgba(128,128,128,.06); }}

/* 수정 행: 좁은 화면에서도 [이름|수량], [저장|취소]를 각각 한 줄로 유지한다 */
[class*="st-key-editrow_"] [data-testid="stHorizontalBlock"] {{
  flex-wrap: nowrap !important; gap: .5rem;
}}
[class*="st-key-editrow_"] [data-testid="stColumn"] {{ min-width: 0 !important; }}
[class*="st-key-editact_"] [data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap !important; gap: .5rem; }}
[class*="st-key-editact_"] [data-testid="stColumn"] {{ flex: 1 1 0 !important; width: auto !important; min-width: 0 !important; }}

/* 좁은 화면에서도 항목 행을 한 줄로 유지한다 (Streamlit 기본은 세로로 쌓음) */
[class*="st-key-row_"] [data-testid="stHorizontalBlock"] {{
  flex-wrap: nowrap !important;
  gap: .4rem;
  align-items: center;
}}
[class*="st-key-row_"] [data-testid="stColumn"] {{
  min-width: 0 !important;
  flex: 1 1 0;
}}
[class*="st-key-row_"] [data-testid="stColumn"]:first-child {{ flex: 1 1 auto; }}
[class*="st-key-row_"] [data-testid="stColumn"]:not(:first-child) {{ flex: 0 0 auto; width: auto !important; }}
[class*="st-key-row_"] .stButton button {{
  padding: .2rem .55rem; min-height: 2.2rem; border-radius: 10px;
}}
.qty {{
  display: inline-block; padding: .1rem .55rem; border-radius: 999px;
  background: rgba(46,158,91,.15); color: {ACCENT}; font-weight: 600; font-size: .85rem;
  white-space: nowrap;
}}
/* 긴 이름은 잘라내지 않고 줄바꿈한다 (Streamlit 기본은 nowrap + 말줄임표) */
[class*="st-key-row_"] [data-testid="stCheckbox"] label div,
[class*="st-key-row_"] [data-testid="stCheckbox"] label p {{
  white-space: normal !important; overflow: visible !important;
  text-overflow: clip !important; overflow-wrap: anywhere;
}}

/* 보기 필터(알약 탭) */
.st-key-filter button[aria-checked="true"], .st-key-filter [aria-pressed="true"] {{
  background-color: {ACCENT}; border-color: {ACCENT}; color: #fff;
}}

/* 위험한 동작은 목록 하단에 두고 빨간 계열로 구분한다 */
.st-key-clear_all button:not(:disabled) {{ color: {DANGER}; border-color: {DANGER}; }}

/* 빈 상태 */
.empty {{ text-align: center; padding: 2rem 1rem; opacity: .7; }}
.empty .big {{ font-size: 2.4rem; }}

@media (max-width: 480px) {{
  .stMainBlockContainer {{ padding-left: 1rem; padding-right: 1rem; padding-top: 1.5rem; }}
  h1 {{ font-size: 1.7rem !important; }}
}}
</style>
"""


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
def escape_md(text: str) -> str:
    """사용자 입력이 마크다운/수식으로 해석되지 않도록 이스케이프한다."""
    return re.sub(r"([\\`*_\[\]()~<>$:#|!])", r"\\\1", text)


def render_header() -> None:
    st.title("🛒 쇼핑 리스트")
    st.markdown('<p class="app-sub">살 물건을 적고, 담으면 체크하세요.</p>',
                unsafe_allow_html=True)


def render_flash() -> None:
    kind, message = st.session_state.pop("flash", (None, None))
    if kind == "error":
        st.error(message, icon="⚠️")
    elif kind == "warning":
        st.warning(message, icon="⚠️")


def render_add_form() -> None:
    with st.form("add_form", clear_on_submit=True, border=False):
        c_name, c_qty = st.columns([3, 1])
        c_name.text_input(
            "아이템 이름", key="new_name", max_chars=MAX_NAME_LEN, placeholder="예: 우유",
        )
        c_qty.number_input(
            "수량", key="new_qty", min_value=1, max_value=MAX_QUANTITY, value=1, step=1,
        )
        st.form_submit_button("➕ 추가", on_click=on_add, type="primary",
                              use_container_width=True)


def render_progress(items: list[dict]) -> None:
    total = len(items)
    done = sum(1 for i in items if i["checked"])
    with st.container(key="progress_card"):
        st.markdown(
            f'<p class="progress-text">전체 <b>{total}</b>개 중 <b>{done}</b>개 완료</p>',
            unsafe_allow_html=True,
        )
        st.progress(done / total if total else 0.0)
    if total and done == total:
        st.success("🎉 장보기 끝! 모두 담았어요.")


def render_edit_row(item: dict) -> None:
    item_id = item["id"]
    with st.container(key=f"editrow_{item_id}"):
        c_name, c_qty = st.columns([3, 1])
        c_name.text_input(
            "이름 수정", key=f"edit_name_{item_id}", value=item["name"],
            max_chars=MAX_NAME_LEN, label_visibility="collapsed",
        )
        c_qty.number_input(
            "수량 수정", key=f"edit_qty_{item_id}", value=item["quantity"],
            min_value=1, max_value=MAX_QUANTITY, step=1, label_visibility="collapsed",
        )
        with st.container(key=f"editact_{item_id}"):
            c_save, c_cancel = st.columns(2)
            c_save.button("저장", key=f"save_{item_id}", on_click=on_edit_save,
                          args=(item_id,), type="primary", use_container_width=True)
            c_cancel.button("취소", key=f"cancel_{item_id}", on_click=on_edit_cancel,
                            use_container_width=True)


def render_row(item: dict) -> None:
    item_id = item["id"]
    if st.session_state.editing_id == item_id:
        render_edit_row(item)
        return

    state = "done" if item["checked"] else "todo"
    # 다른 탭에서 바뀐 값이 오래된 위젯 상태에 가려지지 않도록 매번 파일 값으로 맞춘다.
    st.session_state[f"chk_{item_id}"] = item["checked"]
    with st.container(key=f"row_{state}_{item_id}"):
        c_chk, c_qty, c_edit, c_del = st.columns([6, 1.4, 1, 1], vertical_alignment="center")
        label = escape_md(item["name"])
        c_chk.checkbox(
            f"~~{label}~~" if item["checked"] else label,
            key=f"chk_{item_id}", on_change=on_toggle, args=(item_id,),
        )
        c_qty.markdown(f'<span class="qty">×{int(item["quantity"])}</span>',
                       unsafe_allow_html=True)
        c_edit.button("✏️", key=f"edit_{item_id}", help="수정",
                      on_click=on_edit_start, args=(item_id,))
        c_del.button("🗑️", key=f"del_{item_id}", help="삭제",
                     on_click=on_delete, args=(item_id,))


def render_list(items: list[dict]) -> None:
    if not items:
        st.markdown(
            '<div class="empty"><div class="big">🧺</div>'
            "아직 아이템이 없어요.<br>위에서 추가해 보세요.</div>",
            unsafe_allow_html=True,
        )
        return
    mode = st.segmented_control(
        "보기", FILTERS, key="filter", label_visibility="collapsed",
        on_change=on_filter_change,
    ) or "전체"
    visible = filter_items(items, mode)
    if not visible:
        st.caption("해당하는 항목이 없어요.")
    for item in visible:
        render_row(item)


def render_bulk_actions(items: list[dict]) -> None:
    if not items:
        return
    st.divider()
    has_checked = any(i["checked"] for i in items)
    st.button("완료 항목 삭제", on_click=on_clear_checked, disabled=not has_checked,
              use_container_width=True)
    with st.expander("전체 초기화"):
        confirmed = st.checkbox("전체 삭제를 확인합니다", key="confirm_clear")
        with st.container(key="clear_all"):
            st.button("전체 초기화", on_click=on_clear_all, disabled=not confirmed,
                      use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="쇼핑 리스트", page_icon="🛒", layout="centered")
    st.markdown(CSS, unsafe_allow_html=True)
    init_state()
    render_header()
    render_flash()
    render_add_form()
    items = st.session_state.item_list
    render_progress(items)
    render_list(items)
    render_bulk_actions(items)


main()
