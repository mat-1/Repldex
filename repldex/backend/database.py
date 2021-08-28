from repldex.backend.typings import DatabaseEntry, DatabaseHistoryItem, PartialDatabaseEntry
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import motor.motor_asyncio
import uuid
import os

connection_uri = os.getenv('dburi')

client = motor.motor_asyncio.AsyncIOMotorClient(connection_uri, connectTimeoutMS=1000)  # timeout is 1 sec

db = client['repldex']

entries_coll = db['entries']
sessions_coll = db['sessions']
users_coll = db['users']
config_coll = db['config']

from repldex.discordbot import bot as discordbot
from repldex.backend import images
from repldex import utils


async def fix_entry(data: Any) -> Optional[DatabaseEntry]:
	'''Fix entries by adding missing fields.'''
	if data is None:
		return
	original_data = dict(data)
	if data.get('image') and isinstance(data['image'], str):
		data['image'] = data['image'].replace('imag.cf', 'i.matdoes.dev')
	if data.get('image') and isinstance(data.get('image'), str):
		data['image'] = await images.get_data(data['image'])
	elif data.get('image') and not data['image'].get('thumbnail_b64'):
		data['image'] = await images.get_data(data['image']['src'])
	if data != original_data:
		await entries_coll.update_one({'_id': data['_id']}, {'$set': data})
	data['content'] = utils.fix_html(data['content'])
	if 'nohtml_content' not in data:
		data['nohtml_content'] = utils.remove_html(data['content'])
	return data


async def delete_entry(entry_data: DatabaseEntry, editor_id: int):
	await discordbot.log_delete(entry_data, editor_id)
	await entries_coll.delete_one({'_id': entry_data['_id']})


async def edit_entry(
	title: str,
	content: str,
	editor_id: int,
	unlisted: bool = False,
	entry_id: str = None,
	image: str = None
):
	t = datetime.now()
	title = title.strip()
	await discordbot.log_edit(editor_id, title)
	content = utils.fix_html(content)
	nohtml_content = utils.remove_html(content)
	new_data: PartialDatabaseEntry = {
		'title': title,
		'content': content,
		'last_edited': t,
		'nohtml_content': nohtml_content,
		'unlisted': unlisted or False
	}
	if image is not None:
		new_data['image'] = await images.get_data(image)

	if not entry_id:
		entry_id = str(uuid.uuid4())
	new_history_data: DatabaseHistoryItem = {
		'author': editor_id,
		'content': content,
		'title': title,
		'time': t,
		'unlisted': unlisted,
		'image': None
	}
	if image is not None:
		new_history_data['image'] = {
			'src': image,
			'thumbnail_b64': None,
			'thumbnail_content_type': None
		}

	await entries_coll.update_one({'_id': entry_id}, {'$set': new_data, '$push': {'history': new_history_data}}, upsert=True)
	return entry_id


async def get_entry(query: Optional[str] = None, entry_id: Optional[str] = None, search_id=True, owner=None) -> Union[DatabaseEntry, None]:
	if not entry_id and query:
		entries = await search_entries(query, limit=1, search_id=search_id)
		if not entries:
			return
		return entries[0]
	elif owner:
		found = await entries_coll.find_one({'owner_id': owner})
	else:
		found = await entries_coll.find_one({'_id': entry_id})
	found = await fix_entry(found)
	return found


async def new_editor_session(discord_id):
	sid = str(uuid.uuid4())
	await sessions_coll.insert_one({'_id': sid, 'discord': discord_id, 'time': datetime.now()})
	return sid


async def get_editor_session(sid):
	if not hasattr(get_editor_session, 'cache'):
		get_editor_session.cache = {}
	if sid in get_editor_session.cache:
		found = get_editor_session.cache[sid]
	else:
		found = await sessions_coll.find_one({'_id': sid})
		get_editor_session.cache[sid] = found
	if found is None:
		return
	return found['discord']


async def search_entries(query: str, limit=10, search_id=True, page=0, discord_id=None, unlisted=False) -> List[DatabaseEntry]:
	found: List[DatabaseEntry] = []
	match = {'$match': {'unlisted': {'$ne': True}}}
	if unlisted:
		match = {'$match': {'unlisted': {'$eq': True}}}
	async for doc in entries_coll.aggregate([
		{'$searchBeta': {'compound': {'should': [
			{'search': {'query': query, 'path': 'nohtml_content'}},
			{'search': {'query': query, 'path': 'title', 'score': {'boost': {'value': 20}}}},
		]}}},
		match,
		{'$addFields': {'score': {'$meta': 'searchScore'}}},
		{'$sort': {'score': -1}},
		{'$skip': page * limit},
		{'$limit': limit},
	]):
		fixed_entry = await fix_entry(doc)
		if fixed_entry:
			found.append(fixed_entry)
	if len(found) == 0 and search_id:
		found_entry = await get_entry(entry_id=query)
		if found_entry:
			found = [found_entry]
	if len(found) == 0:
		searched = await entries_coll.find_one({'title': query, 'unlisted': {'$ne': True}})
		if searched:
			found = [searched]
	if len(found) == 0:
		if query.startswith('<@') and query.endswith('>'):
			entry_owner_id = query[2:-1]
			if entry_owner_id[0] == '!':
				entry_owner_id = entry_owner_id[1:]
			entry_owner_id = int(entry_owner_id)
			owned_entry = await entries_coll.find_one({'owner_id': entry_owner_id})
			if entry_owner_id:
				found = [owned_entry]
	return found


# Query is only if sort == relevant
async def get_entries(sort, limit=20, page=0, query=None, discord_id=None, unlisted=False):
	# match = {'$match': {'unlisted': {'$ne': True}}}
	# if discord_id is not None:
	# 	if discord_id in ADMIN_IDS:
	# 		match = {}
	if sort == 'relevant' and query:
		found = await search_entries(query, limit=limit, page=page, discord_id=discord_id, unlisted=unlisted)
		return found
	cursor = entries_coll.find({'unlisted': {'$ne': True}})
	cursor = cursor.sort(sort, -1)
	cursor = cursor.skip(page * limit)
	cursor = cursor.limit(limit)
	found = []
	async for entry in cursor:
		entry = await fix_entry(entry)
		found.append(entry)
	return found


async def set_personal_entry(discord_id, entry_id):
	user_data = {
		'personal_entry': entry_id,
	}
	await users_coll.update_one({'_id': discord_id}, {'$set': user_data}, upsert=True)
	async for entry in entries_coll.find({'owner_id': discord_id}):
		await entries_coll.update_one({'_id': entry['_id']}, {'$set': {'owner_id': None}})
	await entries_coll.update_one({'_id': entry_id}, {'$set': {'owner_id': discord_id}})
	try:
		if hasattr(get_personal_entry, 'cache'):
			get_personal_entry.cache[discord_id] = user_data
	except Exception as e:
		print('BRUH MOMENT', e)


async def get_personal_entry(discord_id):
	if not hasattr(get_personal_entry, 'cache'):
		get_personal_entry.cache = {}
	if discord_id in get_personal_entry.cache:
		found = get_personal_entry.cache[discord_id]
	else:
		found = await users_coll.find_one({'_id': discord_id})
		get_personal_entry.cache[discord_id] = found
	if found is None:
		return
	return found.get('personal_entry')


async def count_entries():
	count = await entries_coll.count_documents({'unlisted': {'$ne': True}})
	return count


async def get_random_entry():
	cursor = entries_coll.aggregate([{'$match': {'unlisted': {'$ne': True}}}, {'$sample': {'size': 1}}])
	found = []
	async for entry in cursor:
		found.append(entry)
	return found[0]


async def get_featured_article():
	return await config_coll.find_one({'name': 'featured'})


async def set_featured_article(entry_id):
	featured = await config_coll.find_one({'name': 'featured'})
	if featured:
		await config_coll.replace_one({'name': 'featured'}, {'name': 'featured', 'value': entry_id})
	else:
		await config_coll.insert_one({'name': 'featured', 'value': entry_id})


async def disable_featured():
	await config_coll.delete_one({'name': 'featured'})
