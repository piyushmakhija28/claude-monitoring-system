# Centralized Authentication & Security Pattern

**Version:** 1.0.0
**Last Updated:** 2026-02-17
**Status:** ✅ IMPLEMENTED

## Overview

Centralized authentication system where Gateway handles all authentication (JWT, admin users, customers) and all microservices trust the Gateway's authentication decisions via headers.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Frontend (Browser/Mobile)                   │
│  - Stores JWT tokens (localStorage)                         │
│  - Sends Authorization header on every request              │
│  - Handles CSRF token from cookie                           │
└─────────────────────────────────────────────────────────────┘
                           ↓ HTTPS
┌─────────────────────────────────────────────────────────────┐
│                    Gateway (Port 8085)                       │
│  ┌──────────────────────────────────────────────────────────┤
│  │ Authentication Layer                                     │
│  │  1. CORS validation                                      │
│  │  2. CSRF token validation                                │
│  │  3. JWT validation                                       │
│  │  4. Extract user info from JWT                           │
│  │  5. Extract roles (ADMIN/USER)                           │
│  │  6. Path authorization (public/admin/user)               │
│  │  7. Add user context headers (X-User-Id, X-User-Email)   │
│  └──────────────────────────────────────────────────────────┤
└─────────────────────────────────────────────────────────────┘
                           ↓ Authenticated Request
┌─────────────────────────────────────────────────────────────┐
│                     Microservices                            │
│  - Receive user context via headers (NO JWT validation)     │
│  - Extract headers into ThreadLocal (UserContextHolder)     │
│  - Use for business logic & auditing                        │
│  - Propagate headers on service-to-service calls (Feign)    │
└─────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. Gateway Authentication Package

**Location:** `gateway/src/main/java/com/techdeveloper/auth/`

**Key Classes:**
- `AuthRestController` - REST endpoints (/login, /admin/login, /logout, /refresh)
- `AuthService` - Business logic for authentication
- `AdminUserService` - Admin user authentication
- `JwtService` - JWT generation, validation, parsing
- `JwtAuthenticationFilter` - Filter to validate JWT on every request
- `SecurityConfig` - Spring Security configuration

### 2. JWT Token Structure

**Access Token Payload:**
```json
{
  "sub": "user123",           // User ID
  "email": "user@example.com",
  "userType": "ADMIN",        // ADMIN or USER or CUSTOMER
  "projectName": "techdeveloper",
  "iat": 1708123456,          // Issued at
  "exp": 1708209856,          // Expires at (24h later)
  "type": "ACCESS"            // Token type
}
```

**Refresh Token Payload:**
```json
{
  "sub": "user123",
  "userType": "ADMIN",
  "projectName": "techdeveloper",
  "iat": 1708123456,
  "exp": 1710715456,          // Expires at (30 days later)
  "type": "REFRESH"
}
```

### 3. Admin User Table

**Table:** `admin_users`

```sql
CREATE TABLE admin_users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL,
    password VARCHAR(255) NOT NULL,  -- BCrypt hashed
    email VARCHAR(255),
    project_id BIGINT NOT NULL,      -- Reference to Project Management Service
    role VARCHAR(50) NOT NULL DEFAULT 'ADMIN',  -- ADMIN, SUPER_ADMIN
    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),

    UNIQUE KEY uk_username_project (username, project_id)
);
```

**Features:**
- One admin username per project (multi-tenant)
- BCrypt password hashing (strength 10)
- Enable/disable accounts
- Role-based access (ADMIN, SUPER_ADMIN)

### 4. Security Configuration

**Location:** `gateway/src/main/java/com/techdeveloper/auth/config/SecurityConfig.java`

**Key Features:**
```java
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Bean
    SecurityFilterChain securityFilterChain(HttpSecurity http) {
        http
            // CSRF Protection
            .csrf(csrf -> csrf.csrfTokenRepository(
                CookieCsrfTokenRepository.withHttpOnlyFalse()
            ))

            // CORS Configuration
            .cors(cors -> cors.configurationSource(corsConfigurationSource()))

            // Stateless session
            .sessionManagement(session -> session
                .sessionCreationPolicy(SessionCreationPolicy.STATELESS))

            // Authorization rules
            .authorizeHttpRequests(auth -> {
                // Public paths
                auth.requestMatchers(publicPaths).permitAll();

                // Admin paths - require ROLE_ADMIN
                for (String adminPath : adminPaths) {
                    String[] parts = adminPath.split(" ", 2);
                    HttpMethod method = HttpMethod.valueOf(parts[0]);
                    String path = parts[1];
                    auth.requestMatchers(method, path).hasRole("ADMIN");
                }

                // User authenticated paths
                auth.requestMatchers(userAuthPaths).authenticated();

                // All other requests require authentication
                auth.anyRequest().authenticated();
            })

            // JWT filter before UsernamePasswordAuthenticationFilter
            .addFilterBefore(jwtAuthenticationFilter,
                UsernamePasswordAuthenticationFilter.class);

        return http.build();
    }

    @Bean
    PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();  // Strength 10
    }
}
```

### 5. Path Configuration (Config Server)

**Location:** `techdeveloper-config-server/configurations/gateway.yml`

```yaml
security:
  # Public paths - no authentication required
  public-paths:
    - GET /api/v1/projects/**
    - GET /api/v1/clients/**
    - GET /api/v1/categories/**
    - GET /api/v1/subCategories/**
    - GET /api/v1/productTypes/**
    - GET /api/v1/products/**
    - GET /api/v1/vendors/**
    - /api/v1/auth/**             # Auth endpoints
    - /swagger-ui.html
    - /swagger-ui/**
    - /v3/api-docs/**
    - /actuator/health
    - /**/actuator/health

  # Admin paths - require ROLE_ADMIN
  admin-paths:
    - POST /api/v1/projects/**
    - PUT /api/v1/projects/**
    - DELETE /api/v1/projects/**
    - POST /api/v1/clients/**
    - PUT /api/v1/clients/**
    - DELETE /api/v1/clients/**
    - POST /api/v1/categories/**
    - PUT /api/v1/categories/**
    - DELETE /api/v1/categories/**
    # ... etc for all catalog resources

  # User authenticated paths - require any authentication
  user-authenticated-paths:
    - /api/v1/customers/**
    - /api/v1/carts/**
    - /api/v1/orders/**
    - /api/v1/payments/**

  # CORS configuration
  cors:
    allowed-origins:
      - https://techdeveloper.in
      - https://api.techdeveloper.in
      - https://surgricalswale.in
      - https://api.surgricalswale.in
      - http://localhost:4200
      - http://localhost:3000
    allowed-methods: [GET, POST, PUT, DELETE, PATCH, OPTIONS]
    allowed-headers: [Authorization, Content-Type, Accept, X-Requested-With, X-CSRF-TOKEN]
    exposed-headers: [Authorization, X-CSRF-TOKEN]
    allow-credentials: true
    max-age: 3600

  # CSRF configuration
  csrf:
    enabled: true
    cookie-http-only: false  # Allow JavaScript access
```

---

## Authentication Flows

### Flow 1: Admin Login

```
1. POST /api/v1/auth/admin/login
   Headers: X-Project-Name: techdeveloper
   Body: { username: "admin", password: "admin123" }

2. Gateway → ProjectManagementClient.getProjectByName("techdeveloper")
   Returns: { id: 1, projectName: "techdeveloper", enabled: true }

3. Gateway → AdminUserRepository.findByUsernameAndProjectId("admin", 1)
   Returns: AdminUser { username: "admin", password: "$2a$10$..." }

4. Gateway → BCrypt.matches("admin123", "$2a$10$...")
   Returns: true

5. Gateway → JwtService.generateAccessToken(userContext)
   Returns: "eyJhbGciOiJIUzUxMiJ9..."

6. Gateway → JwtService.generateRefreshToken(userContext)
   Returns: "eyJhbGciOiJIUzUxMiJ9..."

7. Gateway → AuthTokenRepository.save(authToken)
   Stores: access token, refresh token, user info, IP, User-Agent

8. Response:
   {
     "success": true,
     "message": "Admin login successful",
     "data": {
       "accessToken": "eyJhbGci...",
       "refreshToken": "eyJhbGci...",
       "tokenType": "Bearer",
       "accessTokenExpiresIn": 86400000,
       "refreshTokenExpiresIn": 2592000000,
       "user": {
         "userId": "1",
         "email": "admin@techdeveloper.in",
         "userType": "ADMIN",
         "projectName": "techdeveloper"
       }
     }
   }
```

### Flow 2: Customer Login

```
1. POST /api/v1/auth/login
   Headers: X-Project-Name: surgricalswale
   Body: { email: "customer@example.com", password: "password123" }

2. Gateway → ProjectAuthClient.authenticateWithPassword(
       "surgricalswale", "customer@example.com", "password123")

3. ProjectAuthClient → HTTP POST to surgricalswale-customer-service
   GET http://surgricalswale-customer-service/api/v1/customers/authenticate

4. Customer Service validates email/password
   Returns: CustomerDto { id, email, firstName, lastName, enabled }

5. Gateway receives UserContextDto from ProjectAuthClient

6. Gateway → JwtService.generateAccessToken(userContext)

7. Gateway → JwtService.generateRefreshToken(userContext)

8. Gateway → AuthTokenRepository.save(authToken)

9. Response: (same structure as admin login)
```

### Flow 3: API Request with JWT

```
1. GET /api/v1/products
   Headers:
     Authorization: Bearer eyJhbGci...
     X-Project-Name: surgricalswale

2. JwtAuthenticationFilter intercepts request

3. Extract JWT from Authorization header

4. JwtService.validateToken(token)
   - Verify signature
   - Check expiration
   - Verify token type = ACCESS

5. JwtService.extractUserContext(token)
   Returns: UserContextDto { userId, email, userType, projectName }

6. Extract authorities from userType:
   - ADMIN → ROLE_ADMIN + ROLE_USER
   - USER → ROLE_USER

7. Create UsernamePasswordAuthenticationToken with authorities

8. Set authentication in SecurityContext

9. Add user context headers:
   - X-User-Id: 123
   - X-User-Email: admin@techdeveloper.in
   - X-User-Role: ADMIN
   - X-Project-Name: surgricalswale

10. Forward request to microservice

11. Microservice UserContextFilter extracts headers

12. Store in UserContextHolder (ThreadLocal)

13. Business logic executes

14. Response sent back through Gateway
```

### Flow 4: Token Refresh

```
1. POST /api/v1/auth/refresh
   Headers: X-Project-Name: techdeveloper
   Body: { refreshToken: "eyJhbGci..." }

2. Find token in database:
   AuthTokenRepository.findByRefreshTokenAndIsRevokedFalse(token)

3. Verify:
   - Token not expired
   - Token not revoked
   - Project name matches
   - Token type = REFRESH

4. Extract user context from refresh token

5. Generate new access token

6. Generate new refresh token (token rotation)

7. Update AuthToken record in database

8. Response:
   {
     "success": true,
     "data": {
       "accessToken": "eyJ...",  // new
       "refreshToken": "eyJ...", // new
       "tokenType": "Bearer",
       "accessTokenExpiresIn": 86400000,
       "refreshTokenExpiresIn": 2592000000
     }
   }
```

---

## Microservice Integration

### 1. UserContextFilter (Extract Headers)

**Location:** `{project}-common-utility/.../config/UserContextFilter.java`

```java
@Component
@Order(1)  // Run FIRST
public class UserContextFilter extends OncePerRequestFilter {

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) {
        try {
            UserContext context = UserContext.builder()
                    .userId(request.getHeader("X-User-Id"))
                    .email(request.getHeader("X-User-Email"))
                    .role(request.getHeader("X-User-Role"))
                    .projectName(request.getHeader("X-Project-Name"))
                    .token(extractToken(request.getHeader("Authorization")))
                    .build();

            UserContextHolder.setContext(context);
            filterChain.doFilter(request, response);
        } finally {
            UserContextHolder.clear();  // CRITICAL: Prevent memory leak
        }
    }
}
```

### 2. FeignClientInterceptor (Propagate Headers)

**Location:** `{project}-common-utility/.../config/FeignClientInterceptor.java`

```java
@Component
public class FeignClientInterceptor implements RequestInterceptor {

    @Override
    public void apply(RequestTemplate template) {
        ServletRequestAttributes attributes =
            (ServletRequestAttributes) RequestContextHolder.getRequestAttributes();

        if (attributes != null) {
            HttpServletRequest request = attributes.getRequest();

            // Propagate all user context headers
            propagateHeader(request, template, "Authorization");
            propagateHeader(request, template, "X-User-Id");
            propagateHeader(request, template, "X-User-Email");
            propagateHeader(request, template, "X-User-Role");
            propagateHeader(request, template, "X-Project-Name");
        }
    }

    private void propagateHeader(HttpServletRequest request,
                                 RequestTemplate template,
                                 String headerName) {
        String value = request.getHeader(headerName);
        if (value != null && !value.isEmpty()) {
            template.header(headerName, value);
        }
    }
}
```

---

## Frontend Integration

### 1. AuthService (Angular)

**Location:** `{project}-ui/src/app/services/auth.service.ts`

```typescript
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly GATEWAY_URL = environment.gatewayUrl + '/api/v1/auth';

  adminLogin(username: string, password: string): Observable<ApiResponse<LoginResponse>> {
    return this.http.post<ApiResponse<LoginResponse>>(
      `${this.GATEWAY_URL}/admin/login`,
      { username, password },
      { headers: this.getHeaders() }
    ).pipe(
      tap(response => {
        if (response.success && response.data) {
          this.handleAuthSuccess(response.data);
        }
      })
    );
  }

  private handleAuthSuccess(data: LoginResponse): void {
    localStorage.setItem('access_token', data.accessToken);
    localStorage.setItem('refresh_token', data.refreshToken);
    localStorage.setItem('user_info', JSON.stringify(data.user));
  }

  private getHeaders(): HttpHeaders {
    return new HttpHeaders({
      'Content-Type': 'application/json',
      'X-Project-Name': environment.projectName
    });
  }
}
```

### 2. AuthInterceptor (Angular)

**Location:** `{project}-ui/src/app/interceptors/auth.interceptor.ts`

```typescript
@Injectable()
export class AuthInterceptor implements HttpInterceptor {

  intercept(request: HttpRequest<unknown>, next: HttpHandler): Observable<HttpEvent<unknown>> {
    // Skip auth for login endpoints
    if (this.isAuthEndpoint(request.url)) {
      return next.handle(request);
    }

    // Add auth headers
    const token = this.authService.getAccessToken();
    if (token) {
      request = this.addAuthHeaders(request, token);
    }

    return next.handle(request).pipe(
      catchError(error => {
        if (error instanceof HttpErrorResponse && error.status === 401) {
          return this.handle401Error(request, next);
        }
        return throwError(() => error);
      })
    );
  }

  private addAuthHeaders(request: HttpRequest<any>, token: string): HttpRequest<any> {
    const user = this.authService.getUserInfo();
    let headers = request.headers
      .set('Authorization', `Bearer ${token}`)
      .set('X-Project-Name', environment.projectName);

    if (user) {
      headers = headers
        .set('X-User-Id', user.userId)
        .set('X-User-Email', user.email)
        .set('X-User-Role', user.role);
    }

    return request.clone({ headers });
  }

  private handle401Error(request: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
    return this.authService.refreshToken().pipe(
      switchMap((response) => {
        const newToken = response.data.accessToken;
        return next.handle(this.addAuthHeaders(request, newToken));
      }),
      catchError((err) => {
        this.authService.logout().subscribe();
        return throwError(() => err);
      })
    );
  }
}
```

---

## Security Features

### 1. CSRF Protection

- **Token Repository:** `CookieCsrfTokenRepository.withHttpOnlyFalse()`
- **Cookie Name:** `XSRF-TOKEN`
- **Header Name:** `X-CSRF-TOKEN`
- **HTTP-Only:** `false` (allows JavaScript access)

**Frontend Usage:**
```typescript
// CSRF token automatically read from cookie by Angular
// and sent in X-CSRF-TOKEN header
```

### 2. CORS Configuration

- **Allowed Origins:** techdeveloper.in, api.techdeveloper.in, surgricalswale.in, localhost
- **Allowed Methods:** GET, POST, PUT, DELETE, PATCH, OPTIONS
- **Allowed Headers:** Authorization, Content-Type, X-CSRF-TOKEN
- **Credentials:** Allowed
- **Max Age:** 3600 seconds

### 3. Role-Based Authorization

**Mapping:**
- `userType=ADMIN` → `ROLE_ADMIN` + `ROLE_USER`
- `userType=USER` → `ROLE_USER`
- `userType=CUSTOMER` → `ROLE_USER`

**Usage in Spring Security:**
```java
.requestMatchers(HttpMethod.POST, "/api/v1/projects/**").hasRole("ADMIN")
.requestMatchers("/api/v1/customers/**").authenticated()
```

---

## Best Practices

1. ✅ **JWT stored in localStorage** (not cookies) for SPA flexibility
2. ✅ **CSRF protection** for form POST requests
3. ✅ **Token rotation** on refresh (new access + new refresh token)
4. ✅ **Token revocation** via database (is_revoked flag)
5. ✅ **Short-lived access tokens** (24 hours)
6. ✅ **Long-lived refresh tokens** (30 days)
7. ✅ **BCrypt password hashing** (strength 10)
8. ✅ **Project-based admin users** (multi-tenant)
9. ✅ **Header propagation** in service-to-service calls
10. ✅ **ThreadLocal cleanup** to prevent memory leaks

---

**End of Centralized Authentication & Security Pattern Documentation**
