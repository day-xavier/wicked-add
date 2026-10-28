from telegram.ext import (Application, CommandHandler, MessageHandler,
                         PicklePersistence, filters)

from config import TOKEN
from handlers.usuario import start, adicao, recortar
from handlers.equipe import responder, aprovar, rejeitar, id_grupo

def main():

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

if __name__ == "__main__":
    main()