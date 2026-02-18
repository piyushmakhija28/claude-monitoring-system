# JPA Auditing Pattern

**Version:** 1.0.0
**Last Updated:** 2026-02-17
**Status:** ✅ IMPLEMENTED

## Overview

JPA Auditing automatically tracks creation and modification metadata for all entities across all microservices. This provides complete audit trail of who created/modified records and when.

---

## Implementation

### 1. AuditableEntity Base Class

**Location:** `{project}-common-utility/src/main/java/com/techdeveloper/{project}/entity/AuditableEntity.java`

```java
@Getter
@Setter
@MappedSuperclass
@EntityListeners(AuditingEntityListener.class)
public abstract class AuditableEntity {

    @CreatedDate
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @LastModifiedDate
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    @CreatedBy
    @Column(name = "created_by", updatable = false, length = 100)
    private String createdBy;

    @LastModifiedBy
    @Column(name = "updated_by", length = 100)
    private String updatedBy;
}
```

**Key Points:**
- `@MappedSuperclass` - Not an entity itself, fields inherited by subclasses
- `@EntityListeners(AuditingEntityListener.class)` - Triggers audit population
- `@CreatedDate` / `@LastModifiedDate` - Auto-populated timestamps
- `@CreatedBy` / `@LastModifiedBy` - Auto-populated user info
- `updatable = false` on created fields - Immutable after creation

### 2. AuditorAwareImpl (User Provider)

**Location:** `{project}-common-utility/src/main/java/com/techdeveloper/{project}/config/AuditorAwareImpl.java`

```java
@Component("auditorAwareImpl")
public class AuditorAwareImpl implements AuditorAware<String> {

    @Override
    public Optional<String> getCurrentAuditor() {
        try {
            UserContext context = UserContextHolder.getContext();
            if (context != null && context.isAuthenticated()) {
                String auditor = context.getEmail() != null
                    ? context.getEmail()
                    : context.getUserId();
                return Optional.ofNullable(auditor);
            }
            return Optional.of("SYSTEM");
        } catch (Exception e) {
            return Optional.of("SYSTEM");
        }
    }
}
```

**Key Points:**
- Returns current user from `UserContextHolder` (ThreadLocal)
- Falls back to "SYSTEM" if no user context available
- Prefers email, falls back to userId
- Uses `@Component("auditorAwareImpl")` for explicit bean name

### 3. Enable JPA Auditing

**Location:** Every service's main application class

```java
@SpringBootApplication
@EnableDiscoveryClient
@EnableTransactionManagement(mode = AdviceMode.PROXY)
@EnableJpaAuditing(auditorAwareRef = "auditorAwareImpl")
public class ServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(ServiceApplication.class, args);
    }
}
```

**Key Points:**
- `@EnableJpaAuditing(auditorAwareRef = "auditorAwareImpl")` - Activates auditing
- References the `AuditorAwareImpl` bean by name
- Must be on main application class or a @Configuration class

### 4. Entity Usage

```java
@Entity
@Table(name = "products")
public class Product extends AuditableEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String name;
    private BigDecimal price;

    // Audit fields inherited from AuditableEntity:
    // - createdAt
    // - updatedAt
    // - createdBy
    // - updatedBy
}
```

**Automatic Behavior:**
- On `INSERT`: `createdAt`, `createdBy` auto-populated
- On `UPDATE`: `updatedAt`, `updatedBy` auto-populated
- No manual code needed!

---

## Database Schema

### Table Structure

```sql
CREATE TABLE products (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255),
    price DECIMAL(10,2),

    -- Audit columns (inherited from AuditableEntity)
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP,
    created_by VARCHAR(100),
    updated_by VARCHAR(100)
);
```

### Migration Script Example

```sql
-- Add audit columns to existing table
ALTER TABLE products
    ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    ADD COLUMN created_by VARCHAR(100) DEFAULT 'SYSTEM',
    ADD COLUMN updated_by VARCHAR(100);
```

---

## Integration with User Context

### Flow

```
1. HTTP Request arrives at Gateway
   ↓
2. JwtAuthenticationFilter extracts user from JWT
   ↓
3. User info stored in SecurityContext
   ↓
4. UserContextFilter extracts from headers
   ↓
5. UserContext stored in ThreadLocal (UserContextHolder)
   ↓
6. Service method executes
   ↓
7. Repository save() triggered
   ↓
8. AuditingEntityListener calls AuditorAwareImpl
   ↓
9. getCurrentAuditor() reads from UserContextHolder
   ↓
10. Audit fields auto-populated
   ↓
11. Entity saved to database
```

### User Context Components

**UserContext (POJO):**
```java
@Builder
@Data
public class UserContext {
    private String userId;
    private String email;
    private String role;
    private String projectName;
    private String token;

    public boolean isAuthenticated() {
        return userId != null && !userId.isEmpty();
    }
}
```

**UserContextHolder (ThreadLocal):**
```java
public class UserContextHolder {
    private static final ThreadLocal<UserContext> contextHolder = new ThreadLocal<>();

    public static void setContext(UserContext context) {
        contextHolder.set(context);
    }

    public static UserContext getContext() {
        return contextHolder.get();
    }

    public static void clear() {
        contextHolder.remove();
    }
}
```

**UserContextFilter (Extracts from headers):**
```java
@Component
@Order(1)
public class UserContextFilter extends OncePerRequestFilter {

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
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
            UserContextHolder.clear();
        }
    }
}
```

---

## Dependencies

**pom.xml (common-utility):**
```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-data-jpa</artifactId>
</dependency>

<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-security</artifactId>
</dependency>
```

---

## Testing

### Example Test

```java
@DataJpaTest
@Import(AuditorAwareImpl.class)
class ProductRepositoryTest {

    @Autowired
    private ProductRepository productRepository;

    @Test
    void shouldPopulateAuditFields() {
        // Setup user context
        UserContext context = UserContext.builder()
                .userId("123")
                .email("test@example.com")
                .build();
        UserContextHolder.setContext(context);

        // Create and save entity
        Product product = new Product();
        product.setName("Test Product");
        product.setPrice(new BigDecimal("99.99"));

        Product saved = productRepository.save(product);

        // Verify audit fields
        assertNotNull(saved.getCreatedAt());
        assertNotNull(saved.getUpdatedAt());
        assertEquals("test@example.com", saved.getCreatedBy());
        assertEquals("test@example.com", saved.getUpdatedBy());

        // Cleanup
        UserContextHolder.clear();
    }
}
```

---

## Best Practices

1. ✅ **Always extend AuditableEntity** for database tables that need audit trail
2. ✅ **UserContextFilter must run FIRST** (@Order(1)) to populate context
3. ✅ **Always clear ThreadLocal** in finally block to prevent memory leaks
4. ✅ **Use SYSTEM as fallback** for background jobs/scheduled tasks
5. ✅ **Index audit columns** for query performance (created_at, updated_at)
6. ✅ **Don't override audit fields** - they're auto-populated
7. ✅ **Use LocalDateTime** (not Date) for timezone-aware timestamps

---

## Troubleshooting

### Issue: createdBy/updatedBy are always "SYSTEM"

**Cause:** UserContext not available in ThreadLocal

**Solutions:**
1. Check UserContextFilter is registered and runs first (@Order(1))
2. Verify X-User-Id/X-User-Email headers are sent from Gateway
3. Check FeignClientInterceptor is propagating headers in service-to-service calls

### Issue: Audit fields are null

**Cause:** JPA Auditing not enabled

**Solutions:**
1. Add `@EnableJpaAuditing(auditorAwareRef = "auditorAwareImpl")` to main class
2. Verify AuditorAwareImpl bean exists with correct name
3. Check entity extends AuditableEntity
4. Verify @EntityListeners(AuditingEntityListener.class) is on AuditableEntity

### Issue: updatedAt not changing on UPDATE

**Cause:** Database trigger or JPA not detecting changes

**Solutions:**
1. Use `@LastModifiedDate` annotation
2. Check @DynamicUpdate on entity if needed
3. Verify transaction is committed

---

## Services Implemented

### Surgricalswale Project (12 services)
✅ surgricalswale-cart-service
✅ surgricalswale-category-service
✅ surgricalswale-customer-service
✅ surgricalswale-dashboard-analytics-service
✅ surgricalswale-email-service
✅ surgricalswale-invoice-service
✅ surgricalswale-order-service
✅ surgricalswale-payment-service
✅ surgricalswale-product-service
✅ surgricalswale-product-type-service
✅ surgricalswale-subcategory-service
✅ surgricalswale-vendor-service

### TechDeveloper Project
✅ techdeveloper-common-utility (base implementation)
✅ All services that depend on common-utility

---

**End of JPA Auditing Pattern Documentation**
