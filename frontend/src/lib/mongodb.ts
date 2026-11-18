import { MongoClient, Db, Collection } from 'mongodb';
import bcrypt from 'bcryptjs';
import dns from 'node:dns';

// Ensure DNS resolvers handle MongoDB SRV records reliably on Windows/Node.js
try {
  dns.setServers(['8.8.8.8', '1.1.1.1', '8.8.4.4']);
} catch {
  // Ignore in environments where setServers is restricted
}

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

const uri =
  process.env.MONGODB_DIRECT_URI ||
  process.env.MONGODB_URI ||
  process.env.MONGO_URI ||
  '';

const dbName = process.env.MONGODB_DB_NAME || 'waguri_db';

if (!uri) {
  console.warn('[MongoDB] Warning: MONGODB_URI is not set in environment.');
}

declare global {
  var _mongoClientPromise: Promise<MongoClient> | undefined;
}

let clientPromise: Promise<MongoClient>;

if (process.env.NODE_ENV === 'development') {
  if (!global._mongoClientPromise) {
    const client = new MongoClient(uri, {
      serverSelectionTimeoutMS: 10000,
      connectTimeoutMS: 10000,
    });
    global._mongoClientPromise = client.connect();
  }
  clientPromise = global._mongoClientPromise;
} else {
  const client = new MongoClient(uri, {
    serverSelectionTimeoutMS: 10000,
    connectTimeoutMS: 10000,
  });
  clientPromise = client.connect();
}

export async function getDb(): Promise<Db> {
  const client = await clientPromise;
  return client.db(dbName);
}

let adminProvisioned = false;

export async function getAdminCollection(): Promise<Collection<AdminDocument>> {
  const db = await getDb();
  const collection = db.collection<AdminDocument>('admins');

  if (!adminProvisioned) {
    try {
      // Ensure unique index on email
      await collection.createIndex({ email: 1 }, { unique: true });

      // Check if any admin account exists
      const adminCount = await collection.countDocuments();
      if (adminCount === 0) {
        const defaultEmail = (process.env.ADMIN_EMAIL || 'admin@waguri.bot').toLowerCase().trim();
        let passwordHash = process.env.ADMIN_PASSWORD_HASH;

        if (!passwordHash) {
          const rawPassword = process.env.ADMIN_PASSWORD || 'WaguriAdmin@2026!';
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

        console.info(`[Auth] Initial admin account provisioned: ${defaultEmail}`);
      }
      adminProvisioned = true;
    } catch (err) {
      console.warn('[Auth] Note during admin collection initialization:', err);
    }
  }

  return collection;
}

export default clientPromise;
