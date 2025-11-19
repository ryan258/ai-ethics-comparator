# AI Ethics Comparator - Realistic Roadmap (v5.0 → v6.0)

**Current State Assessment:** Feature-Complete Research Beta
**Target State:** Production-Ready Research Platform
**Timeline:** 6-8 weeks of focused development
**Last Updated:** November 4, 2025

---

## Table of Contents

1. [Current State: Honest Assessment](#current-state-honest-assessment)
2. [Critical Path to Stability](#critical-path-to-stability)
3. [Foundation Phase (v5.1)](#foundation-phase-v51)
4. [Production Phase (v5.2)](#production-phase-v52)
5. [Scale Phase (v5.3)](#scale-phase-v53)
6. [Launch Phase (v6.0)](#launch-phase-v60)
7. [Future Vision (v6.1+)](#future-vision-v61)
8. [Success Metrics](#success-metrics)
9. [Risk Management](#risk-management)

---

## Current State: Honest Assessment

### What Works Well ✅

**Core Functionality (v1-v5):**
- Comprehensive ethical scenario testing (27 scenarios)
- Dual paradox support (trolley-type + open-ended)
- Batch model runner with progress tracking
- Side-by-side comparison with Chi-square testing
- AI-powered insight generation
- Publication-quality statistical analysis module
- Full reproducibility (all parameters captured)
- Results dashboard with export (CSV/JSON)
- Security-conscious design (Helmet, CORS, Zod validation)
- Excellent documentation (README, HANDBOOK, ROADMAP)

### What's Broken 🔴

**Critical Blockers:**
- **Application fails to start** (p-limit TypeError)
- **Zero test coverage** (0% - no tests exist)
- **No observability** (no logging, monitoring, or error tracking)
- **Missing production features** (rate limiting, graceful shutdown)

**Technical Debt:**
- Mixed concerns in controllers (130+ line functions)
- Global state in frontend (7+ global variables)
- No service layer abstraction
- Hardcoded configuration values
- Large monolithic client.js file (>1000 lines estimated)

### Reality Check

**Previous Claim:**
> "Phase 6 (V5.0) is now COMPLETE! The AI Ethics Comparator is now production-ready and suitable for publication as a credible research tool."

**Actual State:**
- **Feature-Complete:** Yes ✅
- **Research-Capable:** Yes ✅
- **Production-Ready:** No ❌
- **Fully Tested:** No ❌
- **Operationally Mature:** No ❌

**Appropriate Label:** "Feature-Complete Research Beta"

---

## Critical Path to Stability

### Emergency Hotfix (v5.0.1) - IMMEDIATE

**Goal:** Make the application functional again
**Timeline:** 1-2 days
**Priority:** 🔴 CRITICAL

#### Tasks

1. **Fix p-limit Import Bug** (1-2 hours)
   ```javascript
   // Investigate and fix the TypeError
   // Verify module resolution
   // Test with fresh npm install
   ```
   - Delete node_modules and package-lock.json
   - Fresh `npm install`
   - Verify p-limit v2.3.0 compatibility
   - Test application startup on clean machine
   - Consider upgrading to p-limit v3.x if needed (requires ESM migration)

2. **Audit and Fix Dependencies** (2-3 hours)
   - Run `npm audit fix`
   - Verify Express 5.x stability (consider downgrade to 4.x)
   - Check Zod version (package.json shows 4.1.12 but v3.x is latest)
   - Update openai SDK if needed
   - Document all dependency decisions

3. **Add Environment Validation** (1 hour)
   ```javascript
   // server.js - add at startup
   const requiredEnvVars = ['OPENROUTER_API_KEY'];
   const missingVars = requiredEnvVars.filter(v => !process.env[v]);

   if (missingVars.length > 0) {
     console.error(`Missing required environment variables: ${missingVars.join(', ')}`);
     console.error('Please check your .env file');
     process.exit(1);
   }
   ```

4. **Create .env.example** (30 minutes)
   - Document all environment variables
   - Include descriptions and example values
   - Add comments explaining each variable's purpose

5. **Basic Smoke Test** (30 minutes)
   - Manual testing checklist
   - Verify app starts
   - Verify one query completes successfully
   - Verify results dashboard loads
   - Document known issues

**Acceptance Criteria:**
- ✅ Application starts without errors
- ✅ Can complete one full query cycle
- ✅ Results are properly saved and displayed
- ✅ All environment variables documented
- ✅ No security vulnerabilities in npm audit

**Deliverables:**
- Working application
- Updated .env.example
- Smoke test checklist document
- Known issues list

---

## Foundation Phase (v5.1)

**Goal:** Build testing infrastructure and observability foundation
**Timeline:** 2-3 weeks
**Priority:** 🔴 HIGH - Cannot skip this

### Why Testing First?

Without tests, you cannot:
- Refactor safely
- Add features confidently
- Verify bug fixes work
- Prevent regressions
- Call the project "production-ready"

**Testing is not optional for production software.**

### Milestone 1: Testing Infrastructure (Week 1)

**Estimated Time:** 6-8 hours

#### Setup Testing Framework

```bash
npm install --save-dev jest supertest @types/jest
```

#### Configure Jest

```javascript
// jest.config.js
module.exports = {
  testEnvironment: 'node',
  coverageDirectory: 'coverage',
  collectCoverageFrom: [
    'server.js',
    'aiService.js',
    'public/stats.js',
    '!node_modules/**'
  ],
  coverageThreshold: {
    global: {
      branches: 60,
      functions: 70,
      lines: 70,
      statements: 70
    }
  }
};
```

#### Update package.json

```json
{
  "scripts": {
    "test": "jest",
    "test:watch": "jest --watch",
    "test:coverage": "jest --coverage",
    "test:ci": "jest --ci --coverage --maxWorkers=2"
  }
}
```

### Milestone 2: Unit Tests (Week 1)

**Estimated Time:** 8-12 hours
**Target Coverage:** 70%+ for pure functions

#### Priority 1: Test stats.js (4-5 hours)

```javascript
// __tests__/stats.test.js
describe('Statistical Analysis Module', () => {
  describe('chiSquareTest', () => {
    test('returns null for empty datasets', () => {
      expect(chiSquareTest([0, 0, 0], [0, 0, 0])).toBeNull();
    });

    test('detects significant differences', () => {
      const result = chiSquareTest([30, 5, 0], [5, 30, 0]);
      expect(result.significant).toBe(true);
      expect(result.pValue).toBeLessThan(0.05);
    });

    test('handles identical distributions', () => {
      const result = chiSquareTest([10, 10, 0], [10, 10, 0]);
      expect(result.significant).toBe(false);
      expect(result.pValue).toBeGreaterThan(0.05);
    });
  });

  describe('wilsonConfidenceInterval', () => {
    test('handles zero total', () => {
      const result = wilsonConfidenceInterval(0, 0);
      expect(result.proportion).toBe(0);
      expect(result.lower).toBe(0);
      expect(result.upper).toBe(0);
    });

    test('calculates correct CI for 50% proportion', () => {
      const result = wilsonConfidenceInterval(50, 100, 0.95);
      expect(result.proportion).toBeCloseTo(0.5, 2);
      expect(result.lower).toBeCloseTo(0.4, 1);
      expect(result.upper).toBeCloseTo(0.6, 1);
    });
  });

  // Add tests for:
  // - bootstrapConsistency
  // - cohensH
  // - interRunEffectSize
  // - comprehensiveStats
});
```

#### Priority 2: Test Server Helpers (3-4 hours)

```javascript
// __tests__/helpers.test.js
describe('Server Helper Functions', () => {
  describe('parseDecision', () => {
    test('parses valid {1} token', () => {
      const result = parseDecision('{1} I choose group 1 because...');
      expect(result.group).toBe('1');
      expect(result.token).toBe('{1}');
      expect(result.explanation).toBe('I choose group 1 because...');
    });

    test('parses valid {2} token', () => {
      const result = parseDecision('{2} Group 2 is better');
      expect(result.group).toBe('2');
      expect(result.explanation).toBe('Group 2 is better');
    });

    test('returns null for invalid input', () => {
      expect(parseDecision('No token here')).toBeNull();
      expect(parseDecision('{3}')).toBeNull();
      expect(parseDecision('')).toBeNull();
      expect(parseDecision(null)).toBeNull();
    });

    test('handles whitespace correctly', () => {
      const result = parseDecision('  {1}  explanation  ');
      expect(result.group).toBe('1');
      expect(result.explanation).toBe('explanation');
    });
  });

  describe('sanitizeModelName', () => {
    test('converts to lowercase', () => {
      expect(sanitizeModelName('GPT-4')).toBe('gpt-4');
    });

    test('replaces special chars with hyphens', () => {
      expect(sanitizeModelName('openai/gpt-4o')).toBe('openai-gpt-4o');
    });

    test('handles empty string', () => {
      expect(sanitizeModelName('')).toBe('model');
    });
  });

  describe('buildPrompt', () => {
    test('replaces placeholders correctly', () => {
      const paradox = {
        promptTemplate: 'Choose between {{GROUP1}} and {{GROUP2}}',
        group1Default: 'A',
        group2Default: 'B'
      };
      const result = buildPrompt(paradox, { group1: 'X', group2: 'Y' });
      expect(result.prompt).toBe('Choose between X and Y');
    });

    test('uses defaults when groups not provided', () => {
      const paradox = {
        promptTemplate: '{{GROUP1}} vs {{GROUP2}}',
        group1Default: 'Default1',
        group2Default: 'Default2'
      };
      const result = buildPrompt(paradox, {});
      expect(result.prompt).toBe('Default1 vs Default2');
    });
  });
});
```

### Milestone 3: Integration Tests (Week 2)

**Estimated Time:** 10-12 hours
**Target:** All API endpoints tested

#### Setup Test Helpers

```javascript
// __tests__/helpers/testServer.js
const express = require('express');
const app = require('../server'); // Export app from server.js

let server;

beforeAll(() => {
  server = app.listen(0); // Random port
});

afterAll(() => {
  server.close();
});

module.exports = { app };
```

#### Mock OpenRouter API

```javascript
// __tests__/helpers/mockAI.js
const mockAI = {
  responses: {
    trolley: '{1} I choose group 1 because they are younger.',
    openEnded: 'This is a thoughtful response to the ethical dilemma.'
  },

  mockSuccess(type = 'trolley') {
    jest.spyOn(require('../../aiService'), 'getModelResponse')
      .mockResolvedValue(this.responses[type]);
  },

  mockFailure(errorCode = 500) {
    jest.spyOn(require('../../aiService'), 'getModelResponse')
      .mockRejectedValue({ status: errorCode, message: 'API error' });
  },

  restore() {
    jest.restoreAllMocks();
  }
};

module.exports = mockAI;
```

#### API Endpoint Tests

```javascript
// __tests__/api/query.test.js
const request = require('supertest');
const { app } = require('../helpers/testServer');
const mockAI = require('../helpers/mockAI');

describe('POST /api/query', () => {
  afterEach(() => {
    mockAI.restore();
  });

  test('validates required fields', async () => {
    const response = await request(app)
      .post('/api/query')
      .send({});

    expect(response.status).toBe(400);
    expect(response.body.error).toMatch(/Invalid request/i);
  });

  test('rejects invalid model name format', async () => {
    const response = await request(app)
      .post('/api/query')
      .send({
        modelName: 'model with spaces!!!',
        paradoxId: 'trolley_problem',
        iterations: 1
      });

    expect(response.status).toBe(400);
  });

  test('completes trolley-type query successfully', async () => {
    mockAI.mockSuccess('trolley');

    const response = await request(app)
      .post('/api/query')
      .send({
        modelName: 'test-model',
        paradoxId: 'trolley_problem',
        iterations: 3,
        groups: { group1: 'A', group2: 'B' }
      });

    expect(response.status).toBe(200);
    expect(response.body.runId).toBeDefined();
    expect(response.body.summary.total).toBe(3);
    expect(response.body.responses).toHaveLength(3);
  });

  test('handles API failures gracefully', async () => {
    mockAI.mockFailure(500);

    const response = await request(app)
      .post('/api/query')
      .send({
        modelName: 'test-model',
        paradoxId: 'trolley_problem',
        iterations: 1
      });

    expect(response.status).toBe(500);
    expect(response.body.error).toBeDefined();
  });

  test('saves run to filesystem', async () => {
    mockAI.mockSuccess('trolley');

    const response = await request(app)
      .post('/api/query')
      .send({
        modelName: 'test-model',
        paradoxId: 'trolley_problem',
        iterations: 1
      });

    const fs = require('fs').promises;
    const path = require('path');
    const runPath = path.join(__dirname, '../../results', response.body.runId, 'run.json');

    const runData = JSON.parse(await fs.readFile(runPath, 'utf8'));
    expect(runData.runId).toBe(response.body.runId);
  });
});

// __tests__/api/runs.test.js
describe('GET /api/runs', () => {
  test('returns empty array when no runs exist', async () => {
    // Mock empty results directory
    const response = await request(app).get('/api/runs');
    expect(response.status).toBe(200);
    expect(Array.isArray(response.body)).toBe(true);
  });

  test('returns list of runs sorted by timestamp', async () => {
    // Create mock runs
    // Test sorting
  });
});

// __tests__/api/health.test.js
describe('GET /health', () => {
  test('returns healthy status', async () => {
    const response = await request(app).get('/health');
    expect(response.status).toBe(200);
    expect(response.body.status).toBe('healthy');
    expect(response.body.version).toBeDefined();
  });
});
```

### Milestone 4: Observability Foundation (Week 2-3)

**Estimated Time:** 6-8 hours

#### Add Structured Logging

```bash
npm install winston
```

```javascript
// lib/logger.js
const winston = require('winston');

const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true }),
    winston.format.json()
  ),
  defaultMeta: { service: 'ai-ethics-comparator' },
  transports: [
    new winston.transports.File({
      filename: 'logs/error.log',
      level: 'error'
    }),
    new winston.transports.File({
      filename: 'logs/combined.log'
    })
  ]
});

if (process.env.NODE_ENV !== 'production') {
  logger.add(new winston.transports.Console({
    format: winston.format.combine(
      winston.format.colorize(),
      winston.format.simple()
    )
  }));
}

module.exports = logger;
```

#### Add Request Logging

```bash
npm install morgan
```

```javascript
// server.js
const morgan = require('morgan');
const logger = require('./lib/logger');

// Morgan stream that uses winston
const stream = {
  write: (message) => logger.info(message.trim())
};

app.use(morgan('combined', { stream }));
```

#### Add API Call Logging to aiService.js

```javascript
// aiService.js - add to getModelResponseWithRetry
logger.info('OpenRouter request', {
  model: modelName,
  hasSystemPrompt: !!systemPrompt,
  params: {
    temperature: requestParams.temperature,
    max_tokens: requestParams.max_tokens
  },
  retryCount
});

// After response
logger.info('OpenRouter response', {
  model: modelName,
  responseLength: response.length,
  duration: Date.now() - startTime
});
```

#### Create Logging Documentation

```markdown
// docs/LOGGING.md
# Logging Guide

## Log Levels
- error: Application errors, API failures
- warn: Rate limits, retries, recoverable issues
- info: Request logs, successful operations
- debug: Detailed debugging information

## Log Files
- logs/error.log: Error level only
- logs/combined.log: All levels
- Console: Development only

## Monitoring Queries
grep "OpenRouter request" logs/combined.log | wc -l  # Count API calls
grep "error" logs/error.log | tail -20              # Recent errors
```

### Milestone 5: Configuration Management (Week 3)

**Estimated Time:** 3-4 hours

#### Create Config Module

```javascript
// config/index.js
require('dotenv').config();

function getEnvInt(key, defaultValue) {
  const value = process.env[key];
  return value ? parseInt(value, 10) : defaultValue;
}

function getEnvBool(key, defaultValue) {
  const value = process.env[key];
  if (value === undefined) return defaultValue;
  return value === 'true' || value === '1';
}

const config = {
  server: {
    port: getEnvInt('PORT', 3000),
    baseUrl: process.env.APP_BASE_URL || 'http://localhost:3000',
    appName: process.env.APP_NAME || 'AI Ethics Comparator'
  },

  openrouter: {
    apiKey: process.env.OPENROUTER_API_KEY,
    baseUrl: process.env.OPENROUTER_BASE_URL || 'https://openrouter.ai/api/v1',
    maxRetries: getEnvInt('OPENROUTER_MAX_RETRIES', 4),
    retryDelayMs: getEnvInt('OPENROUTER_RETRY_DELAY_MS', 2000),
    maxConcurrent: getEnvInt('OPENROUTER_MAX_CONCURRENT', 2)
  },

  limits: {
    maxIterations: getEnvInt('MAX_ITERATIONS', 50),
    minIterations: 1,
    maxModelNameLength: 200,
    maxPromptLength: 2000
  },

  storage: {
    resultsRoot: process.env.RESULTS_ROOT || './results'
  },

  logging: {
    level: process.env.LOG_LEVEL || 'info'
  },

  // Validate required config
  validate() {
    const errors = [];

    if (!this.openrouter.apiKey) {
      errors.push('OPENROUTER_API_KEY is required');
    }

    if (errors.length > 0) {
      throw new Error(`Configuration errors:\n${errors.join('\n')}`);
    }
  }
};

// Validate on load
config.validate();

module.exports = config;
```

#### Update Code to Use Config

```javascript
// server.js
const config = require('./config');

const port = config.server.port;
const limit = pLimit(config.openrouter.maxConcurrent);

// aiService.js
const config = require('./config');

const MAX_RETRIES = config.openrouter.maxRetries;
const INITIAL_RETRY_DELAY = config.openrouter.retryDelayMs;
```

### v5.1 Acceptance Criteria

Before proceeding to v5.2, verify:

- ✅ Test suite runs successfully
- ✅ Code coverage >70% for tested modules
- ✅ All API endpoints have integration tests
- ✅ Structured logging implemented
- ✅ Configuration centralized
- ✅ No hardcoded magic numbers
- ✅ CI pipeline setup (GitHub Actions)
- ✅ README updated with testing instructions

### v5.1 Deliverables

- Complete test suite (unit + integration)
- Jest configuration
- Winston logging system
- Centralized configuration module
- CI/CD workflow file
- Updated documentation

**Estimated Total Time for v5.1:** 2-3 weeks

---

## Production Phase (v5.2)

**Goal:** Add production-grade operational features
**Timeline:** 1-2 weeks
**Priority:** 🟡 HIGH

### Milestone 1: Security Hardening (Week 1)

**Estimated Time:** 6-8 hours

#### Add Rate Limiting

```bash
npm install express-rate-limit
```

```javascript
// middleware/rateLimiter.js
const rateLimit = require('express-rate-limit');
const logger = require('../lib/logger');

const apiLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // Limit each IP to 100 requests per window
  standardHeaders: true,
  legacyHeaders: false,
  handler: (req, res) => {
    logger.warn('Rate limit exceeded', { ip: req.ip, path: req.path });
    res.status(429).json({
      error: 'Too many requests, please try again later.',
      retryAfter: req.rateLimit.resetTime
    });
  }
});

const queryLimiter = rateLimit({
  windowMs: 60 * 60 * 1000, // 1 hour
  max: 20, // Max 20 query runs per hour per IP
  message: {
    error: 'Query rate limit exceeded. This endpoint uses external API credits.',
    retryAfter: '1 hour'
  }
});

module.exports = { apiLimiter, queryLimiter };
```

```javascript
// server.js
const { apiLimiter, queryLimiter } = require('./middleware/rateLimiter');

app.use('/api/', apiLimiter);
app.post('/api/query', queryLimiter, async (req, res) => {
  // ... query logic
});
```

#### Improve Error Handling

```javascript
// middleware/errorHandler.js
const logger = require('../lib/logger');

function errorHandler(err, req, res, next) {
  logger.error('Unhandled error', {
    error: err.message,
    stack: err.stack,
    path: req.path,
    method: req.method
  });

  const isDevelopment = process.env.NODE_ENV !== 'production';

  res.status(err.status || 500).json({
    error: isDevelopment ? err.message : 'Internal server error',
    ...(isDevelopment && { stack: err.stack })
  });
}

module.exports = errorHandler;
```

```javascript
// server.js
app.use(errorHandler);
```

#### Add Request Body Size Limits

```javascript
// server.js
app.use(express.json({
  limit: '10mb',
  verify: (req, res, buf, encoding) => {
    // Log large requests
    if (buf.length > 1000000) { // >1MB
      logger.warn('Large request body', {
        size: buf.length,
        path: req.path
      });
    }
  }
}));
```

### Milestone 2: Graceful Operations (Week 1)

**Estimated Time:** 4-6 hours

#### Implement Graceful Shutdown

```javascript
// lib/shutdown.js
const logger = require('./logger');

class GracefulShutdown {
  constructor(server) {
    this.server = server;
    this.isShuttingDown = false;
    this.connections = new Set();

    // Track connections
    server.on('connection', (conn) => {
      this.connections.add(conn);
      conn.on('close', () => {
        this.connections.delete(conn);
      });
    });
  }

  async shutdown(signal) {
    if (this.isShuttingDown) return;
    this.isShuttingDown = true;

    logger.info(`Received ${signal}, starting graceful shutdown`);

    // Stop accepting new connections
    this.server.close(() => {
      logger.info('Server closed, all requests completed');
    });

    // Give requests 30 seconds to complete
    setTimeout(() => {
      logger.warn('Forcing shutdown after timeout');
      this.connections.forEach(conn => conn.destroy());
      process.exit(1);
    }, 30000);

    // Wait for existing connections to close
    await new Promise((resolve) => {
      const checkInterval = setInterval(() => {
        if (this.connections.size === 0) {
          clearInterval(checkInterval);
          resolve();
        }
      }, 1000);
    });

    logger.info('Graceful shutdown complete');
    process.exit(0);
  }
}

module.exports = GracefulShutdown;
```

```javascript
// server.js
const GracefulShutdown = require('./lib/shutdown');

const server = app.listen(port, () => {
  logger.info(`Server listening at http://localhost:${port}`);
});

const shutdown = new GracefulShutdown(server);

process.on('SIGTERM', () => shutdown.shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown.shutdown('SIGINT'));
```

#### Add Health Check Improvements

```javascript
// routes/health.js
const express = require('express');
const router = express.Router();
const fs = require('fs').promises;
const path = require('path');
const config = require('../config');

router.get('/health', async (req, res) => {
  const health = {
    status: 'healthy',
    version: require('../package.json').version,
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    checks: {}
  };

  // Check filesystem access
  try {
    await fs.access(config.storage.resultsRoot);
    health.checks.filesystem = 'ok';
  } catch (error) {
    health.checks.filesystem = 'error';
    health.status = 'degraded';
  }

  // Check memory usage
  const memUsage = process.memoryUsage();
  health.checks.memory = {
    heapUsed: `${Math.round(memUsage.heapUsed / 1024 / 1024)}MB`,
    heapTotal: `${Math.round(memUsage.heapTotal / 1024 / 1024)}MB`
  };

  if (memUsage.heapUsed / memUsage.heapTotal > 0.9) {
    health.status = 'degraded';
  }

  const statusCode = health.status === 'healthy' ? 200 : 503;
  res.status(statusCode).json(health);
});

router.get('/health/ready', (req, res) => {
  // Kubernetes readiness probe
  res.status(200).json({ ready: true });
});

router.get('/health/live', (req, res) => {
  // Kubernetes liveness probe
  res.status(200).json({ alive: true });
});

module.exports = router;
```

### Milestone 3: Service Layer Refactoring (Week 2)

**Estimated Time:** 8-10 hours

#### Extract Business Logic

```javascript
// services/ExperimentRunner.js
const logger = require('../lib/logger');
const aiService = require('../aiService');
const pLimit = require('p-limit');
const config = require('../config');

class ExperimentRunner {
  constructor() {
    this.limit = pLimit(config.openrouter.maxConcurrent);
  }

  async runExperiment({
    modelName,
    paradox,
    groups,
    iterations,
    systemPrompt,
    params
  }) {
    logger.info('Starting experiment', {
      modelName,
      paradoxId: paradox.id,
      iterations
    });

    const { prompt, group1Text, group2Text } = this.buildPrompt(paradox, groups);
    const responses = await this.executeIterations({
      modelName,
      prompt,
      systemPrompt,
      params,
      iterations,
      paradoxType: paradox.type
    });

    const summary = this.computeSummary(responses, paradox.type, {
      group1: group1Text,
      group2: group2Text
    });

    return {
      prompt,
      groups: { group1: group1Text, group2: group2Text },
      paradoxType: paradox.type,
      responses,
      summary
    };
  }

  async executeIterations(config) {
    const { modelName, prompt, systemPrompt, params, iterations, paradoxType } = config;
    const promises = [];

    for (let i = 0; i < iterations; i++) {
      const delayMs = i * 200; // Stagger requests

      const promise = new Promise(resolve => setTimeout(resolve, delayMs))
        .then(() => this.limit(() =>
          aiService.getModelResponse(modelName, prompt, systemPrompt, params)
            .then(rawResponse => ({
              iteration: i + 1,
              rawResponse,
              timestamp: new Date().toISOString()
            }))
        ));

      promises.push(promise);
    }

    const results = await Promise.all(promises);
    return results.map(result => this.parseResponse(result, paradoxType));
  }

  parseResponse(result, paradoxType) {
    const { iteration, rawResponse, timestamp } = result;

    if (paradoxType === 'trolley') {
      const parsed = this.parseDecision(rawResponse);
      return {
        iteration,
        decisionToken: parsed?.token ?? null,
        group: parsed?.group ?? null,
        explanation: parsed?.explanation?.trim?.() || '',
        raw: rawResponse,
        timestamp
      };
    } else {
      return {
        iteration,
        response: rawResponse,
        raw: rawResponse,
        timestamp
      };
    }
  }

  buildPrompt(paradox, providedGroups = {}) {
    const { promptTemplate, group1Default, group2Default } = paradox;

    const group1Text = (providedGroups.group1 || '').trim() || group1Default || '';
    const group2Text = (providedGroups.group2 || '').trim() || group2Default || '';

    const prompt = (promptTemplate || paradox.prompt || '')
      .replaceAll('{{GROUP1}}', group1Text)
      .replaceAll('{{GROUP2}}', group2Text);

    return { prompt, group1Text, group2Text };
  }

  parseDecision(rawResponse) {
    if (typeof rawResponse !== 'string') return null;

    const match = rawResponse.match(/^\s*\{([12])\}\s*/);
    if (!match) return null;

    return {
      group: match[1],
      token: `{${match[1]}}`,
      explanation: rawResponse.slice(match[0].length).trim()
    };
  }

  computeSummary(responses, paradoxType, groups) {
    if (paradoxType !== 'trolley') {
      return {
        total: responses.length,
        type: 'open_ended',
        message: `${responses.length} iteration${responses.length !== 1 ? 's' : ''} completed`
      };
    }

    const total = responses.length;
    const counts = { group1: 0, group2: 0, undecided: 0 };

    responses.forEach(r => {
      if (r.group === '1') counts.group1++;
      else if (r.group === '2') counts.group2++;
      else counts.undecided++;
    });

    return {
      total,
      group1: {
        count: counts.group1,
        percentage: total ? (counts.group1 / total) * 100 : 0,
        description: groups.group1 || ''
      },
      group2: {
        count: counts.group2,
        percentage: total ? (counts.group2 / total) * 100 : 0,
        description: groups.group2 || ''
      },
      undecided: {
        count: counts.undecided,
        percentage: total ? (counts.undecided / total) * 100 : 0
      }
    };
  }
}

module.exports = ExperimentRunner;
```

```javascript
// services/RunRepository.js
const fs = require('fs').promises;
const path = require('path');
const logger = require('../lib/logger');
const config = require('../config');

class RunRepository {
  constructor(resultsRoot = config.storage.resultsRoot) {
    this.resultsRoot = resultsRoot;
  }

  async save(runData) {
    const { runDir, runId } = await this.createRunDirectory(runData.modelName);
    const runPath = path.join(runDir, 'run.json');

    const record = {
      runId,
      timestamp: new Date().toISOString(),
      ...runData
    };

    await fs.writeFile(runPath, JSON.stringify(record, null, 2), 'utf8');
    logger.info('Run saved', { runId, runPath });

    return record;
  }

  async findAll() {
    try {
      await fs.access(this.resultsRoot);
    } catch {
      return [];
    }

    const entries = await fs.readdir(this.resultsRoot, { withFileTypes: true });
    const runs = [];

    for (const entry of entries) {
      if (!entry.isDirectory()) continue;

      try {
        const runPath = path.join(this.resultsRoot, entry.name, 'run.json');
        const runData = JSON.parse(await fs.readFile(runPath, 'utf8'));

        runs.push({
          runId: runData.runId,
          timestamp: runData.timestamp,
          modelName: runData.modelName,
          paradoxId: runData.paradoxId,
          iterationCount: runData.iterationCount
        });
      } catch (error) {
        logger.warn(`Failed to read run ${entry.name}`, { error: error.message });
      }
    }

    return runs.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
  }

  async findById(runId) {
    const runPath = path.join(this.resultsRoot, runId, 'run.json');
    const runData = await fs.readFile(runPath, 'utf8');
    return JSON.parse(runData);
  }

  async createRunDirectory(modelName) {
    await fs.mkdir(this.resultsRoot, { recursive: true });
    const baseName = this.sanitizeModelName(modelName);

    for (let index = 1; index < 1000; index++) {
      const suffix = String(index).padStart(3, '0');
      const runId = `${baseName}-${suffix}`;
      const runDir = path.join(this.resultsRoot, runId);

      try {
        await fs.mkdir(runDir);
        return { runDir, runId };
      } catch (error) {
        if (error.code === 'EEXIST') continue;
        throw error;
      }
    }

    throw new Error('Unable to allocate run directory');
  }

  sanitizeModelName(modelName) {
    const safe = (modelName || 'model')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
    return safe.length ? safe : 'model';
  }
}

module.exports = RunRepository;
```

#### Refactor Server to Use Services

```javascript
// server.js
const ExperimentRunner = require('./services/ExperimentRunner');
const RunRepository = require('./services/RunRepository');

const experimentRunner = new ExperimentRunner();
const runRepository = new RunRepository();

app.post('/api/query', queryLimiter, async (req, res, next) => {
  try {
    const validation = queryRequestSchema.safeParse(req.body);
    if (!validation.success) {
      return res.status(400).json({
        error: 'Invalid request data',
        details: validation.error.format()
      });
    }

    const { modelName, paradoxId, groups, iterations, systemPrompt, params } = validation.data;

    // Load paradox
    const paradoxesData = await fs.readFile('paradoxes.json', 'utf8');
    const paradoxes = JSON.parse(paradoxesData);
    const paradox = paradoxes.find(p => p.id === paradoxId);

    if (!paradox) {
      return res.status(404).json({ error: 'Paradox not found' });
    }

    // Run experiment
    const result = await experimentRunner.runExperiment({
      modelName,
      paradox,
      groups,
      iterations: iterations || 10,
      systemPrompt,
      params
    });

    // Save results
    const record = await runRepository.save({
      modelName,
      paradoxId,
      paradoxType: paradox.type,
      iterationCount: iterations || 10,
      systemPrompt,
      params,
      ...result
    });

    res.json(record);
  } catch (error) {
    next(error);
  }
});
```

### v5.2 Acceptance Criteria

- ✅ Rate limiting implemented and tested
- ✅ Graceful shutdown working
- ✅ Enhanced health checks
- ✅ Service layer extracted and tested
- ✅ Error handling consistent
- ✅ All logging structured
- ✅ Security audit passed

### v5.2 Deliverables

- Rate limiting middleware
- Graceful shutdown system
- Service layer (ExperimentRunner, RunRepository)
- Enhanced error handling
- Security documentation

**Estimated Total Time for v5.2:** 1-2 weeks

---

## Scale Phase (v5.3)

**Goal:** Optimize for performance and scale to 500+ runs
**Timeline:** 1-2 weeks
**Priority:** 🟢 MEDIUM

### Milestone 1: Performance Optimization (Week 1)

**Estimated Time:** 6-8 hours

#### Parallelize Run Loading

```javascript
// services/RunRepository.js
async findAll() {
  try {
    await fs.access(this.resultsRoot);
  } catch {
    return [];
  }

  const entries = await fs.readdir(this.resultsRoot, { withFileTypes: true });
  const directories = entries.filter(e => e.isDirectory());

  // Parallel reads with concurrency limit
  const limit = pLimit(10);
  const runPromises = directories.map(entry =>
    limit(async () => {
      try {
        const runPath = path.join(this.resultsRoot, entry.name, 'run.json');
        const runData = JSON.parse(await fs.readFile(runPath, 'utf8'));

        return {
          runId: runData.runId,
          timestamp: runData.timestamp,
          modelName: runData.modelName,
          paradoxId: runData.paradoxId,
          iterationCount: runData.iterationCount
        };
      } catch (error) {
        logger.warn(`Failed to read run ${entry.name}`, { error: error.message });
        return null;
      }
    })
  );

  const runs = (await Promise.all(runPromises)).filter(Boolean);
  return runs.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
}
```

#### Add Response Caching

```javascript
// middleware/cache.js
const cache = new Map();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

function cacheMiddleware(req, res, next) {
  const key = req.originalUrl;
  const cached = cache.get(key);

  if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
    res.setHeader('X-Cache', 'HIT');
    return res.json(cached.data);
  }

  res.setHeader('X-Cache', 'MISS');

  const originalJson = res.json.bind(res);
  res.json = (data) => {
    cache.set(key, { data, timestamp: Date.now() });
    return originalJson(data);
  };

  next();
}

// Clear cache when new run is saved
function invalidateCache() {
  cache.clear();
}

module.exports = { cacheMiddleware, invalidateCache };
```

```javascript
// server.js
const { cacheMiddleware } = require('./middleware/cache');

app.get('/api/runs', cacheMiddleware, async (req, res) => {
  // ... existing logic
});
```

#### Add Pagination

```javascript
// routes/runs.js
router.get('/api/runs', cacheMiddleware, async (req, res) => {
  try {
    const page = parseInt(req.query.page) || 1;
    const limit = parseInt(req.query.limit) || 20;
    const offset = (page - 1) * limit;

    const allRuns = await runRepository.findAll();
    const total = allRuns.length;
    const runs = allRuns.slice(offset, offset + limit);

    res.json({
      runs,
      pagination: {
        page,
        limit,
        total,
        totalPages: Math.ceil(total / limit),
        hasNext: offset + limit < total,
        hasPrev: page > 1
      }
    });
  } catch (error) {
    next(error);
  }
});
```

### Milestone 2: Frontend Optimization (Week 1-2)

**Estimated Time:** 6-8 hours

#### Refactor Client State Management

```javascript
// public/state.js
const AppState = {
  // Data
  paradoxes: [],
  runs: [],
  currentRun: null,
  currentChart: null,

  // UI State
  view: 'query',
  compareMode: false,
  batchMode: false,
  selectedRuns: [],

  // Update state and notify listeners
  listeners: [],

  set(key, value) {
    this[key] = value;
    this.notify(key, value);
  },

  subscribe(callback) {
    this.listeners.push(callback);
    return () => {
      this.listeners = this.listeners.filter(cb => cb !== callback);
    };
  },

  notify(key, value) {
    this.listeners.forEach(cb => cb(key, value));
  }
};
```

#### Add Virtual Scrolling for Results

```javascript
// For lists with 100+ items, implement virtual scrolling
// Consider using a library like 'virtual-scroller' or implement basic version
```

### Milestone 3: Data Management (Week 2)

**Estimated Time:** 4-6 hours

#### Add Run Metadata Index

```javascript
// services/RunIndexer.js
class RunIndexer {
  constructor(resultsRoot) {
    this.resultsRoot = resultsRoot;
    this.indexPath = path.join(resultsRoot, '.index.json');
  }

  async buildIndex() {
    const runs = await runRepository.findAll();
    const index = {
      version: 1,
      lastUpdated: new Date().toISOString(),
      runs: runs.map(r => ({
        runId: r.runId,
        timestamp: r.timestamp,
        modelName: r.modelName,
        paradoxId: r.paradoxId
      }))
    };

    await fs.writeFile(this.indexPath, JSON.stringify(index, null, 2));
    return index;
  }

  async readIndex() {
    try {
      const data = await fs.readFile(this.indexPath, 'utf8');
      return JSON.parse(data);
    } catch {
      return null;
    }
  }

  async getOrBuildIndex() {
    const index = await this.readIndex();
    if (index) return index;
    return this.buildIndex();
  }
}
```

#### Add Search/Filter API

```javascript
// routes/runs.js
router.get('/api/runs/search', async (req, res) => {
  try {
    const { model, paradox, dateFrom, dateTo } = req.query;

    let runs = await runRepository.findAll();

    if (model) {
      runs = runs.filter(r => r.modelName.includes(model));
    }

    if (paradox) {
      runs = runs.filter(r => r.paradoxId === paradox);
    }

    if (dateFrom) {
      runs = runs.filter(r => new Date(r.timestamp) >= new Date(dateFrom));
    }

    if (dateTo) {
      runs = runs.filter(r => new Date(r.timestamp) <= new Date(dateTo));
    }

    res.json(runs);
  } catch (error) {
    next(error);
  }
});
```

### v5.3 Acceptance Criteria

- ✅ Run loading <1 second for 100 runs
- ✅ Run loading <3 seconds for 500 runs
- ✅ Pagination working on client and server
- ✅ Response caching reduces repeat query time
- ✅ Search/filter API implemented
- ✅ Client state management improved
- ✅ Performance benchmarks documented

### v5.3 Deliverables

- Optimized run loading (parallel)
- Pagination implementation
- Caching middleware
- Search/filter API
- Client state refactoring
- Performance benchmarks document

**Estimated Total Time for v5.3:** 1-2 weeks

---

## Launch Phase (v6.0)

**Goal:** Production launch with confidence
**Timeline:** 1 week
**Priority:** 🟢 MEDIUM

### Milestone 1: Final Validation (Week 1)

#### Production Readiness Checklist

```markdown
# Production Readiness Checklist

## Code Quality
- [x] Test coverage >70%
- [x] All tests passing
- [x] No linting errors
- [x] Code review completed
- [x] Service layer extracted
- [x] Configuration centralized

## Security
- [x] npm audit shows no vulnerabilities
- [x] Rate limiting implemented
- [x] Input validation comprehensive
- [x] XSS protection verified
- [x] CORS properly configured
- [x] Environment variables not committed
- [x] API keys server-side only

## Operational
- [x] Structured logging implemented
- [x] Health checks working
- [x] Graceful shutdown implemented
- [x] Error handling consistent
- [x] Performance benchmarks met

## Documentation
- [x] README complete and accurate
- [x] API documentation up to date
- [x] Deployment guide written
- [x] CONTRIBUTING.md exists
- [x] Troubleshooting guide written
- [x] Known limitations documented

## Deployment
- [x] Environment variables documented
- [x] Database migrations (if any) tested
- [x] Backup/restore procedures documented
- [x] Rollback plan exists
- [x] Monitoring configured
```

### Milestone 2: Documentation Completion

**Estimated Time:** 4-6 hours

#### Create Missing Documentation

```markdown
// docs/DEPLOYMENT.md
# Deployment Guide

## Prerequisites
- Node.js 20.x or higher
- OpenRouter API key
- Minimum 512MB RAM
- 1GB disk space (for ~1000 runs)

## Environment Variables
See .env.example for full list

## Deployment Options

### Option 1: Traditional Server
1. Clone repository
2. npm install
3. Configure .env
4. npm start

### Option 2: Docker (Coming Soon)

### Option 3: Cloud Platforms
- Heroku
- Railway
- Render
- DigitalOcean App Platform

## Reverse Proxy (HTTPS)
Recommended: nginx with Let's Encrypt

## Backup Strategy
- Backup ./results directory daily
- Backup .env file (securely!)
- Test restore procedure

## Monitoring
- Check /health endpoint every 60s
- Alert on 503 status
- Monitor logs/error.log

---

// docs/TROUBLESHOOTING.md
# Troubleshooting Guide

## Application Won't Start

### p-limit Error
**Symptom:** `TypeError: pLimit is not a function`
**Fix:**
1. Delete node_modules and package-lock.json
2. npm install
3. Verify p-limit version in package.json

### Missing Environment Variables
**Symptom:** "OPENROUTER_API_KEY is required"
**Fix:** Copy .env.example to .env and fill in values

## API Errors

### Rate Limit Exceeded
**Symptom:** 429 status code
**Fix:** Wait for rate limit window to reset

### Model Not Found
**Symptom:** 404 from OpenRouter
**Fix:** Check model name format (e.g., "anthropic/claude-3.5-sonnet")

---

// docs/CONTRIBUTING.md
# Contributing Guide

## Development Setup
1. Fork repository
2. Clone your fork
3. npm install
4. Copy .env.example to .env
5. Add your OpenRouter API key
6. npm run dev

## Running Tests
npm test
npm run test:watch
npm run test:coverage

## Code Style
- Use 2 spaces for indentation
- Use semicolons
- Follow existing patterns
- Add JSDoc comments for functions

## Pull Request Process
1. Create feature branch
2. Write tests for new features
3. Ensure all tests pass
4. Update documentation
5. Submit PR with clear description

## Adding New Paradoxes
1. Edit paradoxes.json
2. Follow existing schema
3. Test with multiple models
4. Document expected behavior
```

### Milestone 3: Launch Preparation

**Estimated Time:** 2-3 hours

#### Update Version and Changelog

```markdown
// CHANGELOG.md
# Changelog

## [6.0.0] - 2025-XX-XX

### Added
- Complete test suite (unit + integration)
- Structured logging with Winston
- Rate limiting on API endpoints
- Graceful shutdown handling
- Service layer architecture
- Performance optimizations
- Pagination for results
- Search and filter API
- Production documentation

### Changed
- Refactored controllers to use services
- Centralized configuration
- Improved error handling
- Optimized run loading (parallel)

### Fixed
- p-limit import bug
- Dependency vulnerabilities
- Memory leaks in chart rendering
- Race conditions in directory creation

### Security
- Added rate limiting
- Improved CSP headers
- Enhanced input validation
- Audit passed with 0 vulnerabilities

---

## [5.0.0] - 2025-10-31

### Added (Previous Releases)
- License & repository metadata
- Full reproducibility parameters
- Rate limiting & concurrency control
- Input sanitization & validation
- Enhanced statistical analysis
- Research ethics documentation
- Security hardening
- Health check & versioning

[See ROADMAP.md for v1-v5 history]
```

#### Create Release Checklist

```markdown
# v6.0 Release Checklist

## Pre-Release
- [ ] All tests passing
- [ ] Version bumped to 6.0.0
- [ ] CHANGELOG.md updated
- [ ] README.md reviewed
- [ ] Documentation complete
- [ ] Security audit clean

## Release
- [ ] Tag release: git tag v6.0.0
- [ ] Push tags: git push --tags
- [ ] Create GitHub release
- [ ] Announce on social media (if applicable)
- [ ] Update documentation site

## Post-Release
- [ ] Monitor error logs for 24h
- [ ] Check health endpoint
- [ ] Gather user feedback
- [ ] Plan v6.1 based on feedback
```

### v6.0 Acceptance Criteria

**All production-ready requirements met:**

- ✅ Application starts without errors
- ✅ Test coverage >70%
- ✅ All API endpoints tested
- ✅ Rate limiting active
- ✅ Structured logging
- ✅ Graceful shutdown
- ✅ Health checks comprehensive
- ✅ Documentation complete
- ✅ Security audit passed
- ✅ Performance benchmarks met

**Can now honestly claim: "Production-Ready"**

### v6.0 Deliverables

- Production-ready application
- Complete documentation
- Deployment guide
- Troubleshooting guide
- Contributing guide
- Release notes

**Estimated Total Time for v6.0:** 1 week

---

## Future Vision (v6.1+)

**Goal:** Enhance research capabilities and user experience
**Timeline:** Ongoing
**Priority:** 🔵 LOW to MEDIUM

### v6.1: Usability Enhancements (2-3 weeks)

#### UI Polish
- Dark mode toggle (3-4 hours)
- Keyboard shortcuts (2-3 hours)
- Model presets dropdown (2 hours)
- Run tagging/categories (4-5 hours)
- Favorites/bookmarks (3-4 hours)
- Improved error messages (2-3 hours)

#### Data Management
- Run notes/annotations (3-4 hours)
- Bulk operations (delete, export) (4-5 hours)
- Run duplication (2 hours)
- Custom paradox templates (6-8 hours)

**Estimated Total:** 30-40 hours (2-3 weeks)

### v6.2: Advanced Analysis (2-3 weeks)

#### Statistical Enhancements
- Display confidence intervals in UI (using existing stats.js) (4-5 hours)
- Consistency scoring visualization (3-4 hours)
- Effect size indicators (2-3 hours)
- Trend analysis over time (6-8 hours)

#### Research Tools
- Response clustering (8-10 hours)
- Pattern detection (8-10 hours)
- Comparative reports (6-8 hours)
- Custom statistical tests (4-6 hours)

**Estimated Total:** 40-50 hours (2-3 weeks)

### v6.3: Collaboration Features (3-4 weeks)

#### Sharing
- Share runs via URL (4-5 hours)
- Export to research paper format (6-8 hours)
- Public/private run toggle (3-4 hours)
- Run collections (5-6 hours)

#### Multi-User (If Needed)
- User authentication (8-10 hours)
- Team workspaces (10-12 hours)
- Collaborative analysis (8-10 hours)
- Activity feed (4-5 hours)

**Estimated Total:** 50-60 hours (3-4 weeks)

### v7.0: Database Migration (2-3 weeks)

**When:** >500 runs, performance degradation noticed

#### SQLite Implementation
- Schema design (4-6 hours)
- Migration script for existing runs (6-8 hours)
- Repository layer update (8-10 hours)
- Query optimization (4-6 hours)
- Full-text search (4-6 hours)
- Index optimization (2-3 hours)
- Testing and validation (6-8 hours)

#### Backward Compatibility
- Keep filesystem as option (4 hours)
- Config flag: STORAGE_BACKEND=sqlite|filesystem (2 hours)
- Migration documentation (2-3 hours)

**Estimated Total:** 40-50 hours (2-3 weeks)

### v8.0: Advanced Integrations (4-6 weeks)

#### API Providers
- Direct provider integrations (Anthropic, OpenAI APIs) (10-12 hours)
- Provider cost tracking (6-8 hours)
- Automatic model discovery (4-6 hours)

#### Export Formats
- PDF reports with charts (8-10 hours)
- LaTeX export for papers (6-8 hours)
- Markdown reports (4-5 hours)

#### Analytics
- Dashboard with aggregate stats (10-12 hours)
- Custom chart builder (8-10 hours)
- Data visualization library (6-8 hours)

**Estimated Total:** 80-100 hours (4-6 weeks)

---

## Success Metrics

### Technical Metrics

**Code Quality:**
- Test coverage: >70% (v5.1+)
- Zero high/critical npm audit issues
- Linting: 0 errors
- TypeScript: 0 errors (if migrated)

**Performance:**
- Server startup: <3 seconds
- Run loading (100 runs): <1 second
- Run loading (500 runs): <3 seconds
- Query response: <30 seconds (depends on model)
- Memory usage: <200MB idle, <500MB under load

**Reliability:**
- Uptime: >99.5%
- Error rate: <1%
- Successful query completion: >95%
- Mean time to recovery: <5 minutes

### Research Metrics

**Usage:**
- Active researchers: Track via analytics
- Runs per week: Measure adoption
- Models tested: Diversity of experimentation
- Paradoxes used: Feature utilization

**Quality:**
- Papers published using tool: Citation tracking
- GitHub stars/forks: Community interest
- Issues/PRs: Community engagement
- Documentation views: User self-service

### Community Metrics

- GitHub stars: Target 100+
- Contributors: Target 5+
- Issues resolved: >80% within 30 days
- PR merge time: <7 days average

---

## Risk Management

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Dependency vulnerabilities | Medium | High | Regular npm audit, automated scanning |
| OpenRouter API changes | Medium | High | Version lock SDK, monitor changelogs |
| Performance degradation | Low | Medium | Benchmarking, profiling, early SQLite migration |
| Data loss | Low | Critical | Backup strategy, data validation |
| Memory leaks | Low | Medium | Monitoring, load testing |

### Project Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Scope creep | Medium | Medium | Strict roadmap, prioritization |
| Testing debt | Low | High | v5.1 makes testing mandatory |
| Documentation debt | Low | Medium | Update docs with each feature |
| Burnout | Low | High | Realistic timelines, incremental progress |

### Research Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Misinterpretation of results | Medium | High | Comprehensive HANDBOOK, interpretation warnings |
| Ethical concerns | Low | High | Research ethics documentation |
| Model API costs | Medium | Medium | Rate limiting, cost tracking |
| Reproducibility issues | Low | High | Full parameter capture, versioning |

---

## Comparison: Old vs. New Roadmap

### Old Roadmap (v5.0)

**Claimed Status:**
- "Phase 6 COMPLETE"
- "Production-ready"
- "Suitable for publication"

**Reality:**
- Application doesn't start ❌
- Zero tests ❌
- Missing operational features ❌
- Production-ready claim: **FALSE**

### New Roadmap (This Document)

**Honest Status:**
- "Feature-complete research beta"
- "Needs testing, observability, optimization"
- "6-8 weeks to production-ready"

**Approach:**
- Fix critical bugs first ✅
- Build foundation (testing) ✅
- Add operational features ✅
- Optimize for scale ✅
- Launch with confidence ✅

**Production-ready claim:** **After v6.0 completion**

---

## Timeline Summary

| Phase | Duration | Description | Priority |
|-------|----------|-------------|----------|
| v5.0.1 | 1-2 days | Emergency hotfix | 🔴 Critical |
| v5.1 | 2-3 weeks | Testing & observability foundation | 🔴 High |
| v5.2 | 1-2 weeks | Production features (rate limiting, shutdown) | 🟡 High |
| v5.3 | 1-2 weeks | Performance & scale optimization | 🟢 Medium |
| v6.0 | 1 week | Final validation & launch | 🟢 Medium |
| **Total to Production** | **6-8 weeks** | **Achievable with focused effort** | |
| v6.1+ | Ongoing | Feature enhancements | 🔵 Low |

---

## Call to Action

### Immediate Next Steps

1. **Week 1:** Fix critical bug, verify app works
2. **Week 2-4:** Build test suite (this is non-negotiable)
3. **Week 5-6:** Add production features (rate limiting, logging)
4. **Week 7:** Optimize performance
5. **Week 8:** Final validation and launch

### Getting Started Today

```bash
# 1. Fix the immediate blocker
rm -rf node_modules package-lock.json
npm install
npm run dev  # Verify it starts

# 2. Set up testing
npm install --save-dev jest supertest
# Create jest.config.js
# Write first test

# 3. Track progress
git checkout -b feature/testing-infrastructure
# Make incremental commits
# Open PR for review
```

### Commitment to Honesty

This roadmap is based on:
- ✅ Honest assessment of current state
- ✅ Realistic time estimates
- ✅ Industry-standard production requirements
- ✅ Incremental, achievable milestones
- ✅ Clear acceptance criteria

**Promise:** When this roadmap claims "production-ready," it will be true.

---

## Conclusion

The AI Ethics Comparator has **exceptional potential** and a **strong foundation**. The journey from "feature-complete beta" to "production-ready" is **6-8 weeks of focused work**.

This is **achievable**. The path is clear. The foundation is solid.

**The difference between v5.0 and v6.0:**
- v5.0: Feature-complete, impressive demo, not production-ready
- v6.0: All of the above, PLUS tested, monitored, secured, optimized

**Let's build something we can be truly proud of.**

---

**Roadmap Version:** 2.0 (Realistic Edition)
**Created:** November 4, 2025
**Author:** Based on comprehensive code review
**Status:** Living document - update as progress is made
**Next Review:** After v5.0.1 completion
