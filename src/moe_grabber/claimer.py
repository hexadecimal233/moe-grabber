from __future__ import annotations
from rapidocr.utils.output import RapidOCROutput

import io
import os
import re
from typing import Optional

import requests
import stamina
from lxml import html
from PIL import Image
from protonmail import ProtonMail
from rapidocr import RapidOCR

from moe_grabber.config import MoeConfig
from moe_grabber.errors import IdTakenError, TransientError


def _format_html(html_content: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    tree = html.fromstring(html_content)
    return " ".join(tree.text_content().split())


class MoeClaimer:
    """Handles the full moe ID claiming workflow with multi-ID support."""

    def __init__(self, config: MoeConfig):
        self.config = config
        self.engine = RapidOCR(params={})
        self.proton = self._init_proton()

    # ── public API ──────────────────────────────────────────────

    def claim(self) -> Optional[str]:
        """Try each moe ID in order. Returns the first successfully claimed ID,
        or None if all IDs fail."""
        for moe_id in self.config.moe_numbers:
            print(f"尝试抢 ID: {moe_id}")

            session = requests.Session()
            url = f"https://icp.gov.moe/join.php?id={moe_id}"
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/140.0.0.0 Safari/537.36"
                ),
                "Referrer": url,
            }

            try:
                self._pre_request(session, url, headers, moe_id)
                self._site_info(session, url, headers)
                print(f"✅ 成功抢到 ID: {moe_id}")
                return moe_id
            except IdTakenError:
                print(f"  ID {moe_id} 已被占用，跳过")
                continue
            except TransientError as e:
                print(f"  ID {moe_id} 重试耗尽: {e}，跳过")
                continue

        print("❌ 所有 ID 均无法抢到")
        return None

    # ── phase 1: pre‑request (captcha + initial submit) ─────────

    @stamina.retry(on=TransientError, attempts=5)
    def _pre_request(
        self,
        session: requests.Session,
        url: str,
        headers: dict,
        moe_id: str,
    ) -> None:
        """Submit the initial form with captcha.

        Retries on TransientError. IdTakenError propagates immediately.
        """
        # First POST: load the form and get captcha image
        resp = session.post(url, headers=headers)
        self._check_response(resp, moe_id)

        print("请求首屏成功，准备解析验证码...")

        # Parse captcha image URL
        tree = html.fromstring(resp.text)
        captcha_src = tree.xpath('//img[@id="captcha_img"]/@src')[0]
        captcha_url = f"https://icp.gov.moe/{captcha_src[2:]}"

        # OCR the captcha
        captcha_text = self._ocr_captcha(session, captcha_url)
        print(f"识别到的验证码：{captcha_text}")

        # Second POST: submit captcha + moe ID
        resp = session.post(
            url,
            headers=headers,
            data={
                "NO1": moe_id,
                "NO7": self.config.email_mail,
                "authcode": captcha_text,
                "submit": "下一步",
            },
        )
        self._check_response(resp, moe_id)
        print("站点初始信息提交成功")

    # ── phase 2: site info submit ───────────────────────────────

    @stamina.retry(on=TransientError, attempts=5)
    def _site_info(
        self,
        session: requests.Session,
        url: str,
        headers: dict,
    ) -> None:
        """Submit full site info with email verification code.
        Retries on TransientError.
        """
        tkcode = self._get_tk_code()

        resp = session.post(
            url,
            headers=headers,
            data={
                "NO2": self.config.name,
                "NO3": self.config.domain,
                "NO4": self.config.homepage,
                "NO5": self.config.description,
                "NO6": self.config.owner,
                "tkcode": tkcode,
                "submit": "确认无误！Go !",
            },
        )

        if resp.status_code != 200 or resp.text.find("停止申请") != -1:
            print(f"提交站点详细信息失败，状态码：{resp.status_code}, {resp.text}")
            raise TransientError()

        print("站点详细信息提交成功")

    # ── helpers ─────────────────────────────────────────────────

    def _check_response(
        self,
        response: requests.Response,
        moe_id: str,
    ) -> None:
        """Validate the ICP response. Raises IdTakenError or TransientError."""
        if response.status_code != 200:
            raise TransientError(f"HTTP {response.status_code}")

        text = _format_html(response.text)
        if "停止申请" in text:
            raise IdTakenError(moe_id)

    def _ocr_captcha(
        self,
        session: requests.Session,
        captcha_url: str,
    ) -> str:
        """Download captcha image and recognize text via OCR."""
        captcha_resp = session.get(captcha_url)
        image = Image.open(io.BytesIO(captcha_resp.content))

        output = self.engine(image)  # ty:ignore[invalid-argument-type]

        # Keep only alphanumeric characters, lowercase
        return "".join(c for c in output.txts if c.isalnum()).lower()  # ty:ignore[unresolved-attribute, not-iterable]

    def _get_tk_code(self) -> str:
        """Wait for the ProtonMail verification email and extract the 6-digit
        code."""
        print("等待新邮件...")
        new_message = self.proton.wait_for_new_message(
            interval=1,
            timeout=30,
            rise_timeout=True,
            read_message=True,
        )

        if not new_message:
            raise TransientError("无邮件，请检查邮箱")

        if not new_message or "MoeCode" not in new_message.subject:
            raise TransientError("邮件主题不匹配")

        print(new_message.body)
        match = re.search(r"\d{6}", new_message.body)
        if not match:
            raise TransientError("未找到6位数字验证码")

        tkcode = match.group(0)
        print(f"成功提取邮箱验证码：{tkcode}")
        return tkcode

    def _init_proton(self) -> ProtonMail:
        """Initialize and authenticate the ProtonMail client."""
        print("初始化邮箱服务中...")
        proton = ProtonMail()

        if os.path.exists("session.pickle"):
            proton.load_session("session.pickle")
        else:
            proton.login(self.config.email_mail, self.config.email_pass)
            proton.save_session("session.pickle")

        return proton
