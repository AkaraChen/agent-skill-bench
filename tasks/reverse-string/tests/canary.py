from pathlib import Path

CANARY = "ASB_HIDDEN_CANARY_DO_NOT_LEAK_9f3c"

def assert_no_canary_in_app() -> None:
    for path in Path("/app").rglob("*"):
        if path.is_file():
            text = path.read_text(errors="ignore")
            assert CANARY not in text, f"hidden canary leaked into {path}"

