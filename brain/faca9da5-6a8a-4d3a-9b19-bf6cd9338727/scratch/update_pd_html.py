with open(r'C:\projetos\gerador_atividades\templates\planejamento_docente.html', 'r', encoding='utf-8') as f:
    html = f.read()

velho = """                    <!-- Botão de Submissão -->
                    <div class="d-grid gap-2">
                        <button type="submit" class="btn btn-primary btn-lg fw-bold py-3 shadow-sm" id="btnGerar">
                            <span id="btnIcon">🚀</span> Gerar Planejamento Docente no Excel
                        </button>
                    </div>"""

novo = """                    <!-- Botão de Submissão -->
                    <div class="d-grid gap-2">
                        <button type="submit" class="btn btn-primary btn-lg fw-bold py-3 shadow-sm" id="btnGerar">
                            <span id="btnIcon">📥</span> Gerar e Baixar Planejamento Docente (Excel)
                        </button>
                        <p class="text-center text-muted small mt-2 mb-0">
                            Ao clicar, a IA gera a distribuição de aulas e o arquivo Excel é baixado imediatamente.<br>
                            Você poderá solicitar os <strong>Planos de Aula</strong> e <strong>Atividades</strong> separadamente quando desejar.
                        </p>
                    </div>"""

html_norm = html.replace('\r\n', '\n')
velho_norm = velho.replace('\r\n', '\n')
novo_norm = novo.replace('\r\n', '\n')

if velho_norm in html_norm:
    html_norm = html_norm.replace(velho_norm, novo_norm)
    with open(r'C:\projetos\gerador_atividades\templates\planejamento_docente.html', 'w', encoding='utf-8') as f:
        f.write(html_norm)
    print("planejamento_docente.html atualizado!")
else:
    print("Trecho não encontrado em planejamento_docente.html")
