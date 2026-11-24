"""Real Chromium against compiled React, FastAPI, a worker process and HTTP fixture."""

import os
import shutil
import subprocess
import sys
from playwright.sync_api import sync_playwright, expect
from conftest import root, service


def test_workspace_flow(client, agent_url):
    assert (root / "frontend/dist/index.html").exists(), "npm run build first"
    worker = subprocess.Popen([sys.executable, "-m", "backend.worker"], cwd=root)
    try:
        for url in service("backend.api:app"):
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    executable_path=os.getenv("CHROMIUM_PATH")
                    or shutil.which("chromium"),
                    args=["--no-sandbox"],
                )
                page = browser.new_page(viewport={"width": 1340, "height": 900})
                page.set_default_timeout(15000)
                errors = []
                page.on("pageerror", lambda exc: errors.append(str(exc)))
                page.goto(url)
                expect(page.get_by_role("heading", name="평가 케이스")).to_be_visible()
                page.get_by_role("button", name="Phoenix 가져오기").click()
                page.get_by_role("button", name="가져올 항목 미리보기").click()
                page.get_by_role("button", name="가져오기", exact=True).click()
                expect(page.get_by_role("status").first).to_contain_text("이미 가져온")
                page.get_by_role("button", name="닫기").click()
                page.get_by_role("link", name="평가함수 관리").click()
                page.locator("article").filter(has_text="Exact Match").get_by_role(
                    "button"
                ).click()
                page.get_by_role("button", name="매핑 미리보기").click()
                expect(page.get_by_role("heading", name="검증 결과")).to_be_visible()
                page.get_by_role("button", name="전체 검증").click()
                expect(page.get_by_text("20 / 20건 매핑 성공")).to_be_visible()
                page.get_by_role("button", name="시험 평가").click()
                expect(page.locator("pre").last).to_contain_text('"score"')
                page.get_by_role("button", name="버전 발행").click()
                expect(
                    page.get_by_text("Evaluator와 매핑 버전을 발행했습니다.")
                ).to_be_visible()
                page.get_by_role("link", name="평가결과 관리").click()
                page.get_by_role("button", name="평가 실행").click()
                page.get_by_label("평가 방식").select_option("ab")
                page.get_by_label("실험 이름").fill("UI 회귀 실험")
                page.get_by_role(
                    "checkbox", name="정책 응답 정확도", exact=False
                ).check()
                page.get_by_role("button", name="실험 시작").click()
                expect(page.get_by_text("처리 20 / 20건", exact=False)).to_be_visible(
                    timeout=90000
                )
                page.get_by_role("button", name="비교하기").click()
                expect(
                    page.get_by_text("동일 케이스·지표 기준", exact=False)
                ).to_contain_text("regression 2")
                page.get_by_role("checkbox", name="회귀만 보기").check()
                expect(
                    page.locator("summary").filter(has_text="regression")
                ).to_have_count(2)
                page.get_by_role("link", name="평가데이터 관리").click()
                page.set_viewport_size({"width": 390, "height": 844})
                expect(
                    page.get_by_role("heading", name="평가데이터 관리")
                ).to_be_visible()
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth"
                )
                assert not errors
                browser.close()
    finally:
        worker.terminate()
        worker.wait(timeout=15)
