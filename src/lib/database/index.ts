import { Db, MongoClient } from 'mongodb'
import { Binary } from 'mongodb'
import { v4 as uuidv4 } from '@lukeed/uuid/secure'

const uri = process.env['MONGODB_URI']

if (!uri) throw new Error('MONGODB_URI environment variable not set')

const options = {}
let clientPromise: Promise<MongoClient>

if (process.env['NODE_ENV'] === 'development') {
	// In development mode, use a global variable so that the value
	// is preserved across module reloads caused by HMR (hot module replacement).
	if (!global._mongoClientPromise) {
		const client = new MongoClient(uri, options)
		global._mongoClientPromise = client.connect()
	}
	clientPromise = global._mongoClientPromise
} else {
	// In production mode, it's best to not use a global variable.
	const client = new MongoClient(uri, options)
	clientPromise = client.connect()
}

/**
 * Flatten an object like { foo: { bar: 'baz' } } to { foo.bar: 'baz' }
 * This is useful for MongoDB queries.
 */
export function flattenMongoQuery(obj: object): Record<string, any> {
	// not an object, can't be flattened
	if (typeof obj !== 'object') return obj

	const result = {}

	for (const [key, value] of Object.entries(obj)) {
		if (typeof value === 'object' && value !== Object(value) && !key.startsWith('$')) {
			for (const [innerKey, innerValue] of Object.entries(flattenMongoQuery(value))) {
				result[`${key}.${innerKey}`] = innerValue
			}
		} else result[key] = value
	}
	return result
}

/** Create a MongoDB UUID */
export function createUuid(uuid?: string): Binary {
	return new Binary(Buffer.from((uuid ?? uuidv4()).replace(/-/g, ''), 'hex'), Binary.SUBTYPE_UUID)
}

/**
 * replace "id" with "_id" and convert it to an ObjectId
 */
export function replaceIdWithUuid<T>(
	data: T
): T extends { id: string }
	? Omit<T, 'id'> & { _id: Binary }
	: T extends { id?: string }
	? Omit<T, 'id'> & { _id?: Binary }
	: T {
	const result = {} as any
	for (const [key, value] of Object.entries(data)) {
		if (key === 'id') {
			result._id = createUuid(value)
		} else {
			result[key] = value
		}
	}
	return result
}

/**
 * replace "_id" with "id" and convert it to a string
 */
export function replaceUuidWithId<T extends object>(
	data: T
): T extends { _id: Binary }
	? Omit<T, '_id'> & { id: string }
	: T extends { _id?: Binary }
	? Omit<T, '_id'> & { id?: string }
	: T {
	const result = {} as any
	for (const [key, value] of Object.entries(data)) {
		if (key === '_id') {
			result.id = value.toString('hex')
		} else {
			result[key] = value
		}
	}
	return result
}

export async function getDatabase(): Promise<Db> {
	const client = await clientPromise
	return client.db()
}

export type ReplaceIdWithUuid<T> = Omit<T, 'id'> & { _id: Binary }

export function createSlug(text: string): string {
	return text
		.toLowerCase()
		.replace(/[^\w ]+/g, '')
		.replace(/ +/g, '-')
}
