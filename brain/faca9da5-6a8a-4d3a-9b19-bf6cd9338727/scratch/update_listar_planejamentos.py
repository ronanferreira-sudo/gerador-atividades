with open(r'C:\projetos\gerador_atividades\templates\listar_planejamentos.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Substituir a coluna de ações
velho = """                        <td class="text-center">
                            <a href="/baixar_planejamento/{{ p[0] }}" class="btn btn-success btn-sm fw-bold me-1" title="Baixar arquivo Excel preenchido">
                                📥 Baixar Excel
                            </a>
                            <a href="/deletar_planejamento/{{ p[0] }}" class="btn btn-outline-danger btn-sm"
                               onclick="return confirm('Deseja realmente excluir este planejamento docente?')" title="Excluir">
                                🗑️
                            </a>
                        </td>"""

novo = """                        <td class="text-center">
                            {% if p[13] %}
                                <a href="/curso/{{ p[13] }}" class="btn btn-primary btn-sm fw-bold me-1" title="Ver Planos de Aula gerados a partir deste planejamento">
                                    📖 Ver Planos
                                </a>
                            {% else %}
                                <a href="/gerar_planos_planejamento/{{ p[0] }}" class="btn btn-warning btn-sm fw-bold me-1" title="Gerar os planos de aula para este planejamento">
                                    ⚡ Gerar Planos
                                </a>
                            {% endif %}
                            <a href="/baixar_planejamento/{{ p[0] }}" class="btn btn-success btn-sm fw-bold me-1" title="Baixar arquivo Excel preenchido">
                                📥 Excel
                            </a>
                            <a href="/deletar_planejamento/{{ p[0] }}" class="btn btn-outline-danger btn-sm"
                               onclick="return confirm('Deseja realmente excluir este planejamento docente e arquivos associados?')" title="Excluir">
                                🗑️
                            </a>
                        </td>"""

if velho in html:
    html = html.replace(velho, novo)
    with open(r'C:\projetos\gerador_atividades\templates\listar_planejamentos.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("listar_planejamentos.html atualizado!")
else:
    print("Aviso: trecho não encontrado diretamente, verificando quebras de linha...")
    html_normalized = html.replace('\r\n', '\n')
    velho_normalized = velho.replace('\r\n', '\n')
    if velho_normalized in html_normalized:
        html_normalized = html_normalized.replace(velho_normalized, novo.replace('\r\n', '\n'))
        with open(r'C:\projetos\gerador_atividades\templates\listar_planejamentos.html', 'w', encoding='utf-8') as f:
            f.write(html_normalized)
        print("listar_planejamentos.html atualizado após normalização!")
    else:
        print("Erro: não foi possível localizar bloco.")
