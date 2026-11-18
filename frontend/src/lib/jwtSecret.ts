const configuredSecret = process.env.JWT_SECRET;

if (!configuredSecret || new TextEncoder().encode(configuredSecret).byteLength < 32) {
  throw new Error('JWT_SECRET must be configured with at least 32 bytes.');
}

export const jwtSecretKey = new TextEncoder().encode(configuredSecret);
