with open(r'C:\projetos\gerador_atividades\templates\planos.html', 'r', encoding='utf-8') as f:
    html = f.read()

velho = """                <div class="text-center mb-4">
                    <h2 class="fw-bold">Importar Plano de Curso</h2>
                    <p class="text-muted">Faca upload do PDF do plano de curso para gerar os planos de aula automaticamente</p>
                </div>"""

novo = """                <div class="alert alert-info border-0 shadow-sm d-flex align-items-center mb-4">
                    <div class="me-3 fs-3">ℹ️</div>
                    <div>
                        <strong>Novo Fluxo Pedagógico Recomendado:</strong>
                        <p class="mb-1 small">
                            O plano de curso deve gerar primeiro o <strong>Planejamento Docente</strong> (com Taxonomia de Bloom e planilha oficial), e deste são gerados os <strong>Planos de Aula</strong> e <strong>Atividades</strong>.
                        </p>
                        <a href="/planejamento_docente" class="btn btn-sm btn-primary fw-bold mt-1">
                            🚀 Ir para Gerador de Planejamento Docente
                        </a>
                    </div>
                </div>

                <div class="text-center mb-4">
                    <h2 class="fw-bold">Importar Plano de Curso</h2>
                    <p class="text-muted">Ou use o formulário rápido abaixo para gerar planos de aula diretos</p>
                </div>"""

html_norm = html.replace('\r\n', '\n')
velho_norm = velho.replace('\r\n', '\n')
novo_norm = novo.replace('\r\n', '\n')

if velho_norm in html_norm:
    html_norm = html_norm.replace(velho_norm, novo_norm)
    with open(r'C:\projetos\gerador_atividades\templates\planos.html', 'w', encoding='utf-8') as f:
        f.write(html_norm)
    print("planos.html atualizado com orientação do fluxo!")
else:
    print("Trecho não encontrado em planos.html")
