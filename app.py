import streamlit as st, pandas as pd
from PIL import Image
import io, datetime as dt, hashlib, os
import db, storage
st.set_page_config(page_title="Controle de Armamento — PMCE", page_icon="🛡️", layout="wide")
with open("theme.css","r",encoding="utf-8") as f: st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
TIPOS_MATERIAL=["PISTOLA","REVOLVER","ESPINGARDA","CARABINA","SUBMETRALHADORA","COLETE","ALGEMAS","ESPARGIDOR","EQUIPAMENTO_PROTECAO","OUTROS"]
SITUACOES=["DISPONIVEL","ACAUTELADA","EM_MANUTENCAO","DESATIVADA"]; PERFIS=["admin","armeiro","usuario"]
def hash_password(pw:str)->str: return hashlib.sha256(pw.encode("utf-8")).hexdigest()
def logged_user(): return st.session_state.get("user")
def login_box():
    left,right=st.columns([1,2])
    with left:
        try: st.image(Image.open("mascote.png"), use_column_width=True)
        except Exception: st.markdown("<h2>🛡️ SIARM</h2>", unsafe_allow_html=True)
    with right:
        st.markdown("### Sistema de Armamento da Polícia Militar — **Controle de Armamento**")
        st.info("Use seu **Usuário (Nome de Guerra)** e senha para entrar.")
        usuario=st.text_input("Usuário (Nome de Guerra)"); senha=st.text_input("Senha", type="password")
        if st.button("Entrar", type="primary", use_container_width=True):
            row=db.get_user_by_usuario(usuario.strip())
            if not row: st.error("Usuário não encontrado.")
            else:
                uid,usr,nome,email,telefone,numeral_pm,matricula,senha_hash,perfil,ativo=row
                if not ativo: st.error("Usuário inativo.")
                elif senha_hash!=hash_password(senha): st.error("Senha incorreta.")
                else:
                    st.session_state["user"]=dict(id=uid,usuario=usr,nome=nome,email=email,telefone=telefone,numeral_pm=numeral_pm,matricula=matricula,perfil=perfil)
                    db.log_auditoria(uid,"login",{"usuario":usr}); st.rerun()
def topbar():
    u=logged_user(); st.markdown(f"#### 👤 {u['nome']} ({u['usuario']}) — Perfil: **{u['perfil'].upper()}**"); st.write("")
    cols=st.columns([1,1,1,1,1,1,2])
    if cols[0].button("🏠 Dashboard", use_container_width=True): st.session_state["page"]="dashboard"
    if cols[1].button("🧾 Cautela/Devolução", use_container_width=True): st.session_state["page"]="cautela"
    if cols[2].button("🗃️ Materiais", use_container_width=True): st.session_state["page"]="materiais"
    if cols[3].button("🔫 Munições", use_container_width=True): st.session_state["page"]="municoes"
    if cols[4].button("📈 Relatórios", use_container_width=True): st.session_state["page"]="relatorios"
    if cols[5].button("👥 Usuários", use_container_width=True): st.session_state["page"]="usuarios"
    if cols[6].button("Sair", use_container_width=True): st.session_state.clear(); st.rerun()
    st.divider()
def require_role(*roles):
    u=logged_user()
    if u["perfil"] not in roles: st.warning("Você não tem permissão para acessar esta seção."); st.stop()
def page_dashboard():
    st.subheader("📊 Visão Geral")
    mats=db.list_materiais()
    df=pd.DataFrame(mats,columns=["ID","Tipo","Especificação","Marca","Modelo","Calibre","Nº Série","Unidade","Local","Situação","Status Conf.","Conferida","Criado em"])
    total=len(df); q_disp=(df["Situação"]=="DISPONIVEL").sum(); q_acaut=(df["Situação"]=="ACAUTELADA").sum(); q_manut=(df["Situação"]=="EM_MANUTENCAO").sum()
    m1,m2,m3,m4=st.columns(4); m1.metric("Total de Itens", total); m2.metric("Disponíveis", int(q_disp)); m3.metric("Acautelados", int(q_acaut)); m4.metric("Em manutenção", int(q_manut))
    # 'Com quem' (apenas se acautelada)
    open_rows=db.listar_cautelas(status="ABERTA")
    holder_by_nserie={r[8]: f"{r[5]} ({r[4]})" for r in open_rows}  # Nº Série -> Nome (Usuário)
    df["Com quem"] = df.apply(lambda r: holder_by_nserie.get(r["Nº Série"], "") if r["Situação"]=="ACAUTELADA" else "", axis=1)
    st.write(""); st.dataframe(df, use_container_width=True, height=420)
def page_materiais():
    u=logged_user(); can_edit=u["perfil"] in ("admin","armeiro")
    st.subheader("🗃️ Materiais")
    filtro=st.text_input("Pesquisar (tipo, especificação, nº de série, unidade)...", key="filtro_mats")
    mats=db.list_materiais(filtro or None); df=pd.DataFrame(mats,columns=["ID","Tipo","Especificação","Marca","Modelo","Calibre","Nº Série","Unidade","Local","Situação","Status Conf.","Conferida","Criado em"])
    st.dataframe(df, use_container_width=True, height=420)
    st.markdown("##### Incluir / Editar Material")
    with st.form("form_material"):
        c=st.columns(4); tipo=c[0].selectbox("Tipo",TIPOS_MATERIAL,0); especificacao=c[1].text_input("Especificação (ex: TAURUS PT-100)"); marca=c[2].text_input("Marca"); modelo=c[3].text_input("Modelo")
        c2=st.columns(4); calibre=c2[0].text_input("Calibre"); numero_serie=c2[1].text_input("Nº de Série"); unidade=c2[2].text_input("Unidade/OPM (ex: 3º BPM)"); local=c2[3].text_input("Local/Depósito/Armário")
        c3=st.columns(4); situacao=c3[0].selectbox("Situação",SITUACOES,0); status_conf=c3[1].text_input("Status de Conferência (ex: CONFIRMADO)"); conferida=c3[2].checkbox("Conferida",False)
        observacao=st.text_area("Observação",height=80); mid_edit=st.text_input("ID para editar (opcional)")
        if st.form_submit_button("Salvar", type="primary", disabled=not can_edit):
            if not can_edit: st.error("Seu perfil não permite esta ação.")
            else:
                try:
                    if mid_edit.strip():
                        db.update_material(int(mid_edit), tipo=tipo, especificacao=especificacao, marca=marca, modelo=modelo, calibre=calibre, numero_serie=numero_serie, unidade=unidade, local=local, situacao=situacao, status_conf=status_conf, conferida=int(conferida), observacao=observacao)
                        db.log_auditoria(u["id"],"material_update",{"id":int(mid_edit),"numero_serie":numero_serie}); st.success(f"Material ID {mid_edit} atualizado.")
                    else:
                        db.create_material(tipo=tipo, especificacao=especificacao, marca=marca, modelo=modelo, calibre=calibre, numero_serie=numero_serie, unidade=unidade, local=local, situacao=situacao, status_conf=status_conf, conferida=int(conferida), observacao=observacao)
                        db.log_auditoria(u["id"],"material_create",{"numero_serie":numero_serie}); st.success("Material incluído com sucesso.")
                except Exception as e: st.error(f"Erro ao salvar material: {e}")
    st.markdown("##### 📎 Anexos do Material")
    if len(df):
        target_id=st.number_input("ID do material para anexar arquivo", min_value=1, step=1)
        up=st.file_uploader("Envie imagem/PDF do material", type=["png","jpg","jpeg","pdf"])
        if up and st.button("Anexar ao material", type="primary"):
            path,fname=storage.save_uploaded_file(up, prefix=f"material_{int(target_id)}"); db.add_anexo("material", int(target_id), fname, path, logged_user()["id"])
            db.log_auditoria(u["id"],"anexo_material",{"material_id":int(target_id),"file":fname}); st.success("Anexo salvo.")
        if st.button("Listar anexos do material informado"):
            anexos=db.list_anexos("material", int(target_id))
            if anexos:
                for (aid,fname,path,up_by,up_at) in anexos:
                    with open(path,"rb") as fh: st.download_button(f"Baixar: {fname}", data=fh.read(), file_name=fname)
            else: st.info("Sem anexos para este material.")
def _df_users(rows): return pd.DataFrame(rows, columns=["ID","Usuário","Nome","Email","Telefone","Numeral PM","Matrícula","Perfil","Ativo"])
def page_usuarios():
    require_role("admin"); u=logged_user(); st.subheader("👥 Usuários")
    q=st.text_input("Pesquisar usuário/nome/email/matrícula..."); rows=db.list_users(q or None); st.dataframe(_df_users(rows), use_container_width=True, height=360)
    st.markdown("##### Criar/Editar")
    with st.form("form_user"):
        c=st.columns(3); usuario=c[0].text_input("Usuário (Nome de Guerra)"); nome=c[1].text_input("Nome"); email=c[2].text_input("E-mail")
        c2=st.columns(3); telefone=c2[0].text_input("Telefone"); numeral_pm=c2[1].text_input("Numeral PM"); matricula=c2[2].text_input("Matrícula")
        c3=st.columns(3); perfil=c3[0].selectbox("Perfil",PERFIS,2); ativo=c3[1].checkbox("Ativo",True); uid_edit=c3[2].text_input("ID p/ editar (deixe vazio para criar)")
        pw1=st.text_input("Senha (ao criar) ou nova senha (opcional)", type="password")
        if st.form_submit_button("Salvar", type="primary"):
            try:
                if uid_edit.strip():
                    db.update_user(int(uid_edit), nome, email, telefone, numeral_pm, matricula, perfil, ativo)
                    db.log_auditoria(u["id"],"user_update",{"id":int(uid_edit),"perfil":perfil,"ativo":bool(ativo)})
                    if pw1.strip(): db.update_password(int(uid_edit), hash_password(pw1)); db.log_auditoria(u["id"],"user_password_reset",{"id":int(uid_edit)})
                    st.success("Usuário atualizado.")
                else:
                    if not pw1.strip(): st.error("Informe uma senha para criar o usuário.")
                    else:
                        db.create_user(usuario, nome, email, telefone, numeral_pm, matricula, hash_password(pw1), perfil)
                        db.log_auditoria(u["id"],"user_create",{"usuario":usuario,"perfil":perfil}); st.success("Usuário criado.")
            except Exception as e: st.error(f"Erro: {e}")
def _usuarios_selectbox(label, key=None, filtro_perfil=None):
    rows=db.list_users(); users=[]
    for r in rows:
        uid,usuario,nome,_,_,_,_,perfil,ativo=r
        if not ativo: continue
        if filtro_perfil and perfil not in filtro_perfil: continue
        users.append({"id":uid,"label":f"{nome} ({usuario}) — {perfil}"})
    if not users: st.warning("Nenhum usuário encontrado/ativo."); return None
    idx=st.selectbox(label, range(len(users)), format_func=lambda i: users[i]["label"], key=key); return users[idx]["id"]
def page_cautela():
    u=logged_user(); st.subheader("🧾 Cautela / Devolução")
    st.caption("Armeiro/Admin podem acautelar para qualquer usuário. Usuário comum só pode acautelar para si e só fecha suas próprias cautelas.")
    cols=st.columns(2)
    with cols[0]:
        st.markdown("##### 📤 Nova Cautela (Retirada)")
        if u["perfil"] in ("admin","armeiro"): uid=_usuarios_selectbox("Para quem será a cautela?", key="c_aut")
        else: uid=u["id"]; st.text_input("Para quem será a cautela?", value=f"{u['nome']} ({u['usuario']})", disabled=True)
        mats=[m for m in db.list_materiais() if m[9]=="DISPONIVEL"]
        if mats:
            options=[f"ID {m[0]} — {m[1]} {m[2]} — Nº {m[6]} — {m[7]}" for m in mats]
            midx=st.selectbox("Escolha um material DISPONÍVEL", range(len(mats)), format_func=lambda i: options[i]); material_id=mats[midx][0]
        else: material_id=None; st.info("Nenhum material disponível no momento.")
        obs=st.text_area("Observação (opcional)", height=80)
        if st.button("Acautelar", type="primary", disabled=(material_id is None)):
            try:
                armeiro_id=u["id"] if u["perfil"] in ("admin","armeiro") else None
                db.create_cautela(material_id, uid, armeiro_id, obs); db.log_auditoria(u["id"],"cautela_create",{"material_id":material_id,"usuario_destino":uid})
                ok,msg=storage.send_mail("Nova Cautela Registrada", f"Cautela criada para material ID {material_id} por {u['usuario']} em {dt.datetime.utcnow().isoformat()}Z")
                st.success("Cautela registrada com sucesso." + ("" if ok else f" (sem e-mail: {msg})"))
            except Exception as e: st.error(f"Erro ao criar cautela: {e}")
    with cols[1]:
        st.markdown("##### 📥 Devolução")
        reg=db.listar_cautelas(status="ABERTA", user_id=u['id'] if u['perfil']=='usuario' else None)
        if not reg: st.info("Nenhuma cautela aberta para você." if u["perfil"]=="usuario" else "Nenhuma cautela aberta.")
        else:
            labels=[]; ids=[]
            for (cid,dret,ddev,status,uuser,unome,mtipo,mesp,nserie,armeiro_user) in reg:
                labels.append(f"ID {cid} — {mtipo} {mesp} (Nº {nserie}) — {unome} [{uuser}] — retirada: {dret[:19]}Z"); ids.append(cid)
            sel=st.selectbox("Cautela a dar baixa/devolver", range(len(ids)), format_func=lambda i: labels[i])
            if st.button("Dar baixa / Fechar Cautela", type="primary"):
                try:
                    db.fechar_cautela(ids[sel]); db.log_auditoria(u["id"],"cautela_close",{"cautela_id":int(ids[sel])})
                    ok,msg=storage.send_mail("Devolução Registrada", f"Cautela {int(ids[sel])} fechada por {u['usuario']} em {dt.datetime.utcnow().isoformat()}Z")
                    st.success("Cautela fechada (devolução registrada)." + ("" if ok else f" (sem e-mail: {msg})"))
                except Exception as e: st.error(f"Erro: {e}")
    st.markdown("##### 📄 Comprovante de Cautela (imprimir)")
    reg=db.listar_cautelas(status="ABERTA")
    if reg:
        cid,dret,ddev,status,uuser,unome,mtipo,mesp,nserie,armeiro_user=reg[0]
        html=f"""<html><body><h2 style='text-align:center'>GOVERNO DO ESTADO DO CEARÁ — PMCE</h2>
        <h3 style='text-align:center'>CAUTELA DE ARMA/MATERIAL INSTITUCIONAL</h3>
        <p><b>Nº Cautela:</b> {cid}<br><b>Policial:</b> {unome} ({uuser})<br><b>Material:</b> {mtipo} — {mesp} — Nº {nserie}<br>
        <b>Data/Hora da Retirada (UTC):</b> {dret}</p><p>Declaro que recebi o material acima descrito, comprometendo-me a zelar pelo seu uso e conservação e a devolvê-lo nas condições normais de funcionamento, observando as normas e POPs da PMCE.</p>
        <p style='margin-top:80px'>_____________________________<br>Assinatura do militar</p></body></html>"""
        st.download_button("Baixar comprovante (HTML)", data=html.encode("utf-8"), file_name=f"cautela_{cid}.html", mime="text/html")
    else: st.caption("Crie uma cautela para habilitar a emissão do comprovante.")
    st.markdown("##### 📎 Anexos de Cautela")
    rows=db.listar_cautelas()[:50]
    if rows:
        map_ids=[r[0] for r in rows]; labels=[f"#{r[0]} — {r[6]} {r[7]} Nº {r[8]} — {r[5]} [{r[4]}]" for r in rows]
        idx=st.selectbox("Escolha a cautela", range(len(map_ids)), format_func=lambda i: labels[i]); sel_id=int(map_ids[idx])
        upc=st.file_uploader("Enviar anexo da cautela (imagem/PDF)", type=["png","jpg","jpeg","pdf"], key="up_caut")
        if upc and st.button("Anexar à cautela", type="primary"):
            path,fname=storage.save_uploaded_file(upc, prefix=f"cautela_{sel_id}"); db.add_anexo("cautela", sel_id, fname, path, u["id"])
            db.log_auditoria(u["id"],"anexo_cautela",{"cautela_id":sel_id,"file":fname}); st.success("Anexo salvo.")
        if st.button("Listar anexos desta cautela"):
            anexos=db.list_anexos("cautela", sel_id)
            if anexos:
                for (aid,fname,path,up_by,up_at) in anexos:
                    with open(path,"rb") as fh: st.download_button(f"Baixar: {fname}", data=fh.read(), file_name=fname, key=f"dl_{aid}")
            else: st.info("Sem anexos nesta cautela.")
def page_relatorios():
    u=logged_user(); st.subheader("📈 Relatórios e Exportação / Backup")
    tipo=st.selectbox("Tipo de relatório", ["Materiais por situação","Cautelas por período","Movimentação de munição"])
    if tipo=="Materiais por situação":
        mats=db.list_materiais(); df=pd.DataFrame(mats,columns=["ID","Tipo","Especificação","Marca","Modelo","Calibre","Nº Série","Unidade","Local","Situação","Status Conf.","Conferida","Criado em"])
        st.dataframe(df, use_container_width=True, height=420); st.download_button("Exportar CSV", data=df.to_csv(index=False).encode("utf-8"), file_name="materiais.csv", mime="text/csv")
    elif tipo=="Cautelas por período":
        c1,c2=st.columns(2); dt_ini=c1.date_input("Data inicial", value=dt.date.today().replace(day=1)); dt_fim=c2.date_input("Data final", value=dt.date.today())
        rows=db.listar_cautelas(dt_ini=str(dt_ini), dt_fim=str(dt_fim)); df=pd.DataFrame(rows,columns=["ID","Retirada","Devolução","Status","Usuário","Nome","Tipo","Especificação","Nº Série","Armeiro"])
        st.dataframe(df, use_container_width=True, height=420); st.download_button("Exportar CSV", data=df.to_csv(index=False).encode("utf-8"), file_name="cautelas.csv", mime="text/csv")
    else:
        rows=db.listar_mov_municao(); df=pd.DataFrame(rows,columns=["ID","MunicaoID","Tipo","Calibre","Lote","Mov","Qtd","UsuarioID","CautelaID","Obs","Data/Hora"])
        st.dataframe(df, use_container_width=True, height=420); st.download_button("Exportar CSV", data=df.to_csv(index=False).encode("utf-8"), file_name="mov_municao.csv", mime="text/csv")
    st.divider(); st.markdown("#### 💾 Backup do Banco")
    if st.button("Gerar backup agora"):
        p=storage.create_backup()
        if p: db.log_auditoria(u["id"],"backup_create",{"path":p}); st.success(f"Backup gerado: {os.path.basename(p)}")
        else: st.info("Banco ainda não existe.")
    latest=storage.latest_backup()
    if latest:
        with open(latest,"rb") as fh: st.download_button("Baixar backup mais recente (.db)", data=fh.read(), file_name=os.path.basename(latest))
def page_municoes():
    u=logged_user(); require_role("admin","armeiro"); st.subheader("🔫 Munições — Estoque e Movimentação")
    tabs=st.tabs(["Estoque","Entrada de Lote","Saída / Consumo","Movimentação"])
    with tabs[0]:
        filtro=st.text_input("Pesquisar (tipo, calibre, lote, unidade)..."); rows=db.list_municoes(filtro or None)
        df=pd.DataFrame(rows,columns=["ID","Tipo","Calibre","Lote","Qtd Inicial","Qtd Atual","Unidade","Situação","Obs","Criado em"]); st.dataframe(df, use_container_width=True, height=380)
    with tabs[1]:
        st.markdown("##### ➕ Entrada de Lote")
        with st.form("entrada_lote"):
            c=st.columns(3); tipo=c[0].text_input("Tipo (ex: Pistola)"); calibre=c[1].text_input("Calibre (ex: .40)"); lote=c[2].text_input("Lote")
            c2=st.columns(3); qini=c2[0].number_input("Quantidade inicial", min_value=1, step=1); unidade=c2[1].text_input("Unidade/OPM"); situacao=c2[2].text_input("Situação (ex: CONFIRMADO)")
            obs=st.text_area("Observação", height=80); submitted=st.form_submit_button("Cadastrar lote", type="primary")
            if submitted:
                try: db.create_municao(tipo=tipo, calibre=calibre, lote=lote, quantidade_inicial=int(qini), quantidade_atual=int(qini), unidade=unidade, situacao=situacao, observacao=obs); db.log_auditoria(u["id"],"municao_lote_create",{"lote":lote,"quantidade":int(qini)}); st.success("Lote cadastrado.")
                except Exception as e: st.error(f"Erro: {e}")
    with tabs[2]:
        st.markdown("##### ➖ Saída / Consumo"); rows=db.list_municoes()
        if rows:
            opts=[f"ID {r[0]} — {r[1]} {r[2]} — lote {r[3]} — saldo {r[5]}" for r in rows]; idx=st.selectbox("Escolha o lote de munição", range(len(rows)), format_func=lambda i: opts[i])
            mun_id=rows[idx][0]; qtd=st.number_input("Quantidade para saída", min_value=1, step=1)
            st.caption("Vinculação (opcional):"); usuario_id=None
            all_users=db.list_users()
            if all_users:
                options=[f"ID {r[0]} — {r[2]} ({r[1]})" for r in all_users if r[8]==1]; idmap=[r[0] for r in all_users if r[8]==1]
                selu=st.selectbox("Vincular a usuário (opcional)", [-1]+list(range(len(idmap))), format_func=lambda i: "—" if i==-1 else options[i])
                if selu!=-1: usuario_id=idmap[selu]
            cautela_id=st.text_input("Vincular a ID da Cautela (opcional)"); obs=st.text_area("Observação", height=80)
            if st.button("Registrar saída", type="primary"):
                try:
                    vinc_caut=int(cautela_id) if cautela_id.strip() else None
                    db.registrar_mov_municao(mun_id,"SAIDA",int(qtd),vinculo_usuario_id=usuario_id,vinculo_cautela_id=vinc_caut,observacao=obs)
                    db.log_auditoria(u["id"],"municao_saida",{"municao_id":mun_id,"quantidade":int(qtd),"usuario":usuario_id,"cautela":vinc_caut}); st.success("Saída registrada.")
                except Exception as e: st.error(f"Erro: {e}")
        else: st.info("Nenhum lote de munição cadastrado.")
    with tabs[3]:
        st.markdown("##### 🧾 Movimentação de Munição"); rows=db.listar_mov_municao()
        df=pd.DataFrame(rows,columns=["ID","MunicaoID","Tipo","Calibre","Lote","Mov","Qtd","UsuarioID","CautelaID","Obs","Data/Hora"]); st.dataframe(df, use_container_width=True, height=380)
        st.download_button("Exportar CSV", data=df.to_csv(index=False).encode("utf-8"), file_name="mov_municao.csv", mime="text/csv")
def main():
    storage.ensure_dirs(); db.init_db(); db.seed_admin(hash_password); storage.create_backup()
    if "user" not in st.session_state:
        st.markdown("> ⚠️ **Dica**: configure o envio de e-mails em `config.json` para receber notificações de novas cautelas/devoluções.")
        login_box(); return
    topbar(); page=st.session_state.get("page","dashboard")
    if page=="dashboard": page_dashboard()
    elif page=="materiais": page_materiais()
    elif page=="usuarios": page_usuarios()
    elif page=="cautela": page_cautela()
    elif page=="relatorios": page_relatorios()
    elif page=="municoes": page_municoes()
    else: page_dashboard()
if __name__=="__main__": main()
