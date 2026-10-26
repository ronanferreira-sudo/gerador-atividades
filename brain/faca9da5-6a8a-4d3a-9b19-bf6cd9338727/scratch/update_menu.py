with open(r'C:\projetos\gerador_atividades\templates\menu.html', 'r', encoding='utf-8') as f:
    html = f.read()

velho = """                <li class="nav-item">
                    <a class="nav-link" href="/planos">
                        Gerar Plano
                    </a>
                </li>

                <li class="nav-item">
                    <a class="nav-link" href="/listar_planos">
                        Planos de Aula
                    </a>
                </li>"""

novo = """                <li class="nav-item dropdown">
                    <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                        Planejamento Docente
                    </a>
                    <ul class="dropdown-menu">
                        <li><a class="dropdown-item" href="/planejamento_docente">+ Gerar Planejamento (Excel)</a></li>
                        <li><a class="dropdown-item" href="/listar_planejamentos">Meus Planejamentos</a></li>
                    </ul>
                </li>

                <li class="nav-item dropdown">
                    <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                        Planos de Aula
                    </a>
                    <ul class="dropdown-menu">
                        <li><a class="dropdown-item" href="/listar_cursos">Ver Cursos e Planos</a></li>
                    </ul>
                </li>"""

html_norm = html.replace('\r\n', '\n')
velho_norm = velho.replace('\r\n', '\n')
novo_norm = novo.replace('\r\n', '\n')

if velho_norm in html_norm:
    html_norm = html_norm.replace(velho_norm, novo_norm)
    with open(r'C:\projetos\gerador_atividades\templates\menu.html', 'w', encoding='utf-8') as f:
        f.write(html_norm)
    print("menu.html atualizado!")
else:
    print("Trecho não encontrado em menu.html.")
