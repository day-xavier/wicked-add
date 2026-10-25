import os
import html
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          ContextTypes, PicklePersistence, filters)

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

USO = (
    "📌 Envie a imagem da carta juntamente com esta legenda:\n\n"
    "/adicao nome, raridade, coleção, categoria, tag, créditos\n\n"
    "Tag e créditos são opcionais (deixe vazio se não tiver).\n"
    "Exemplo: /adicao Batman, lendaria, DC Comics, Liga da Justiça"
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

print("Bot de adições iniciado!")
app.run_polling()