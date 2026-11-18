const http = require('http');

const BASE_URL = 'http://localhost:3000';

function makeRequest(method, path, body = null, headers = {}, followRedirect = false) {
  return new Promise((resolve, reject) => {
    const url = new URL(path, BASE_URL);
    const options = {
      hostname: url.hostname,
      port: url.port,
      path: url.pathname + url.search,
      method: method,
      headers: {
        'Accept': 'text/html,application/json',
        ...headers,
      },
    };

    if (body) {
      const payload = typeof body === 'string' ? body : JSON.stringify(body);
      options.headers['Content-Type'] = 'application/json';
      options.headers['Content-Length'] = Buffer.byteLength(payload);
    }

    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => {
        data += chunk;
      });
      res.on('end', () => {
        resolve({
          statusCode: res.statusCode,
          headers: res.headers,
          body: data,
        });
      });
    });

    req.on('error', (err) => reject(err));

    if (body) {
      req.write(typeof body === 'string' ? body : JSON.stringify(body));
    }
    req.end();
  });
}

async function runTestSuite() {
  console.log("===============================================================================");
  console.log("       WAGURI BOT ADMIN AUTHENTICATION & SECURITY TEST SUITE");
  console.log("===============================================================================\n");

  let testsPassed = 0;
  let testsFailed = 0;

  function assert(condition, message) {
    if (condition) {
      console.log(`  [PASS] ${message}`);
      testsPassed++;
    } else {
      console.error(`  [FAIL] ${message}`);
      testsFailed++;
    }
  }

  // ---------------------------------------------------------------------------
  console.log("--- 1. Direct Page Access Without Authentication (Route Guard) ---");
  const protectedPages = ['/', '/settings', '/promotions', '/shayari', '/stickers', '/users'];
  for (const page of protectedPages) {
    const res = await makeRequest('GET', page);
    const isRedirect = res.statusCode === 307 || res.statusCode === 308 || res.statusCode === 302;
    const location = res.headers['location'] || '';
    assert(isRedirect && location.includes('/login'), `GET ${page} redirects to /login (Status: ${res.statusCode}, Location: ${location})`);
  }

  // ---------------------------------------------------------------------------
  console.log("\n--- 2. Backend Protected API Endpoints Without Authentication ---");
  const protectedApis = ['/api/users', '/api/promotions', '/api/settings', '/api/admin/me'];
  for (const api of protectedApis) {
    const res = await makeRequest('GET', api);
    assert(res.statusCode === 401, `GET ${api} blocked with 401 Unauthorized (Status: ${res.statusCode})`);
    try {
      const json = JSON.parse(res.body);
      assert(json.error !== undefined, `  ${api} returns JSON error: "${json.error}"`);
    } catch {
      assert(false, `  ${api} response body was not valid JSON`);
    }
  }

  // ---------------------------------------------------------------------------
  console.log("\n--- 3. Public Admin Login Page & UI Verification ---");
  const loginRes = await makeRequest('GET', '/login');
  assert(loginRes.statusCode === 200, `GET /login returns HTTP 200 OK (Status: ${loginRes.statusCode})`);
  assert(loginRes.body.includes('/waguri.png'), `Login page references the correct background image '/waguri.png'`);
  assert(loginRes.body.includes('Waguri Bot'), `Login page contains 'Waguri Bot' branding`);
  assert(loginRes.body.includes('Admin Login'), `Login page contains 'Admin Login' badge`);
  assert(loginRes.body.includes('Secure Admin Panel'), `Login page contains 'Secure Admin Panel' subtitle`);
  assert(!loginRes.body.toLowerCase().includes('google login'), `Login page strictly does NOT contain Google Login`);
  assert(!loginRes.body.toLowerCase().includes('sign up'), `Login page strictly does NOT contain Sign Up`);
  assert(!loginRes.body.toLowerCase().includes('forgot password'), `Login page strictly does NOT contain Forgot Password`);

  // ---------------------------------------------------------------------------
  console.log("\n--- 4. Backend Login API Validation & Negative Testing ---");
  const emptyRes = await makeRequest('POST', '/api/admin/login', {});
  assert(emptyRes.statusCode === 400, `Empty credentials rejected with HTTP 400 (Status: ${emptyRes.statusCode})`);

  const invalidEmailRes = await makeRequest('POST', '/api/admin/login', { email: 'not-an-email', password: 'password123' });
  assert(invalidEmailRes.statusCode === 400, `Malformed email rejected with HTTP 400 (Status: ${invalidEmailRes.statusCode})`);

  const TEST_EMAIL = process.env.ADMIN_EMAIL || 'waguri@gmail.com';
  const TEST_PASSWORD = process.env.ADMIN_PASSWORD || '@#$WaguriBot';

  const wrongCredsRes = await makeRequest('POST', '/api/admin/login', { email: TEST_EMAIL, password: 'WrongPassword@123' });
  assert(wrongCredsRes.statusCode === 401, `Incorrect password rejected with HTTP 401 (Status: ${wrongCredsRes.statusCode})`);
  const wrongJson = JSON.parse(wrongCredsRes.body);
  assert(wrongJson.error === 'Invalid email or password.', `Generic error message returned: "${wrongJson.error}"`);

  // ---------------------------------------------------------------------------
  console.log("\n--- 5. Valid Admin Login & HttpOnly Cookie Issuance ---");
  const validLoginRes = await makeRequest('POST', '/api/admin/login', {
    email: TEST_EMAIL,
    password: TEST_PASSWORD,
  });
  assert(validLoginRes.statusCode === 200, `Valid login returns HTTP 200 OK (Status: ${validLoginRes.statusCode})`);
  const validJson = JSON.parse(validLoginRes.body);
  assert(validJson.success === true, `Response indicates success: ${validJson.success}`);
  assert(validJson.user?.email === TEST_EMAIL, `Response user email: ${validJson.user?.email}`);
  assert(validJson.passwordHash === undefined && validJson.user?.passwordHash === undefined, `Password hash is strictly NEVER exposed in response`);

  // Extract auth cookie
  const setCookieHeader = validLoginRes.headers['set-cookie'];
  assert(Array.isArray(setCookieHeader) && setCookieHeader.length > 0, `Set-Cookie header received`);
  const cookieStr = setCookieHeader ? setCookieHeader.find(c => c.startsWith('waguri_admin_token=')) : '';
  assert(cookieStr && cookieStr.includes('HttpOnly'), `waguri_admin_token cookie is marked HttpOnly`);
  assert(cookieStr && cookieStr.toLowerCase().includes('samesite=lax'), `waguri_admin_token cookie has SameSite=Lax`);

  const authToken = cookieStr ? cookieStr.split(';')[0] : '';
  const authHeaders = { 'Cookie': authToken };

  // ---------------------------------------------------------------------------
  console.log("\n--- 6. Authenticated Session Access to Protected Pages & APIs ---");
  const authMeRes = await makeRequest('GET', '/api/admin/me', null, authHeaders);
  assert(authMeRes.statusCode === 200, `GET /api/admin/me with session returns HTTP 200 (Status: ${authMeRes.statusCode})`);
  const authMeJson = JSON.parse(authMeRes.body);
  assert(authMeJson.authenticated === true, `Session is authenticated: ${authMeJson.authenticated}`);
  assert(authMeJson.user?.email === TEST_EMAIL, `Session user: ${authMeJson.user?.email}`);

  const authDashboardRes = await makeRequest('GET', '/', null, authHeaders);
  assert(authDashboardRes.statusCode === 200, `GET / with session returns HTTP 200 OK (Dashboard accessible)`);

  const authUsersApiRes = await makeRequest('GET', '/api/users', null, authHeaders);
  assert(authUsersApiRes.statusCode === 200, `GET /api/users with session returns HTTP 200 (API accessible)`);

  // ---------------------------------------------------------------------------
  console.log("\n--- 7. Login Page Redirect When Already Authenticated ---");
  const loginWhileAuthRes = await makeRequest('GET', '/login', null, authHeaders);
  const isAuthRedirect = loginWhileAuthRes.statusCode === 307 || loginWhileAuthRes.statusCode === 308 || loginWhileAuthRes.statusCode === 302;
  const authRedirectLoc = loginWhileAuthRes.headers['location'] || '';
  assert(isAuthRedirect && (authRedirectLoc.endsWith('/') || authRedirectLoc === 'http://localhost:3000/'),
    `GET /login when authenticated redirects to main dashboard / (Status: ${loginWhileAuthRes.statusCode}, Location: ${authRedirectLoc})`);

  // ---------------------------------------------------------------------------
  console.log("\n--- 8. Admin Logout Flow & Post-Logout Protection ---");
  const logoutRes = await makeRequest('POST', '/api/admin/logout', null, authHeaders);
  assert(logoutRes.statusCode === 200, `POST /api/admin/logout returns HTTP 200 OK (Status: ${logoutRes.statusCode})`);
  const logoutCookies = logoutRes.headers['set-cookie'];
  const clearedCookie = logoutCookies ? logoutCookies.find(c => c.startsWith('waguri_admin_token=')) : '';
  assert(clearedCookie && (clearedCookie.includes('Max-Age=0') || clearedCookie.includes('expires=Thu, 01 Jan 1970')), `waguri_admin_token is cleared/expired upon logout`);

  // Try accessing dashboard with cleared cookie
  const postLogoutHeaders = { 'Cookie': 'waguri_admin_token=; Max-Age=0' };
  const postLogoutDashRes = await makeRequest('GET', '/', null, postLogoutHeaders);
  const isPostLogoutRedirect = postLogoutDashRes.statusCode === 307 || postLogoutDashRes.statusCode === 308;
  assert(isPostLogoutRedirect && postLogoutDashRes.headers['location']?.includes('/login'),
    `Dashboard access immediately blocked after logout (Redirects to /login)`);

  const postLogoutMeRes = await makeRequest('GET', '/api/admin/me', null, postLogoutHeaders);
  assert(postLogoutMeRes.statusCode === 401, `GET /api/admin/me returns HTTP 401 after logout`);

  // ---------------------------------------------------------------------------
  console.log("\n===============================================================================");
  console.log(`SUMMARY: ${testsPassed} PASSED, ${testsFailed} FAILED out of ${testsPassed + testsFailed} tests.`);
  console.log("===============================================================================");

  if (testsFailed > 0) {
    process.exit(1);
  }
}

runTestSuite().catch(err => {
  console.error("Test execution encountered an error:", err);
  process.exit(1);
});
