import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
GRUPO = int(os.getenv("GRUPO_ADICOES"))
TOPICO_NOTIF = int(os.getenv("TOPICO_NOTIFICACOES"))
if not TOKEN:
    raise ValueError("❌ BOT_TOKEN não configurado em .env")

RARIDADES = {"rara", "lendaria"}            # ajuste conforme as suas
CATEGORIAS = {"musiwand", "animawand", "cinewand", "gamewand", "multiwand"}
MAX_ABERTOS = 3                             # pedidos abertos por usuário
TEMPO_SEM_RESPOSTA = 3600                   # 1 hora
TEMPO_DELETAR = 86400                       # 24 horas depois de fechar
PROPORCAO_ALVO = 3 / 4                      # 0.75 (padrão 3:4 vertical)
TOLERANCIA = 0.02                           # 2% de margem para variações de pixels
TAMANHO_CARTA = (600, 800)                  # Resolução 3:4 gerada pelo /recortar

USO = (
    "📌 Envie a imagem da carta juntamente com esta legenda:\n\n"
    "/adicao nome, raridade, coleção, categoria, tag, créditos\n\n"
    "Tag e créditos são opcionais (deixe vazio se não tiver).\n"
    "Exemplo: /adicao Batman, lendaria, DC Comics, Liga da Justiça\n\n"
    "✂️ Imagem fora da proporção 3:4? Envie a foto com a legenda /recortar "
    "(ou responda a uma foto com /recortar) para cortar automaticamente no centro!"
)