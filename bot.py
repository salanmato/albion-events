import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Olá, eu sou o seu gerenciador de eventos!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

load_dotenv()
TOKEN = os.getenv("TOKEN")

# --- MUDANÇA 1: DE ROLES PARA TEMPLATES ---
# Criamos um dicionário principal que guarda diferentes "moldes" de eventos.
TEMPLATES = {
    "raid": {
        "nome_exibicao": "Raid (Padrão 5 Pessoas)",
        "roles": {
            "🛡️": {"nome": "Tanque", "limite": 1},
            "➕": {"nome": "Healer", "limite": 1},
            "⚔️": {"nome": "DPS",    "limite": 3},
            "❓": {"nome": "Reserva", "limite": 5}
        }
    },
    "dungeon": {
        "nome_exibicao": "Dungeon (5 Pessoas)",
        "roles": {
            "🛡️": {"nome": "Tanque", "limite": 1},
            "➕": {"nome": "Healer", "limite": 1},
            "⚔️": {"nome": "DPS",    "limite": 3}
            # Sem reserva neste template, por exemplo
        }
    }
}

# --- MUDANÇA 2: DICIONÁRIO PARA EVENTOS ATIVOS ---
# O bot usará isso para "lembrar" qual template pertence a qual mensagem.
# A chave será o ID da mensagem, o valor será o template usado.
ACTIVE_EVENTS = {}

intents = discord.Intents.default()
intents.message_content = True
intents.members = True 

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')

# --- MUDANÇA 3: NOVO COMANDO DE EVENTO BASEADO EM TEMPLATE ---
@bot.command(name="evento")
async def criar_evento(ctx, template_nome: str, titulo: str, data_hora: str, *, descricao: str):
    template_nome = template_nome.lower()
    if template_nome not in TEMPLATES:
        await ctx.send(f"Erro: Template `{template_nome}` não encontrado. Tente: `{', '.join(TEMPLATES.keys())}`")
        return

    template_selecionado = TEMPLATES[template_nome]
    roles_do_template = template_selecionado["roles"]

    embed = discord.Embed(
        title=f"📅 Evento: {titulo}",
        description=(
            f"**Quando:** {data_hora}\n"
            f"**Organizador:** {ctx.author.mention}\n\n"
            f"**📝 Descrição:**\n{descricao}"
        ),
        color=discord.Color.dark_gold()
    )
    
    for emoji, info_role in roles_do_template.items():
        nome_funcao = info_role["nome"]
        limite = info_role["limite"]
        embed.add_field(name=f"{emoji} {nome_funcao} (0/{limite})", value="Ninguém inscrito.", inline=False)
    
    embed.set_footer(text=f"Evento criado com o template: {template_selecionado['nome_exibicao']}")
    mensagem_do_evento = await ctx.send(embed=embed)

    # Associa a mensagem ao template no nosso "banco de dados" em memória
    ACTIVE_EVENTS[mensagem_do_evento.id] = template_selecionado

    for emoji in roles_do_template.keys():
        await mensagem_do_evento.add_reaction(emoji)

# --- MUDANÇA 4: ATUALIZAR OS "OUVINTES" PARA USAR OS TEMPLATES ---
# Todas as funções abaixo agora consultam ACTIVE_EVENTS para saber as regras do evento específico.

@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id or payload.message_id not in ACTIVE_EVENTS:
        return
    
    template_do_evento = ACTIVE_EVENTS[payload.message_id]
    roles_do_template = template_do_evento["roles"]
    emoji_str = str(payload.emoji)

    if emoji_str in roles_do_template:
        guild = await bot.fetch_guild(payload.guild_id)
        member = await guild.fetch_member(payload.user_id)
        channel = await bot.fetch_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        if message.author.id == bot.user.id and member is not None:
            info_role = roles_do_template[emoji_str]
            limite = info_role["limite"]
            
            for reaction in message.reactions:
                if str(reaction.emoji) == emoji_str and reaction.count - 1 >= limite:
                    await reaction.remove(member)
                    try:
                        await member.send(f"A inscrição para **{info_role['nome']}** no evento '{message.embeds[0].title}' falhou, pois as vagas estão preenchidas!")
                    except discord.Forbidden: pass
                    return
            
            for reaction in message.reactions:
                if str(reaction.emoji) in roles_do_template and str(reaction.emoji) != emoji_str:
                    try:
                        await reaction.remove(member)
                    except discord.Forbidden: pass
            
            await atualizar_inscritos(message)

@bot.event
async def on_raw_reaction_remove(payload):
    if payload.user_id == bot.user.id or payload.message_id not in ACTIVE_EVENTS:
        return

    template_do_evento = ACTIVE_EVENTS[payload.message_id]
    roles_do_template = template_do_evento["roles"]

    if str(payload.emoji) in roles_do_template:
        channel = await bot.fetch_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        if message.author.id == bot.user.id:
            await atualizar_inscritos(message)

async def atualizar_inscritos(message):
    if message.id not in ACTIVE_EVENTS:
        return

    template_do_evento = ACTIVE_EVENTS[message.id]
    roles_do_template = template_do_evento["roles"]
    
    embed_antigo = message.embeds[0]
    novo_embed = discord.Embed.from_dict(embed_antigo.to_dict())
    novo_embed.clear_fields()

    for emoji, info_role in roles_do_template.items():
        nome_funcao = info_role["nome"]
        limite = info_role["limite"]
        
        lista_de_membros = []
        for reaction in message.reactions:
            if str(reaction.emoji) == emoji:
                async for user in reaction.users():
                    if not user.bot:
                        lista_de_membros.append(user.mention)
        
        valor_campo = "\n".join(lista_de_membros) if lista_de_membros else "Ninguém inscrito."
        contagem = len(lista_de_membros)
        
        novo_embed.add_field(name=f"{emoji} {nome_funcao} ({contagem}/{limite})", value=valor_campo, inline=False)
    
    await message.edit(embed=novo_embed)

keep_alive()
bot.run(TOKEN)