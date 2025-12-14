# **AI Ethics Comparator - Roadmap**

This document outlines the development roadmap for the AI Ethics Comparator.

## **📝 Status Update (2025-12-14)**

**Phase 7 (V6.0) - Python Migration is 98% COMPLETE!** 🚧

The project has been fully rewritten in Python using FastAPI + HTMX, following the Arsenal Strategy. The codebase is now more maintainable, testable, and follows Mission Control protocols.

**What was completed (Migration to Python):**
1. ✅ Created Arsenal Strategy lib/ modules (validation, ai_service, storage, query_processor, stats, config, analysis)
2. ✅ Built main.py FastAPI app (~300 lines, thin routing layer)
3. ✅ Converted frontend to Jinja2 + HTMX (no build steps)
4. ✅ Applied Candlelight Mode styling (#121212, #EBD2BE, #A6ACCD)
5. ✅ Implemented async/await with asyncio concurrency limiting (semaphore=2)
6. ✅ Updated CLAUDE.md with Mission Control format

**What needs fixing (Code Review 2025-12-14):**
- ❌ Critical: Missing `Optional` import in lib/stats.py (blocks runtime)
- ⚠️ Version mismatch: config shows 5.0.0, docs claim 6.0.0
- ⚠️ Dead code: main.py:38 defines unused VERSION variable

**Technology Stack:**
- **Backend:** FastAPI + Python 3.9+ (tested on 3.14.2, asyncio)
- **Frontend:** Jinja2 + HTMX + Chart.js (CDN)
- **No Docker, No React, No Build Steps**

---

## **Status Overview**

* **Phase 1 (V1.x):** ✅ **COMPLETE** (5/6 features) - Trolley Problem Engine
* **Phase 2 (V2.0):** ✅ **COMPLETE** (4/5 features) - Dual Paradox Support
* **Phase 3 (V3.0):** ✅ **COMPLETE** (4/4 features) - Ethical Priming
* **Phase 4 (V4.0):** ✅ **COMPLETE** (4/4 features) - Results Dashboard
* **Phase 5 (V-Next):** ✅ **COMPLETE** (5/5 features) - Batch Mode & Insights
* **Phase 6 (V5.0):** ✅ **COMPLETE** (8/8 features) - Production-Ready (Node.js)
* **Phase 7 (V6.0):** 🚧 **IN PROGRESS** (6/6 features, 1 blocking bug) - Python Migration

---

## **✅ Completed Features**

### **Phase 7: Python Migration (V6.0) - Arsenal Strategy**

**Goal:** Rewrite entire application in Python following Arsenal Strategy for better maintainability and testability.

**Completed:**
* ✅ **Arsenal Modules (lib/):**
  * `validation.py` - Pydantic models (copy-paste ready)
  * `ai_service.py` - AsyncOpenAI client with retry logic
  * `storage.py` - Filesystem JSON persistence
  * `query_processor.py` - Async run execution with semaphore
  * `stats.py` - Statistical functions (pure Python)
* ✅ **FastAPI Application:**
  * `main.py` - Thin routing layer (~250 lines)
  * Health check, paradoxes API, runs management
  * Query execution with async processing
  * Insight generation endpoint
* ✅ **Frontend Migration:**
  * `templates/index.html` - Jinja2 + HTMX
  * `static/style.css` - Candlelight Mode
  * No build steps, CDN-based dependencies
* ✅ **Infrastructure:**
  * `requirements.txt` - Python dependencies
  * `.env` support with python-dotenv
  * Virtual environment setup (Python 3.13)

**Benefits:**
- Copy-Paste Test: All lib/ modules are portable
- Async Performance: Non-blocking I/O with asyncio
- Type Safety: Full Pydantic validation
- Maintainability: Clear separation of concerns
- Testing Ready: Arsenal modules easy to unit test

### **Phase 6: Production-Ready (V5.0)**

**Goal:** Make the tool publication-ready with security, reproducibility, and documentation.

* ✅ **License & Repository Metadata**
* ✅ **Full Reproducibility** (generation parameters)
* ✅ **Rate Limiting & Concurrency Control**
* ✅ **Input Sanitization & Validation**
* ✅ **Enhanced Statistical Analysis**
* ✅ **Research Ethics Documentation**
* ✅ **Security Hardening**
* ✅ **Health Check & Versioning**

### **Phase 5: Advanced Features (V-Next)**

**Goal:** Add batch testing and AI-powered analysis.

* ✅ **Batch Model Runner** - Test multiple models simultaneously
* ✅ **Side-by-Side Comparison** - Compare 2-3 runs with chi-square tests
* ✅ **AI Insight Summary** - Auto-analyze runs with meta-AI
* ✅ **Enhanced Statistics Module** - Wilson CI, bootstrap, Cohen's h
* ✅ **Data Export** - CSV, JSON, and batch export

### **Phase 4: Results Dashboard (V4.0)**

**Goal:** Self-contained research tool with full results management.

* ✅ **Run Browser API** - List and fetch past runs
* ✅ **Results Tab UI** - Browse all experiments
* ✅ **Run Viewer** - Detailed view with charts
* ✅ **Export Functionality** - CSV/JSON export

### **Phase 3: Ethical Priming (V3.0)**

**Goal:** Enable testing of how AI ethical reasoning can be influenced.

* ✅ **System Prompt UI** - Optional ethical priming
* ✅ **Dual API Support** - chat.completions vs responses.create
* ✅ **Data Persistence** - System prompt saved to run.json
* ✅ **Documentation** - HANDBOOK.md with research methodology

### **Phase 2: Dual Paradox Support (V2.0)**

**Goal:** Support both trolley-type and open-ended ethical scenarios.

* ✅ **Data Structure Update** - Type field in paradoxes.json
* ✅ **Conditional UI** - Auto show/hide group inputs
* ✅ **Conditional Back-End Logic** - Paradox-aware parsing
* ✅ **New Content** - 5 open-ended scenarios added

### **Phase 1: Trolley Problem Engine (V1.x)**

**Goal:** Perfect the core functionality with robust features.

* ✅ **Result Validation** - Flag undecided responses
* ✅ **API & Error Handling** - Specific error messages
* ✅ **UI Quality-of-Life** - Clear button, localStorage

---

## **🚧 Known Issues & Technical Debt**

### **Critical**
- 🚨 **Missing Optional Import (lib/stats.py:6):** Function uses `Optional[Dict[str, Any]]` but doesn't import Optional - causes ImportError at runtime

### **Important**
- ⚠️ **Version Mismatch:** config.py shows 5.0.0, ROADMAP claims 6.0.0 - needs alignment
- ⚠️ **Dead Code:** main.py:38 defines VERSION variable that's never used
- ⚠️ **No .env Validation:** App starts without API key, fails on first query (should fail fast)
- ⚠️ **HTMX Form Serialization:** Nested params handled by validator but may have edge cases

### **Nice to Have**
- Testing Infrastructure (pytest)
- SQLite storage backend (when filesystem scales out)
- Frontend refactoring (split JavaScript)
- Dark/Light mode toggle

---

## **🔮 Future Phases**

### **Phase 8: Testing & Quality (V6.1) - NEXT**

**Goal:** Fix blocking bugs and add automated testing.

**Planned:**
- [ ] **Fix Critical Bug** - Add Optional import to lib/stats.py (BLOCKS v6.0 release)
- [ ] **Version Alignment** - Decide on 5.0.0 vs 6.0.0, update config + docs
- [ ] **Remove Dead Code** - Delete unused VERSION in main.py:38
- [ ] **Environment Validation** - Fail fast if OPENROUTER_API_KEY missing
- [ ] **pytest Integration** - Unit tests for all lib/ modules
- [ ] **Integration Tests** - API endpoint testing with httpx
- [ ] **Logging Configuration** - Add structured logging to main.py

### **Phase 9: Scale & Performance (V7.0)**

**Goal:** Support larger datasets and concurrent users.

**Planned:**
- [ ] **SQLite Storage** - Replace filesystem JSON
- [ ] **Caching Layer** - Redis for run metadata
- [ ] **Background Tasks** - Celery for long-running experiments
- [ ] **Rate Limiting** - slowapi middleware

### **Phase 10: UI/UX Enhancements (V8.0)**

**Goal:** Improve researcher experience and visualization.

**Planned:**
- [ ] **Search & Filter** - Find runs by model, date, paradox
- [ ] **Advanced Charts** - D3.js for interactive visualizations
- [ ] **Export Improvements** - XLSX, PDF reports
- [ ] **Prompt Templates** - Library of ethical priming prompts
- [ ] **Dark/Light Mode** - Respect system preferences

---

## **📊 Metrics**

**Current State (V6.0-dev):**
- **Lines of Code:** ~1,803 total (1,500 Python, 230 HTML, 307 CSS)
- **Arsenal Modules:** 7 (validation, ai_service, storage, query_processor, stats, config, analysis)
- **API Endpoints:** 7 (health, paradoxes, runs, query, insight, analyze)
- **Paradoxes:** 12 (7 trolley, 5 open-ended)
- **Dependencies:** 9 Python packages (fastapi, uvicorn, pydantic, python-dotenv, httpx, jinja2, python-multipart, markdown, openai)
- **Build Steps:** 0 (no npm, webpack, docker)

**Code Quality:**
- **Type Coverage:** ~95% (Pydantic + type hints)
- **Test Coverage:** 0% (Phase 8 priority)
- **Documentation:** Excellent (README, HANDBOOK, CLAUDE.md, AGENTS.md)
- **Security:** Excellent (Pydantic validation, CORS, path traversal prevention, regex sanitization)

---

## **🎯 Mission Control Principles**

1. **Arsenal Strategy:** All lib/ modules are portable
2. **No-Bloat:** NO Docker, NO React, NO build steps
3. **ETC (Easier To Change):** Prefer simple over perfect
4. **Copy-Paste Test:** Can you drop lib/stats.py into another project? YES.
5. **Mission Control Tone:** Concise, direct, use "we"

---

## **Contributing**

We welcome contributions! Priority areas:
- Phase 8 (Testing) - Most impactful
- Bug fixes for known issues
- New paradoxes for paradoxes.json
- Statistical analysis improvements

See **CLAUDE.md** for development guidance.

---

## **Version History**

- **V6.0 (2025-12-14):** Python migration with Arsenal Strategy
- **V5.0 (2025-10-31):** Production-ready with security & reproducibility
- **V4.0:** Results dashboard and data export
- **V3.0:** Ethical priming with system prompts
- **V2.0:** Dual paradox support (trolley + open-ended)
- **V1.0:** Initial trolley problem engine

---

*Last Updated: 2025-12-14*
*Current Version: 6.0.0-dev (pending bug fixes)*
*Status: In Development - 1 blocking bug, 98% complete*
