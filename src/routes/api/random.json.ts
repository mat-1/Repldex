import { fetchEntries } from '../../lib/database/entries'
import type { RequestHandler } from '@sveltejs/kit'
import type { JSONString } from '@sveltejs/kit/types/helper'

// get an entry
export const get: RequestHandler = async req => {
	const entries = await fetchEntries({
		limit: 0,
		skip: 0
	})
	let entry = entries[Math.floor(Math.random() * entries.length)];
	return {
		body: entry as unknown as JSONString,
	}
}