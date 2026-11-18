import { MongoClient, Db, Collection } from 'mongodb';
import bcrypt from 'bcryptjs';

export interface AdminDocument {
  _id?: import('mongodb').ObjectId | string;
  email: string;
  passwordHash: string;
  role: 'admin' | 'superadmin';
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
  lastLoginAt?: string;
}

declare global {
  var _mongoClientPromise: Promise<MongoClient> | undefined;
}

function getUri(): string {
  return (
    process.env.MONGODB_DIRECT_URI ||
    process.env.MONGODB_URI ||
    process.env.MONGO_URI ||
    ''
  );
}

export function getMongoClientPromise(): Promise<MongoClient> {
  const uri = getUri();
  if (!uri) {
    throw new Error('MONGODB_URI is not set in environment variables.');
  }

  if (process.env.NODE_ENV === 'development') {
    if (!global._mongoClientPromise) {
      const client = new MongoClient(uri, {
        serverSelectionTimeoutMS: 10000,
        connectTimeoutMS: 10000,
      });
      global._mongoClientPromise = client.connect();
    }
    return global._mongoClientPromise;
  }

  if (!global._mongoClientPromise) {
    const client = new MongoClient(uri, {
      serverSelectionTimeoutMS: 10000,
      connectTimeoutMS: 10000,
    });
    global._mongoClientPromise = client.connect();
  }
  return global._mongoClientPromise;
}

export async function getDb(): Promise<Db> {
  const dbName = process.env.MONGODB_DB_NAME || 'waguri_db';
  const client = await getMongoClientPromise();
  return client.db(dbName);
}

let adminProvisioned = false;

export async function getAdminCollection(): Promise<Collection<AdminDocument>> {
  const db = await getDb();
  const collection = db.collection<AdminDocument>('admins');

  if (!adminProvisioned) {
    await collection.createIndex({ email: 1 }, { unique: true });

    const adminCount = await collection.countDocuments();
    if (adminCount === 0) {
      const defaultEmail = process.env.ADMIN_EMAIL?.toLowerCase().trim();
      const rawPassword = process.env.ADMIN_PASSWORD;
      let passwordHash = process.env.ADMIN_PASSWORD_HASH;

      if (!defaultEmail || (!passwordHash && !rawPassword)) {
        throw new Error(
          'Configure ADMIN_EMAIL and either ADMIN_PASSWORD or ADMIN_PASSWORD_HASH before initializing the first admin.'
        );
      }

      if (passwordHash && !/^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}$/.test(passwordHash)) {
        throw new Error('ADMIN_PASSWORD_HASH must be a valid bcrypt hash.');
      }

      if (!passwordHash) {
        if (!rawPassword) {
          throw new Error('ADMIN_PASSWORD is required when ADMIN_PASSWORD_HASH is not configured.');
        }
        passwordHash = await bcrypt.hash(rawPassword, 12);
      }

      const now = new Date().toISOString();
      await collection.insertOne({
        email: defaultEmail,
        passwordHash,
        role: 'admin',
        isActive: true,
        createdAt: now,
        updatedAt: now,
      });

      console.info('[Auth] Initial admin account provisioned.');
    }
    adminProvisioned = true;
  }

  return collection;
}

export default getMongoClientPromise;
