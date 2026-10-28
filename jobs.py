from config import GRUPO, TOPICO_NOTIF, TEMPO_SEM_RESPOSTA
from telegram.ext import ContextTypes

async def excluir_topico(context: ContextTypes.DEFAULT_TYPE):
    d = context.job.data
    try:
        await context.bot.send_message(
            GRUPO, message_thread_id=TOPICO_NOTIF,
            text=f"🗑️ TÓPICO EXCLUÍDO\n\n📂 {d['nome_topico']}\n🆔 {d['thread_id']}")
        await context.bot.delete_forum_topic(GRUPO, d["thread_id"])
    except Exception as e:
        print("Erro ao excluir tópico:", e)

def reagendar_aviso(context, thread_id, nome_topico):
    for job in context.job_queue.get_jobs_by_name(f"sem_resposta_{thread_id}"):
        job.schedule_removal()
    context.job_queue.run_once(
        notificar_sem_resposta, when=TEMPO_SEM_RESPOSTA,
        data={"thread_id": thread_id, "nome_topico": nome_topico},
        name=f"sem_resposta_{thread_id}",
    )

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