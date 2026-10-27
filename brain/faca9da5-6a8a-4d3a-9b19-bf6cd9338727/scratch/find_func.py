import sys
sys.path.insert(0, r'C:\projetos\gerador_atividades')

with open(r'C:\projetos\gerador_atividades\app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Encontra o início e fim da função planejamento_docente
start_marker = '# =========================\n# PLANEJAMENTO DOCENTE\n# =========================\n@app.route("/planejamento_docente", methods=["GET", "POST"])\ndef planejamento_docente():'
end_marker = '\n    return render_template("planejamento_docente.html")\n'

start_idx = content.find(start_marker)
end_idx = content.find(end_marker, start_idx) + len(end_marker)

print(f"Start: {start_idx}, End: {end_idx}")
print("--- Trecho encontrado ---")
print(repr(content[start_idx:start_idx+200]))
print("--- Fim ---")
