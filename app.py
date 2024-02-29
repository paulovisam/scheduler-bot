from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from ScheduleModel import ScheduleModel
from datetime import datetime, timedelta
import re
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.base import ConflictingIdError
import os
from dotenv import load_dotenv

load_dotenv()

scheduler = AsyncIOScheduler()

bot_token = os.getenv("BOT_TOKEN")
print(bot_token)
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
app = Client("app", api_id, api_hash, bot_token=bot_token)

cluster = {}
create_progress = {}
delete_progress = {}
get_id_progress = {}
tg_schedule = None
time_format = r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"

# TODO - Salvar agendamentos em um banco de dados
# TODO - Exibir agendamentos em botões, ao clicar informa detalhes sobre
# TODO - Avisar quando termina os agendamentos
# TODO - Suporte a msg com foto/video
# TODO - 
async def send_message(chat_destiny, message, chat_id, cluster_name, job_id):
    global cluster
    await app.send_message(chat_destiny, message)
    cluster[chat_id][cluster_name].remove(job_id)
    if len(cluster[chat_id][cluster_name]) == 0:
        await app.send_message(
            chat_id, f"Seu agendamento **{cluster_name}** foi finalizado! ⌛️✅"
        )
        del cluster[chat_id][cluster_name]
        print(cluster)


async def delete_jobs(chat_id, cluster_name):
    global cluster
    cluster_id = cluster[chat_id]
    for job in cluster_id[cluster_name]:
        scheduler.remove_job(job)
    del cluster_id[cluster_name]


async def schedule_message(tg_schedule: ScheduleModel, chat_id):
    global cluster
    submensagens = list(filter(lambda x: x != "", tg_schedule.message.split(";")))
    cluster_id = cluster[chat_id]
    if tg_schedule.freq == "D":
        cluster_id[tg_schedule.name] = []
        for i, submensagem in enumerate(submensagens):
            time = datetime.strptime(tg_schedule.time, "%H:%M").time()
            if time <= datetime.time(datetime.now()):
                if tg_schedule.step_day != 1:
                    data = (
                        datetime.now()
                        + timedelta(days=(tg_schedule.step_day * (i)))
                        + timedelta(days=1)
                    )
                else:
                    data = datetime.now() + timedelta(
                        days=(tg_schedule.step_day * (i + 1))
                    )
            else:
                data = datetime.now() + timedelta(days=(tg_schedule.step_day * (i)))
            data_hora = datetime.combine(data.date(), time)
            job_id = tg_schedule.name + "_" + str(i)
            job = scheduler.add_job(
                send_message,
                "date",
                run_date=data_hora,
                args=[
                    tg_schedule.chat_id,
                    submensagem,
                    chat_id,
                    tg_schedule.name,
                    job_id,
                ],
                id=job_id,
            )
            cluster_id[tg_schedule.name].append(job_id)
    elif tg_schedule.freq == "M":
        cluster_id[tg_schedule.name] = []
        for i, submensagem in enumerate(submensagens):
            data_hora = datetime.now() + timedelta(
                minutes=(tg_schedule.step_day * (i + 1))
            )
            job_id = tg_schedule.name + "_" + str(i)
            try:
                job = scheduler.add_job(
                    send_message,
                    "date",
                    run_date=data_hora,
                    args=[
                        tg_schedule.chat_id,
                        submensagem,
                        chat_id,
                        tg_schedule.name,
                        job_id,
                    ],
                    id=job_id,
                )
            except ConflictingIdError:
                job_id = tg_schedule.name + "_" + str(i) + "_" + str(i)
                job = scheduler.add_job(
                    send_message,
                    "date",
                    run_date=data_hora,
                    args=[
                        tg_schedule.chat_id,
                        submensagem,
                        chat_id,
                        tg_schedule.name,
                        job_id,
                    ],
                    id=job_id,
                )
            cluster_id[tg_schedule.name].append(job_id)
    return {"len": len(submensagens)}


@app.on_message(filters.command("start"))
async def start(client: Client, message: Message):
    text = "Bem-vindo! Escolha uma opção abaixo:"

    # Criação dos botões com comandos
    keyboard = ReplyKeyboardMarkup(
        [
            [KeyboardButton("/criar_agendamento"), KeyboardButton("/obter_id")],
            [
                KeyboardButton("/obter_agendamentos"),
                KeyboardButton("/deletar_agendamento"),
            ],
        ]
    )

    # Envio da mensagem com os botões
    await client.send_message(message.chat.id, text, reply_markup=keyboard)


@app.on_message(filters.command("obter_id"))
async def get_idchat(client: Client, message: Message):
    chat_id = message.chat.id
    get_id_progress[chat_id] = 0
    delete_progress[chat_id] = 0
    create_progress[chat_id] = 0

    await client.send_message(
        chat_id,
        "Ok, me encaminhe qualquer mensagem de texto para obter o ID do chat de origem",
    )
    get_id_progress[chat_id] += 1


@app.on_callback_query()
async def handle_callback_query(client, query):
    button = query.data
    chat_id = query.message.chat.id
    tg_schedule.freq = button
    if button == "D":
        await client.send_message(
            chat_id, f"A cada quantos dias a mensagem deve ser enviada?"
        )
        create_progress[chat_id] += 1  # Go to next step
    elif button == "M":
        await client.send_message(
            chat_id, f"A cada quantos minutos a mensagem deve ser enviada?"
        )
        create_progress[chat_id] += 2  # Go to step 5
    await query.answer()


@app.on_message(filters.command("obter_agendamentos"))
async def obter_agendamentos(client: Client, message: Message):
    global cluster
    get_id_progress[message.chat.id] = 0
    delete_progress[message.chat.id] = 0
    create_progress[message.chat.id] = 0
    msg = "**Seus Agendamentos** 🗓\n"
    try:
        cluster_id = cluster[message.chat.id]
        if len(cluster_id) == 0:
            await client.send_message(
                message.chat.id,
                "Você ainda não tem agendamentos criados 🙁\n\nUse o comando /criar_agendamento para criar",
            )
            return
        for i in cluster_id:
            msg += f"\n- `{i}`"
        await client.send_message(message.chat.id, msg)
    except:
        await client.send_message(
            message.chat.id,
            "Você ainda não tem agendamentos criados 🙁\n\nUse o comando /criar_agendamento para criar",
        )


@app.on_message(filters.command("deletar_agendamento"))
async def deletar_agendamento(client: Client, message: Message):
    try:
        get_id_progress[message.chat.id] = 0
        delete_progress[message.chat.id] = 0
        create_progress[message.chat.id] = 0
        if len(cluster[message.chat.id]) == 0:
            await client.send_message(
                message.chat.id,
                "Você ainda não tem agendamentos criados 🙁\n\nUse o comando /criar_agendamento para criar",
            )
            return
        chat_id = message.chat.id
        await client.send_message(
            chat_id, "Qual o nome do agendamento que deseja deletar?"
        )
        delete_progress[chat_id] = 1
    except:
        await client.send_message(
            message.chat.id,
            "Você ainda não tem agendamentos criados 🙁\n\nUse o comando /criar_agendamento para criar",
        )


@app.on_message(filters.command("criar_agendamento"))
async def start_command(client: Client, message: Message):
    global tg_schedule
    global cluster
    get_id_progress[message.chat.id] = 0
    delete_progress[message.chat.id] = 0
    create_progress[message.chat.id] = 0
    tg_schedule = ScheduleModel()
    tg_schedule.message = ""
    chat_id = message.chat.id
    if chat_id not in cluster:
        cluster[chat_id] = {}
    await client.send_message(chat_id, "Qual o nome do agendamento?")
    create_progress[chat_id] += 1


@app.on_message(filters.text)
async def handle_message(client: Client, message: Message):
    global tg_schedule
    global cluster
    chat_id = message.chat.id
    if chat_id in delete_progress:
        progress = delete_progress[chat_id]
        if progress == 1:
            cluster_name = message.text
            if cluster_name in cluster[chat_id]:
                await delete_jobs(chat_id, cluster_name)
                await client.send_message(
                    chat_id, f"Agendamento **{cluster_name}** apagado ❌"
                )
            else:
                await client.send_message(
                    chat_id,
                    f"Agendamento **{cluster_name}** não encontrado, verifique o nome e tente novamente 😕",
                )
            del delete_progress[chat_id]
            return

    if chat_id in create_progress:
        progress = create_progress[chat_id]
        if progress == 1:
            cluster_name = message.text
            if cluster_name in cluster[chat_id]:
                print(f"Já existe um agendamento com este nome - {progress}")
                await client.send_message(
                    chat_id, f"Você já tem um agendamento com este nome, tente outro..."
                )
                return
            else:
                tg_schedule.name = message.text
                print(tg_schedule.name)
                await client.send_message(chat_id, f"Qual o ID do chat?")
                create_progress[chat_id] += 1
                return

        elif progress == 2:  # Resposta para a segunda pergunta
            try:
                await client.get_chat(chat_id)
                tg_schedule.chat_id = message.text
            except Exception or ValueError as e:
                await client.send_message(chat_id, f"Chat ID {chat_id} é inválido.")
                return
            res = await client.send_message(
                message.chat.id,  # Edit this
                "Selecione a frequência",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [  # First row
                            InlineKeyboardButton(  # Generates a callback query when pressed
                                "Dias", callback_data="D"
                            ),
                            InlineKeyboardButton(  # Opens a web URL
                                "Minutos", callback_data="M"
                            ),
                        ]
                    ]
                ),
            )
            return

        elif progress == 3:
            tg_schedule.step_day = int(message.text)
            if tg_schedule.freq == "D":
                await client.send_message(
                    chat_id, f"Qual o horário da mensagem? (HH:MM)"
                )
                create_progress[chat_id] += 1  # Go to next step
                return

        elif progress == 4:
            if tg_schedule.freq == "D":
                if re.match(time_format, message.text):
                    tg_schedule.time = message.text
                else:
                    await client.send_message(
                        chat_id, f"O horário {message.text} é inválido, tente novamente"
                    )
                    return
            if tg_schedule.freq == "M":
                tg_schedule.step_day = int(message.text)
            await client.send_message(
                chat_id,
                f"Digite as mensagens, separadas por ;\nAo terminar envie outra mensagem com o texto: `FIM`",
            )
            create_progress[chat_id] += 1
            return

        elif progress == 5:
            if message.text != "FIM":
                tg_schedule.message += message.text
            else:
                res_schedule = await schedule_message(tg_schedule, chat_id)
                await client.send_message(
                    chat_id, f'Ok, {res_schedule["len"]} agendamento(s) criado(s)! 👍'
                )
                del create_progress[chat_id]
            return

    if chat_id in get_id_progress:
        progress = get_id_progress[chat_id]
        if message.forward_from_chat:
            forwarded_chat_id = message.forward_from_chat.id
            await client.send_message(
                message.chat.id,
                f"**{message.forward_from_chat.title}** possui o ID: `{forwarded_chat_id}`",
            )
            del get_id_progress[chat_id]
            return

        elif message.forward_from:
            forwarded_chat_id = message.forward_from.id
            await client.send_message(
                message.chat.id,
                f"**{message.forward_from.first_name}** possui o ID: `{forwarded_chat_id}`",
            )
            del get_id_progress[chat_id]
            return
        else:
            chat_id = message.chat.id
            from_user = message.from_user.id
            await client.send_message(chat_id, f"Seu ID é `{from_user}`")
            del get_id_progress[chat_id]
            return


scheduler.start()
app.run()
