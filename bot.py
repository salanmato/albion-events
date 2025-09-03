import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import database # Importamos nosso novo módulo de banco de dados

load_dotenv()
TOKEN = os.getenv('TOKEN')

# Os dicionários TEMPLATES e ACTIVE_EVENTS foram removidos.
# Toda a lógica agora vem do banco de dados.

intents = discord.Intents.default()
intents.message_content = True
intents.members = True 

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    # Inicializa o banco de dados (cria as tabelas se não existirem) quando o bot liga
    database.init_db()
    print(f'Bot conectado como {bot.user}')

@bot.command(name="evento")
async def criar_evento(ctx, template_nome: str, titulo: str, data_hora: str, *, descricao: str):
    template_nome = template_nome.lower()
    
    # Busca os templates disponíveis do banco de dados
    available_templates = database.get_all_template_names()
    if template_nome not in available_templates:
        await ctx.send(f"Erro: Template `{template_nome}` não encontrado. Tente: `{', '.join(available_templates)}`")
        return

    # Busca as roles do template específico do banco de dados
    roles_do_template = database.get_template_roles(template_nome)

    embed = discord.Embed(
        title=f"📅 Evento: {titulo}",
        description=(
            f"**Quando:** {data_hora}\n"
            f"**Organizador:** {ctx.author.mention}\n\n"
            f"**📝 Descrição:**\n{descricao}"
        ),
        color=discord.Color.dark_gold()
    )
    
    emojis_para_reagir = []
    for role in roles_do_template:
        embed.add_field(name=f"{role['emoji']} {role['role_name']} (0/{role['role_limit']})", value="Ninguém inscrito.", inline=False)
        emojis_para_reagir.append(role['emoji'])
    
    embed.set_footer(text=f"Evento criado com o template: {template_nome}")
    mensagem_do_evento = await ctx.send(embed=embed)

    # Salva o evento no banco de dados para que o bot "lembre" dele
    database.add_active_event(mensagem_do_evento.id, ctx.channel.id, ctx.guild.id, template_nome)

    for emoji in emojis_para_reagir:
        await mensagem_do_evento.add_reaction(emoji)

@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return
    
    # Verifica se a mensagem é um evento ativo buscando no DB
    event_details = database.get_event_details(payload.message_id)
    if not event_details:
        return
    
    template_name = event_details['template_name']
    roles_do_template_raw = database.get_template_roles(template_name)
    # Converte a lista de roles para um dicionário para facilitar o acesso
    roles_do_template = {role['emoji']: {'nome': role['role_name'], 'limite': role['role_limit']} for role in roles_do_template_raw}
    
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
    if payload.user_id == bot.user.id:
        return

    event_details = database.get_event_details(payload.message_id)
    if not event_details:
        return
    
    template_name = event_details['template_name']
    roles_do_template_raw = database.get_template_roles(template_name)
    roles_do_template = {role['emoji']: {'nome': role['role_name'], 'limite': role['role_limit']} for role in roles_do_template_raw}

    if str(payload.emoji) in roles_do_template:
        channel = await bot.fetch_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        if message.author.id == bot.user.id:
            await atualizar_inscritos(message)

async def atualizar_inscritos(message):
    event_details = database.get_event_details(message.id)
    if not event_details:
        return
    
    template_name = event_details['template_name']
    roles_do_template_raw = database.get_template_roles(template_name)
    roles_do_template = {role['emoji']: {'nome': role['role_name'], 'limite': role['role_limit']} for role in roles_do_template_raw}
    
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

bot.run(TOKEN)