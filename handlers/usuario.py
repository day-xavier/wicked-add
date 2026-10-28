# handlers/usuario.py
import html
from config import GRUPO, TOPICO_NOTIF, MAX_ABERTOS, TEMPO_SEM_RESPOSTA, USO
from telegram import Update
from telegram.ext import ContextTypes
from services.imagens import verificar_proporcao, recortar_no_centro
from services.pedidos import pedidos, interpretar
from jobs import notificar_sem_resposta

# /recortar na legenda da foto OU respondendo a uma foto
async def recortar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = update.message

    # Verifica se a imagem está na própria mensagem ou na mensagem que o utilizador respondeu
    alvo = m if (m.photo or m.document) else m.reply_to_message
    eh_doc_imagem = bool(alvo and alvo.document and alvo.document.mime_type and alvo.document.mime_type.startswith("image/"))

    if not alvo or not (alvo.photo or eh_doc_imagem):
        await m.reply_text(
            "✂️ <b>Como usar o recorte automático (3:4):</b>\n\n"
            "• Envie uma foto com a legenda <code>/recortar</code>, ou\n"
            "• Responda a uma foto que você já enviou com <code>/recortar</code>.\n\n"
            "⚠️ <i>O recorte é feito no centro da imagem. Se o personagem/foco estiver nos cantos, faça o recorte manualmente.</i>",
            parse_mode="HTML",
        )
        return

    file_id = alvo.photo[-1].file_id if alvo.photo else alvo.document.file_id

    try:
        img_pronta = await recortar_no_centro(context.bot, file_id)

        # Se o utilizador respondeu a uma foto que já tinha a legenda "/adicao ...", devolve a legenda pronta para copiar
        legenda_antiga = (alvo.caption or "").strip()
        texto = "✅ <b>Imagem recortada para o padrão 3:4!</b>\n\n"
        if legenda_antiga.startswith("/adicao"):
            texto += (
                "📋 Se o foco ficou bom, envie esta imagem recortada usando a sua legenda (toque para copiar):\n"
                f"<code>{html.escape(legenda_antiga)}</code>\n\n"
            )
        texto += "⚠️ <i>Caso o foco principal tenha sido cortado, recorte a imagem original manualmente antes de enviar.</i>"

        await m.reply_photo(photo=img_pronta, caption=texto, parse_mode="HTML")
    except Exception as e:
        print("ERRO AO RECORTAR IMAGEM:", e)
        await m.reply_text("❌ Não consegui recortar esta imagem. Envie um ficheiro JPG ou PNG válido.")
        
# /start e /adicao sem imagem
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🔮 Olá! Aqui você pede a adição de novas cartas.\n\n{USO}")


# imagem + legenda "/adicao ..."
async def adicao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = update.message
    user = update.effective_user

    dados, erro = interpretar(m.caption or "")
    if erro:
        await m.reply_text(f"❌ {erro}\n\n{USO}")
        return

    abertos = [p for p in pedidos(context).values()
               if p["usuario_id"] == user.id and p["status"] == "aberto"]
    if len(abertos) >= MAX_ABERTOS:
        await m.reply_text(f"❌ Você já tem {MAX_ABERTOS} pedidos em aberto. Aguarde a equipe responder.")
        return

    eh_foto = bool(m.photo)
    file_id = m.photo[-1].file_id if eh_foto else m.document.file_id
    
    # Verifica se a imagem está na proporção 3:4 antes de criar o pedido
    try:
        proporcao_ok, larg, alt = await verificar_proporcao(m, context.bot)
    except Exception as e:
        print("ERRO AO LER IMAGEM:", e)
        await m.reply_text("❌ Não consegui verificar as dimensões da imagem. Envie um arquivo JPG ou PNG válido.")
        return

    if not proporcao_ok:
        await m.reply_text(
            f"❌ <b>Imagem fora da proporção padrão!</b>\n\n"
            f"📏 Tamanho enviado: <code>{larg}x{alt}px</code>\n"
            f"📐 Proporção exigida: <b>3:4</b> (ex: 600x800, 750x1000, 900x1200)\n\n"
            f"💡 <b>Como resolver:</b>\n"
            f"• Se o foco principal estiver no <b>centro</b>, responda a essa sua foto com /recortar que eu ajusto para você!\n"
            f"• Se o foco estiver fora do centro, recorte manualmente na proporção 3:4 e envie novamente.",
            parse_mode="HTML",
        )
        return

    n = context.bot_data["contador"] = context.bot_data.get("contador", 0) + 1
    nome_topico = f"Adição #{n} - {dados['nome']} ({dados['col']})"[:128]

    try:
        topico = await context.bot.create_forum_topic(chat_id=GRUPO, name=nome_topico)
        thread_id = topico.message_thread_id

        pedidos(context)[thread_id] = {
            "usuario_id": user.id, "nome_topico": nome_topico,
            "numero": n, "status": "aberto", **dados,
        }

        legenda = (
            "🃏 NOVO PEDIDO DE ADIÇÃO\n\n"
            f"👤 {user.first_name} (@{user.username or 'sem username'}) | 🆔 {user.id}\n\n"
            f"Nome: {dados['nome']}\nRaridade: {dados['raridade']}\n"
            f"Categoria: {dados['categ']}\nColeção: {dados['col']}\n"
            f"Tag: {dados['tag'] or '-'}\nCréditos: {dados['creditos'] or '-'}"
        )
        enviar = context.bot.send_photo if eh_foto else context.bot.send_document
        await enviar(GRUPO, file_id, message_thread_id=thread_id, caption=legenda) \
            if eh_foto else await enviar(GRUPO, file_id, message_thread_id=thread_id, caption=legenda)

        # linha pronta pro /addcarta (toque pra copiar)
        linha = (f"/addcarta {dados['nome']},{dados['raridade']},{dados['col']},{dados['categ']},"
                 f"{dados['tag'] or ''},URL_DA_IMAGEM,{dados['creditos'] or ''}")
        await context.bot.send_message(
            GRUPO, message_thread_id=thread_id, parse_mode="HTML",
            text=f"<code>{html.escape(linha)}</code>\n\nDepois de cadastrar, use /aprovar [id da carta] ou /rejeitar [motivo].",
        )

        await context.bot.send_message(
            GRUPO, message_thread_id=TOPICO_NOTIF,
            text=f"🔔 NOVO PEDIDO DE ADIÇÃO\n\n📂 {nome_topico}\n👤 {user.first_name}",
        )

        context.job_queue.run_once(
            notificar_sem_resposta, when=TEMPO_SEM_RESPOSTA,
            data={"thread_id": thread_id, "nome_topico": nome_topico},
            name=f"sem_resposta_{thread_id}",
        )

        await m.reply_text(
            f"✅ Pedido #{n} recebido!\n"
            "A equipe vai analisar. Se precisarem de algo, você recebe aqui.\n"
            "Pra falar com a equipe: /responder sua mensagem"
        )
    except Exception as e:
        print("ERRO AO CRIAR PEDIDO:", e)
        await m.reply_text("❌ Não consegui registrar seu pedido agora. Tente de novo em instantes.")

