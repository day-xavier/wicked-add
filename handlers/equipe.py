
from config import GRUPO, TEMPO_DELETAR
from telegram import Update
from telegram.ext import ContextTypes
from services.pedidos import pedidos
from jobs import excluir_topico, reagendar_aviso

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


async def id_grupo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"ID do grupo: {update.effective_chat.id}\nID do tópico: {update.message.message_thread_id}")