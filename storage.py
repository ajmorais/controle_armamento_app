import os, shutil, json, smtplib, ssl, datetime as dt
from email.mime.text import MIMEText
from email.utils import formataddr
BASE_DIR = os.path.dirname(__file__)
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
DB_PATH = os.path.join(BASE_DIR, "armamento.db")
def ensure_dirs():
    os.makedirs(UPLOAD_DIR, exist_ok=True); os.makedirs(BACKUP_DIR, exist_ok=True)
def load_config():
    if not os.path.exists(CONFIG_PATH): return {"notify":{"enabled":False,"admin_emails":[]}}
    with open(CONFIG_PATH,"r",encoding="utf-8") as f: return json.load(f)
def save_uploaded_file(uploaded_file, prefix="geral"):
    ensure_dirs(); now = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe = "".join(c for c in uploaded_file.name if c.isalnum() or c in (".","_","-")).strip(".")
    fname = f"{prefix}_{now}_{safe}" if safe else f"{prefix}_{now}"
    path = os.path.join(UPLOAD_DIR, fname)
    with open(path,"wb") as out: out.write(uploaded_file.read())
    return path, fname
def create_backup():
    ensure_dirs(); now = dt.datetime.utcnow().strftime("%Y%m%d_%H%M")
    dst = os.path.join(BACKUP_DIR, f"backup_{now}.db")
    if os.path.exists(DB_PATH): shutil.copy2(DB_PATH, dst); return dst
    return None
def latest_backup():
    ensure_dirs(); files = [os.path.join(BACKUP_DIR,f) for f in os.listdir(BACKUP_DIR) if f.endswith(".db")]
    if not files: return None
    files.sort(key=os.path.getmtime, reverse=True); return files[0]
def send_mail(subject, body, to_emails=None):
    cfg = load_config(); notify = cfg.get("notify",{})
    if not notify.get("enabled"): return False, "Notificações desativadas"
    to_emails = to_emails or notify.get("admin_emails", [])
    if not to_emails: return False, "Sem destinatário configurado"
    msg = MIMEText(body, "plain", "utf-8"); msg["Subject"]=subject
    msg["From"]=formataddr((notify.get("from_name") or "Sistema", notify.get("from_email"))); msg["To"]=", ".join(to_emails)
    ctx = ssl.create_default_context()
    try:
        with smtplib.SMTP(notify["smtp_host"], notify["smtp_port"], timeout=15) as s:
            if notify.get("use_tls", True): s.starttls(context=ctx)
            if notify.get("username"): s.login(notify["username"], notify["password"])
            s.sendmail(notify.get("from_email"), to_emails, msg.as_string())
        return True, "Enviado"
    except Exception as e:
        return False, f"Falha ao enviar: {e}"
