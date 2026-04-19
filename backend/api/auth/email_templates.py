"""
Branded HTML + plain-text email bodies.

Plain-text emails that are just a raw URL are aggressively flagged as
spam by Gmail and friends. Sending a matching HTML alternative with a
greeting, CTA button, and the link in plain sight materially improves
deliverability and, more importantly, doesn't look like phishing to
the recipient.
"""

PRODUCT_NAME = "Quant Backtester"


def _html_shell(heading: str, intro: str, cta_label: str, url: str, footer: str) -> str:
  return f"""<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f6f7f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#111;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f6f7f9;padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;border:1px solid #e5e7eb;overflow:hidden;">
            <tr>
              <td style="padding:28px 32px 8px 32px;">
                <div style="font-size:14px;color:#6b7280;letter-spacing:0.04em;text-transform:uppercase;">{PRODUCT_NAME}</div>
                <h1 style="margin:12px 0 0 0;font-size:22px;line-height:1.3;font-weight:600;">{heading}</h1>
              </td>
            </tr>
            <tr>
              <td style="padding:16px 32px 8px 32px;font-size:15px;line-height:1.55;color:#111;">
                {intro}
              </td>
            </tr>
            <tr>
              <td style="padding:16px 32px 8px 32px;">
                <a href="{url}" style="display:inline-block;background:#111827;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:8px;font-weight:600;font-size:15px;">{cta_label}</a>
              </td>
            </tr>
            <tr>
              <td style="padding:8px 32px 16px 32px;font-size:13px;color:#6b7280;">
                Or copy and paste this link into your browser:<br>
                <a href="{url}" style="color:#2563eb;word-break:break-all;">{url}</a>
              </td>
            </tr>
            <tr>
              <td style="padding:16px 32px 28px 32px;border-top:1px solid #f3f4f6;font-size:12px;color:#9ca3af;">
                {footer}
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def verification_email(verify_url: str) -> tuple[str, str]:
  text = (
    f"Welcome to {PRODUCT_NAME}.\n\n"
    f"Confirm your email to activate your account:\n{verify_url}\n\n"
    "If you didn't create an account, you can ignore this message."
  )
  html = _html_shell(
    heading="Confirm your email",
    intro=f"Welcome to {PRODUCT_NAME}. Click the button below to confirm your email address and activate your account.",
    cta_label="Verify email",
    url=verify_url,
    footer="If you didn't create an account, you can safely ignore this email.",
  )
  return text, html


def reverification_email(verify_url: str) -> tuple[str, str]:
  text = (
    "You asked for a new verification link.\n\n"
    f"Confirm your email here:\n{verify_url}\n\n"
    "If this wasn't you, you can ignore this message."
  )
  html = _html_shell(
    heading="New verification link",
    intro="You asked for a fresh link to confirm your email. It replaces any earlier one.",
    cta_label="Verify email",
    url=verify_url,
    footer="If this wasn't you, you can safely ignore this email.",
  )
  return text, html


def password_reset_email(reset_url: str, expire_hours: int) -> tuple[str, str]:
  text = (
    "We received a request to reset your password.\n\n"
    f"Reset it here:\n{reset_url}\n\n"
    f"This link expires in {expire_hours} hours. "
    "If you didn't request a reset, you can ignore this message."
  )
  html = _html_shell(
    heading="Reset your password",
    intro="We received a request to reset your password. Click the button below to choose a new one.",
    cta_label="Reset password",
    url=reset_url,
    footer=(
      f"This link expires in {expire_hours} hours. "
      "If you didn't request a reset, you can safely ignore this email."
    ),
  )
  return text, html
