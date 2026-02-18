# Docker, Jenkins, and Kubernetes Patterns

**Version:** 1.0.0
**Last Updated:** 2026-02-17
**Projects:** TechDeveloper, Surgricalswale, LovePoet

This document provides comprehensive patterns and templates for Docker, Jenkins CI/CD pipelines, and Kubernetes deployments across all projects.

---

## Table of Contents

1. [Docker Patterns](#docker-patterns)
2. [Jenkins Patterns](#jenkins-patterns)
3. [Kubernetes Patterns](#kubernetes-patterns)
4. [Common Patterns](#common-patterns)
5. [Reusable Templates](#reusable-templates)

---

## Docker Patterns

### Pattern 1: Spring Boot Microservice Dockerfile

**Used by:** ALL backend services (Eureka, Gateway, Config Server, all microservices)

**Key Characteristics:**
- Single-stage build (JAR pre-built by Jenkins/Maven)
- Base image: `148.113.197.135:5000/eclipse-temurin:21-jre-alpine`
- Non-root user: `spring` (UID/GID 1000)
- JVM optimized for containers
- Port varies per service

**Template:**
```dockerfile
FROM 148.113.197.135:5000/eclipse-temurin:21-jre-alpine
WORKDIR /app

RUN addgroup -g 1000 spring && adduser -u 1000 -G spring -s /bin/sh -D spring
USER 1000:1000

COPY target/*.jar app.jar

EXPOSE {PORT}

ENTRYPOINT ["java", \
    "-XX:+UseContainerSupport", \
    "-XX:MaxRAMPercentage=75.0", \
    "-XX:InitialRAMPercentage=25.0", \
    "-XX:MinRAMPercentage=25.0", \
    "-XX:+UseG1GC", \
    "-XX:MaxGCPauseMillis=200", \
    "-XX:+ParallelRefProcEnabled", \
    "-XX:+DisableExplicitGC", \
    "-XX:+UseStringDeduplication", \
    "-Djava.security.egd=file:/dev/./urandom", \
    "-jar", "app.jar"]
```

**JVM Flags Explained:**
- `UseContainerSupport` - JVM aware of container memory limits
- `MaxRAMPercentage=75.0` - Use max 75% of container memory
- `InitialRAMPercentage=25.0` - Start with 25% of container memory
- `UseG1GC` - G1 garbage collector (low pause times)
- `MaxGCPauseMillis=200` - Target max GC pause of 200ms
- `ParallelRefProcEnabled` - Parallel reference processing
- `DisableExplicitGC` - Ignore System.gc() calls
- `UseStringDeduplication` - Deduplicate identical strings
- `java.security.egd` - Use /dev/urandom for faster entropy

**Special Case - Config Server:**
```dockerfile
# ... (same as above) ...
COPY target/*.jar app.jar
COPY configurations ./configurations  # Extra: configuration files
EXPOSE 8888
# ... (same entrypoint) ...
```

### Pattern 2: Angular Frontend Dockerfile (Multi-Stage)

**Used by:** techdeveloper-ui, surgricalswale-ui

**Key Characteristics:**
- Two-stage build: Node.js build + Nginx runtime
- Build stage: `148.113.197.135:5000/node:20-alpine`
- Runtime stage: `148.113.197.135:5000/nginx-unprivileged:1.27-alpine`
- Non-root user: `101` (nginx user)
- Custom nginx.conf for Angular routing
- Health check endpoint at `/health`

**Template:**
```dockerfile
# Stage 1: Build Angular Application
FROM 148.113.197.135:5000/node:20-alpine AS builder
LABEL stage=builder
WORKDIR /app

# Build dependencies for native modules
RUN apk add --no-cache python3 make g++

# Copy package files first (layer caching optimization)
COPY package.json package-lock.json ./
RUN npm ci --frozen-lockfile --prefer-offline --no-audit

# Copy source code
COPY . .

# Production build with asset hashing
RUN npm run build -- --configuration production --output-hashing all

# Verify build output exists
RUN ls -la /app/dist/{APP_NAME}/browser || \
    (echo "ERROR: Build output not found" && exit 1)

# Stage 2: Production Nginx Runtime
FROM 148.113.197.135:5000/nginx-unprivileged:1.27-alpine
LABEL maintainer="TechDeveloper <admin@techdeveloper.com>" \
      app="{APP_NAME}" \
      project="{PROJECT}" \
      version="1.0.0"

USER root
RUN apk upgrade --no-cache && \
    apk add --no-cache curl && \
    rm -rf /var/cache/apk/*

# Create nginx cache directories with correct permissions
RUN mkdir -p /var/cache/nginx/{client_temp,proxy_temp,fastcgi_temp,uwsgi_temp,scgi_temp} && \
    chown -R 101:101 /var/cache/nginx && \
    chmod -R 755 /var/cache/nginx

RUN rm -rf /usr/share/nginx/html/*
USER 101

# Copy built Angular app from builder stage
COPY --from=builder --chown=101:101 /app/dist/{APP_NAME}/browser /usr/share/nginx/html

# Copy custom nginx configuration
COPY --chown=101:101 nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

ENV NGINX_ENTRYPOINT_QUIET_LOGS=1

CMD ["nginx", "-g", "daemon off;"]
```

**Replace:**
- `{APP_NAME}`: `techdeveloper-ui` or `surgricalswale-ui`
- `{PROJECT}`: `techdeveloper` or `surgricalswale`

### Pattern 3: Nginx Configuration for Angular

**File:** `nginx.conf`

```nginx
server {
    listen 8080;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1000;
    gzip_comp_level 6;
    gzip_types text/plain text/css application/json application/javascript
               application/x-javascript text/xml application/xml
               application/xml+rss text/javascript image/svg+xml;

    # API proxy to backend gateway
    location /api/v1/ {
        proxy_pass http://gateway.{NAMESPACE}.svc.cluster.local:8085;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Angular Service Worker - NEVER cache
    location ~ ^/(ngsw-worker\.js|ngsw\.json|safety-worker\.js)$ {
        expires -1;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
    }

    # index.html - No cache (for deployments)
    location = /index.html {
        expires -1;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
    }

    # Static assets (JS/CSS/images) - Long cache (1 year, immutable)
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    # Angular HTML5 routing fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Health check endpoint (used by K8s liveness/readiness probes)
    location = /health {
        access_log off;
        add_header 'Content-Type' 'application/json';
        return 200 '{"status":"UP"}';
    }
}
```

**Replace:**
- `{NAMESPACE}`: `techdeveloper` or `surgricalswale`

### Pattern 4: .dockerignore (Backend Services)

```
# target/ is intentionally NOT ignored - pre-built JAR needed
.mvn/
.git/
.settings/
.classpath
.project
.factorypath
.vscode/
.idea/
*.iml
*.log
*.md
!README.md
```

**Important:** The `target/` directory containing the pre-built JAR must be available for `COPY target/*.jar app.jar`.

### Pattern 5: docker-compose.yml (Local Development)

**Used for:** Local development, single-service testing

```yaml
version: '3.8'
services:
  {SERVICE_NAME}:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: {SERVICE_NAME}
    ports:
      - "{PORT}:{PORT}"
    environment:
      - SPRING_APPLICATION_NAME={SERVICE_NAME}
      - SPRING_CONFIG_IMPORT=configserver:http://techdeveloper-config-server:8888
      - SPRING_CLOUD_CONFIG_FAIL_FAST=true
      - SPRING_CLOUD_CONFIG_RETRY_ENABLED=true
      - EUREKA_CLIENT_REGISTER_WITH_EUREKA=true
      - EUREKA_CLIENT_FETCH_REGISTRY=true
      - EUREKA_CLIENT_SERVICE_URL_DEFAULT_ZONE=http://eureka-server:8761/eureka/
      - MANAGEMENT_ENDPOINTS_WEB_EXPOSURE_INCLUDE=health,info,metrics,prometheus
      - MANAGEMENT_TRACING_SAMPLING_PROBABILITY=1.0
      - JAVA_OPTS=-Xms256m -Xmx512m
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
    networks:
      - microservices-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:{PORT}/actuator/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
    restart: always

networks:
  microservices-network:
    external: true  # Shared network across all services
```

**Network Setup (one-time):**
```bash
docker network create microservices-network
```

---

## Jenkins Patterns

### Pattern 1: Simple Spring Boot Backend (No Dependencies)

**Used by:** eureka-server, techdeveloper-config-server, standalone services

```groovy
pipeline {
    agent {
        kubernetes {
            cloud 'kubernetes'
            inheritFrom 'k8s-agent'
            defaultContainer 'maven'
        }
    }

    environment {
        LOCAL_REGISTRY = '148.113.197.135:5000'
        MAVEN_CACHE = "${WORKSPACE}/../.m2"
        SERVICE_NAME = '{SERVICE_NAME}'
        K8S_NAMESPACE = '{NAMESPACE}'
        KUBECONFIG = '/var/jenkins_home/.kube/config'
    }

    stages {
        stage('Checkout') {
            steps { checkout scm }
        }

        stage('Build & Package') {
            steps {
                script {
                    sh "git config --global --add safe.directory ${WORKSPACE}"
                    sh """
                        mvn clean package -DskipTests -B -nsu -ntp \
                        -Dmaven.repo.local=${MAVEN_CACHE}
                    """
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                container('docker') {
                    script {
                        sh """
                            docker build --network host --no-cache \
                            -t ${LOCAL_REGISTRY}/${SERVICE_NAME}:latest .
                        """
                        sh "docker push ${LOCAL_REGISTRY}/${SERVICE_NAME}:latest"
                    }
                }
            }
        }

        stage('Deploy to Kubernetes') {
            steps {
                script {
                    withEnv(["KUBECONFIG=${env.KUBECONFIG}"]) {
                        sh "kubectl create namespace ${K8S_NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -"
                        sh "kubectl apply -f k8s/"
                        sh """
                            kubectl set image deployment/${SERVICE_NAME} \
                            ${SERVICE_NAME}=${LOCAL_REGISTRY}/${SERVICE_NAME}:latest \
                            -n ${K8S_NAMESPACE}
                        """
                        sh "kubectl rollout restart deployment/${SERVICE_NAME} -n ${K8S_NAMESPACE}"
                        sh "kubectl rollout status deployment/${SERVICE_NAME} -n ${K8S_NAMESPACE} --timeout=1m"
                    }
                }
            }
        }
    }

    post {
        success { echo "✅ ${SERVICE_NAME} deployed successfully" }
        failure { echo "❌ ${SERVICE_NAME} deployment failed" }
        always {
            script {
                try { cleanWs() }
                catch (Exception e) { echo "Warning: cleanWs failed: ${e.message}" }
            }
        }
    }
}
```

**Maven Flags:**
- `-DskipTests` - Skip test execution (tests run separately)
- `-B` - Batch/non-interactive mode
- `-nsu` - No snapshot updates (use cached)
- `-ntp` - No transfer progress (cleaner logs)
- `-Dmaven.repo.local=${MAVEN_CACHE}` - Shared Maven cache across builds

### Pattern 2: Spring Boot with Shared Library Dependencies

**Used by:** Gateway, all Surgricalswale microservices

**Build Order:**
1. `techdeveloper-common-utility` (base)
2. `techdeveloper-secret-manager-client` (depends on common-utility)
3. `surgricalswale-common-utility` (depends on secret-manager-client)
4. Main service

```groovy
// ... (same environment as Pattern 1) ...

stages {
    stage('Build Dependencies') {
        steps {
            script {
                // Build techdeveloper-common-utility
                dir('../techdeveloper-common-utility') {
                    git branch: 'main',
                        url: 'https://github.com/techdeveloper-org/techdeveloper-common-utility.git',
                        credentialsId: '8430c3a7-6fa4-49a2-b786-44fa5f9b513d'
                    sh "git config --global --add safe.directory ${WORKSPACE}/../techdeveloper-common-utility"
                    sh """
                        mvn clean install -DskipTests -B -nsu -ntp \
                        -Dmaven.repo.local=${MAVEN_CACHE}
                    """
                    container('docker') {
                        sh "docker build --network host --no-cache -t ${LOCAL_REGISTRY}/techdeveloper-common-utility:latest ."
                        sh "docker push ${LOCAL_REGISTRY}/techdeveloper-common-utility:latest"
                    }
                }

                // Build techdeveloper-secret-manager-client
                dir('../techdeveloper-secret-manager-client') {
                    git branch: 'main',
                        url: 'https://github.com/techdeveloper-org/techdeveloper-secret-manager-client.git',
                        credentialsId: '8430c3a7-6fa4-49a2-b786-44fa5f9b513d'
                    sh "git config --global --add safe.directory ${WORKSPACE}/../techdeveloper-secret-manager-client"
                    sh """
                        mvn clean install -DskipTests -B -nsu -ntp \
                        -Dmaven.repo.local=${MAVEN_CACHE}
                    """
                    container('docker') {
                        sh "docker build --network host --no-cache -t ${LOCAL_REGISTRY}/techdeveloper-secret-manager-client:latest ."
                        sh "docker push ${LOCAL_REGISTRY}/techdeveloper-secret-manager-client:latest"
                    }
                }

                // Build surgricalswale-common-utility (if Surgricalswale service)
                dir('../surgricalswale-common-utility') {
                    git branch: 'master',
                        url: 'https://github.com/techdeveloper-org/surgricalswale-common-utility.git',
                        credentialsId: '8430c3a7-6fa4-49a2-b786-44fa5f9b513d'
                    sh "git config --global --add safe.directory ${WORKSPACE}/../surgricalswale-common-utility"
                    sh """
                        mvn clean install -DskipTests -B -nsu -ntp \
                        -Dmaven.repo.local=${MAVEN_CACHE}
                    """
                    container('docker') {
                        sh "docker build --network host --no-cache -t ${LOCAL_REGISTRY}/surgricalswale-common-utility:latest ."
                        sh "docker push ${LOCAL_REGISTRY}/surgricalswale-common-utility:latest"
                    }
                }
            }
        }
    }

    // Then continue with standard Build & Package, Docker Build, Deploy stages...
}
```

### Pattern 3: Angular Frontend

**Used by:** techdeveloper-ui, surgricalswale-ui

```groovy
pipeline {
    agent {
        kubernetes {
            cloud 'kubernetes'
            inheritFrom 'k8s-agent'
            defaultContainer 'node'  // Node container for npm
        }
    }

    parameters {
        choice(
            name: 'BUILD_ENV',
            choices: ['production', 'development'],
            description: 'Build environment (production = Service Worker enabled)'
        )
    }

    environment {
        LOCAL_REGISTRY = '148.113.197.135:5000'
        SERVICE_NAME = '{UI_NAME}'
        K8S_NAMESPACE = '{NAMESPACE}'
        BUILD_TAG = "${env.BUILD_NUMBER}-${env.GIT_COMMIT?.take(7) ?: 'latest'}"
        KUBECONFIG = '/var/jenkins_home/.kube/config'
    }

    options {
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10', artifactNumToKeepStr: '5'))
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                script {
                    env.GIT_COMMIT = sh(returnStdout: true, script: 'git rev-parse HEAD').trim()
                }
            }
        }

        stage('Install Dependencies') {
            steps {
                sh 'npm ci --frozen-lockfile --prefer-offline --no-audit'
            }
        }

        stage('Lint') {
            steps {
                sh 'npm run lint || true'  // Non-blocking
            }
        }

        stage('Build Application') {
            steps {
                script {
                    def buildConfig = params.BUILD_ENV
                    sh """
                        npm run build -- \
                        --configuration ${buildConfig} \
                        --output-hashing all
                    """
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                container('docker') {
                    sh "docker build --no-cache -t ${LOCAL_REGISTRY}/${SERVICE_NAME}:${BUILD_TAG} ."
                    sh "docker tag ${LOCAL_REGISTRY}/${SERVICE_NAME}:${BUILD_TAG} ${LOCAL_REGISTRY}/${SERVICE_NAME}:latest"
                }
            }
        }

        stage('Push Docker Image') {
            steps {
                container('docker') {
                    sh "docker push ${LOCAL_REGISTRY}/${SERVICE_NAME}:${BUILD_TAG}"
                    sh "docker push ${LOCAL_REGISTRY}/${SERVICE_NAME}:latest"
                }
            }
        }

        stage('Deploy to Kubernetes') {
            steps {
                container('maven') {  // kubectl available in maven container
                    withEnv(["KUBECONFIG=${env.KUBECONFIG}"]) {
                        sh "kubectl create namespace ${K8S_NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -"
                        sh "kubectl apply -f k8s/ -n ${K8S_NAMESPACE}"
                        sh """
                            kubectl set image deployment/${SERVICE_NAME} \
                            ${SERVICE_NAME}=${LOCAL_REGISTRY}/${SERVICE_NAME}:latest \
                            -n ${K8S_NAMESPACE}
                        """
                        sh "kubectl rollout restart deployment/${SERVICE_NAME} -n ${K8S_NAMESPACE}"
                        sh "kubectl rollout status deployment/${SERVICE_NAME} -n ${K8S_NAMESPACE} --timeout=2m"
                        sh "kubectl get pods -n ${K8S_NAMESPACE} -l app=${SERVICE_NAME}"
                    }
                }
            }
        }
    }

    post {
        always {
            container('docker') {
                sh 'docker image prune -f'
                sh "docker images --filter 'label=stage=builder' -q | xargs -r docker rmi -f 2>/dev/null || true"
            }
            cleanWs()
        }
        success { echo "✅ UI deployed successfully" }
        failure { echo "❌ UI deployment failed" }
    }
}
```

---

## Kubernetes Patterns

### Namespaces

```
techdeveloper    - Central hub: Eureka, Gateway, Config Server, TechDeveloper services, TechDeveloper UI
surgricalswale   - Surgricalswale business microservices + UI
common           - Shared infrastructure: PostgreSQL, MongoDB, RabbitMQ, Redis, Elasticsearch
ingress-nginx    - Nginx Ingress Controller
lovepoet         - LovePoet project services
```

### Pattern 1: Backend Microservice Deployment

**Used by:** ALL Spring Boot backend services

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {SERVICE_NAME}
  namespace: {NAMESPACE}
  labels:
    app: {SERVICE_NAME}
    version: v1
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {SERVICE_NAME}
  template:
    metadata:
      labels:
        app: {SERVICE_NAME}
        version: v1
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "{PORT}"
        prometheus.io/path: "/actuator/prometheus"
    spec:
      # Optimized DNS for fast service discovery
      dnsPolicy: ClusterFirst
      dnsConfig:
        options:
          - name: ndots
            value: "1"
          - name: timeout
            value: "2"
          - name: attempts
            value: "2"

      # Pod-level security context
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000

      containers:
        - name: {SERVICE_NAME}
          image: 148.113.197.135:5000/{SERVICE_NAME}:latest
          imagePullPolicy: Always
          ports:
            - name: http
              containerPort: {PORT}
              protocol: TCP

          env:
            - name: SPRING_PROFILES_ACTIVE
              value: "{PROJECT},k8s"
            - name: SPRING_CONFIG_IMPORT
              value: "configserver:http://techdeveloper-config-server.techdeveloper.svc.cluster.local:8888"

          resources:
            requests:
              memory: "512Mi"
              cpu: "500m"
            limits:
              memory: "1Gi"
              cpu: "1000m"

          livenessProbe:
            httpGet:
              path: /actuator/health/liveness
              port: {PORT}
            initialDelaySeconds: {LIVENESS_DELAY}  # 30-120s depending on service
            periodSeconds: 30
            timeoutSeconds: 10
            failureThreshold: 3

          readinessProbe:
            httpGet:
              path: /actuator/health/readiness
              port: {PORT}
            initialDelaySeconds: {READINESS_DELAY}  # 20-80s depending on service
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3

          # Container-level security context
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: false
            runAsNonRoot: true
            runAsUser: 1000
            runAsGroup: 1000
            capabilities:
              drop:
                - ALL

      restartPolicy: Always
      terminationGracePeriodSeconds: 30
```

**Probe Initial Delays by Service Type:**

| Service Type | Liveness Delay | Readiness Delay |
|---|---|---|
| Infrastructure (Eureka, Config Server) | 60s | 40s |
| Gateway | 120s | 80s |
| Business microservices | 30s | 20s |

### Pattern 2: Frontend (Angular UI) Deployment

**Used by:** techdeveloper-ui, surgricalswale-ui

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {UI_NAME}
  namespace: {NAMESPACE}
  labels:
    app: {UI_NAME}
    tier: frontend
    project: {PROJECT}
spec:
  replicas: 2  # Higher than backend for HA
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0  # Zero-downtime updates
  selector:
    matchLabels:
      app: {UI_NAME}
  template:
    metadata:
      labels:
        app: {UI_NAME}
        tier: frontend
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 101  # nginx user
        runAsGroup: 101
        fsGroup: 101
        seccompProfile:
          type: RuntimeDefault

      containers:
        - name: {UI_NAME}
          image: 148.113.197.135:5000/{UI_NAME}:latest
          imagePullPolicy: Always
          ports:
            - name: http
              containerPort: 8080
              protocol: TCP

          resources:
            requests:
              memory: "128Mi"
              cpu: "100m"
            limits:
              memory: "512Mi"
              cpu: "500m"

          startupProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 0
            periodSeconds: 5
            failureThreshold: 12  # 60s total

          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 30
            timeoutSeconds: 5
            failureThreshold: 3

          readinessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 10
            timeoutSeconds: 3
            failureThreshold: 3

          securityContext:
            allowPrivilegeEscalation: false
            runAsNonRoot: true
            runAsUser: 101
            runAsGroup: 101
            capabilities:
              drop:
                - ALL

      terminationGracePeriodSeconds: 30
```

### Pattern 3: Service (ClusterIP)

**Used by:** ALL services

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {SERVICE_NAME}
  namespace: {NAMESPACE}
  labels:
    app: {SERVICE_NAME}
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "{PORT}"
    prometheus.io/path: "/actuator/prometheus"
spec:
  type: ClusterIP
  selector:
    app: {SERVICE_NAME}
  ports:
    - name: http
      port: {PORT}
      targetPort: {PORT}
      protocol: TCP
  sessionAffinity: ClientIP
  sessionAffinityConfig:
    clientIP:
      timeoutSeconds: 10800  # 3 hours
```

### Pattern 4: Ingress

**TechDeveloper Multi-Host Ingress:**

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: tech-ingress
  namespace: techdeveloper
  annotations:
    nginx.ingress.kubernetes.io/proxy-connect-timeout: "180"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "180"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "180"
    nginx.ingress.kubernetes.io/proxy-buffering: "off"
spec:
  ingressClassName: nginx
  rules:
    - host: api.techdeveloper.in
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: gateway
                port:
                  number: 8085

    - host: eureka.techdeveloper.in
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: eureka-server
                port:
                  number: 8761

    - host: techdeveloper.in
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: techdeveloper-ui
                port:
                  number: 4200
```

**Surgricalswale Ingress:**

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: surgricalswale-ingress
  namespace: techdeveloper
  annotations:
    nginx.ingress.kubernetes.io/proxy-connect-timeout: "180"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "180"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "180"
spec:
  ingressClassName: nginx
  rules:
    - host: surgricalswale.in
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: surgricalswale-ui
                port:
                  number: 80

    - host: www.surgricalswale.in
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: surgricalswale-ui
                port:
                  number: 80
```

### Pattern 5: Network Policy

**Central Hub Policy (TechDeveloper Namespace):**

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: central-hub-network-policy
  namespace: techdeveloper
spec:
  podSelector: {}  # Applies to ALL pods
  policyTypes:
    - Ingress
  ingress:
    # External traffic via Nginx Ingress
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx

    # Internal pod-to-pod
    - from:
        - podSelector: {}

    # Cross-namespace: surgricalswale → central services
    - from:
        - namespaceSelector:
            matchLabels:
              name: surgricalswale

    # Cross-namespace: lovepoet → central services
    - from:
        - namespaceSelector:
            matchLabels:
              name: lovepoet

    # Cross-namespace: common infrastructure
    - from:
        - namespaceSelector:
            matchLabels:
              name: common
```

**Microservices Policy (Surgricalswale Namespace):**

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: microservices-network-policy
  namespace: surgricalswale
spec:
  podSelector: {}
  policyTypes:
    - Ingress
  ingress:
    # From central hub (Gateway, Eureka, Monitoring)
    - from:
        - namespaceSelector:
            matchLabels:
              name: techdeveloper

    # From Nginx Ingress
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx

    # Internal service-to-service
    - from:
        - namespaceSelector:
            matchLabels:
              name: surgricalswale

    # From common infrastructure
    - from:
        - namespaceSelector:
            matchLabels:
              name: common
```

---

## Common Patterns

### 1. Private Registry
- **Registry:** `148.113.197.135:5000`
- **Base Images:**
  - `eclipse-temurin:21-jre-alpine` (Java 21 JRE)
  - `node:20-alpine` (Node.js 20)
  - `nginx-unprivileged:1.27-alpine` (Nginx 1.27)

### 2. Non-Root Containers
- **Backend (Spring Boot):** UID/GID 1000 (`spring` user)
- **Frontend (Nginx):** UID/GID 101 (`nginx` user)
- **Capabilities:** ALL dropped

### 3. Image Pull Policy
- **Custom services:** `Always` (Jenkins builds latest)
- **Infrastructure:** `IfNotPresent`

### 4. Service Discovery
- **DNS:** `{service-name}.{namespace}.svc.cluster.local`
- **Config Server:** `techdeveloper-config-server.techdeveloper.svc.cluster.local:8888`
- **Eureka:** `eureka-server.techdeveloper.svc.cluster.local:8761`
- **Gateway:** `gateway.techdeveloper.svc.cluster.local:8085`

### 5. Spring Profiles
- **Format:** `{PROJECT},k8s`
- **Examples:** `techdeveloper,k8s` or `surgricalswale,k8s`

### 6. Session Affinity
- **Type:** `ClientIP`
- **Timeout:** 10800 seconds (3 hours)

### 7. Prometheus Monitoring
- **Annotations:**
  ```yaml
  prometheus.io/scrape: "true"
  prometheus.io/port: "{PORT}"
  prometheus.io/path: "/actuator/prometheus"
  ```

### 8. Resource Allocation

| Service Type | Memory Request | Memory Limit | CPU Request | CPU Limit |
|---|---|---|---|---|
| Backend | 512Mi | 1Gi | 500m | 1000m |
| Frontend | 128Mi | 512Mi | 100m | 500m |
| Infrastructure | 512Mi - 2Gi | 1Gi - 4Gi | 250m - 1000m | 500m - 2000m |

### 9. DNS Tuning (Backend Only)
```yaml
dnsConfig:
  options:
    - name: ndots
      value: "1"
    - name: timeout
      value: "2"
    - name: attempts
      value: "2"
```

### 10. Maven Build Flags (Jenkins)
```bash
mvn clean package \
  -DskipTests \        # Skip tests
  -B \                 # Batch mode
  -nsu \               # No snapshot updates
  -ntp \               # No transfer progress
  -Dmaven.repo.local=${MAVEN_CACHE}  # Shared cache
```

### 11. Shared Docker Network (Local Dev)
```bash
docker network create microservices-network
```

All docker-compose.yml files reference:
```yaml
networks:
  microservices-network:
    external: true
```

### 12. Kubernetes Deployment Flow (Jenkins)
```bash
# 1. Create namespace (idempotent)
kubectl create namespace {NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

# 2. Apply manifests
kubectl apply -f k8s/ -n {NAMESPACE}

# 3. Update image
kubectl set image deployment/{SERVICE} \
  {SERVICE}={REGISTRY}/{SERVICE}:latest \
  -n {NAMESPACE}

# 4. Rolling restart
kubectl rollout restart deployment/{SERVICE} -n {NAMESPACE}

# 5. Wait for completion
kubectl rollout status deployment/{SERVICE} -n {NAMESPACE} --timeout=1m
```

---

## Reusable Templates

### Quick Reference

**Docker:**
- [Spring Boot Dockerfile](#pattern-1-spring-boot-microservice-dockerfile)
- [Angular Dockerfile](#pattern-2-angular-frontend-dockerfile-multi-stage)
- [nginx.conf](#pattern-3-nginx-configuration-for-angular)

**Jenkins:**
- [Simple Backend Jenkinsfile](#pattern-1-simple-spring-boot-backend-no-dependencies)
- [Backend with Dependencies](#pattern-2-spring-boot-with-shared-library-dependencies)
- [Angular Frontend Jenkinsfile](#pattern-3-angular-frontend)

**Kubernetes:**
- [Backend Deployment](#pattern-1-backend-microservice-deployment)
- [Frontend Deployment](#pattern-2-frontend-angular-ui-deployment)
- [Service](#pattern-3-service-clusterip)
- [Ingress](#pattern-4-ingress)
- [Network Policy](#pattern-5-network-policy)

---

## Best Practices

### Docker
1. ✅ Use private registry for all custom images
2. ✅ Run as non-root user (UID 1000 or 101)
3. ✅ Use Alpine-based images for smaller size
4. ✅ Multi-stage builds for frontend (reduce image size)
5. ✅ Pre-build JARs in Jenkins (single-stage backend Dockerfiles)
6. ✅ Layer caching optimization (package files before source code)
7. ✅ Use `.dockerignore` to exclude unnecessary files

### Jenkins
1. ✅ Use Kubernetes agents for dynamic scaling
2. ✅ Shared Maven cache (`${WORKSPACE}/../.m2`)
3. ✅ Build dependencies in correct order
4. ✅ Skip tests in CI build (-DskipTests)
5. ✅ Always cleanup workspace in `post { always }`
6. ✅ Use `--dry-run=client` for idempotent namespace creation
7. ✅ Wait for rollout status to confirm deployment

### Kubernetes
1. ✅ Use namespaces to isolate projects
2. ✅ Always set resource requests and limits
3. ✅ Configure liveness, readiness (and startup for frontend) probes
4. ✅ Use Network Policies for security
5. ✅ Run containers as non-root
6. ✅ Drop ALL capabilities
7. ✅ Use ClusterIP services (not NodePort/LoadBalancer)
8. ✅ Configure session affinity for stateful apps
9. ✅ Use DNS tuning for faster service discovery
10. ✅ Prometheus annotations for monitoring

---

**End of DevOps Patterns Documentation**
