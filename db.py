import sqlite3, datetime as dt, json
DB_PATH = "armamento.db"
def get_conn(): return sqlite3.connect(DB_PATH, check_same_thread=False)
def init_db():
    conn=get_conn(); cur=conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT UNIQUE, nome TEXT, email TEXT, telefone TEXT,
        numeral_pm TEXT, matricula TEXT, senha_hash TEXT,
        perfil TEXT CHECK(perfil IN ('admin','armeiro','usuario')) NOT NULL DEFAULT 'usuario',
        ativo INTEGER DEFAULT 1, created_at TEXT);""")
    cur.execute("""CREATE TABLE IF NOT EXISTS materiais(
        id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT, especificacao TEXT, marca TEXT, modelo TEXT, calibre TEXT,
        numero_serie TEXT UNIQUE, unidade TEXT, local TEXT,
        situacao TEXT CHECK(situacao IN ('DISPONIVEL','ACAUTELADA','EM_MANUTENCAO','DESATIVADA')) DEFAULT 'DISPONIVEL',
        status_conf TEXT, conferida INTEGER DEFAULT 0, observacao TEXT, created_at TEXT, updated_at TEXT);""")
    cur.execute("""CREATE TABLE IF NOT EXISTS cautelas(
        id INTEGER PRIMARY KEY AUTOINCREMENT, material_id INTEGER NOT NULL, usuario_id INTEGER NOT NULL, armeiro_id INTEGER,
        data_retirada TEXT, data_devolucao TEXT, status TEXT CHECK(status IN ('ABERTA','FECHADA')) DEFAULT 'ABERTA',
        observacao TEXT,
        FOREIGN KEY(material_id) REFERENCES materiais(id),
        FOREIGN KEY(usuario_id) REFERENCES users(id),
        FOREIGN KEY(armeiro_id) REFERENCES users(id));""")
    cur.execute("""CREATE TABLE IF NOT EXISTS auditoria(
        id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER, acao TEXT, detalhe TEXT, ts TEXT);""")
    # anexos para materiais e cautelas
    cur.execute("""CREATE TABLE IF NOT EXISTS anexos(
        id INTEGER PRIMARY KEY AUTOINCREMENT, ref_tipo TEXT CHECK(ref_tipo IN ('material','cautela')), ref_id INTEGER,
        filename TEXT, path TEXT, uploaded_by INTEGER, uploaded_at TEXT);""")
    # munições (estoque e movimentos)
    cur.execute("""CREATE TABLE IF NOT EXISTS municoes(
        id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT, calibre TEXT, lote TEXT,
        quantidade_inicial INTEGER, quantidade_atual INTEGER, unidade TEXT, situacao TEXT,
        observacao TEXT, created_at TEXT, updated_at TEXT);""")
    cur.execute("""CREATE TABLE IF NOT EXISTS municao_mov(
        id INTEGER PRIMARY KEY AUTOINCREMENT, municao_id INTEGER, tipo_mov TEXT CHECK(tipo_mov IN ('ENTRADA','SAIDA')),
        quantidade INTEGER, vinculo_usuario_id INTEGER, vinculo_cautela_id INTEGER, observacao TEXT, ts TEXT,
        FOREIGN KEY(municao_id) REFERENCES municoes(id));""")
    conn.commit(); conn.close()
def seed_admin(hash_func):
    conn=get_conn(); cur=conn.cursor(); cur.execute("SELECT id FROM users WHERE usuario='admin';"); row=cur.fetchone()
    if not row:
        cur.execute("""INSERT INTO users(usuario,nome,email,telefone,numeral_pm,matricula,senha_hash,perfil,ativo,created_at)
                       VALUES(?,?,?,?,?,?,?,?,1,?);""", ("admin","Administrador","admin@example.com","","","",hash_func("admin123"),"admin",dt.datetime.utcnow().isoformat()))
        conn.commit()
    conn.close()
def log_auditoria(usuario_id, acao, detalhe_dict_or_str):
    conn=get_conn(); cur=conn.cursor()
    if isinstance(detalhe_dict_or_str,(dict,list)): detalhe=json.dumps(detalhe_dict_or_str,ensure_ascii=False)
    else: detalhe=str(detalhe_dict_or_str or "")
    cur.execute("INSERT INTO auditoria(usuario_id,acao,detalhe,ts) VALUES(?,?,?,?);",
                (usuario_id,acao,detalhe,dt.datetime.utcnow().isoformat())); conn.commit(); conn.close()
def list_users(q=None):
    conn=get_conn(); cur=conn.cursor()
    if q:
        cur.execute("""SELECT id,usuario,nome,email,telefone,numeral_pm,matricula,perfil,ativo FROM users
                       WHERE usuario LIKE ? OR nome LIKE ? OR email LIKE ? OR matricula LIKE ?
                       ORDER BY ativo DESC, perfil, nome;""", (f"%{q}%",)*4)
    else:
        cur.execute("""SELECT id,usuario,nome,email,telefone,numeral_pm,matricula,perfil,ativo FROM users
                       ORDER BY ativo DESC, perfil, nome;""")
    rows=cur.fetchall(); conn.close(); return rows
def get_user_by_usuario(usuario):
    conn=get_conn(); cur=conn.cursor()
    cur.execute("SELECT id,usuario,nome,email,telefone,numeral_pm,matricula,senha_hash,perfil,ativo FROM users WHERE usuario=?;", (usuario,))
    row=cur.fetchone(); conn.close(); return row
def get_user_by_id(uid):
    conn=get_conn(); cur=conn.cursor()
    cur.execute("SELECT id,usuario,nome,email,telefone,numeral_pm,matricula,perfil,ativo FROM users WHERE id=?;", (uid,))
    row=cur.fetchone(); conn.close(); return row
def create_user(usuario,nome,email,telefone,numeral_pm,matricula,senha_hash,perfil):
    conn=get_conn(); cur=conn.cursor()
    cur.execute("""INSERT INTO users(usuario,nome,email,telefone,numeral_pm,matricula,senha_hash,perfil,ativo,created_at)
                   VALUES(?,?,?,?,?,?,?,?,1,?);""", (usuario,nome,email,telefone,numeral_pm,matricula,senha_hash,perfil,dt.datetime.utcnow().isoformat()))
    conn.commit(); conn.close()
def update_user(uid,nome,email,telefone,numeral_pm,matricula,perfil,ativo):
    conn=get_conn(); cur=conn.cursor()
    cur.execute("""UPDATE users SET nome=?,email=?,telefone=?,numeral_pm=?,matricula=?,perfil=?,ativo=? WHERE id=?;""",
                (nome,email,telefone,numeral_pm,matricula,perfil,int(ativo),uid)); conn.commit(); conn.close()
def update_password(uid,senha_hash):
    conn=get_conn(); cur=conn.cursor(); cur.execute("UPDATE users SET senha_hash=? WHERE id=?;", (senha_hash,uid))
    conn.commit(); conn.close()
def list_materiais(filtro=None):
    conn=get_conn(); cur=conn.cursor()
    base="SELECT id,tipo,especificacao,marca,modelo,calibre,numero_serie,unidade,local,situacao,status_conf,conferida,created_at FROM materiais"
    if filtro:
        base+=" WHERE tipo LIKE ? OR especificacao LIKE ? OR numero_serie LIKE ? OR unidade LIKE ?"
        cur.execute(base+" ORDER BY created_at DESC;", (f"%{filtro}%",)*4)
    else:
        cur.execute(base+" ORDER BY created_at DESC;")
    rows=cur.fetchall(); conn.close(); return rows
def create_material(**kwargs):
    keys=",".join(kwargs.keys()); qmarks=",".join(["?"]*len(kwargs)); vals=list(kwargs.values())
    conn=get_conn(); cur=conn.cursor()
    cur.execute(f"INSERT INTO materiais({keys},created_at) VALUES({qmarks},?);", vals+[dt.datetime.utcnow().isoformat()])
    conn.commit(); conn.close()
def update_material(mid,**kwargs):
    sets=",".join([f"{k}=?" for k in kwargs.keys()]); vals=list(kwargs.values())+[mid]
    conn=get_conn(); cur=conn.cursor()
    cur.execute(f"UPDATE materiais SET {sets}, updated_at=? WHERE id=?;", vals[:-1]+[dt.datetime.utcnow().isoformat(),mid])
    conn.commit(); conn.close()
def get_material(mid):
    conn=get_conn(); cur=conn.cursor()
    cur.execute("SELECT id,tipo,especificacao,marca,modelo,calibre,numero_serie,unidade,local,situacao,status_conf,conferida,observacao FROM materiais WHERE id=?;", (mid,))
    row=cur.fetchone(); conn.close(); return row
def create_cautela(material_id,usuario_id,armeiro_id,observacao=''):
    now=dt.datetime.utcnow().isoformat(); conn=get_conn(); cur=conn.cursor()
    cur.execute("""INSERT INTO cautelas(material_id,usuario_id,armeiro_id,data_retirada,status,observacao)
                   VALUES(?,?,?,?, 'ABERTA', ?);""", (material_id,usuario_id,armeiro_id,now,observacao))
    cur.execute("UPDATE materiais SET situacao='ACAUTELADA', updated_at=? WHERE id=?;", (now,material_id))
    conn.commit(); conn.close()
def fechar_cautela(cautela_id):
    now=dt.datetime.utcnow().isoformat(); conn=get_conn(); cur=conn.cursor()
    cur.execute("SELECT material_id FROM cautelas WHERE id=?;", (cautela_id,)); row=cur.fetchone()
    if row:
        material_id=row[0]
        cur.execute("UPDATE cautelas SET status='FECHADA', data_devolucao=? WHERE id=?;", (now,cautela_id))
        cur.execute("UPDATE materiais SET situacao='DISPONIVEL', updated_at=? WHERE id=?;", (now,material_id))
        conn.commit()
    conn.close()
def listar_cautelas(aper=None, user_id=None, material_id=None, status=None, dt_ini=None, dt_fim=None):
    conn=get_conn(); cur=conn.cursor()
    base="""SELECT c.id,c.data_retirada,c.data_devolucao,c.status,u.usuario,u.nome,m.tipo,m.especificacao,m.numero_serie,a.usuario as armeiro_user
            FROM cautelas c JOIN users u ON u.id=c.usuario_id JOIN materiais m ON m.id=c.material_id
            LEFT JOIN users a ON a.id=c.armeiro_id WHERE 1=1"""
    params=[]
    if user_id: base+=" AND c.usuario_id=?"; params.append(user_id)
    if material_id: base+=" AND c.material_id=?"; params.append(material_id)
    if status: base+=" AND c.status=?"; params.append(status)
    if dt_ini: base+=" AND date(c.data_retirada) >= date(?)"; params.append(dt_ini)
    if dt_fim: base+=" AND date(c.data_retirada) <= date(?)"; params.append(dt_fim)
    base+=" ORDER BY c.id DESC;"
    cur.execute(base, params); rows=cur.fetchall(); conn.close(); return rows
def get_cautela_by_id(cid):
    conn=get_conn(); cur=conn.cursor()
    cur.execute("SELECT c.id,c.material_id,c.usuario_id,c.armeiro_id,c.data_retirada,c.data_devolucao,c.status,c.observacao FROM cautelas c WHERE c.id=?;", (cid,))
    row=cur.fetchone(); conn.close(); return row
def cautela_aberta_por_material(material_id):
    conn=get_conn(); cur=conn.cursor()
    cur.execute("SELECT id,material_id,usuario_id,data_retirada FROM cautelas WHERE material_id=? AND status='ABERTA' ORDER BY id DESC LIMIT 1;", (material_id,))
    row=cur.fetchone(); conn.close(); return row
def add_anexo(ref_tipo, ref_id, filename, path, uploaded_by):
    conn=get_conn(); cur=conn.cursor()
    cur.execute("""INSERT INTO anexos(ref_tipo,ref_id,filename,path,uploaded_by,uploaded_at) VALUES (?,?,?,?,?,?);""",
                (ref_tipo,ref_id,filename,path,uploaded_by,dt.datetime.utcnow().isoformat()))
    conn.commit(); conn.close()
def list_anexos(ref_tipo, ref_id):
    conn=get_conn(); cur=conn.cursor()
    cur.execute("SELECT id,filename,path,uploaded_by,uploaded_at FROM anexos WHERE ref_tipo=? AND ref_id=? ORDER BY id DESC;", (ref_tipo,ref_id))
    rows=cur.fetchall(); conn.close(); return rows
def list_municoes(filtro=None):
    conn=get_conn(); cur=conn.cursor()
    base="SELECT id,tipo,calibre,lote,quantidade_inicial,quantidade_atual,unidade,situacao,observacao,created_at FROM municoes"
    if filtro:
        base+=" WHERE tipo LIKE ? OR calibre LIKE ? OR lote LIKE ? OR unidade LIKE ?"
        cur.execute(base+" ORDER BY created_at DESC;", (f"%{filtro}%",)*4)
    else:
        cur.execute(base+" ORDER BY created_at DESC;")
    rows=cur.fetchall(); conn.close(); return rows
def create_municao(**kwargs):
    keys=",".join(kwargs.keys()); qmarks=",".join(["?"]*len(kwargs)); vals=list(kwargs.values())
    conn=get_conn(); cur=conn.cursor(); now=dt.datetime.utcnow().isoformat()
    cur.execute(f"INSERT INTO municoes({keys},created_at,updated_at) VALUES({qmarks}, ?, ?);", vals+[now,now])
    conn.commit(); conn.close()
def update_municao(mid,**kwargs):
    sets=",".join([f"{k}=?" for k in kwargs.keys()]); vals=list(kwargs.values())+[mid]
    conn=get_conn(); cur=conn.cursor()
    cur.execute(f"UPDATE municoes SET {sets}, updated_at=? WHERE id=?;", vals[:-1]+[dt.datetime.utcnow().isoformat(),mid])
    conn.commit(); conn.close()
def registrar_mov_municao(municao_id,tipo_mov,quantidade,vinculo_usuario_id=None,vinculo_cautela_id=None,observacao=''):
    conn=get_conn(); cur=conn.cursor()
    cur.execute("SELECT quantidade_atual FROM municoes WHERE id=?;", (municao_id,)); row=cur.fetchone()
    if not row: conn.close(); raise ValueError("Munição não encontrada")
    saldo=int(row[0] or 0)
    if tipo_mov=='ENTRADA': saldo_novo=saldo+int(quantidade)
    else:
        if int(quantidade)>saldo: conn.close(); raise ValueError("Quantidade maior que o saldo")
        saldo_novo=saldo-int(quantidade)
    cur.execute("UPDATE municoes SET quantidade_atual=?, updated_at=? WHERE id=?;", (saldo_novo,dt.datetime.utcnow().isoformat(),municao_id))
    cur.execute("""INSERT INTO municao_mov(municao_id,tipo_mov,quantidade,vinculo_usuario_id,vinculo_cautela_id,observacao,ts)
                   VALUES(?,?,?,?,?,?,?);""", (municao_id,tipo_mov,int(quantidade),vinculo_usuario_id,vinculo_cautela_id,observacao,dt.datetime.utcnow().isoformat()))
    conn.commit(); conn.close()
def listar_mov_municao(municao_id=None, dt_ini=None, dt_fim=None):
    conn=get_conn(); cur=conn.cursor()
    base="""SELECT mv.id,mv.municao_id,m.tipo,m.calibre,m.lote,mv.tipo_mov,mv.quantidade,
                   mv.vinculo_usuario_id,mv.vinculo_cautela_id,mv.observacao,mv.ts
            FROM municao_mov mv JOIN municoes m ON m.id=mv.municao_id WHERE 1=1"""
    params=[]
    if municao_id: base+=" AND mv.municao_id=?"; params.append(municao_id)
    if dt_ini: base+=" AND date(mv.ts) >= date(?)"; params.append(dt_ini)
    if dt_fim: base+=" AND date(mv.ts) <= date(?)"; params.append(dt_fim)
    base+=" ORDER BY mv.id DESC;"
    cur.execute(base, params); rows=cur.fetchall(); conn.close(); return rows
