# **AI Ethics Comparator \- Roadmap**

This document outlines the development roadmap for the AI Ethics Comparator. The tool has evolved from a specialized "Trolley Problem Engine" into a comprehensive research platform for studying AI alignment and ethical reasoning.

## **📝 Recent Feedback & Priorities (2025-10-31)**

A comprehensive code review identified the project as having **solid foundations** with clear value proposition, good research affordances, and maintainable architecture. However, to become production-ready and publishable as a credible research tool, **Phase 6** focuses on:

**Top 3 Critical Items:**
1. **Reproducibility** - Persist all generation parameters (temperature, top_p, max_tokens, seed, etc.)
2. **Rate Limiting** - Add concurrency control and retry logic to prevent API failures
3. **Security** - Input sanitization, validation, and hardening

**Quick Wins (1-2 afternoons):**
- Add LICENSE file (10 minutes)
- Health endpoint & versioning (30 minutes)
- Security headers with helmet (1 hour)
- Research ethics section in HANDBOOK (1-2 hours)

See **Phase 6** below for full details and **feedback.md** for the complete analysis.

## **Status Overview**

* **Phase 1 (V1.x):** ✅ **COMPLETE** (5/6 features)
* **Phase 2 (V2.0):** ✅ **COMPLETE** (4/5 features)
* **Phase 3 (V3.0):** ✅ **COMPLETE** (4/4 features)
* **Phase 4 (V4.0):** ✅ **COMPLETE** (4/4 features)
* **Phase 5 (V-Next):** ✅ **COMPLETE** (5/5 features)
* **Phase 6 (V5.0):** 🔄 **IN PROGRESS** (0/11 features) - Production-ready improvements

## **✅ Completed Features**

### **Phase 1: Solidify the "Trolley Problem Engine" (V1.x)**

**Goal:** Perfect the core functionality with robust, reliable, user-friendly features.

* ✅ **Result Validation:**  
  * Flag iterations in the UI where the AI's response is "Undecided" (⚠️ warning indicator)  
* ✅ **API & Error Handling:**  
  * Enhanced error passthrough with specific messages for rate limits, billing issues, model not found, invalid API keys, etc.  
* ✅ **UI Quality-of-Life:**  
  * "Clear Run" button to reset summary and response panes  
  * localStorage remembers user's last-used model identifier between sessions  
  * Iterations input properly enforces 1-50 min/max limits with validation

### **Phase 2: The Great Expansion (V2.0) \- Supporting All Paradox Types**

**Goal:** Support both trolley-type and open-ended ethical scenarios.

* ✅ **Data Structure Update:**  
  * Added type field to paradoxes.json ("trolley" or "open\_ended")  
  * All 12 paradoxes now properly typed  
* ✅ **Conditional UI:**  
  * UI automatically reads paradox type and shows/hides Group textareas accordingly  
  * Seamless transition between paradox types  
* ✅ **Conditional Back-End Logic:**  
  * Server checks paradox type before processing  
  * Trolley-type: Parses decision tokens and computes statistical summary  
  * Open-ended: Skips parsing, shows iteration count and full responses  
* ✅ **New Content:**  
  * Added 5 open-ended ethical paradoxes:  
    * The White Lie Dilemma (patient autonomy vs. family wishes)  
    * The Rescue Bot's Probability Gamble (certainty vs. potential impact)  
    * Privacy vs. Security Paradox (individual rights vs. collective safety)  
    * The Artistic Censorship Question (free expression vs. harm prevention)  
    * Medical Resource Allocation (fairness criteria in scarcity)

### **Phase 3: Deepen the Research (V3.0) \- Testing Alignment & Priming**

**Goal:** Enable testing of how AI ethical reasoning can be influenced by ethical frameworks.

* ✅ **System Prompt UI:**  
  * Added collapsible "Advanced Settings" section  
  * Optional textarea for system prompt/context  
  * Placeholder examples guide users on effective priming  
* ✅ **Back-End Update:**  
  * Dual API support: responses.create (legacy) and chat.completions (with system prompt)  
  * Automatically uses chat.completions when system prompt provided  
  * System messages properly formatted: {role: "system", content: systemPrompt}  
* ✅ **Data Persistence:**  
  * System prompt saved to run.json for full reproducibility  
  * Includes paradoxType for proper result rendering  
* ✅ **Documentation:**  
  * README.md thoroughly updated with system prompt usage  
  * HANDBOOK.md created with ethical priming examples and research methodology  
  * Example prompts for utilitarian, deontological, virtue ethics, and care ethics frameworks

### **Phase 4: Complete the Loop (V4.0) \- The Results Dashboard**

**Goal:** Self-contained research tool with full results management.

* ✅ **Run Browser API:**  
  * GET /api/runs \- Returns metadata for all past runs, sorted by timestamp  
  * GET /api/runs/:runId \- Fetches complete data for specific run  
* ✅ **Results Dashboard UI:**  
  * New "Results" tab with browsable list of all past experiments  
  * Each card shows: Run ID, model, paradox, iteration count, timestamp  
  * Clean, clickable interface for exploration  
* ✅ **Run Importer/Viewer:**  
  * Click any run to view full details  
  * Reuses existing rendering functions for consistency  
  * Shows summary, chart (trolley-type), and iteration details  
  * "Back to List" navigation  
* ✅ **Data Export:**  
  * "Export to CSV" button on run viewer  
  * Proper CSV formatting with headers  
  * Different structures for trolley-type vs. open-ended  
  * Compatible with Excel, R, Python, Google Sheets

### **Phase 5: Automation & Advanced Analysis (V-Next)**

**Goal:** Power-user features for large-scale comparative analysis.

* ✅ **Visualization Toolkit:**
  * Chart.js integration complete
  * Automatic bar charts for trolley-type runs
  * Shows Group 1, Group 2, and Undecided distributions
  * Responsive design with proper legends and titles

* ✅ **Batch Model Runner:**
  * Multi-select models from dropdown with checkbox interface
  * Run same scenario across all selected models simultaneously
  * Creates separate run.json for each model
  * Real-time progress indicator with progress bar
  * Batch results summary showing success/failure for each model

* ✅ **Side-by-Side Comparison & Statistical Validation:**
  * Select 2-3 runs from Results dashboard with comparison mode
  * Split-screen layout to compare summaries and charts directly
  * Automated Chi-square test for trolley-type runs
  * P-value displayed directly in comparison UI with significance interpretation
  * Visual side-by-side charts for easy comparison

* ✅ **AI Insight Summary:**
  * "Generate AI Insight Summary" button on run results view
  * Compiles all iteration explanations into structured analysis request
  * Sends to high-level analyst model (Claude 3.5 Sonnet)
  * Meta-prompt analyzes: dominant ethical framework, common justifications, consistency, contradictions
  * Beautiful styled output with markdown rendering
  * Dramatically reduces cognitive load for analyzing complex results

* ✅ **Advanced Data Exports:**
  * JSON export alongside existing CSV export
  * Batch export all runs from Results dashboard
  * Combined export format with metadata and timestamp
  * Supports programmatic analysis in Python/R

## **🚀 Phase 6: Production-Ready Improvements (V5.0)**

**Goal:** Transform the research tool into a robust, production-ready application based on comprehensive code review feedback.

**Status:** 🔄 **IN PROGRESS**

### **Critical (High Priority)**

* 🔲 **License & Repository Metadata**
  * Add LICENSE file (MIT or Apache-2.0)
  * Set `license` field in `package.json`
  * Add `repository`, `homepage`, and `bugs` fields to package.json
  * **Impact:** Legal clarity for researchers and contributors
  * **Effort:** 10 minutes

* 🔲 **Full Reproducibility - Generation Parameters**
  * Extend UI to capture: temperature, top_p, max_tokens, seed, frequency_penalty, presence_penalty
  * Persist all parameters in POST /api/query body and run.json
  * Display parameters in Results card for full reproducibility
  * **Impact:** Critical for research validity and replication
  * **Effort:** 2-3 hours

* 🔲 **Rate Limiting & Concurrency Control**
  * Implement p-limit for controlled concurrency (2-4 concurrent requests)
  * Add retry logic with exponential backoff for 429/5xx errors
  * Surface progress meter per run in UI
  * **Impact:** Prevents API failures, better UX for batch runs
  * **Effort:** 3-4 hours

* 🔲 **Input Sanitization & Validation**
  * Server-side: Validate modelName, paradoxId, text lengths with zod or joi
  * Client-side: Sanitize rendered Markdown and group labels (consider DOMPurify)
  * Prevent XSS/injection through stored results
  * **Impact:** Security - prevents attacks through user input
  * **Effort:** 2-3 hours

### **Important (Medium Priority)**

* 🔲 **Enhanced Statistical Analysis**
  * Create stats.js module with:
    - Chi-square (already implemented)
    - Wilson confidence intervals for proportions
    - Bootstrap method for consistency scores
    - Inter-run effect sizes
  * Display confidence intervals on bar charts
  * **Impact:** Stronger statistical rigor for research
  * **Effort:** 4-5 hours

* 🔲 **Testing Infrastructure**
  * Unit tests: Parser for {1}/{2}, aggregator, chi-square wrapper (Jest/Vitest)
  * Integration tests: Mock OpenRouter (MSW/nock) to verify requests, concurrency, retries
  * E2E tests: Playwright smoke test (run, see chart, compare, export)
  * **Impact:** Code quality, prevent regressions
  * **Effort:** 6-8 hours

* 🔲 **Research Ethics Documentation**
  * Add prominent "Study Design Checklist" section to HANDBOOK.md
  * Include: sampling considerations, priming variants, randomization, params logging
  * Add "Interpretation Caveats" section
  * Reminder that LLM "ethical frames" are training artifacts, not ground truth
  * Link from Query tab help text
  * **Impact:** Responsible research practices
  * **Effort:** 1-2 hours

* 🔲 **Security Hardening**
  * Add helmet middleware
  * Disable x-powered-by header
  * Implement strict CORS (only APP_BASE_URL)
  * Ensure API keys never exposed in client
  * **Impact:** Production security best practices
  * **Effort:** 1 hour

### **Nice to Have (Lower Priority)**

* 🔲 **Configuration & Type Safety**
  * Create config.js module for magic strings
  * Add JSDoc typedefs for Run, Iteration, Params types
  * Or migrate to TypeScript
  * **Impact:** Better developer experience, fewer bugs
  * **Effort:** 3-4 hours (JSDoc) or 8-12 hours (TypeScript)

* 🔲 **SQLite Storage Backend**
  * Optional flag: RESULTS_BACKEND=sqlite|fs
  * Schema: runs, iterations, params tables
  * One-time migration command to import existing JSON
  * Better indexing and querying for large datasets
  * **Impact:** Scalability for >100 runs
  * **Effort:** 6-8 hours

* 🔲 **Health Check & Versioning**
  * Add GET /health endpoint
  * Version header in responses for reproducibility
  * **Impact:** Deployment monitoring, better debugging
  * **Effort:** 30 minutes

## **🚧 Future Enhancements**

The following features are planned for future releases:

### **Remaining Earlier Phase Items**

* ⏸️ **Contradiction Flagging** (Complex)
  * Detect when AI explanation contradicts chosen token
  * Requires secondary AI call for text analysis
  * Example: AI chooses {1} but text says "therefore I save Group 1"
  * **Complexity:** High \- requires NLP or additional LLM call
  * **Priority:** Low \- edge case, rare occurrence

* ⏸️ **Prompt Management UI** (Feature Request)
  * In-app interface to add, edit, or duplicate paradoxes
  * Direct editing of paradoxes.json through web UI
  * Validation and preview before saving
  * **Complexity:** Medium \- requires full CRUD interface
  * **Priority:** Medium \- useful for researchers creating custom scenarios
  * **Workaround:** Currently users can manually edit paradoxes.json

## **📋 Additional Feature Ideas**

Beyond the original roadmap, the following enhancements could add value:

### **Analysis & Research Features**

* Response clustering and pattern detection (Could be part of the AI Insight Summary feature)  
* Custom paradox templates with variables  
* A/B testing framework (built-in comparison mode)  
* Collaborative features (share runs via URL)  
* Anonymous data submission for public research corpus

### **Export Enhancements**

* PDF report generation with charts  
* Markdown export for documentation

### **UI/UX Improvements**

* 💡 **Dark mode toggle** (mentioned in feedback as polish item)
* 💡 **Model alias presets** - Dropdown of common OpenRouter model IDs for easier selection
* 💡 **Keyboard shortcuts** for common actions
* 💡 **Run tagging and categorization** system
* 💡 **Search/filter runs** by model, date, or paradox
* 💡 **Favorites/bookmarking** system for frequently referenced runs

### **Performance Optimizations**

* Pagination for Results list (\>100 runs)  
* Lazy loading of run details  
* Caching of frequently accessed runs  
* Background processing for long batch runs

## **🎯 Contribution Opportunities**

Interested in contributing? Here are areas where help would be most valuable:

### **Phase 6 (Production-Ready) - Top Priority**
1. **Critical:**
   * Full reproducibility - Generation parameters UI and persistence
   * Rate limiting & concurrency control with p-limit and retry logic
   * Input sanitization & validation (zod/joi server-side, DOMPurify client-side)
   * Testing infrastructure (unit, integration, E2E)

2. **Important:**
   * Enhanced statistical analysis (confidence intervals, bootstrap, effect sizes)
   * Security hardening (helmet, CORS, headers)
   * Research ethics documentation for HANDBOOK

3. **Nice to Have:**
   * SQLite storage backend option
   * TypeScript migration or JSDoc types
   * Configuration module for magic strings

### **Future Enhancements**
1. **High Priority:**
   * Search/filter functionality for Results tab
   * Prompt Management UI
   * PDF export with charts

2. **Medium Priority:**
   * Dark mode toggle
   * Model alias presets dropdown
   * Additional paradox scenarios

3. **Nice to Have:**
   * Response clustering and pattern detection
   * Collaborative features (share runs via URL)
   * Anonymous data submission for public research corpus
   * Localization (i18n)

See the GitHub repository for contribution guidelines and current issues.

## **📚 Documentation**

All features and development plans are documented in:

* **README.md** - Technical overview and quick start guide
* **HANDBOOK.md** - Comprehensive user guide with research methodology and examples
* **ROADMAP.md** (this file) - Development status, completed features, and future plans
* **feedback.md** - Detailed code review feedback and concrete next steps (Oct 2025)

## **📊 Estimated Timeline (Phase 6)**

Based on effort estimates:

* **Week 1-2:** Critical items (license, parameters, rate limiting, sanitization) - ~10-12 hours
* **Week 3-4:** Important items (stats, security, docs) - ~8-10 hours
* **Week 5+:** Testing infrastructure - ~6-8 hours
* **Optional:** SQLite backend, TypeScript migration - ~14-20 hours

**Total for production-ready release:** ~24-30 hours of focused development (3-4 weeks part-time)

## **🔗 Related Resources**

* OpenRouter API: https://openrouter.ai/docs
* Research best practices: See HANDBOOK.md "Research Methodology" section
* Code review feedback: feedback.md (October 2025)
* Issue tracker: [GitHub repository URL]