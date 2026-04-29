# Auth Testing Playbook — Emergent Google Auth (Jobpath)

## Cookie / header auth
- Backend reads `session_token` from cookie first, then from `Authorization: Bearer <token>` header.
- Sessions stored in `user_sessions` collection, expire in 7 days.

## Create a test user + session directly in MongoDB
```
mongosh --eval "
use('test_database');
var userId = 'test-user-' + Date.now();
var sessionToken = 'test_session_' + Date.now();
db.users.insertOne({
  user_id: userId,
  email: 'test.user.' + Date.now() + '@example.com',
  name: 'Test User',
  picture: 'https://via.placeholder.com/150',
  created_at: new Date()
});
db.user_sessions.insertOne({
  user_id: userId,
  session_token: sessionToken,
  expires_at: new Date(Date.now() + 7*24*60*60*1000),
  created_at: new Date()
});
print('Session token: ' + sessionToken);
print('User ID: ' + userId);
"
```

## Backend API smoke
```
BACKEND=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2)
curl -s -X GET "$BACKEND/api/auth/me" -H "Authorization: Bearer $SESSION_TOKEN"
curl -s -X GET "$BACKEND/api/jobs" -H "Authorization: Bearer $SESSION_TOKEN"
curl -s -X POST "$BACKEND/api/jobs/scrape" -H "Content-Type: application/json" -H "Authorization: Bearer $SESSION_TOKEN" -d '{"limit":3}'
```

## Browser testing
```
await page.context.add_cookies([{
  "name": "session_token",
  "value": "<SESSION_TOKEN>",
  "domain": "<host-without-scheme>",
  "path": "/",
  "httpOnly": True,
  "secure": True,
  "sameSite": "None"
}])
await page.goto("<REACT_APP_BACKEND_URL-equivalent-origin>/dashboard")
```

## Checklist
- users doc has `user_id` (uuid string), `_id` is not used in queries
- All Mongo queries exclude `_id` via `{"_id": 0}`
- Session expiry is timezone-aware (UTC)
- Cookie is `httpOnly`, `secure`, `SameSite=None`
