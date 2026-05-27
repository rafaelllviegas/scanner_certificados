#!/usr/bin/env python3
"""
Scanner de Certificados Digitais

"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

def recurso(caminho: str) -> str:
    """Localiza arquivos de recurso tanto em dev quanto dentro do .exe gerado pelo PyInstaller."""
    base = getattr(sys, "_MEIPASS", Path(__file__).parent)
    return str(Path(base) / caminho) 

# ─── Configurações ────────────────────────────────────────────────────────────

VALIDADE_DIAS = 365          # Validade padrão dos certificados
ALERTA_DIAS   = 30           # Dias antes do vencimento para exibir alerta
EXTENSOES     = {".pfx", ".p12"}  # Extensões de certificado reconhecidas
PASTA_PADRAO  = ""
PASTA_DOWNLOADS = Path.home() / "Downloads" 

# ─── Leitura dos certificados ─────────────────────────────────────────────────

def extrair_info_nome(nome_arquivo: str) -> dict:
    """Tenta extrair razão social e CNPJ/CPF do nome do arquivo."""
    nome = Path(nome_arquivo).stem  # sem extensão
    partes = nome.split("_")
    razao_social = partes[0].strip() if partes else nome
    cnpj_cpf = partes[1].strip() if len(partes) > 1 else ""

    # Limpa possível número do CNPJ (14 dígitos) ou CPF (11 dígitos)
    doc = ""
    for parte in partes[1:]:
        limpo = "".join(c for c in parte if c.isdigit())
        if len(limpo) in (11, 14):
            doc = limpo
            break

    return {
        "razao_social": razao_social.title(),
        "documento": formatar_documento(doc),
        "nome_arquivo": nome_arquivo,
    }


def formatar_documento(doc: str) -> str:
    if len(doc) == 14:
        return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"
    if len(doc) == 11:
        return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
    return doc


def calcular_status(vencimento: datetime) -> dict:
    hoje = datetime.now()
    dias_restantes = (vencimento - hoje).days

    if dias_restantes < 0:
        return {"status": "VENCIDO", "classe": "vencido", "emoji": "❌", "dias": dias_restantes}
    elif dias_restantes <= ALERTA_DIAS:
        return {"status": "ATENÇÃO", "classe": "atencao", "emoji": "⚠️", "dias": dias_restantes}
    else:
        return {"status": "VÁLIDO", "classe": "valido", "emoji": "✅", "dias": dias_restantes}


def escanear_pasta(caminho: str) -> list:
    pasta = Path(caminho)
    if not pasta.exists():
        print(f"❌ Pasta não encontrada: {caminho}")
        sys.exit(1)

    certificados = []

    for arquivo in sorted(pasta.iterdir()):
        if arquivo.suffix.lower() not in EXTENSOES:
            continue

        try:
            ts_modificacao = arquivo.stat().st_mtime
            dt_instalacao  = datetime.fromtimestamp(ts_modificacao)
            dt_vencimento  = dt_instalacao + timedelta(days=VALIDADE_DIAS)
            status         = calcular_status(dt_vencimento)
            info           = extrair_info_nome(arquivo.name)

            certificados.append({
                **info,
                "instalacao"  : dt_instalacao.strftime("%d/%m/%Y %H:%M"),
                "vencimento"  : dt_vencimento.strftime("%d/%m/%Y"),
                "dias_restantes": status["dias"],
                "status"      : status["status"],
                "classe"      : status["classe"],
                "emoji"       : status["emoji"],
                "tamanho_kb"  : round(arquivo.stat().st_size / 1024, 1),
                "caminho"     : str(arquivo),
            })
        except Exception as e:
            print(f"  ⚠️  Erro ao processar {arquivo.name}: {e}")

    return certificados


# ─── Geração do relatório HTML ─────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Certificados Digitais</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

  :root {{
    --bg:        #0d1117;
    --surface:   #161b22;
    --border:    #21262d;
    --text:      #e6edf3;
    --muted:     #7d8590;
    --accent:    #3b82f6;

    --valido:    #22c55e;
    --valido-bg: #052e16;
    --atencao:   #f59e0b;
    --atencao-bg:#451a03;
    --vencido:   #ef4444;
    --vencido-bg:#3b0000;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: 'Sora', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    padding: 2rem;
  }}

  /* ── Header ── */
  .header {{
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 1rem;
    margin-bottom: 2rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid var(--border);
  }}

  .header-left h1 {{
    font-size: 1.6rem;
    font-weight: 700;
    letter-spacing: -0.5px;
  }}

  .header-left p {{
    color: var(--muted);
    font-size: 0.85rem;
    margin-top: 0.3rem;
    font-family: 'JetBrains Mono', monospace;
  }}

  .badge-pasta {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.5rem 0.9rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    color: var(--accent);
    word-break: break-all;
    max-width: 500px;
  }}

  /* ── Cards de resumo ── */
  .resumo {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 1rem;
    margin-bottom: 2rem;
  }}

  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.2rem 1.4rem;
  }}

  .card .numero {{
    font-size: 2rem;
    font-weight: 700;
    line-height: 1;
  }}

  .card .label {{
    font-size: 0.78rem;
    color: var(--muted);
    margin-top: 0.4rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}

  .card.valido   .numero {{ color: var(--valido); }}
  .card.atencao  .numero {{ color: var(--atencao); }}
  .card.vencido  .numero {{ color: var(--vencido); }}
  .card.total    .numero {{ color: var(--accent); }}

  /* ── Filtros ── */
  .filtros {{
    display: flex;
    gap: 0.6rem;
    flex-wrap: wrap;
    margin-bottom: 1.2rem;
    align-items: center;
  }}

  .filtros input {{
    flex: 1;
    min-width: 220px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    font-family: 'Sora', sans-serif;
    font-size: 0.88rem;
    padding: 0.55rem 1rem;
    outline: none;
  }}

  .filtros input:focus {{ border-color: var(--accent); }}
  .filtros input::placeholder {{ color: var(--muted); }}

  .btn-filtro {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    cursor: pointer;
    font-family: 'Sora', sans-serif;
    font-size: 0.82rem;
    padding: 0.55rem 1rem;
    transition: all 0.15s;
    white-space: nowrap;
  }}

  .btn-filtro:hover,
  .btn-filtro.ativo {{ background: var(--accent); border-color: var(--accent); color: #fff; }}

  /* ── Tabela ── */
  .tabela-wrap {{ overflow-x: auto; border-radius: 10px; border: 1px solid var(--border); }}

  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
  }}

  thead th {{
    background: #1c2128;
    color: var(--muted);
    font-weight: 600;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 0.75rem 1rem;
    text-align: left;
    border-bottom: 1px solid var(--border);
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
  }}

  thead th:hover {{ color: var(--text); }}
  thead th .sort-icon {{ margin-left: 4px; opacity: 0.4; }}

  tbody tr {{
    border-bottom: 1px solid var(--border);
    transition: background 0.1s;
  }}

  tbody tr:last-child {{ border-bottom: none; }}
  tbody tr:hover {{ background: rgba(59,130,246,0.05); }}

  td {{ padding: 0.75rem 1rem; vertical-align: middle; }}

  .td-nome {{
    font-weight: 600;
    max-width: 280px;
  }}

  .td-doc {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    color: var(--muted);
    white-space: nowrap;
  }}

  .td-data {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem;
    white-space: nowrap;
  }}

  .td-dias {{
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600;
    white-space: nowrap;
  }}

  .pill {{
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0.3rem 0.75rem;
    white-space: nowrap;
  }}

  .pill.valido   {{ background: var(--valido-bg);   color: var(--valido);  border: 1px solid var(--valido); }}
  .pill.atencao  {{ background: var(--atencao-bg);  color: var(--atencao); border: 1px solid var(--atencao); }}
  .pill.vencido  {{ background: var(--vencido-bg);  color: var(--vencido); border: 1px solid var(--vencido); }}

  .td-dias.valido  {{ color: var(--valido); }}
  .td-dias.atencao {{ color: var(--atencao); }}
  .td-dias.vencido {{ color: var(--vencido); }}

  .sem-dados {{
    text-align: center;
    padding: 3rem;
    color: var(--muted);
  }}

  /* ── Rodapé ── */
  .footer {{
    margin-top: 2rem;
    display: flex;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.5rem;
    font-size: 0.78rem;
    color: var(--muted);
  }}

  .btn-exportar {{
    background: var(--accent);
    border: none;
    border-radius: 8px;
    color: #fff;
    cursor: pointer;
    font-family: 'Sora', sans-serif;
    font-size: 0.82rem;
    font-weight: 600;
    padding: 0.55rem 1.2rem;
    transition: opacity 0.15s;
  }}

  .btn-exportar:hover {{ opacity: 0.85; }}
</style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <h1>🔐 Certificados Digitais</h1>
    <p>Gerado em {data_geracao} &nbsp;·&nbsp; Validade padrão: {validade_dias} dias</p>
  </div>
  <div class="badge-pasta">📁 {pasta}</div>
</div>

<div class="resumo">
  <div class="card total">
    <div class="numero">{total}</div>
    <div class="label">Total</div>
  </div>
  <div class="card valido">
    <div class="numero">{n_valido}</div>
    <div class="label">Válidos</div>
  </div>
  <div class="card atencao">
    <div class="numero">{n_atencao}</div>
    <div class="label">Vencendo em breve</div>
  </div>
  <div class="card vencido">
    <div class="numero">{n_vencido}</div>
    <div class="label">Vencidos</div>
  </div>
</div>

<div class="filtros">
  <input id="busca" type="text" placeholder="🔍  Buscar por nome, CNPJ/CPF ou arquivo…" oninput="filtrar()">
  <button class="btn-filtro ativo" onclick="filtrarStatus('todos', this)">Todos</button>
  <button class="btn-filtro" onclick="filtrarStatus('valido', this)">✅ Válidos</button>
  <button class="btn-filtro" onclick="filtrarStatus('atencao', this)">⚠️ Atenção</button>
  <button class="btn-filtro" onclick="filtrarStatus('vencido', this)">❌ Vencidos</button>
  <button class="btn-exportar" onclick="exportarCSV()">⬇ Exportar CSV</button>
</div>

<div class="tabela-wrap">
  <table id="tabela">
    <thead>
      <tr>
        <th onclick="ordenar('razao_social')">Razão Social <span class="sort-icon">⇅</span></th>
        <th onclick="ordenar('documento')">CNPJ / CPF <span class="sort-icon">⇅</span></th>
        <th onclick="ordenar('instalacao')">Instalação <span class="sort-icon">⇅</span></th>
        <th onclick="ordenar('vencimento')">Vencimento <span class="sort-icon">⇅</span></th>
        <th onclick="ordenar('dias_restantes')">Dias restantes <span class="sort-icon">⇅</span></th>
        <th onclick="ordenar('status')">Status <span class="sort-icon">⇅</span></th>
        <th>Arquivo</th>
      </tr>
    </thead>
    <tbody id="corpo"></tbody>
  </table>
</div>

<div class="footer">
  <span id="contador"></span>
</div>

<script>
const dados = {dados_json};
let filtroStatus = 'todos';
let colOrdem = 'dias_restantes';
let ascOrdem = true;

function filtrar() {{
  const busca = document.getElementById('busca').value.toLowerCase();
  return dados.filter(d => {{
    const matchBusca = !busca ||
      d.razao_social.toLowerCase().includes(busca) ||
      d.documento.includes(busca) ||
      d.nome_arquivo.toLowerCase().includes(busca);
    const matchStatus = filtroStatus === 'todos' || d.classe === filtroStatus;
    return matchBusca && matchStatus;
  }});
}}

function renderizar() {{
  const lista = filtrar().sort((a, b) => {{
    let va = a[colOrdem], vb = b[colOrdem];
    if (colOrdem === 'dias_restantes') {{ va = +va; vb = +vb; }}
    if (typeof va === 'string') va = va.toLowerCase();
    if (typeof vb === 'string') vb = vb.toLowerCase();
    return ascOrdem ? (va > vb ? 1 : -1) : (va < vb ? 1 : -1);
  }});

  const corpo = document.getElementById('corpo');
  if (!lista.length) {{
    corpo.innerHTML = '<tr><td colspan="7" class="sem-dados">Nenhum certificado encontrado.</td></tr>';
  }} else {{
    corpo.innerHTML = lista.map(d => `
      <tr>
        <td class="td-nome">${{d.razao_social}}</td>
        <td class="td-doc">${{d.documento}}</td>
        <td class="td-data">${{d.instalacao}}</td>
        <td class="td-data">${{d.vencimento}}</td>
        <td class="td-dias ${{d.classe}}">${{d.dias_restantes < 0 ? d.dias_restantes + ' dias' : d.dias_restantes + ' dias'}}</td>
        <td><span class="pill ${{d.classe}}">${{d.emoji}} ${{d.status}}</span></td>
        <td class="td-doc" title="${{d.caminho}}">${{d.nome_arquivo}}</td>
      </tr>`).join('');
  }}

  document.getElementById('contador').textContent =
    `Exibindo ${{lista.length}} de ${{dados.length}} certificados`;
}}

function filtrarStatus(status, btn) {{
  filtroStatus = status;
  document.querySelectorAll('.btn-filtro').forEach(b => b.classList.remove('ativo'));
  btn.classList.add('ativo');
  renderizar();
}}

function ordenar(col) {{
  if (colOrdem === col) ascOrdem = !ascOrdem;
  else {{ colOrdem = col; ascOrdem = true; }}
  renderizar();
}}

function exportarCSV() {{
  const lista = filtrar();
  const cabecalho = ['Razão Social','CNPJ/CPF','Instalação','Vencimento','Dias Restantes','Status','Arquivo'];
  const linhas = lista.map(d =>
    [d.razao_social, d.documento, d.instalacao, d.vencimento, d.dias_restantes, d.status, d.nome_arquivo]
    .map(v => `"${{String(v).replace(/"/g,'""')}}"`)
    .join(';')
  );
  const csv = [cabecalho.join(';'), ...linhas].join('\\n');
  const blob = new Blob(['\\uFEFF' + csv], {{type: 'text/csv;charset=utf-8;'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'certificados_' + new Date().toISOString().slice(0,10) + '.csv';
  a.click();
}}

renderizar();
</script>
</body>
</html>
"""


def gerar_html(certificados: list, pasta: str, saida: str) -> None:
    contagem = {"valido": 0, "atencao": 0, "vencido": 0}
    for c in certificados:
        contagem[c["classe"]] += 1

    html = HTML_TEMPLATE.format(
        data_geracao   = datetime.now().strftime("%d/%m/%Y %H:%M"),
        validade_dias  = VALIDADE_DIAS,
        pasta          = pasta,
        total          = len(certificados),
        n_valido       = contagem["valido"],
        n_atencao      = contagem["atencao"],
        n_vencido      = contagem["vencido"],
        dados_json     = json.dumps(certificados, ensure_ascii=False),
    )

    with open(saida, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ Relatório gerado: {saida}")


# ─── Entrada principal ─────────────────────────────────────────────────────────

def main():

    def selecionar_e_gerar():
        pasta = filedialog.askdirectory(
            title="Selecione a pasta com os certificados digitais (.pfx)"
        )
        if not pasta:
            return

        nome_saida    = f"relatorio_certificados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        caminho_saida = str(PASTA_DOWNLOADS / nome_saida)

        btn_gerar.config(state="disabled", text="⏳  Gerando relatório...")
        root.update()

        try:
            certificados = escanear_pasta(pasta)
            if not certificados:
                messagebox.showwarning(
                    "Atenção",
                    "Nenhum certificado .pfx ou .p12 encontrado na pasta selecionada."
                )
                return

            gerar_html(certificados, pasta, caminho_saida)

            validos  = sum(1 for c in certificados if c["classe"] == "valido")
            atencao  = sum(1 for c in certificados if c["classe"] == "atencao")
            vencidos = sum(1 for c in certificados if c["classe"] == "vencido")

            dialog = tk.Toplevel(root)
            dialog.title("Relatório Gerado")
            dialog.configure(bg="#0d1117")
            dialog.resizable(False, False)
            dialog.grab_set()
            try:
                dialog.iconbitmap(recurso("icone.ico"))
            except Exception:
                pass

            # ── Cabeçalho verde ───────────────────────────────────────────
            tk.Frame(dialog, bg="#052e16", height=6).pack(fill="x")

            frame_topo = tk.Frame(dialog, bg="#052e16")
            frame_topo.pack(fill="x", padx=0, pady=0)

            tk.Label(
                frame_topo, text="✅  Relatório Gerado com Sucesso",
                font=("Segoe UI", 11, "bold"), fg="#22c55e", bg="#052e16",
                padx=24, pady=14
            ).pack(anchor="w")

            tk.Frame(dialog, bg="#21262d", height=1).pack(fill="x")

            # ── Corpo ─────────────────────────────────────────────────────
            frame_corpo = tk.Frame(dialog, bg="#0d1117")
            frame_corpo.pack(padx=28, pady=20, fill="x")

            tk.Label(
                frame_corpo,
                text=f"{len(certificados)} certificado(s) encontrado(s)",
                font=("Segoe UI", 10), fg="#7d8590", bg="#0d1117"
            ).pack(anchor="w", pady=(0, 14))

            # Cards de contagem
            frame_cards = tk.Frame(frame_corpo, bg="#0d1117")
            frame_cards.pack(fill="x", pady=(0, 18))

            for emoji, rotulo, valor, cor, bg_cor in [
                ("✅", "Válidos",           validos,                  "#22c55e", "#052e16"),
                ("⚠️",  "Vencendo em breve", atencao,                  "#f59e0b", "#451a03"),
                ("❌", "Vencidos",          vencidos,                 "#ef4444", "#3b0000"),
            ]:
                card = tk.Frame(frame_cards, bg=bg_cor,
                                highlightthickness=1, highlightbackground=cor)
                card.pack(side="left", expand=True, fill="x", padx=(0, 8))

                tk.Label(card, text=str(valor),
                         font=("Segoe UI", 18, "bold"),
                         fg=cor, bg=bg_cor).pack(pady=(10, 2))
                tk.Label(card, text=f"{emoji} {rotulo}",
                         font=("Segoe UI", 7), fg=cor, bg=bg_cor).pack(pady=(0, 10))

            # Caminho do arquivo
            tk.Frame(frame_corpo, bg="#21262d", height=1).pack(fill="x", pady=(0, 12))

            tk.Label(
                frame_corpo, text="Arquivo salvo em:",
                font=("Segoe UI", 8), fg="#7d8590", bg="#0d1117"
            ).pack(anchor="w")

            tk.Label(
                frame_corpo, text=caminho_saida,
                font=("JetBrains Mono", 8), fg="#3b82f6", bg="#0d1117",
                wraplength=360, justify="left"
            ).pack(anchor="w", pady=(2, 0))

            # ── Botão OK ──────────────────────────────────────────────────
            tk.Frame(dialog, bg="#21262d", height=1).pack(fill="x")

            frame_btn = tk.Frame(dialog, bg="#161b22")
            frame_btn.pack(fill="x", padx=20, pady=14)

            tk.Button(
                frame_btn, text="OK  —  Abrir no Navegador",
                font=("Segoe UI", 9, "bold"),
                fg="#ffffff", bg="#3b82f6",
                activeforeground="#ffffff", activebackground="#2563eb",
                relief="flat", cursor="hand2", padx=20, pady=8,
                command=dialog.destroy
            ).pack(side="right")

            tk.Button(
                frame_btn, text="Fechar",
                font=("Segoe UI", 9),
                fg="#7d8590", bg="#161b22",
                activeforeground="#e6edf3", activebackground="#21262d",
                relief="flat", cursor="hand2", padx=16, pady=8,
                command=dialog.destroy
            ).pack(side="right", padx=(0, 8))

            dialog.wait_window()

            import webbrowser
            webbrowser.open(Path(caminho_saida).resolve().as_uri())

        except Exception as e:
            messagebox.showerror("Erro", f"Ocorreu um erro inesperado:\n{e}")
        finally:
            btn_gerar.config(state="normal", text="📂  Selecionar Pasta e Gerar Relatório")

    # ── Janela principal ───────────────────────────────────────────────────────
    root = tk.Tk()
    root.title("Scanner de Certificados Digitais")
    root.configure(bg="#00030a")
    root.resizable(False, False)

    try:
        root.iconbitmap(recurso("icone.ico"))
    except Exception:
        pass

    # ── Logo ──────────────────────────────────────────────────────────────────
    try:
        img_raw  = tk.PhotoImage(file=recurso("icone.png"))
        # Exibe a ~350 px independente do tamanho original
        fator    = max(1, img_raw.width() // 350)
        img      = img_raw.subsample(fator, fator)
        lbl_logo = tk.Label(root, image=img, bg="#0d1117", borderwidth=0)
        lbl_logo.image = img
        lbl_logo.pack(pady=(20, 0))
    except Exception:
        pass

    # ── Caixa de instruções ───────────────────────────────────────────────────
    frame_inst = tk.Frame(
        root, bg="#161b22",
        highlightthickness=1, highlightbackground="#21262d"
    )
    frame_inst.pack(padx=30, pady=(0, 12), fill="x")

    instrucoes = (
        "Como usar:\n\n"
        "  1. Clique no botão abaixo e selecione a pasta que\n"
        "     contém os certificados digitais (.pfx ou .p12).\n\n"
        "  2. O programa verifica automaticamente a validade de\n"
        "     cada certificado com base na data do arquivo.\n\n"
        "  3. O relatório HTML será aberto no seu navegador.\n\n"
        f"  ⚠️  O arquivo será salvo automaticamente em:\n"
        f"     {PASTA_DOWNLOADS}"
    )

    tk.Label(
        frame_inst, text=instrucoes,
        font=("Segoe UI", 9), fg="#e6edf3", bg="#161b22",
        justify="left", padx=18, pady=14, wraplength=410
    ).pack()

    # ── Legenda de status ─────────────────────────────────────────────────────
    frame_leg = tk.Frame(root, bg="#0d1117")
    frame_leg.pack(pady=(4, 0))

    for emoji, texto, cor in [
        ("✅", "Válido",               "#22c55e"),
        ("⚠️",  f"Atenção (≤{ALERTA_DIAS}d)", "#f59e0b"),
        ("❌", "Vencido",              "#ef4444"),
    ]:
        col = tk.Frame(frame_leg, bg="#0d1117")
        col.pack(side="left", padx=14)
        tk.Label(col, text=f"{emoji} {texto}",
                 font=("Segoe UI", 8), fg=cor, bg="#0d1117").pack()

    # ── Botão principal ───────────────────────────────────────────────────────
    btn_gerar = tk.Button(
        root,
        text="📂  Selecionar Pasta e Gerar Relatório",
        font=("Segoe UI", 10, "bold"),
        fg="#ffffff",         bg="#3b82f6",
        activeforeground="#ffffff", activebackground="#2563eb",
        relief="flat", cursor="hand2",
        padx=22, pady=11,
        command=selecionar_e_gerar,
    )
    btn_gerar.pack(pady=22)

    # ── Rodapé ────────────────────────────────────────────────────────────────
    tk.Label(
        root,
        text=f"Validade padrão: {VALIDADE_DIAS} dias  ·  Alerta: {ALERTA_DIAS} dias antes do vencimento",
        font=("Segoe UI", 8), fg="#7d8590", bg="#0d1117"
    ).pack(pady=(0, 20))

    root.mainloop()

if __name__ == "__main__":
    main()