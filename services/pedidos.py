from config import RARIDADES, CATEGORIAS

def pedidos(context):
    # fica salvo em arquivo (PicklePersistence), então sobrevive a reinício
    return context.bot_data.setdefault("pedidos", {})


def interpretar(legenda: str):
    partes = legenda.split(None, 1)
    if len(partes) < 2:
        return None, "Faltam os dados da carta."
    campos = [c.strip() for c in partes[1].split(",")]
    if len(campos) < 4 or not all(campos[:4]):
        return None, "Preencha ao menos nome, raridade, coleção e categoria."
    nome, raridade, col, categ = campos[:4]
    if raridade.lower() not in RARIDADES:
        return None, f"Raridade inválida. Use: {', '.join(sorted(RARIDADES))}."
    if categ.lower() not in CATEGORIAS:
        return None, f"Categoria inválida. Use: {', '.join(c.capitalize() for c in sorted(CATEGORIAS))}."
    tag = campos[4] or None if len(campos) > 4 else None
    creditos = ", ".join(campos[5:]).strip() or None if len(campos) > 5 else None
    return {"nome": nome, "raridade": raridade.lower(), "col": col,
            "categ": categ.capitalize(), "tag": tag, "creditos": creditos}, None
