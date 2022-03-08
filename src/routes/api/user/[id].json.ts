import { APIUser, fetchUser } from '../../../lib/database/users'
import type { RequestHandler } from '@sveltejs/kit'
import type { JSONValue } from '@sveltejs/kit/types/helper'

export const get: RequestHandler = async req => {
	const user = await fetchUser({
		id: req.params.id,
	})

	if (user === null) {
		return {
			status: 404,
			body: { error: 'Not found' },
		}
	}

	return {
		body: {
			id: user.id,
			username: user.username,
		} as APIUser as unknown as JSONValue,
	}
}
