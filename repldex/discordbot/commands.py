from repldex.config import DEV_IDS, EDITOR_IDS, BASE_URL, ADMIN_IDS, BLACKLIST_IDS
from repldex.backend import database
from .bot import betterbot, client
from repldex import utils
import discord
import asyncio

blacklist_wait = 5
# ACTUAL COMMANDS START HERE

print('commands')


@betterbot.command(name='help', allowed=True)
async def help(message):
	if message.message.author.id in BLACKLIST_IDS:
		await asyncio.sleep(blacklist_wait)

	commands = {
		'search <query>': 'Finds entries that match the query',
		'entry <name>': 'Shows the matching entry',
		'random': 'Gets a random entry',
		'request <entry>': 'Lets noneditors request a Repldex entry',
		'source': 'Links my source on github',
		'ping': 'Gets current bot ping',
		'selfentry': 'Gets your own entry if you have one.',
		'featured': 'Get featured article',
	}
	if message.author.id in EDITOR_IDS:
		commands['selfentry <name>'] = 'Links you to your entry (editor only)'
		commands['newentry <name>'] = 'Sends link to write new entry (editor only)'
		if message.author.id in ADMIN_IDS:
			commands['link <user mention> <article>'] = 'Manually link non-editors to entries (admin only)'
			commands['view_selfentry <user mention>'] = 'View a users selfentry (admin only)'
			commands['who_is_the_leader'] = 'tells you who the supreme leader is (admin only)'
			commands['userinfo <user mention>'] = 'get info on the mentioned user (admin only)'
			commands['unlist <article id>'] = 'Toggles unlisting of entry (admin only)'
			commands['delete <article id>'] = 'Delete entry (admin only)'
			commands['changefeatured <article id>'] = 'Change featured article on Repldex Main Page (admin only). Do `disabled` instead of entryid to disable featured entries'
			# commands['neweditor <user mention>'] = 'Make user editor (admin only)'
	content = []
	prefix = message.prefix
	for command in commands:
		content.append(f'{prefix}**{command}** - {commands[command]}')

	embed = discord.Embed(title='Commands', description='\n'.join(content))
	await message.send(embed=embed)


async def create_entry_embed(entry_data, author_id=None, raw_entry=False):
	if not raw_entry:
		html = entry_data['content']
		content = utils.html_to_markdown(html)

		content_ending = ''

		if len(content) > 2048:
			content = content[:2045 - len(content_ending)] + '...'
		content += content_ending
		title = utils.url_title(entry_data['title'])
		view_url = f'{BASE_URL}/entry/{title}'
		view_url = view_url
		embed = discord.Embed(title=entry_data['title'], description=content, url=view_url)
		if entry_data.get('image'):
			embed.set_thumbnail(url=entry_data['image']['src'])

		return embed
	else:
		entry_data = dict(entry_data)
		content = entry_data['nohtml_content']
		content_ending = ''
		if len(content) > 1024:
			content = content[:1021 - len(content_ending)] + '...'
		try:
			del entry_data['image']
		except KeyError:
			pass
		entry_data['nohtml_content'] = content
		del entry_data['content']
		del entry_data['history']
		return utils.embed_from_dict(entry_data, color=0x00FF00, title='raw entry data')


@betterbot.command(name='search')
async def search_entries(message, search_query: str):
	numbers = ('1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟')
	found = await database.search_entries(search_query)
	if found:
		content = []
		for i, result in enumerate(found, 1):
			title = result['title']
			content.append(f'{i}) {title}')
		content = '\n'.join(content)
	else:
		content = 'No results'
	embed = discord.Embed(title=f'Results for {search_query}', description=content)
	# if found:
	#     embed.set_footer(text=f'React with {one_emoji} to get the first result')
	msg = await message.send(embed=embed)
	if found:
		for emoji in numbers[:len(found)]:
			await msg.add_reaction(emoji)

		def check(reaction, user):
			message_matches = reaction.message.id == msg.id
			user_matches = user == message.author
			emoji_matches = str(reaction.emoji) in numbers
			return message_matches and user_matches and emoji_matches

		reaction, _ = await client.wait_for('reaction_add', check=check)
		emoji = str(reaction.emoji)
		emoji_pos = numbers.index(emoji)
		embed = await create_entry_embed(found[emoji_pos], author_id=message.author.id)
		await message.send(embed=embed)


@betterbot.command(name='source', allowed=True, aliases=['code'])
async def link_source(message):
	embed = discord.Embed(title='Source code', description='My source code on github')
	embed.add_field(name='github', value='https://github.com/mat-1/ReplDex')

	await message.send(embed=embed)


@betterbot.command(name='entry', allowed=True)
async def show_entry(message, search_query: str):
	if message.message.author.id in BLACKLIST_IDS:
		await asyncio.sleep(blacklist_wait)
	found = await database.search_entries(search_query, limit=1)
	if found:
		embed = await create_entry_embed(found[0], author_id=message.author.id)
		await message.send(embed=embed)
	else:
		embed = discord.Embed(title="This entry doesn't exist")
		search_query_url_encoded = utils.url_title(search_query)
		edit_url = f'{BASE_URL}/edit?title={search_query_url_encoded}'
		edit_url = edit_url
		if message.author.id in EDITOR_IDS:
			embed.description = f'[Click here to write it!]({edit_url})'
		await message.send(embed=embed)


@betterbot.command(name='raw_entry')
async def show_raw_entry(message, search_query: str):
	if message.author.id not in ADMIN_IDS:
		return
	found = await database.search_entries(search_query, limit=1)
	if found:
		data = await create_entry_embed(found[0], author_id=message.author.id, raw_entry=True)
		await message.send(embed=data)
	else:
		embed = discord.Embed(title="This entry doesn't exist")
		await message.send(embed=embed)


@betterbot.command(name='selfentry', bots_allowed=True)
async def personal_entry(message, search_query: str):
	if not search_query:
		entry_id = await database.get_personal_entry(message.author.id)
		if not entry_id:
			if message.author.id not in EDITOR_IDS:
				return await message.send("You don't have a personal entry set yet. An admin needs to set one for you")
			else:
				return await message.send("You haven't set a personal entry yet")
		entry = await database.get_entry(entry_id)
		embed = await create_entry_embed(entry, author_id=message.author.id)
		return await message.send(embed=embed)
	if message.author.id not in EDITOR_IDS:
		return await message.send('Only editors can set personal entries')
	found = await database.search_entries(search_query, limit=1)
	if found:
		entry = found[0]
		title = entry['title']
		entry_id = entry['_id']
		await database.set_personal_entry(message.author.id, entry_id)
		await message.send(f'Set your personal entry to `{title}`')
	else:
		await message.send('Invalid entry')


@betterbot.command(name='userinfo')
async def user_info(message, member: utils.Member):
	if message.author.id not in ADMIN_IDS:
		return
	embed = discord.Embed(title='user info', description=f'info on <@{member.id}>', color=0x00FF00)
	editor = False
	if member.id in EDITOR_IDS:
		editor = True
	admin = False
	if member.id in ADMIN_IDS:
		admin = True

	entry_id = await database.get_personal_entry(member.id)

	if entry_id is None:
		selfentry = 'None'
	else:
		entry = await database.get_entry(entry_id)
		selfentry = entry['title']
	embed.add_field(name='editor', value=str(editor), inline=True)
	embed.add_field(name='admin', value=str(admin), inline=True)
	embed.add_field(name='selfentry', value=f'`{selfentry}`', inline=False)
	await message.send(embed=embed)


@betterbot.command(name='view_selfentry')
async def view_self_entry(message, member: utils.User):
	if message.author.id not in ADMIN_IDS:
		return
	entry_id = await database.get_personal_entry(member.id)
	entry = await database.get_entry(entry_id)
	try:
		embed = await create_entry_embed(entry, author_id=message.author.id)
	except:  # TODO: figure out what error happens here
		return await message.send('no selfentry exists for this person')
	return await message.send(embed=embed)


@betterbot.command(name='who_is_the_leader')
async def leader(message):
	if message.channel.id in utils.auto_delete_channels:
		return
	if message.author.id not in ADMIN_IDS:
		return
	await message.send('PRUSSIA IS THE SUPREME LEADER')
	pass


@betterbot.command(name='request')
async def suggest(message, request: str):
	suggestions_channel = client.get_channel(753331575034347642)
	if request:
		embed = discord.Embed(title='Entry Suggestion', description=request)
		embed.set_footer(text='Requested by {}'.format(message.author.name))
		await message.send('Suggestion sent.')
		return await suggestions_channel.send(embed=embed)
	else:
		return await message.send('Invalid command usage.')


@betterbot.command(name='unlist')
async def unlist(message, entry_id: str):
	if message.author.id not in ADMIN_IDS:
		return
	entry_data = await database.get_entry(entry_id)
	if entry_data is None:
		return
	unlist = not entry_data['unlisted']
	await database.edit_entry(
		title=entry_data['title'],
		entry_id=entry_id,
		content=entry_data['content'],
		unlisted=unlist,
		editor_id=message.author.id
	)
	embed = discord.Embed(title='toggle unlist', description='toggling entry being listed/unlisted', color=0x00FF00)
	embed.add_field(name='entry name', value=entry_data['title'], inline=True)
	embed.add_field(name='entry id', value=entry_id, inline=True)
	embed.add_field(name='entry link', value=f'{BASE_URL}/entry/{entry_id}', inline=True)
	embed.add_field(name='unlisted', value=str(unlist), inline=False)
	await message.send(embed=embed)


@betterbot.command(name='link')
async def link_entry(message, member: utils.Member, search_query: str):
	if message.author.id not in ADMIN_IDS:
		return
	if not member:
		return await message.send('Invalid member')

	found = await database.search_entries(search_query, limit=1)
	if found:
		entry = found[0]
		title = entry['title']
		entry_id = entry['_id']
		await database.set_personal_entry(member.id, entry_id)
		await message.send(embed=discord.Embed(description=f'Set {member.mention} personal entry to `{title}`'))
	else:
		await message.send('Invalid entry')


@betterbot.command(name='newentry')
async def new_entry(message, search_query: str):
	search_query_url_encoded = utils.url_title(search_query)
	edit_url = f'{BASE_URL}/edit?title={search_query_url_encoded}'
	edit_url = edit_url
	if message.author.id in EDITOR_IDS:
		embed = discord.Embed(title=f'Write {search_query}', description=f'[Click here to write it!]({edit_url})')
		found = await database.search_entries(search_query, limit=1)
		if found:
			embed.set_footer(text='Alert: There may be an entry with the same/similar name or topic.')
	else:
		embed = discord.Embed(title='This command is editor only')
	await message.send(embed=embed)


@betterbot.command(name='random')
async def random_entry(message):
	entry = await database.get_random_entry()

	embed = await create_entry_embed(entry, author_id=message.author.id)
	await message.send(embed=embed)


@betterbot.command(name='changefeatured')
async def change_featured(message, entry_id: str):
	if message.author.id not in ADMIN_IDS:
		return
	if entry_id.lower() == 'disabled':
		await database.disable_featured()
		return await message.send('Featured articles disabled')
	else:
		entry = await database.get_entry(entry_id=entry_id, name=None, search_id=True, owner=None)
		if entry:
			await database.set_featured_article(entry_id)
			await message.send('Featured Article changed')
		else:
			await message.send('Entry ID is not valid')


@betterbot.command(name='featured')
async def featured(message):
	# get the featured article and send it
	featured = await database.get_featured_article()
	if not featured or not featured['value']:
		return await message.send('No Featured Article Set.')
	embed = await create_entry_embed(await database.get_entry(featured['value']), author_id=message.author.id)
	await message.send(embed=embed)


@betterbot.command(name='delete')
async def delete(message, entry_id: int):
	if message.author.id not in ADMIN_IDS:
		return
	entry = await database.get_entry(entry_id=entry_id)
	if entry:
		if entry['unlisted']:
			await database.delete_entry(entry, entry_id)
			await message.send('Entry deleted')
		else:
			await message.send('You cannot delete non-unlisted entries')
	else:
		await message.send('Invalid entry id')


@betterbot.command(name='ping', aliases=['pong', 'pung'])
async def ping(message):
	if message.author.id in ADMIN_IDS or message.author.id in DEV_IDS:
		ping = client.latency * 1000
		await message.send(embed=discord.Embed(title='Ping!', description=f'Bot ping is: `{ping}ms`'))


# @betterbot.command(name="neweditor")
# async def new_editor(message, member: utils.Member):
#     print('new editor command')
#     if message.author.id not in ADMIN_IDS: return

#     with open("editors.txt") as editors:
#         if str(member.id) in editors.read().split("\n"):
#             await message.send(embed=discord.Embed(
#                 description="This user is already an editor!",
#                 colour=discord.Colour.red()
#             ))
#             return

#     with open("editors.txt","a") as editors:
#         editors.write("\n")
#         editors.write(str(member.id))
#         EDITOR_IDS.append(member.id)
#         await message.send(embed=discord.Embed(
#             description=f"Added {member.mention} as an editor!",
#             colour=discord.Colour.green()
#         ))

# @betterbot.command(name="removeeditor")
# async def new_editor(message, member: utils.Member):
#     print('remove editor command')
#     if message.author.id not in ADMIN_IDS: return

#     with open("editors.txt") as editors:
#         editorlist=editors.read().split("\n")
#         if str(member.id) not in editorlist:
#             await message.send(embed=discord.Embed(
#                 description="This user is not an editor!",
#                 colour=discord.Colour.red()
#             ))
#             return

#     editorlist.remove(str(member.id))
#     with open("editors.txt","w") as editors:
#         editors.write("\n".join(editorlist))
#         EDITOR_IDS.remove(member.id)
#         await message.send(embed=discord.Embed(
#             description=f"Removed {member.mention} from editors!",
#             colour=discord.Colour.green()
#         ))
