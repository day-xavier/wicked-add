from config import PROPORCAO_ALVO, TOLERANCIA, TAMANHO_CARTA
import io
from PIL import Image, ImageOps

async def verificar_proporcao(m, bot):
    # Se foi enviada como foto normal, o Telegram já entrega largura e altura sem baixar nada
    if m.photo:
        largura, altura = m.photo[-1].width, m.photo[-1].height
    else:
        # Se foi enviada como documento/arquivo, baixa na memória para ler as dimensões
        arquivo_tg = await bot.get_file(m.document.file_id)
        buffer = io.BytesIO()
        await arquivo_tg.download_to_memory(out=buffer)
        buffer.seek(0)
        with Image.open(buffer) as img:
            largura, altura = img.size

    proporcao_atual = largura / altura
    dentro_do_padrao = abs(proporcao_atual - PROPORCAO_ALVO) <= TOLERANCIA
    return dentro_do_padrao, largura, altura

async def recortar_no_centro(bot, file_id: str) -> io.BytesIO:
    arquivo_tg = await bot.get_file(file_id)
    buffer_entrada = io.BytesIO()
    await arquivo_tg.download_to_memory(out=buffer_entrada)
    buffer_entrada.seek(0)

    with Image.open(buffer_entrada) as img:
        img = img.convert("RGB")
        # Recorta na proporção 3:4 exatamente a partir do centro (0.5, 0.5) sem achatar a imagem
        img_cortada = ImageOps.fit(
            img,
            TAMANHO_CARTA,
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        buffer_saida = io.BytesIO()
        img_cortada.save(buffer_saida, format="JPEG", quality=92)
        buffer_saida.seek(0)
        return buffer_saida
