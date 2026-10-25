import os
import html
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          ContextTypes, PicklePersistence, filters)
import io
from PIL import Image, ImageOps

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


async def notificar_sem_resposta(context: ContextTypes.DEFAULT_TYPE):
    d = context.job.data
    try:
        await context.bot.send_message(
            GRUPO, message_thread_id=TOPICO_NOTIF,
            text=(f"⏰ PEDIDO AGUARDANDO\n\n📂 {d['nome_topico']}\n🆔 Tópico: {d['thread_id']}\n\n"
                  "Ainda não foi respondido nem finalizado."),
        )
    except Exception as e:
        print("Erro ao notificar:", e)


def reagendar_aviso(context, thread_id, nome_topico):
    for job in context.job_queue.get_jobs_by_name(f"sem_resposta_{thread_id}"):
        job.schedule_removal()
    context.job_queue.run_once(
        notificar_sem_resposta, when=TEMPO_SEM_RESPOSTA,
        data={"thread_id": thread_id, "nome_topico": nome_topico},
        name=f"sem_resposta_{thread_id}",
    )


# /responder (mod no tópico OU usuário no privado)
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = update.message
    texto = " ".join(context.args)
    if not texto:
        await m.reply_text("Use: /responder sua mensagem")
        return

    # moderador, dentro de um tópico
    if update.effective_chat.id == GRUPO and m.message_thread_id is not None:
        p = pedidos(context).get(m.message_thread_id)
        if not p:
            await m.reply_text("❌ Não encontrei o usuário deste tópico.")
            return
        await context.bot.send_message(
            p["usuario_id"],
            f"💬 RESPOSTA DA EQUIPE (pedido #{p['numero']})\n\n{texto}\n\nPra responder: /responder sua mensagem",
        )
        reagendar_aviso(context, m.message_thread_id, p["nome_topico"])
        await m.reply_text("✅ Enviado ao usuário. Contador reiniciado.")
        return

    # usuário, no privado
    if update.effective_chat.id > 0:
        abertos = [(t, p) for t, p in pedidos(context).items()
                   if p["usuario_id"] == update.effective_user.id and p["status"] == "aberto"]
        if not abertos:
            await m.reply_text("❌ Você não tem nenhum pedido em aberto.")
            return
        thread_id, p = abertos[-1]          # o mais recente
        await context.bot.send_message(
            GRUPO, message_thread_id=thread_id, text=f"👤 RESPOSTA DO USUÁRIO\n\n{texto}")
        await m.reply_text(f"✅ Enviado à equipe (pedido #{p['numero']}).")
        return

    await m.reply_text("❌ Use /responder dentro de um pedido ou no privado do bot.")


# /aprovar [id da carta]  e  /rejeitar [motivo]  (dentro do tópico)
async def finalizar(update: Update, context: ContextTypes.DEFAULT_TYPE, status: str):
    m = update.message
    thread_id = m.message_thread_id
    p = pedidos(context).get(thread_id) if thread_id else None
    if update.effective_chat.id != GRUPO or not p:
        await m.reply_text("Use este comando dentro do tópico de um pedido.")
        return
    if p["status"] != "aberto":
        await m.reply_text("⚠️ Este pedido já foi finalizado.")
        return

    extra = " ".join(context.args)
    if status == "aprovado":
        msg = f"✅ Seu pedido #{p['numero']} ({p['nome']}) foi aprovado!"
        if extra:
            msg += f"\nID da carta: {extra}"
    else:
        msg = f"❌ Seu pedido #{p['numero']} ({p['nome']}) foi rejeitado."
        if extra:
            msg += f"\nMotivo: {extra}"

    p["status"] = status
    for job in context.job_queue.get_jobs_by_name(f"sem_resposta_{thread_id}"):
        job.schedule_removal()

    try:
        await context.bot.send_message(p["usuario_id"], msg)
    except Exception as e:
        await m.reply_text("⚠️ Não consegui avisar o usuário (ele pode ter bloqueado o bot).")
        print("Erro ao avisar usuário:", e)

    emoji = "✅" if status == "aprovado" else "❌"
    try:
        await context.bot.edit_forum_topic(GRUPO, thread_id, name=f"{emoji} {p['nome_topico']}"[:128])
        await context.bot.close_forum_topic(GRUPO, thread_id)
    except Exception as e:
        print("Erro ao fechar tópico:", e)

    context.job_queue.run_once(
        excluir_topico, when=TEMPO_DELETAR,
        data={"thread_id": thread_id, "nome_topico": p["nome_topico"]},
        name=f"excluir_{thread_id}",
    )
    await m.reply_text(f"🔒 Pedido {status}. O tópico será excluído em 24h.")


async def aprovar(update, context):
    await finalizar(update, context, "aprovado")


async def rejeitar(update, context):
    await finalizar(update, context, "rejeitado")


async def excluir_topico(context: ContextTypes.DEFAULT_TYPE):
    d = context.job.data
    try:
        await context.bot.send_message(
            GRUPO, message_thread_id=TOPICO_NOTIF,
            text=f"🗑️ TÓPICO EXCLUÍDO\n\n📂 {d['nome_topico']}\n🆔 {d['thread_id']}")
        await context.bot.delete_forum_topic(GRUPO, d["thread_id"])
    except Exception as e:
        print("Erro ao excluir tópico:", e)


async def id_grupo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"ID do grupo: {update.effective_chat.id}\nID do tópico: {update.message.message_thread_id}")


app = (Application.builder().token(TOKEN)
       .persistence(PicklePersistence(filepath="adicoes.pkl")).build())

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("adicao", start))     # sem imagem: mostra como usar
app.add_handler(MessageHandler(
    filters.ChatType.PRIVATE & filters.CaptionRegex(r"^/adicao") &
    (filters.PHOTO | filters.Document.IMAGE), adicao))
app.add_handler(CommandHandler("responder", responder))
app.add_handler(CommandHandler("aprovar", aprovar))
app.add_handler(CommandHandler("rejeitar", rejeitar))
app.add_handler(CommandHandler("id", id_grupo))
app.add_handler(CommandHandler("recortar", recortar))
app.add_handler(MessageHandler(
    filters.ChatType.PRIVATE & filters.CaptionRegex(r"^/recortar") &
    (filters.PHOTO | filters.Document.IMAGE), recortar))

print("Bot de adições iniciado!")
app.run_polling()