import urllib.request
import json

res = urllib.request.urlopen('http://localhost:3000/api/users')
data = json.loads(res.read())

print("=== PERSONAL DM ACCOUNTS (Added Bot on Personal Direct Messages) ===")
print(f"Total: {len(data['users'])}")
for u in data['users']:
    print(f" • Account Name: {u['firstName']}")
    print(f"   Username: @{u.get('username')}")
    print(f"   User ID: {u['telegramId']}")
    print(f"   Features in Use:")
    for f in u['featuresUsed']:
        print(f"     - {f['name']} ({f['statusLabel']})")
    print()

print("=== GROUP CHATS (GCs that Added the Bot) ===")
print(f"Total: {len(data['groups'])}")
for g in data['groups']:
    print(f" • Group Title: {g['title']}")
    print(f"   Chat ID: {g['chatId']}")
    print(f"   Features in Use:")
    for f in g['featuresUsed']:
        print(f"     - {f['name']} ({f['statusLabel']})")
    print()

print("=== CHANNELS (Channels that Added the Bot) ===")
print(f"Total: {len(data['channels'])}")
for c in data['channels']:
    print(f" • Channel Title: {c['title']}")
    print(f"   Channel ID: {c['channelId']}")
    print(f"   Features in Use:")
    for f in c['featuresUsed']:
        print(f"     - {f['name']} ({f['statusLabel']})")
    print()
