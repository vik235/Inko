# Inko® — by Moviar LLC

A small local Windows app for generating, storing, and emailing payment
receipts as PDFs. Single-user, runs offline, no cloud account.

> Internally the project folder is still named `Quickr` for historical
> reasons (renaming would invalidate the existing `.venv`). The shipped
> app, executable, installer, and data folders are all `Inko`.

---

## Quick start

### Running from source (development)

```bat
:: One-time setup
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt

:: Run the app
.venv\Scripts\python.exe app.py
```

A native window opens (Edge WebView2). Three tabs in the top nav:

- **New receipt** — fill in payer, amount, date; PDF is generated and saved.
- **History** — list of past receipts; click any to view, reprint, or email.
- **Settings** — your business info, signature, currency, receipt numbering,
  and email (SMTP) configuration.

### Running the installed `.exe`

After `build.bat` and `iscc installer.iss` produce `Inko-Setup-*.exe`, the
end user just double-clicks the installer, then launches Inko from the
Start menu or desktop shortcut.

---

## Where files live

| What | Path |
|------|------|
| App data folder (DB, settings) | `%APPDATA%\Inko\` |
| SQLite database (receipts + settings) | `%APPDATA%\Inko\inko.db` |
| Generated PDFs | `%USERPROFILE%\Documents\Inko\` |
| Installed program (when installed via .exe) | `%LOCALAPPDATA%\Programs\Inko\` |
| Build output (PyInstaller) | `dist\Inko\` |
| Installer output (Inno Setup) | `installer\Inko-Setup-*.exe` |

The DB and PDFs are completely separate from the program install — you can
uninstall the app without losing any receipts. To start over, delete the
`%APPDATA%\Inko\` folder; the app will create a fresh DB on next launch.

**Legacy migration:** if `%APPDATA%\Receiptly\` or `%APPDATA%\Quickr\` are
present from earlier brand names, they are automatically renamed to `Inko`
on first launch. Same for `Documents\Receiptly\` and `Documents\Quickr Receipts\`.

---

## Receipt numbering

Configurable in **Settings → Receipt numbering**:

| Option | Effect | Example |
|--------|--------|---------|
| Prefix empty, year off | Plain 5-digit | `00001`, `00002` |
| Prefix `R`, year off | Prefix + 5-digit | `R-00001` |
| Prefix `R`, year on | Prefix + year + 5-digit (resets each Jan 1) | `R-2026-00001` |

A live preview shows the next number while you edit.

---

## Signatures

Two ways to create one (Settings → Signature):

- **Draw tab** — draw with the mouse / stylus on the canvas pad.
- **Type tab** — type your name, choose a script font (Caveat, Dancing Script,
  Great Vibes, Sacramento), preview live, and save.

The saved signature is shown inline under the tabs as **"Currently saved on
this device"** so you can verify it's stored.

To re-sign or remove on a single receipt, open the receipt and click
**Re-sign**. A modal with the same Draw/Type tabs opens; the new signature
applies to that receipt only and overrides the default.

PDFs are **regenerated on every view**, so a signature change in Settings
flows into all existing receipts the next time they are opened or downloaded.

---

## Email (SMTP)

Configure once in **Settings → Email**, then use the **Email** button on any
receipt's detail page. A compose window opens — review the To / Subject /
Body (pre-filled from your templates), then **Send via Gmail/SMTP**. The
receipt's email status is recorded in History.

### Common provider settings

| Provider | Host | Port | Encryption | Notes |
|---|---|---|---|---|
| **Gmail (personal)** | `smtp.gmail.com` | `465` | SSL | **App Password required** (2-Step Verification must be on). Generate at <https://myaccount.google.com/apppasswords>. Do **not** use your regular Google password. |
| **Outlook.com / Hotmail** | `smtp-mail.outlook.com` | `587` | STARTTLS | Account password works; if 2FA is on, generate an app password at <https://account.live.com/proofs/AppPassword>. |
| **Microsoft 365 (corporate)** | `smtp.office365.com` | `587` | STARTTLS | Often **disabled by tenant policy** (SMTP basic auth blocked). If your IT has disabled it, use the Outlook desktop client to send the PDF manually instead. |
| **Yahoo Mail** | `smtp.mail.yahoo.com` | `465` | SSL | App Password required. Settings → Account Security → Generate app password. |
| **iCloud Mail** | `smtp.mail.me.com` | `587` | STARTTLS | App-specific password required from <https://appleid.apple.com>. Username is your full iCloud email. |
| **Zoho Mail** | `smtp.zoho.com` | `465` | SSL | App password recommended. |
| **ProtonMail** | (requires Bridge) | — | — | Native SMTP not exposed; install ProtonMail Bridge and use its localhost SMTP relay (`127.0.0.1:1025`). |
| **Custom / your domain** | your SMTP host | `465` or `587` | SSL or STARTTLS | Get from your hosting provider. |

In the app, port `465` triggers SSL (implicit TLS); any other port (typically
`587`) triggers STARTTLS.

### Step-by-step: Gmail

1. Sign in to your Google account → <https://myaccount.google.com/security>.
2. Enable **2-Step Verification** (required before App Passwords are
   available).
3. Go to <https://myaccount.google.com/apppasswords>.
4. App = **Mail**, Device = **Other → "Inko"**. Click **Generate**.
5. Copy the 16-character code (no spaces required).
6. In Inko: **Settings → Email**:
   - Tick **Enable email sending**
   - Gmail address: `you@gmail.com`
   - App password: paste the 16 characters
   - From name: anything (defaults to your Business name)
   - Host / port: `smtp.gmail.com` / `465`
   - Save settings.
7. Open any receipt → **Email** → adjust message → **Send via Gmail**.

### Subject and body templates

Both fields support placeholders that are substituted at send time:

| Placeholder | Value |
|---|---|
| `{payer_name}` | "Received from" name |
| `{amount}` | Amount, formatted with thousands separators (e.g. `28,000.00`) |
| `{currency}` | Currency code (e.g. `INR`) |
| `{currency_symbol}` | Symbol (e.g. `₹`) |
| `{receipt_number}` | Display number (e.g. `R-2026-00001`) |
| `{receipt_date}` | Date as ISO `YYYY-MM-DD` |
| `{business_name}` | From settings |
| `{id}` | Internal ULID receipt ID |

**Where the SMTP password is stored:** plain text in `inko.db` (settings
table). This is acceptable for a single-user local install on your own
machine — but the file is unencrypted, so don't share or sync the
`%APPDATA%\Inko\` folder. Always use a provider-specific App Password
(not your real account password).

---

## Backup & restore

Everything is in two folders:

```text
%APPDATA%\Inko\inko.db                <- receipts + settings
%USERPROFILE%\Documents\Inko\*.pdf    <- generated receipt PDFs
```

To back up: copy both folders. To restore on a different machine: install
Inko, then drop the same files into the same paths and relaunch. The DB
captures every receipt's data — PDFs are derivative and will regenerate from
the DB on first view if missing.

---

## Building the Windows installer

Requires:

- Python 3.10+ on PATH (`python --version`)
- [Inno Setup 6](https://jrsoftware.org/isdl.php) on PATH (`iscc /?`)

```bat
:: 1. Build the app .exe (PyInstaller)
build.bat

:: 2. Build the setup installer (Inno Setup)
iscc installer.iss

:: Output: installer\Inko-Setup-0.1.0.exe
```

To bump the version, edit `#define AppVersion` in `installer.iss`.

To re-issue the app under a fresh identity (so old installs don't get
silently upgraded), regenerate the `AppId` GUID in `installer.iss`.

---

## Project layout

```text
app.py                  pywebview launcher
server.py               Flask routes
db.py                   SQLite schema + queries + receipt numbering
pdf_gen.py              ReportLab PDF rendering + branding
emailer.py              SMTP send (Gmail-friendly)
paths.py                resolves %APPDATA% / Documents paths + legacy migration
templates/              Jinja templates (base, index, history, settings,
                        receipt_view, email_compose)
static/style.css        web UI styling
static/signature-pad.js drawing pad + typed-signature renderer
static/fonts/           4 cursive TTFs for typed signatures (SIL OFL)
Inko.spec               PyInstaller spec
installer.iss           Inno Setup script
build.bat               build helper
smoke_test.py           headless tests (signatures, numbering, email mock)
test_signature_flow.py  signature persistence regression test
```

---

## Troubleshooting

**The PDF isn't picking up my new signature / business name.**
PDFs are regenerated on every view. If a stale PDF persists, hard-restart
the app (close window AND kill the `python` process), then reload the
receipt. Check **Settings → Currently saved on this device** to confirm the
server has your signature.

**Gmail says "Username and Password not accepted".**
You used your regular Google password. Gmail requires an App Password —
see the Gmail step-by-step above.

**Email status stays "failed".**
The error message in the red banner names the cause. Common ones:
- *"Gmail rejected the credentials"* — App Password wrong or not generated.
- *"SMTP error: \[Errno 11001] getaddrinfo failed"* — wrong host or no
  internet.
- *"SMTP error: timed out"* — corporate firewall or wrong port.

**The `₹` (or `€`, `£`) symbol shows as a box in the PDF.**
The PDF embeds Arial from `C:\Windows\Fonts\arial.ttf` to render currency
symbols. If your system is missing Arial, install it or pick a different
currency symbol in Settings.

**My existing PDFs disappeared after rebrand.**
On first launch after a rename, the legacy folder is migrated. If a PDF
viewer was holding any file open, that file stays in the old folder; the
migration retries on the next launch. To force-clean, close all PDF
viewers and relaunch the app.

**The `python` process is still running after I close the window.**
On Windows, pywebview occasionally leaves a daemon thread alive. Close it
in Task Manager (or `Stop-Process -Name python` in PowerShell) before
relaunching from source.

---

## Roadmap / extension points

- **Email status flag in DB** is already wired (`email_status` column +
  `email_address`). Adding bulk re-send, retry, or scheduled send is
  small.
- **Logo upload** in settings would replace the auto-generated initial
  badge in the PDF header (the `LogoFlowable` class in `pdf_gen.py`
  already renders to a fixed area).
- **Per-currency receipts**: the schema stores currency per receipt, so
  multi-currency support is just a UI dropdown change.
- **Audit immutability**: today the PDF regenerates on every view, picking
  up current settings. If you want receipts to be frozen at issue time,
  cache the rendered PDF bytes in the DB and serve those instead of
  regenerating.
